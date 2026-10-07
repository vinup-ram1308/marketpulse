with source_observations as (
    select *
    from {{ ref('int_competitor_pricing') }}
),

competitor_observations as (
    select
        product_id,
        market,
        currency,
        observed_at,
        competitor_id,
        avg(price) as competitor_price,
        array_agg(
            struct(
                batch_id as batch_id,
                product_name as product_name,
                category as category,
                brand as brand,
                competitor_name as competitor_name,
                in_stock_indicator as in_stock_indicator,
                promotion_indicator as promotion_indicator,
                observation_id as observation_id
            )
            order by batch_id asc, observation_id asc
            limit 1
        )[offset(0)] as representative_observation
    from source_observations
    group by
        product_id,
        market,
        currency,
        observed_at,
        competitor_id
),

market_metrics as (
    select
        product_id,
        market,
        currency,
        observed_at,
        count(*) as competitor_count,
        avg(competitor_price) as avg_competitor_price,
        min(competitor_price) as min_competitor_price,
        max(competitor_price) as max_competitor_price,
        max(competitor_price) - min(competitor_price) as price_spread,
        countif(representative_observation.in_stock_indicator) as in_stock_competitor_count,
        countif(representative_observation.promotion_indicator) as promotion_competitor_count
    from competitor_observations
    group by
        product_id,
        market,
        currency,
        observed_at
),

snapshot_dimensions as (
    select
        product_id,
        market,
        currency,
        observed_at,
        array_agg(
            struct(
                representative_observation.batch_id as batch_id,
                representative_observation.product_name as product_name,
                representative_observation.category as category,
                representative_observation.brand as brand
            )
            order by
                representative_observation.batch_id asc,
                competitor_id asc
            limit 1
        )[offset(0)] as dimensions
    from competitor_observations
    group by
        product_id,
        market,
        currency,
        observed_at
),

ranked_competitors as (
    select
        product_id,
        market,
        currency,
        observed_at,
        competitor_id,
        representative_observation.competitor_name as competitor_name,
        competitor_price,
        row_number() over (
            partition by product_id, market, currency, observed_at
            order by competitor_price asc, competitor_id asc
        ) as lowest_price_order,
        row_number() over (
            partition by product_id, market, currency, observed_at
            order by competitor_price desc, competitor_id asc
        ) as highest_price_order
    from competitor_observations
),

price_extremes as (
    select
        product_id,
        market,
        currency,
        observed_at,
        array_agg(
            if(
                lowest_price_order = 1,
                struct(
                    competitor_id as competitor_id,
                    competitor_name as competitor_name,
                    competitor_price as price
                ),
                null
            )
            ignore nulls
            limit 1
        )[offset(0)] as lowest,
        array_agg(
            if(
                highest_price_order = 1,
                struct(
                    competitor_id as competitor_id,
                    competitor_name as competitor_name,
                    competitor_price as price
                ),
                null
            )
            ignore nulls
            limit 1
        )[offset(0)] as highest
    from ranked_competitors
    group by
        product_id,
        market,
        currency,
        observed_at
)

select
    snapshot_dimensions.product_id,
    snapshot_dimensions.dimensions.product_name as product_name,
    snapshot_dimensions.dimensions.category as category,
    snapshot_dimensions.dimensions.brand as brand,
    snapshot_dimensions.market,
    snapshot_dimensions.currency,
    snapshot_dimensions.observed_at,
    snapshot_dimensions.dimensions.batch_id as batch_id,
    market_metrics.competitor_count,
    market_metrics.avg_competitor_price,
    market_metrics.min_competitor_price,
    market_metrics.max_competitor_price,
    market_metrics.price_spread,
    safe_divide(
        market_metrics.price_spread,
        market_metrics.avg_competitor_price
    ) * 100 as price_spread_pct,
    price_extremes.lowest.competitor_id as lowest_price_competitor_id,
    price_extremes.lowest.competitor_name as lowest_price_competitor_name,
    price_extremes.lowest.price as lowest_price,
    price_extremes.highest.competitor_id as highest_price_competitor_id,
    price_extremes.highest.competitor_name as highest_price_competitor_name,
    price_extremes.highest.price as highest_price,
    market_metrics.in_stock_competitor_count,
    safe_divide(
        market_metrics.in_stock_competitor_count,
        market_metrics.competitor_count
    ) * 100 as in_stock_pct,
    market_metrics.promotion_competitor_count,
    safe_divide(
        market_metrics.promotion_competitor_count,
        market_metrics.competitor_count
    ) * 100 as promotion_competitor_pct,
    safe_divide(
        market_metrics.price_spread,
        market_metrics.avg_competitor_price
    ) as market_price_pressure,
    market_metrics.promotion_competitor_count > 0 as promotion_activity_flag
from snapshot_dimensions
inner join market_metrics
    using (product_id, market, currency, observed_at)
inner join price_extremes
    using (product_id, market, currency, observed_at)
