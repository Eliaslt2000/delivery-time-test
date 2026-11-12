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
zone = results.transactional
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

COMPUTE INCREMENTAL STATS development.tb_delivery_data ;
  
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