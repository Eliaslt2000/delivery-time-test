/*

                                        GENERAL ASSUMPTIONS:
    1. I'm assuming that I'm working with IMPALA SQL.
    2. The given tables are have been pass through an ETL process and are productive.
    3. I used invented fake names for the zone where the're storage and their respective tables names.  
==================================================================================================

table_name = tb_delivery_level_data
zone = results_deliveries

deliveries (
delivery_id VARCHAR,
delivery_person_id VARCHAR,
restaurant_area VARCHAR,
customer_area VARCHAR,
delivery_distance_km FLOAT,
delivery_time_min INT,
order_placed_at TIMESTAMP,
weather_condition VARCHAR,
traffic_condition VARCHAR,
delivery_rating FLOAT
)
==================================================================================================
table_name = tb_delivery_personnel
zone = results_deliveries
Delivery personnel metadata
delivery_persons (
delivery_person_id INT,
name VARCHAR,
region VARCHAR,
hired_date DATE,
is_active BOOLEAN
)
==================================================================================================
table_name = tb_restaurant   
zone = results_channels 
restaurants (
restaurant_id VARCHAR,
area VARCHAR,
name VARCHAR,
cuisine_type VARCHAR,
avg_preparation_time_min FLOAT
)


==================================================================================================
table_name = tb_order
zone = results_transactional
-- Orders table
orders (
order_id INT,
delivery_id VARCHAR,
restaurant_id VARCHAR,
customer_id VARCHAR,
order_value FLOAT,
items_count INT
)

==================================================================================================
*/

/*
==================================================================================================
QUESTION 1: Top 5 customer areas with highest average delivery time in the last 30 days.
--------------------------
ASSUMPTIONS:
1. Because there are no ingestion dates or year/month/day partition columns, I used order_placed_at to get the deliveries from the last 30 days.
2. The reference date is MAX(order_placed_at), not NOW(), so the query also works on historical data.
3. total_deliveries is shown so the business can judge how reliable each average is. No minimum threshold is applied.
4. I used DENSE_RANK() instead of ROW_NUMBER() so it can bring more information to the business in case a tie happens. I'll expand more
on this in sql_insights.md.
==================================================================================================
*/

WITH 
max_or_date AS(
    SELECT MAX(order_placed_at)                                                     AS max_order_date 
    FROM results_deliveries.tb_delivery_level_data
),
avg_time AS(
    SELECT 
        dtime.customer_area,
        AVG(dtime.delivery_time_min)                                              AS avg_delivery_time,
        COUNT(*)                                                                  AS total_deliveries
    FROM results_deliveries.tb_delivery_level_data         AS dtime
    CROSS JOIN max_or_date                                 AS odate
    WHERE order_placed_at >= DAYS_SUB(odate.max_order_date,30)
    GROUP BY dtime.customer_area
),
ranked_areas AS(
    SELECT 
        customer_area, 
        avg_delivery_time, 
        total_deliveries, 
        DENSE_RANK() OVER(ORDER BY avg_delivery_time DESC)                         AS ranking 
    FROM avg_time 
)
SELECT 
    customer_area, 
    avg_delivery_time,
    total_deliveries,
    ranking
FROM ranked_areas 
WHERE ranking <= 5
ORDER BY ranking, customer_area;
  
