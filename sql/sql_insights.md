# SQL Insights

Extra analyses for the business problem: delays are reported, but the causes are not clear.
All queries are in **Impala SQL** and use the same assumed tables as **sql_queries.sql**.

## General assumptions

1. The tables are the ones from sql_queries.sql. The names are invented.
2. The reference date is MAX(order_placed_at), not NOW(). Monthly windows leave out the anchor month because it is partial.
3. **Every average delivery time is read with delivery_distance_km.** I use min_per_km = delivery_time_min / delivery_distance_km, and when I compare times I do it inside a distance band (0-3, 3-6, 6-10, 10+ km).
4. **"Slow" is the top decile (NTILE(10) = 10) of delivery_time_min inside its distance band**, so a long route is not slow just for being long. "Fast" is decile 1. The bands and the 10% cutoff are my judgment.
5. delivery_id is unique in tb_delivery_level_data, order_id is unique in tb_order, and one delivery has one restaurant and one customer.
6. I use APPX_MEDIAN() because it is the median function in Impala. It is approximate.
7. delivery_person_id is cast to INT, as in Q3.
8. The minimum volumes (30 for areas, 10 for groups) are my judgment and are written in each query.
9. I use DENSE_RANK() because I prefer to show the top in buckets than to miss a record that was tied. It could also depend on the campaign, the type of data the business requires, or the variables at my disposal.
10. Tables marked **HYPOTHETICAL** are not in the brief. They are the data I would ask for.

---


## 1. Q1 insights: what is "slow" and why

### 1.1 Definition of slow (distance aware)

**Business question:** which deliveries are slow *for their distance*? I use this definition in the rest of the file.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
base AS(
    SELECT
        dinfo.delivery_id,
        dinfo.customer_area,
        dinfo.delivery_time_min,
        dinfo.delivery_distance_km,
        dinfo.delivery_time_min / NULLIF(dinfo.delivery_distance_km, 0)       AS min_per_km,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= DAYS_SUB(odate.order_date_max, 30)
),
ranked AS(
    SELECT
        delivery_id,
        customer_area,
        distance_band,
        delivery_time_min,
        min_per_km,
        NTILE(10) OVER(PARTITION BY distance_band ORDER BY delivery_time_min) AS time_decile
    FROM base
)
SELECT
    distance_band,
    CASE
        WHEN time_decile = 10 THEN 'SLOW'
        WHEN time_decile = 1  THEN 'FAST'
        ELSE 'TYPICAL'
    END                                                                       AS speed_group,
    COUNT(*)                                                                  AS total_deliveries,
    MIN(delivery_time_min)                                                    AS min_time,
    MAX(delivery_time_min)                                                    AS max_time,
    AVG(min_per_km)                                                           AS avg_min_per_km
FROM ranked
GROUP BY
    distance_band,
    CASE
        WHEN time_decile = 10 THEN 'SLOW'
        WHEN time_decile = 1  THEN 'FAST'
        ELSE 'TYPICAL'
    END
ORDER BY
    distance_band,
    speed_group;
```

The min_time of the SLOW group in each band is the threshold Ops can use: "more than X minutes for this distance is a delay".

### 1.2 Q1 with distance, volume and outliers

**Business question:** which areas are slowest *per km*, with enough deliveries to trust the number, and are outliers pushing the average?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
area_stats AS(
    SELECT
        dinfo.customer_area,
        COUNT(*)                                                              AS total_deliveries,
        AVG(dinfo.delivery_time_min)                                          AS avg_delivery_time,
        APPX_MEDIAN(dinfo.delivery_time_min)                                  AS median_delivery_time,
        AVG(dinfo.delivery_distance_km)                                       AS avg_distance_km,
        SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= DAYS_SUB(odate.order_date_max, 30)
    GROUP BY dinfo.customer_area
    HAVING COUNT(*) >= 30
),
ranked_areas AS(
    SELECT
        customer_area,
        total_deliveries,
        avg_delivery_time,
        median_delivery_time,
        avg_delivery_time - median_delivery_time                              AS avg_minus_median,
        avg_distance_km,
        min_per_km,
        DENSE_RANK() OVER(ORDER BY min_per_km DESC)                           AS ranking
    FROM area_stats
)
SELECT
    customer_area,
    total_deliveries,
    avg_delivery_time,
    median_delivery_time,
    avg_minus_median,
    avg_distance_km,
    min_per_km,
    ranking
FROM ranked_areas
WHERE ranking <= 5
ORDER BY
    ranking,
    customer_area;
```

