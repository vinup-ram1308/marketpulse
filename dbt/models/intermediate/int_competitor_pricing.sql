with observations as (
    select *
    from {{ ref('stg_market_observations') }}
),

competitor_prices as (
    select
        product_id,
        market,
        currency,
        observed_at,
        competitor_id,
        avg(price) as competitor_price
    from observations
    group by
        product_id,
        market,
        currency,
        observed_at,
        competitor_id
),

market_price_metrics as (
    select
        product_id,
        market,
        currency,
        observed_at,
        count(*) as competitor_count,
        avg(competitor_price) as avg_competitor_price,
        min(competitor_price) as min_competitor_price,
        max(competitor_price) as max_competitor_price
    from competitor_prices
    group by
        product_id,
        market,
        currency,
        observed_at
),

ranked_competitor_prices as (
    select
        product_id,
        market,
        currency,
        observed_at,
        competitor_id,
        dense_rank() over (
            partition by product_id, market, currency, observed_at
            order by competitor_price asc
        ) as price_rank
    from competitor_prices
)

select
    observations.*,
    market_price_metrics.competitor_count,
    market_price_metrics.avg_competitor_price,
    market_price_metrics.min_competitor_price,
    market_price_metrics.max_competitor_price,
    market_price_metrics.max_competitor_price
        - market_price_metrics.min_competitor_price as price_spread,
    ranked_competitor_prices.price_rank,
    safe_divide(
        observations.price - market_price_metrics.avg_competitor_price,
        market_price_metrics.avg_competitor_price
    ) * 100 as pct_diff_from_avg_price,
    safe_divide(
        observations.price - market_price_metrics.min_competitor_price,
        market_price_metrics.min_competitor_price
    ) * 100 as pct_diff_from_lowest_price,
    observations.stock_quantity > 0 as in_stock_indicator,
    observations.promotion_flag as promotion_indicator
from observations
inner join market_price_metrics
    on observations.product_id = market_price_metrics.product_id
    and observations.market = market_price_metrics.market
    and observations.currency = market_price_metrics.currency
    and observations.observed_at = market_price_metrics.observed_at
inner join ranked_competitor_prices
    on observations.product_id = ranked_competitor_prices.product_id
    and observations.market = ranked_competitor_prices.market
    and observations.currency = ranked_competitor_prices.currency
    and observations.observed_at = ranked_competitor_prices.observed_at
    and observations.competitor_id = ranked_competitor_prices.competitor_id