/*
==================================================================================================
QUESTION 2: Average delivery time per traffic condition, by restaurant area and cuisine type.
--------------------------
ASSUMPTIONS:
1. One delivery is picked up from one restaurant, so SELECT DISTINCT delivery_id, restaurant_id gives one row per delivery.
If that is false, a delivery would be counted under two cuisines.
2. The restaurant area is taken from tb_delivery_level_data (restaurant_area), not from tb_restaurant (area).
3. No date filter is applied, since the question doesn't ask for one. I expand on this in sql_insights.md.
4. The INNER JOIN is intentional, so deliveries with no matching order or restaurant are excluded. I quantify them in sql_insights.md.
==================================================================================================
*/
WITH
rest_id AS(
    SELECT 
        distinct delivery_id, restaurant_id
    FROM results_transactional.tb_order
),
rest_del AS(
    SELECT 
        dinfo.delivery_id,
        rinfo.restaurant_id,
        dinfo.traffic_condition,
        dinfo.restaurant_area,
        dinfo.delivery_time_min
    FROM results_deliveries.tb_delivery_level_data    AS dinfo 
    INNER JOIN rest_id                                AS rinfo
    ON dinfo.delivery_id = rinfo.delivery_id
),
rest_area AS(
    SELECT
        rdinfo.restaurant_area,
        arinfo.cuisine_type,
        rdinfo.traffic_condition,
        COUNT(*)                                                      AS total_deliveries,
        AVG(rdinfo.delivery_time_min)                                 AS avg_delivery_time
    FROM results_channels.tb_restaurant               AS arinfo            
    INNER JOIN rest_del                               AS rdinfo 
    ON arinfo.restaurant_id = rdinfo.restaurant_id
    GROUP BY 
        rdinfo.restaurant_area,
        arinfo.cuisine_type,
        rdinfo.traffic_condition
)
SELECT 
        restaurant_area,
        cuisine_type,
        traffic_condition,
        total_deliveries,
        avg_delivery_time 
FROM rest_area
ORDER BY 
    restaurant_area,
    cuisine_type,
    traffic_condition;

/*
==================================================================================================
QUESTION 3: Top 10 delivery people with the fastest average delivery time, considering only those with at least 50 deliveries and who are still active.
--------------------------
ASSUMPTIONS: 
1. The column delivery_person_id from the table results_deliveries.tb_delivery_level_data has only numeric values stored as VARCHAR (strings in IMPALA).
2. The question asks for the top 10 delivery people. I used DENSE_RANK() instead of ROW_NUMBER() so it can bring more information to the business in case a tie happens. I'll expand more 
on this in sql_insights.md.
3. The column is_active from the table tb_delivery_personnel is today's status (full-load snapshot), not the status at the time of each delivery.
4. The data could be downloaded in a .xlsx file (typically used within the business). I left the is_active column so the user can be sure of the status of the delivery employee.   
==================================================================================================
*/

WITH 
employee AS(
    SELECT 
        delivery_person_id,
        name,
        is_active
    FROM results_deliveries.tb_delivery_personnel
    WHERE is_active IS TRUE 
),
deliveries AS(
    SELECT 
        CAST(delivery_person_id AS INT)                       AS delivery_person_id,
        COUNT(*)                                              AS total_deliveries,
        AVG(delivery_time_min)                                AS avg_delivery_time
    FROM results_deliveries.tb_delivery_level_data
    GROUP BY 
        CAST(delivery_person_id AS INT)
    HAVING COUNT(*) >= 50        
),
employee_deliveries AS(
    SELECT 
        emp.delivery_person_id,
        emp.name,
        emp.is_active,
        del.total_deliveries,
        del.avg_delivery_time
    FROM employee                     AS emp
    INNER JOIN deliveries             AS del 
    ON emp.delivery_person_id = del.delivery_person_id
),
ranking AS(
    SELECT 
        delivery_person_id,
        name,
        is_active,
        total_deliveries,
        avg_delivery_time,
        DENSE_RANK() OVER(ORDER BY avg_delivery_time ASC)     AS ranked_deliveries 
    FROM employee_deliveries
)
SELECT 
    delivery_person_id,
    name,
    is_active,
    total_deliveries,
    avg_delivery_time,
    ranked_deliveries
FROM ranking 
WHERE  ranked_deliveries <= 10
ORDER BY 
    ranked_deliveries,
    delivery_person_id;