**How I read it:**
- HAVING COUNT(*) >= 30 removes areas with too few deliveries.
- A big avg_minus_median means a few extreme deliveries inflate the average. The typical delivery is not that slow, so I would check the outliers.
- If an area is slow in avg_delivery_time but not in min_per_km, its routes are just longer.

### 1.3 Weather and traffic: slow vs typical vs fast

**Business question:** are the conditions different in the slow deliveries?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
base AS(
    SELECT
        dinfo.delivery_time_min,
        dinfo.weather_condition,
        dinfo.traffic_condition,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
),
ranked AS(
    SELECT
        weather_condition,
        traffic_condition,
        NTILE(10) OVER(PARTITION BY distance_band ORDER BY delivery_time_min) AS time_decile
    FROM base
),
speed_groups AS(
    SELECT
        weather_condition,
        traffic_condition,
        CASE
            WHEN time_decile = 10 THEN 'SLOW'
            WHEN time_decile = 1  THEN 'FAST'
            ELSE 'TYPICAL'
        END                                                                   AS speed_group
    FROM ranked
)
SELECT
    speed_group,
    weather_condition,
    traffic_condition,
    COUNT(*)                                                                  AS total_deliveries,
    COUNT(*) / SUM(COUNT(*)) OVER(PARTITION BY speed_group)                   AS share_in_group
FROM speed_groups
GROUP BY
    speed_group,
    weather_condition,
    traffic_condition
ORDER BY
    speed_group,
    share_in_group DESC;
```

**Action:** if one combination (for example heavy traffic with rain) shows up much more in **SLOW** than in **TYPICAL**, the delay is environmental and the answer is dispatch rules and customer expectations. If the mix is similar, I would look at couriers, tenure or restaurants.

### 1.4 Median vs average by month

**Business question:** are deliveries getting slower, or are outliers pulling the average?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max,
        TRUNC(MAX(order_placed_at), 'MM')                                     AS anchor_month_start
    FROM results_deliveries.tb_delivery_level_data
)
SELECT
    FROM_TIMESTAMP(dinfo.order_placed_at, 'yyyy-MM')                          AS monthly_date,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(dinfo.delivery_time_min)                                              AS avg_delivery_time,
    APPX_MEDIAN(dinfo.delivery_time_min)                                      AS median_delivery_time,
    SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
FROM results_deliveries.tb_delivery_level_data             AS dinfo
CROSS JOIN max_or_date                                     AS odate
WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 12)
AND   dinfo.order_placed_at <  odate.anchor_month_start
GROUP BY FROM_TIMESTAMP(dinfo.order_placed_at, 'yyyy-MM')
ORDER BY monthly_date;
```

**Reading:** if the average rises and the median does not, outliers are the cause. If both rise, the whole distribution moved and it is a real slowdown.

### 1.5 Tenure and learning curve

**Business question:** how much slower are new couriers and how many months do they need to reach the normal pace? I measure tenure **at the time of each delivery**, not today.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
courier_deliveries AS(
    SELECT
        CAST(dinfo.delivery_person_id AS INT)                                 AS delivery_person_id,
        dinfo.delivery_time_min,
        dinfo.delivery_distance_km,
        dinfo.delivery_rating,
        INT_MONTHS_BETWEEN(dinfo.order_placed_at, pinfo.hired_date)           AS tenure_months
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN results_deliveries.tb_delivery_personnel    AS pinfo
    ON CAST(dinfo.delivery_person_id AS INT) = pinfo.delivery_person_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 12)
),
tenure_curve AS(
    SELECT
        CASE WHEN tenure_months >= 12 THEN 12 ELSE tenure_months END         AS tenure_month,
        COUNT(*)                                                              AS total_deliveries,
        COUNT(DISTINCT delivery_person_id)                                    AS total_couriers,
        AVG(delivery_time_min)                                                AS avg_delivery_time,
        APPX_MEDIAN(delivery_time_min)                                        AS median_delivery_time,
        SUM(delivery_time_min) / NULLIF(SUM(delivery_distance_km), 0)         AS min_per_km,
        AVG(delivery_rating)                                                  AS avg_rating
    FROM courier_deliveries
    WHERE tenure_months >= 0
    GROUP BY CASE WHEN tenure_months >= 12 THEN 12 ELSE tenure_months END
)
SELECT
    tenure_month,
    total_couriers,
    total_deliveries,
    avg_delivery_time,
    median_delivery_time,
    min_per_km,
    avg_rating
