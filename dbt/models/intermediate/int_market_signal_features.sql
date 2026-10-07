with market_snapshots as (
    select
        product_id,
        product_name,
        category,
        brand,
        market,
        currency,
        observed_at,
        batch_id,
        competitor_count,
        avg_competitor_price,
        min_competitor_price,
        max_competitor_price,
        price_spread,
        price_spread_pct,
        lowest_price_competitor_id,
        lowest_price_competitor_name,
        lowest_price,
        highest_price_competitor_id,
        highest_price_competitor_name,
        highest_price,
        in_stock_competitor_count,
        in_stock_pct,
        promotion_competitor_count,
        promotion_competitor_pct,
        market_price_pressure,
        promotion_activity_flag
    from {{ ref('mart_market_signals') }}
),

snapshots_with_previous_metrics as (
    select
        market_snapshots.*,
        lag(avg_competitor_price) over snapshot_history
            as previous_avg_competitor_price,
        lag(min_competitor_price) over snapshot_history
            as previous_min_competitor_price,
        lag(max_competitor_price) over snapshot_history
            as previous_max_competitor_price,
        lag(price_spread) over snapshot_history
            as previous_price_spread,
        lag(price_spread_pct) over snapshot_history
            as previous_price_spread_pct,
        lag(in_stock_pct) over snapshot_history
            as previous_in_stock_pct,
        lag(promotion_competitor_pct) over snapshot_history
            as previous_promotion_competitor_pct,
        lag(market_price_pressure) over snapshot_history
            as previous_market_price_pressure
    from market_snapshots
    window snapshot_history as (
        partition by product_id, market, currency
        order by observed_at asc
    )
),

snapshot_changes as (
    select
        snapshots_with_previous_metrics.*,
        avg_competitor_price - previous_avg_competitor_price
            as avg_competitor_price_change,
        safe_divide(
            avg_competitor_price - previous_avg_competitor_price,
            previous_avg_competitor_price
        ) * 100 as avg_competitor_price_change_pct,
        price_spread - previous_price_spread
            as price_spread_change,
        safe_divide(
            price_spread - previous_price_spread,
            previous_price_spread
        ) * 100 as price_spread_change_pct,
        in_stock_pct - previous_in_stock_pct
            as in_stock_pct_change,
        safe_divide(
            in_stock_pct - previous_in_stock_pct,
            previous_in_stock_pct
        ) * 100 as in_stock_pct_change_pct,
        promotion_competitor_pct - previous_promotion_competitor_pct
            as promotion_competitor_pct_change,
        safe_divide(
            promotion_competitor_pct - previous_promotion_competitor_pct,
            previous_promotion_competitor_pct
        ) * 100 as promotion_competitor_pct_change_pct,
        market_price_pressure - previous_market_price_pressure
            as market_price_pressure_change,
        safe_divide(
            market_price_pressure - previous_market_price_pressure,
            previous_market_price_pressure
        ) * 100 as market_price_pressure_change_pct
    from snapshots_with_previous_metrics
)

select
    product_id,
    product_name,
    category,
    brand,
    market,
    currency,
    observed_at,
    batch_id,
    competitor_count,
    avg_competitor_price,
    min_competitor_price,
    max_competitor_price,
    price_spread,
    price_spread_pct,
    lowest_price_competitor_id,
    lowest_price_competitor_name,
    lowest_price,
    highest_price_competitor_id,
    highest_price_competitor_name,
    highest_price,
    in_stock_competitor_count,
    in_stock_pct,
    promotion_competitor_count,
    promotion_competitor_pct,
    market_price_pressure,
    promotion_activity_flag,
    previous_avg_competitor_price,
    previous_min_competitor_price,
    previous_max_competitor_price,
    previous_price_spread,
    previous_price_spread_pct,
    previous_in_stock_pct,
    previous_promotion_competitor_pct,
    previous_market_price_pressure,
    avg_competitor_price_change,
    avg_competitor_price_change_pct,
    price_spread_change,
    price_spread_change_pct,
    in_stock_pct_change,
    in_stock_pct_change_pct,
    promotion_competitor_pct_change,
    promotion_competitor_pct_change_pct,
    market_price_pressure_change,
    market_price_pressure_change_pct,
    case
        when previous_avg_competitor_price is null then cast(null as string)
        when avg_competitor_price > previous_avg_competitor_price then 'UP'
        when avg_competitor_price < previous_avg_competitor_price then 'DOWN'
        else 'FLAT'
    end as price_direction,
    case
        when previous_promotion_competitor_pct is null then cast(null as string)
        when promotion_competitor_pct > previous_promotion_competitor_pct
            then 'UP'
        when promotion_competitor_pct < previous_promotion_competitor_pct
            then 'DOWN'
        else 'FLAT'
    end as promotion_direction,
    case
        when previous_in_stock_pct is null then cast(null as string)
        when in_stock_pct > previous_in_stock_pct then 'UP'
        when in_stock_pct < previous_in_stock_pct then 'DOWN'
        else 'FLAT'
    end as inventory_direction
from snapshot_changes