/*
==================================================================================================
QUESTION 4: The most profitable restaurant area in the last 3 months, defined as the area with the highest total order value.
--------------------------
ASSUMPTIONS: 
1. Because there are no ingestion dates or year/month/day partition columns, I used order_placed_at to get the deliveries from the last 30 days.
2. The reference date is MAX(order_placed_at), not NOW(), so the query also works on historical data.
3. total_items_count is shown so the business can judge how reliable each average is. No minimum threshold is applied.
4. I used DENSE_RANK() instead of ROW_NUMBER() so it can bring more information to the business in case a tie happens. I'll expand more
on this in sql_insights.md.
5."Profitable" follows the brief: total order value, which is revenue, not profit (the data has no costs).
6.The area comes from tb_delivery_level_data (restaurant_area), as in Q2.
==================================================================================================
*/
WITH 
order_date AS(
    SELECT 
        MAX(order_placed_at)                                                  AS order_date_max
    FROM results_deliveries.tb_delivery_level_data
),
deliveries AS(
    SELECT 
        dinfo.delivery_id, 
        dinfo.restaurant_area
    FROM results_deliveries.tb_delivery_level_data     AS dinfo 
    CROSS JOIN order_date                              AS odate
    WHERE dinfo.order_placed_at >= MONTHS_SUB(odate.order_date_max,3)
),
area_order AS(
    SELECT 
        deli.restaurant_area,
        SUM(ord.order_value)                                                 AS total_order_value, 
        SUM(ord.items_count)                                                 AS total_items_count
    FROM deliveries                                 AS deli
    INNER JOIN results_transactional.tb_order       AS ord 
    ON deli.delivery_id = ord.delivery_id 
    GROUP BY deli.restaurant_area
),
top_area AS(
    SELECT 
        restaurant_area,
        total_order_value, 
        total_items_count,
        DENSE_RANK() OVER(ORDER BY total_order_value DESC)                   AS ranked_order_value
    FROM area_order 
)
SELECT 
    restaurant_area,
    total_order_value, 
    total_items_count,
    ranked_order_value
FROM top_area 
WHERE ranked_order_value = 1
ORDER BY restaurant_area;

/*
================================================================================================================
QUESTION 5: Identify whether any delivery people show an increasing trend in average delivery time.
--------------------------
ASSUMPTIONS:
1. The development zone exists and is used to make testing and one-time tables. 
2. Just in case there are months without deliveries, I used the tmp_calendar table. 
3. The column is_active from the table tb_delivery_personnel is today's status (full-load snapshot), not the status at the time of each delivery.
4. The anchor month is excluded as partial. The window is m1 to m6: m1 to m3 is the recent quarter, m4 to m6 the older one.

================================================================================================================
*/

DROP TABLE IF EXISTS development.tmp_calendar PURGE;
CREATE TABLE development.tmp_calendar STORED AS PARQUET AS 
WITH 
calendar_months AS(
    SELECT
        mcal.month_idx,
        FROM_TIMESTAMP(MONTHS_SUB(TRUNC(dmax.max_date, 'MM'), mcal.month_idx), 'yyyy-MM')             AS monthly_date,
        MONTHS_SUB(TRUNC(dmax.max_date, 'MM'), mcal.month_idx)                                        AS month_start,
        TRUNC(dmax.max_date, 'MM')                                                                    AS anchor_month_start
    FROM (SELECT MAX(order_placed_at) AS max_date
          FROM results_deliveries.tb_delivery_level_data)                             AS dmax
    CROSS JOIN (SELECT 1 AS month_idx UNION ALL SELECT 2 UNION ALL SELECT 3
                UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6)             AS mcal
)
SELECT *
FROM calendar_months;

COMPUTE INCREMENTAL STATS development.tmp_calendar;