FROM tenure_curve
ORDER BY tenure_month;
```

`tenure_month = 12` groups "12 months or more". The month where `min_per_km` stops falling is the length of the learning curve.

**Action:** I would not penalize couriers inside that period in rankings like Q3. I would support them with shorter routes, pairing with an experienced courier and route tips, and measure the same curve before and after (see 5.3).

---

## 2. Q2 insights: time, outliers and drivers of delay

### 2.1 Q2 by month, with median and share of slow deliveries
**Business question:** a history-wide average compares nothing. How do traffic, area and cuisine behave **by month**, and can I trust the numbers?

**Why median and share slow:** 3 perfect deliveries look better than 24 great ones and 3 horrible ones, and the average hides that. total_deliveries, the median and share_slow make it visible.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max,
        TRUNC(MAX(order_placed_at), 'MM')                                     AS anchor_month_start
    FROM results_deliveries.tb_delivery_level_data
),
rest_id AS(
    SELECT DISTINCT
        delivery_id,
        restaurant_id
    FROM results_transactional.tb_order
),
base AS(
    SELECT
        FROM_TIMESTAMP(dinfo.order_placed_at, 'yyyy-MM')                      AS monthly_date,
        dinfo.restaurant_area,
        rinfo.cuisine_type,
        dinfo.traffic_condition,
        dinfo.delivery_time_min,
        dinfo.delivery_distance_km,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN rest_id                                     AS oinfo
    ON dinfo.delivery_id = oinfo.delivery_id
    INNER JOIN results_channels.tb_restaurant              AS rinfo
    ON oinfo.restaurant_id = rinfo.restaurant_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 6)
    AND   dinfo.order_placed_at <  odate.anchor_month_start
),
ranked AS(
    SELECT
        monthly_date,
        restaurant_area,
        cuisine_type,
        traffic_condition,
        delivery_time_min,
        delivery_distance_km,
        NTILE(10) OVER(PARTITION BY distance_band ORDER BY delivery_time_min) AS time_decile
    FROM base
)
SELECT
    monthly_date,
    restaurant_area,
    cuisine_type,
    traffic_condition,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(delivery_time_min)                                                    AS avg_delivery_time,
    APPX_MEDIAN(delivery_time_min)                                            AS median_delivery_time,
    SUM(delivery_time_min) / NULLIF(SUM(delivery_distance_km), 0)             AS min_per_km,
    SUM(CASE WHEN time_decile = 10 THEN 1 ELSE 0 END) / COUNT(*)              AS share_slow
FROM ranked
GROUP BY
    monthly_date,
    restaurant_area,
    cuisine_type,
    traffic_condition
HAVING COUNT(*) >= 10
ORDER BY
    restaurant_area,
    cuisine_type,
    traffic_condition,
    monthly_date;
```

**Business reason:** the business sees where and since when a problem started, not one blended number. I would compare each month against the same month of last year, so seasonality is not read as a trend.

### 2.2 Does the preparation time explain part of the delay?

