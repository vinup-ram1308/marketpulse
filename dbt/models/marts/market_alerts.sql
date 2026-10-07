with signal_features as (
    select *
    from {{ ref('int_market_signal_features') }}
),

price_movement_signals as (
    select
        product_id,
        product_name,
        category,
        brand,
        market,
        currency,
        observed_at,
        batch_id,
        'PRICE_MOVEMENT' as signal_type,
        case
            when abs(avg_competitor_price_change_pct) >= 5 then 'HIGH'
            when abs(avg_competitor_price_change_pct) >= 3.75 then 'MEDIUM'
            else 'LOW'
        end as severity,
        avg_competitor_price as signal_value,
        previous_avg_competitor_price as previous_value,
        avg_competitor_price_change as absolute_change,
        avg_competitor_price_change_pct as percentage_change,
        format(
            'Average competitor price %s by %.2f%%, from %.2f to %.2f %s.',
            if(avg_competitor_price_change_pct > 0, 'increased', 'decreased'),
            abs(avg_competitor_price_change_pct),
            cast(previous_avg_competitor_price as float64),
            cast(avg_competitor_price as float64),
            currency
        ) as message
    from signal_features
    where avg_competitor_price_change_pct is not null
        and abs(avg_competitor_price_change_pct) >= 2.5
),

promotion_surge_signals as (
    select
        product_id,
        product_name,
        category,
        brand,
        market,
        currency,
        observed_at,
        batch_id,
        'PROMOTION_SURGE' as signal_type,
        case
            when promotion_competitor_pct_change >= 75 then 'HIGH'
            when promotion_competitor_pct_change >= 50 then 'MEDIUM'
            else 'LOW'
        end as severity,
        promotion_competitor_pct as signal_value,
        previous_promotion_competitor_pct as previous_value,
        promotion_competitor_pct_change as absolute_change,
        promotion_competitor_pct_change_pct as percentage_change,
        format(
            'Competitors promoting increased from %.2f%% to %.2f%%, a rise of %.2f percentage points.',
            cast(previous_promotion_competitor_pct as float64),
            cast(promotion_competitor_pct as float64),
            cast(promotion_competitor_pct_change as float64)
        ) as message
    from signal_features
    where promotion_competitor_pct_change is not null
        and promotion_competitor_pct_change >= 25
),

inventory_pressure_signals as (
    select
        product_id,
        product_name,
        category,
        brand,
        market,
        currency,
        observed_at,
        batch_id,
        'INVENTORY_PRESSURE' as signal_type,
        case
            when in_stock_pct_change <= -75 then 'HIGH'
            when in_stock_pct_change <= -50 then 'MEDIUM'
            else 'LOW'
        end as severity,
        in_stock_pct as signal_value,
        previous_in_stock_pct as previous_value,
        in_stock_pct_change as absolute_change,
        in_stock_pct_change_pct as percentage_change,
        format(
            'Competitors in stock decreased from %.2f%% to %.2f%%, a decline of %.2f percentage points.',
            cast(previous_in_stock_pct as float64),
            cast(in_stock_pct as float64),
            abs(cast(in_stock_pct_change as float64))
        ) as message
    from signal_features
    where in_stock_pct_change is not null
        and in_stock_pct_change <= -25
),

price_dispersion_signals as (
    select
        product_id,
        product_name,
        category,
        brand,
        market,
        currency,
        observed_at,
        batch_id,
        'PRICE_DISPERSION' as signal_type,
        case
            when market_price_pressure_change >= 0.12 then 'HIGH'
            when market_price_pressure_change >= 0.09 then 'MEDIUM'
            else 'LOW'
        end as severity,
        price_spread_pct as signal_value,
        previous_price_spread_pct as previous_value,
        market_price_pressure_change * 100 as absolute_change,
        market_price_pressure_change_pct as percentage_change,
        format(
            'Competitor price dispersion increased from %.2f%% to %.2f%% of the average price, a rise of %.2f percentage points.',
            cast(previous_price_spread_pct as float64),
            cast(price_spread_pct as float64),
            cast(market_price_pressure_change as float64) * 100
        ) as message
    from signal_features
    where market_price_pressure_change is not null
        and market_price_pressure_change >= 0.06
)

select *
from price_movement_signals

union all

select *
from promotion_surge_signals

union all

select *
from inventory_pressure_signals

union all

select *
from price_dispersion_signals