WITH
deliveries AS(
    SELECT 
        FROM_TIMESTAMP(dinfo.order_placed_at,'yyyy-MM')                                              AS monthly_date,
        CAST(dinfo.delivery_person_id AS INT)                                                        AS delivery_person_id,
        AVG(dinfo.delivery_distance_km)                                                              AS avg_distance_km,
        AVG(dinfo.delivery_time_min)                                                                 AS avg_delivery_time,
        COUNT(*)                                                                                     AS total_deliveries 
    FROM results_deliveries.tb_delivery_level_data                AS dinfo       
    INNER JOIN development.tmp_calendar                           AS cal
    ON FROM_TIMESTAMP(dinfo.order_placed_at,'yyyy-MM') = cal.monthly_date
    GROUP BY 
        FROM_TIMESTAMP(dinfo.order_placed_at,'yyyy-MM'),
        CAST(dinfo.delivery_person_id AS INT)
),
personnel AS(
    SELECT 
        pinfo.delivery_person_id, 
        pinfo.name 
    FROM results_deliveries.tb_delivery_personnel                   AS pinfo
    CROSS JOIN (SELECT MIN(month_start) AS oldest_month_start
                FROM development.tmp_calendar)                      AS cal
    WHERE pinfo.is_active = TRUE
    AND   pinfo.hired_date <= MONTHS_SUB(cal.oldest_month_start, 6)
),
personnel_deliv AS(
    SELECT 
        del.monthly_date,
        cal.month_idx,
        per.delivery_person_id, 
        per.name, 
        del.avg_distance_km,
        del.avg_delivery_time,
        del.total_deliveries
    FROM personnel                                               AS per
    INNER JOIN deliveries                                        AS del
    ON  per.delivery_person_id = del.delivery_person_id
    INNER JOIN development.tmp_calendar                          AS cal
    ON  del.monthly_date = cal.monthly_date
),
delta AS(
    SELECT 
        delivery_person_id,
        name, 
        SUM(CASE WHEN month_idx <= 3 THEN avg_delivery_time * total_deliveries END)
        / SUM(CASE WHEN month_idx <=3 THEN total_deliveries END)                                  AS avg_time_recent,
        SUM(CASE WHEN month_idx >= 4 THEN avg_delivery_time * total_deliveries END)
        / SUM(CASE WHEN month_idx >= 4 THEN total_deliveries END)                                 AS avg_time_old, 
        SUM(CASE WHEN month_idx <= 3 THEN avg_delivery_time * total_deliveries END)
        / SUM(CASE WHEN month_idx <=3 THEN avg_distance_km * total_deliveries END)                AS avg_min_km_recent,
        SUM(CASE WHEN month_idx >= 4 THEN avg_delivery_time * total_deliveries END)
        / SUM(CASE WHEN month_idx >= 4 THEN avg_distance_km * total_deliveries END)               AS avg_min_km_old
    FROM personnel_deliv
    GROUP BY 
        delivery_person_id,
        name
), 
zscore AS(
    SELECT 
        delivery_person_id,
        name, 
        avg_time_recent,
        avg_time_old,
        avg_time_recent - avg_time_old                                                           AS delta_mins,
        avg_min_km_recent - avg_min_km_old                                                       AS delta_min_km,
        ((avg_time_recent - avg_time_old) - AVG(avg_time_recent - avg_time_old) OVER ())
            / NULLIF(STDDEV_SAMP(avg_time_recent - avg_time_old) OVER (), 0)                     AS z_score
    FROM delta 
    WHERE avg_time_recent IS NOT NULL
    AND avg_time_old  IS NOT NULL
)
SELECT 
    delivery_person_id,
    name, 
    avg_time_recent,
    avg_time_old,
    delta_mins,
    delta_min_km,
    z_score, 
    CASE 
        WHEN z_score >= 1.5 THEN "SLOWER"
        WHEN z_score <= -1.5 THEN "FASTER"
        ELSE "IN LINE"
    END                                                                                        AS trend_flag
FROM zscore 
WHERE delta_mins > 0
ORDER BY    
    z_score DESC;