**Business question:** does a slow kitchen show up as a slow delivery once distance is controlled? 

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
rest_id AS(
    SELECT DISTINCT
        delivery_id,
        restaurant_id
    FROM results_transactional.tb_order
),
base AS(
    SELECT
        dinfo.delivery_time_min,
        dinfo.delivery_distance_km,
        CASE
            WHEN rinfo.avg_preparation_time_min < 10 THEN '<10 min'
            WHEN rinfo.avg_preparation_time_min < 20 THEN '10-20 min'
            WHEN rinfo.avg_preparation_time_min < 30 THEN '20-30 min'
            ELSE '30+ min'
        END                                                                   AS prep_band,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN rest_id                                     AS oinfo
    ON dinfo.delivery_id = oinfo.delivery_id
    INNER JOIN results_channels.tb_restaurant              AS rinfo
    ON oinfo.restaurant_id = rinfo.restaurant_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
)
SELECT
    distance_band,
    prep_band,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(delivery_time_min)                                                    AS avg_delivery_time,
    APPX_MEDIAN(delivery_time_min)                                            AS median_delivery_time
FROM base
GROUP BY
    distance_band,
    prep_band
HAVING COUNT(*) >= 10
ORDER BY
    distance_band,
    prep_band;
```

**Reading:** inside each distance band, if time grows with prep_band, the kitchen is part of the delay. In the real Kaggle data the preparation time is per order, which is more precise than this restaurant average.

### 2.3 Weather and traffic: how related are they?

**Business question:** if weather and traffic almost always move together, the model cannot separate their effects. Both are categories, so I use a cross-tab instead of a correlation.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
)
SELECT
    dinfo.weather_condition,
    dinfo.traffic_condition,
    COUNT(*)                                                                  AS total_deliveries,
    COUNT(*) / SUM(COUNT(*)) OVER(PARTITION BY dinfo.weather_condition)       AS share_of_weather,
    AVG(dinfo.delivery_time_min)                                              AS avg_delivery_time,
    SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
FROM results_deliveries.tb_delivery_level_data             AS dinfo
CROSS JOIN max_or_date                                     AS odate
WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
GROUP BY
    dinfo.weather_condition,
    dinfo.traffic_condition
ORDER BY
    dinfo.weather_condition,
    share_of_weather DESC;
```

**Reading:** if one traffic level holds almost all of a weather value (for example rain always with high traffic), they are close to collinear. For the model, linear coefficients get unstable, so a combined variable or a regularized model is safer. For Ops, the response (extra couriers, expectation messages) should be decided on the combination.

### 2.4 Peak hours and days

**Business question:** when does the pace get worse?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
)
SELECT
    DAYNAME(dinfo.order_placed_at)                                            AS weekday_name,
    HOUR(dinfo.order_placed_at)                                               AS order_hour,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(dinfo.delivery_time_min)                                              AS avg_delivery_time,
    APPX_MEDIAN(dinfo.delivery_time_min)                                      AS median_delivery_time,
    SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
FROM results_deliveries.tb_delivery_level_data             AS dinfo
CROSS JOIN max_or_date                                     AS odate
WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
GROUP BY
    DAYNAME(dinfo.order_placed_at),
    HOUR(dinfo.order_placed_at)
HAVING COUNT(*) >= 10
ORDER BY
    weekday_name,
    order_hour;
```

**Action:** if the pace worsens at the hours with the most volume, it is a capacity problem (not enough couriers at peak). If it worsens at the same hours with low volume, I would look at traffic.

### 2.5 Does a longer delivery lower the rating?

**Business question:** from which delay do customers actually notice?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
base AS(
    SELECT
        dinfo.delivery_time_min,
        dinfo.delivery_rating,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
    AND   dinfo.delivery_rating IS NOT NULL
),
ranked AS(
    SELECT
        distance_band,
        delivery_rating,
        NTILE(10) OVER(PARTITION BY distance_band ORDER BY delivery_time_min) AS time_decile
    FROM base
)
SELECT
    distance_band,
    time_decile,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(delivery_rating)                                                      AS avg_rating
FROM ranked
GROUP BY
    distance_band,
    time_decile
ORDER BY
    distance_band,
    time_decile;
```

**Action:** the decile where the rating drops sharply is the delay customers notice. I would use it as the error tolerance of the prediction model and for customer messages.

---

## 3. Q3 insights: tracking couriers over time

### 3.1 Courier performance by month (for Power BI)

