INSERT INTO lineorder (lo_orderkey, lo_linenumber, lo_custkey, lo_partkey, lo_suppkey
	, lo_orderdate, lo_orderpriority, lo_shippriority, lo_quantity, lo_extendedprice
	, lo_ordtotalprice, lo_discount, lo_revenue, lo_supplycost, lo_tax
	, lo_commitdate, lo_shipmode)
VALUES
    (1, 1, 101, 201, 301, 19930101, 'HIGH', 1, 10, 100, 90, 0, 90, 50, 5, 19930115, 'AIR'),
    (2, 2, 102, 202, 302, 19940101, 'MEDIUM', 2, 20, 200, 180, 5, 175, 75, 7, 19940116, 'SHIP');

INSERT INTO customer (c_custkey, c_name, c_address, c_city, c_nation
    , c_region, c_phone, c_mktsegment)
VALUES
(1, 'Customer1', '123 Main St', 'City1', 'Nation1', 'Region1', '123-456-7890', 'Segment1'),
(2, 'Customer2', '456 Oak St', 'City2', 'Nation2', 'Region2', '987-654-3210', 'Segment2'),
(3, 'Customer3', '789 Pine St', 'City3', 'Nation3', 'Region3', '555-123-4567', 'Segment3');

INSERT INTO dates (d_datekey, d_date, d_dayofweek, d_month, d_year
	, d_yearmonthnum, d_yearmonth, d_daynuminweek, d_daynuminmonth, d_daynuminyear
	, d_monthnuminyear, d_weeknuminyear, d_sellingseason, d_lastdayinweekfl, d_lastdayinmonthfl
	, d_holidayfl, d_weekdayfl)
VALUES (1, '2023-12-07', 'Wednesday', 'December', 2023, 202312, '2023-12', 3, 7, 341, 12, 49, 'Holiday Season', 0, 0, 1, 1);

INSERT INTO supplier (s_suppkey, s_name, s_address, s_city, s_nation, s_region, s_phone)
VALUES (1, 'Supplier1', '123 Main St', 'City1', 'Nation1', 'Region1', '123-456-7890');

INSERT INTO part (p_partkey, p_name, p_mfgr, p_category, p_brand, p_color, p_type, p_size, p_container)
VALUES (1, 'Part1', 'Manufr1', 'Catey1', 'Brand1', 'Red', 'Type1', 10, 'Container1');