**Business question:** how does each courier evolve month by month, so Ops can follow progress and correct strategies? One row per courier and month, ready for Power BI.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max,
        TRUNC(MAX(order_placed_at), 'MM')                                     AS anchor_month_start
    FROM results_deliveries.tb_delivery_level_data
)
SELECT
    FROM_TIMESTAMP(dinfo.order_placed_at, 'yyyy-MM')                          AS monthly_date,
    CAST(dinfo.delivery_person_id AS INT)                                     AS delivery_person_id,
    pinfo.name,
    COUNT(*)                                                                  AS total_deliveries,
    AVG(dinfo.delivery_time_min)                                              AS avg_delivery_time,
    APPX_MEDIAN(dinfo.delivery_time_min)                                      AS median_delivery_time,
    SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km,
    AVG(dinfo.delivery_rating)                                                AS avg_rating
FROM results_deliveries.tb_delivery_level_data             AS dinfo
CROSS JOIN max_or_date                                     AS odate
INNER JOIN results_deliveries.tb_delivery_personnel        AS pinfo
ON CAST(dinfo.delivery_person_id AS INT) = pinfo.delivery_person_id
WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 12)
AND   dinfo.order_placed_at <  odate.anchor_month_start
AND   pinfo.is_active = TRUE
GROUP BY
    FROM_TIMESTAMP(dinfo.order_placed_at, 'yyyy-MM'),
    CAST(dinfo.delivery_person_id AS INT),
    pinfo.name
ORDER BY
    delivery_person_id,
    monthly_date;
```

For a weekly view I would replace the month label with **FROM_TIMESTAMP(DATE_TRUNC('WEEK', dinfo.order_placed_at), 'yyyy-MM-dd')** and shorten the window. In Power BI: **min_per_km** per courier and month in a line chart, plus a slicer for tenure band.

### 3.2 Q3 with a time window and pace (fairer ranking)

**Business question:** Q3 ranks all-history averages, which favors long tenure and short routes. Who is fastest **in the last 90 days, per km**?

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
courier_stats AS(
    SELECT
        CAST(dinfo.delivery_person_id AS INT)                                 AS delivery_person_id,
        COUNT(*)                                                              AS total_deliveries,
        AVG(dinfo.delivery_time_min)                                          AS avg_delivery_time,
        SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= DAYS_SUB(odate.order_date_max, 90)
    GROUP BY CAST(dinfo.delivery_person_id AS INT)
    HAVING COUNT(*) >= 50
),
ranking AS(
    SELECT
        cstats.delivery_person_id,
        pinfo.name,
        cstats.total_deliveries,
        cstats.avg_delivery_time,
        cstats.min_per_km,
        DENSE_RANK() OVER(ORDER BY cstats.min_per_km ASC)                     AS ranked_pace
    FROM courier_stats                                     AS cstats
    INNER JOIN results_deliveries.tb_delivery_personnel    AS pinfo
    ON cstats.delivery_person_id = pinfo.delivery_person_id
    WHERE pinfo.is_active = TRUE
)
SELECT
    delivery_person_id,
    name,
    total_deliveries,
    avg_delivery_time,
    min_per_km,
    ranked_pace
FROM ranking
WHERE ranked_pace <= 10
ORDER BY
    ranked_pace,
    delivery_person_id;
```

**Reading:** I compare it with Q3. A courier in both lists is fast in any window. A courier only in Q3 may be benefiting from tenure or short routes. DENSE_RANK() keeps ties visible for bonus decisions.

---

## 4. Q4 insights: revenue, ticket size and slow customers

### 4.1 From revenue to profit (costs are missing)

Q4 follows the brief and ranks by `order_value`, which is **revenue**. Profit also needs costs (courier pay, restaurant commission, incentives, payment fees) and none is in the data. This is the query I would run with an order-level cost table.

**HYPOTHETICAL table:** **results_transactional.tb_order_cost (order_id INT, order_cost FLOAT)**

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
area_profit AS(
    SELECT
        dinfo.restaurant_area,
        COUNT(DISTINCT oinfo.order_id)                                        AS total_orders,
        SUM(oinfo.order_value)                                                AS total_revenue,
        SUM(cinfo.order_cost)                                                 AS total_cost,
        SUM(oinfo.order_value) - SUM(cinfo.order_cost)                        AS total_profit
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN results_transactional.tb_order              AS oinfo
    ON dinfo.delivery_id = oinfo.delivery_id
    INNER JOIN results_transactional.tb_order_cost         AS cinfo
    ON oinfo.order_id = cinfo.order_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 3)
    GROUP BY dinfo.restaurant_area
)
SELECT
    restaurant_area,
    total_orders,
    total_revenue,
    total_cost,
    total_profit,
    total_profit / NULLIF(total_revenue, 0)                                   AS profit_margin,
    DENSE_RANK() OVER(ORDER BY total_profit DESC)                             AS ranking
FROM area_profit
ORDER BY ranking;
```

**Reading:** the area with the most revenue may not be the most profitable, especially if long or slow deliveries cost more (couriers are paid for time).

### 4.2 Ticket size per area and restaurant

**Business question:** how much do customers spend per order and how different is it between areas and restaurants? With it, promotions can target the right spending level.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
restaurant_ticket AS(
    SELECT
        dinfo.restaurant_area,
        rinfo.restaurant_id,
        rinfo.name                                                            AS restaurant_name,
        COUNT(DISTINCT oinfo.order_id)                                        AS total_orders,
        SUM(oinfo.order_value)                                                AS total_revenue,
        AVG(oinfo.order_value)                                                AS avg_ticket,
        APPX_MEDIAN(oinfo.order_value)                                        AS median_ticket,
        STDDEV_SAMP(oinfo.order_value)                                        AS stddev_ticket,
        SUM(oinfo.order_value) / NULLIF(SUM(oinfo.items_count), 0)            AS ticket_per_item
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN results_transactional.tb_order              AS oinfo
    ON dinfo.delivery_id = oinfo.delivery_id
    INNER JOIN results_channels.tb_restaurant              AS rinfo
    ON oinfo.restaurant_id = rinfo.restaurant_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 3)
    GROUP BY
        dinfo.restaurant_area,
        rinfo.restaurant_id,
        rinfo.name
    HAVING COUNT(DISTINCT oinfo.order_id) >= 10
)
SELECT
    restaurant_area,
    restaurant_id,
    restaurant_name,
    total_orders,
    avg_ticket,
    median_ticket,
    stddev_ticket,
    ticket_per_item,
    avg_ticket - SUM(total_revenue) OVER(PARTITION BY restaurant_area)
               / SUM(total_orders)  OVER(PARTITION BY restaurant_area)        AS gap_vs_area_avg,
    DENSE_RANK() OVER(PARTITION BY restaurant_area ORDER BY avg_ticket DESC)  AS ranking_in_area
FROM restaurant_ticket
ORDER BY
    restaurant_area,
    ranking_in_area;
```

**Reading and strategy:**
- The spread of avg_ticket inside an area shows the room to upsell.
- A promotion slightly above the area's typical median_ticket (for example free delivery above that amount) makes customers add items.
- The campaign can be **with a bank, with discounts on its credit cards**. The bank funds part of the discount, and the platform gets higher tickets and customer data to target segments.

### 4.3 Pareto: do a few customers hold most of the slow deliveries?

**Business question:** are the slow deliveries spread out or concentrated in a few customers? "Slow" is the SLOW decile from 1.1, and customers come from tb_order.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
base AS(
    SELECT
        dinfo.delivery_id,
        dinfo.delivery_time_min,
        CASE
            WHEN dinfo.delivery_distance_km <  3  THEN '0-3 km'
            WHEN dinfo.delivery_distance_km <  6  THEN '3-6 km'
            WHEN dinfo.delivery_distance_km < 10  THEN '6-10 km'
            ELSE '10+ km'
        END                                                                   AS distance_band
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
),
ranked AS(
    SELECT
        delivery_id,
        NTILE(10) OVER(PARTITION BY distance_band ORDER BY delivery_time_min) AS time_decile
    FROM base
),
customer_delivery AS(
    SELECT DISTINCT
        delivery_id,
        customer_id
    FROM results_transactional.tb_order
),
customer_slow AS(
    SELECT
        cinfo.customer_id,
        COUNT(*)                                                              AS total_deliveries,
        SUM(CASE WHEN rinfo.time_decile = 10 THEN 1 ELSE 0 END)               AS slow_deliveries
    FROM ranked                                            AS rinfo
    INNER JOIN customer_delivery                           AS cinfo
    ON rinfo.delivery_id = cinfo.delivery_id
    GROUP BY cinfo.customer_id
    HAVING SUM(CASE WHEN rinfo.time_decile = 10 THEN 1 ELSE 0 END) > 0
),
pareto AS(
    SELECT
        customer_id,
        total_deliveries,
        slow_deliveries,
        ROW_NUMBER() OVER(ORDER BY slow_deliveries DESC, customer_id)         AS customer_rank,
        SUM(slow_deliveries) OVER(ORDER BY slow_deliveries DESC, customer_id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            / SUM(slow_deliveries) OVER()                                     AS cumulative_share_slow,
        COUNT(*) OVER()                                                       AS total_customers_with_slow
    FROM customer_slow
)
SELECT
    customer_id,
    total_deliveries,
    slow_deliveries,
    customer_rank,
    customer_rank / total_customers_with_slow                                 AS share_of_customers,
    cumulative_share_slow
FROM pareto
WHERE cumulative_share_slow <= 0.8
ORDER BY customer_rank;
```

**Reading:** if the first 20% of customers hold about 80% of the slow deliveries, the problem is concentrated and Ops can target them. If the curve is flat, the cause is systemic (traffic, weather, courier supply) and a targeted fix will not work. Grouping by `customer_area` answers the same question at area level and avoids privacy issues.

---

## 5. Q5 insights: retention, survivorship and the A/B test

### 5.1 Minimum volume rule (left out of Q5 on purpose)

Q5 does not ask for a minimum of deliveries per courier-month, so the two quarters can rest on very different volumes. To add it, I would use HAVING COUNT(DISTINCT monthly_date) = 6 AND MIN(total_deliveries) >= 10  in the courier-level CTE. The 10 is my judgment, but I would define it with the bussines.

### 5.2 Retained vs churned couriers

**Business question:** Q5 only compares couriers who are still active, which hides the ones who left. Did couriers who **delivered in the older three months but not in the last three** (or are inactive now) have a worse pace? If yes, the trend of the survivors looks better than reality.

```sql
WITH
max_or_date AS(
    SELECT
        TRUNC(MAX(order_placed_at), 'MM')                                     AS anchor_month_start
    FROM results_deliveries.tb_delivery_level_data
),
period_stats AS(
    SELECT
        CAST(dinfo.delivery_person_id AS INT)                                 AS delivery_person_id,
        CASE
            WHEN dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 3) THEN 'RECENT'
            ELSE 'OLDER'
        END                                                                   AS period,
        COUNT(*)                                                              AS total_deliveries,
        SUM(dinfo.delivery_time_min)                                          AS sum_time,
        SUM(dinfo.delivery_distance_km)                                       AS sum_distance
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 6)
    AND   dinfo.order_placed_at <  odate.anchor_month_start
    GROUP BY
        CAST(dinfo.delivery_person_id AS INT),
        CASE
            WHEN dinfo.order_placed_at >= MONTHS_SUB(odate.anchor_month_start, 3) THEN 'RECENT'
            ELSE 'OLDER'
        END
),
courier_status AS(
    SELECT
        delivery_person_id,
        MAX(CASE WHEN period = 'OLDER'  THEN 1 ELSE 0 END)                    AS delivered_older,
        MAX(CASE WHEN period = 'RECENT' THEN 1 ELSE 0 END)                    AS delivered_recent,
        SUM(CASE WHEN period = 'OLDER'  THEN sum_time END)
        / SUM(CASE WHEN period = 'OLDER'  THEN sum_distance END)              AS min_per_km_older
    FROM period_stats
    GROUP BY delivery_person_id
)
SELECT
    CASE
        WHEN cstatus.delivered_recent = 1 AND pinfo.is_active = TRUE THEN 'RETAINED'
        ELSE 'CHURNED'
    END                                                                       AS courier_group,
    COUNT(*)                                                                  AS total_couriers,
    AVG(cstatus.min_per_km_older)                                             AS avg_min_per_km_older_period
FROM courier_status                                        AS cstatus
INNER JOIN results_deliveries.tb_delivery_personnel        AS pinfo
ON cstatus.delivery_person_id = pinfo.delivery_person_id
WHERE cstatus.delivered_older = 1
GROUP BY
    CASE
        WHEN cstatus.delivered_recent = 1 AND pinfo.is_active = TRUE THEN 'RETAINED'
        ELSE 'CHURNED'
    END;
```

**Reading:** if **CHURNED** had a higher **min_per_km** in the older period, the couriers who struggled are the ones who left, and the Q5 trend is biased upwards. It is also a retention signal, and it shows if the learning curve is a reason to quit.

### 5.3 A/B test: did the strategy work? (difference in differences)

**Business question:** if a support strategy (training, route tips, mentoring) was applied to some couriers and not to others, did their pace improve more than the control group?

**HYPOTHETICAL table:** **development.tb_courier_program (delivery_person_id INT, program_group STRING, program_start DATE)**, where **program_group** is **'TREATMENT'** or **'CONTROL'**. Controls get the same **program_start** as the treatment cohort, to define their before and after.

```sql
WITH
max_or_date AS(
    SELECT
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
group_period AS(
    SELECT
        prog.program_group,
        CASE
            WHEN dinfo.order_placed_at >= prog.program_start THEN 'AFTER'
            ELSE 'BEFORE'
        END                                                                   AS period,
        COUNT(*)                                                              AS total_deliveries,
        COUNT(DISTINCT prog.delivery_person_id)                               AS total_couriers,
        SUM(dinfo.delivery_time_min) / NULLIF(SUM(dinfo.delivery_distance_km), 0) AS min_per_km
    FROM results_deliveries.tb_delivery_level_data         AS dinfo
    CROSS JOIN max_or_date                                 AS odate
    INNER JOIN development.tb_courier_program              AS prog
    ON CAST(dinfo.delivery_person_id AS INT) = prog.delivery_person_id
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max, 6)
    GROUP BY
        prog.program_group,
        CASE
            WHEN dinfo.order_placed_at >= prog.program_start THEN 'AFTER'
            ELSE 'BEFORE'
        END
),
pivoted AS(
    SELECT
        program_group,
        MAX(CASE WHEN period = 'BEFORE' THEN min_per_km END)                  AS min_per_km_before,
        MAX(CASE WHEN period = 'AFTER'  THEN min_per_km END)                  AS min_per_km_after,
        MAX(CASE WHEN period = 'AFTER'  THEN total_couriers END)              AS total_couriers
    FROM group_period
    GROUP BY program_group
)
SELECT
    program_group,
    total_couriers,
    min_per_km_before,
    min_per_km_after,
    min_per_km_after - min_per_km_before                                      AS change_in_pace
FROM pivoted
ORDER BY program_group;
```

**Reading:** the effect is **change_in_pace** of **TREATMENT** minus **change_in_pace** of **CONTROL**. A negative number means the strategy made couriers faster than they would have been anyway (traffic and weather affect both groups). SQL gives only the point estimate, so before concluding I would run a t-test or bootstrap in Python.

Also, it would be useful to apply  the same query for **new couriers** only (hired less than 6 months ago), because the learning-curve strategy should show up first there. I compare it with their tenure curve (1.5).

### 5.4 Limits of the Z-score

- It is relative: if all couriers slow down, the Z-scores look normal. That is why Q5 shows the raw delta too.
- With about six months per courier the standard deviation is noisy. I treat 1.5 as a flag to review, not proof.
- Alternatives: a fitted slope per courier, or the count of months with a positive month-over-month change.
- A rising average can come from longer routes, traffic or weather and not from the courier, so I read **min_per_km** and conditions with the delta.