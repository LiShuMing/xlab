CREATE TABLE IF NOT EXISTS tbl_0 (
 dt date NULL COMMENT "etl",
 p1_col1 varchar(60) NULL COMMENT "",
 p1_col2 varchar(240) NULL COMMENT "",
 p1_col3 varchar(30) NULL COMMENT "",
 p1_col4 decimal128(22, 2) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p1_col1)
PARTITION BY (dt)
PROPERTIES (
"replication_num"="1");

CREATE TABLE IF NOT EXISTS tbl_1 (
 dt date NULL COMMENT "",
 p1_col1 varchar(240) NULL COMMENT "",
 p1_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p1_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p1_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);

CREATE TABLE IF NOT EXISTS tbl_2 (
 dt date NULL COMMENT "",
 p2_col1 varchar(240) NULL COMMENT "",
 p2_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p2_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p2_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_3 (
 dt date NULL COMMENT "",
 p3_col1 varchar(240) NULL COMMENT "",
 p3_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p3_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p3_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_4 (
 dt date NULL COMMENT "",
 p4_col1 varchar(240) NULL COMMENT "",
 p4_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p4_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p4_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_5 (
 dt date NULL COMMENT "",
 p5_col1 varchar(240) NULL COMMENT "",
 p5_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p5_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p5_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_6 (
 dt date NULL COMMENT "",
 p6_col1 varchar(240) NULL COMMENT "",
 p6_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p6_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p6_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_7 (
 dt date NULL COMMENT "",
 p7_col1 varchar(240) NULL COMMENT "",
 p7_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p7_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p7_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_8 (
 dt date NULL COMMENT "",
 p8_col1 varchar(240) NULL COMMENT "",
 p8_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p8_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p8_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_9 (
 dt date NULL COMMENT "",
 p9_col1 varchar(240) NULL COMMENT "",
 p9_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p9_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p9_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_10 (
 dt date NULL COMMENT "",
 p10_col1 varchar(240) NULL COMMENT "",
 p10_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p10_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p10_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_11 (
 dt date NULL COMMENT "",
 p11_col1 varchar(240) NULL COMMENT "",
 p11_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p11_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p11_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_12 (
 dt date NULL COMMENT "",
 p12_col1 varchar(240) NULL COMMENT "",
 p12_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p12_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p12_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_13 (
 dt date NULL COMMENT "",
 p13_col1 varchar(240) NULL COMMENT "",
 p13_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p13_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p13_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_14 (
 dt date NULL COMMENT "",
 p14_col1 varchar(240) NULL COMMENT "",
 p14_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p14_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p14_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_15 (
 dt date NULL COMMENT "",
 p15_col1 varchar(240) NULL COMMENT "",
 p15_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p15_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p15_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_16 (
 dt date NULL COMMENT "",
 p16_col1 varchar(240) NULL COMMENT "",
 p16_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p16_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p16_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_17 (
 dt date NULL COMMENT "",
 p17_col1 varchar(240) NULL COMMENT "",
 p17_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p17_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p17_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_18 (
 dt date NULL COMMENT "",
 p18_col1 varchar(240) NULL COMMENT "",
 p18_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p18_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p18_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);
CREATE TABLE IF NOT EXISTS tbl_19 (
 dt date NULL COMMENT "",
 p19_col1 varchar(240) NULL COMMENT "",
 p19_col2 varchar(240) NULL COMMENT ""
) ENGINE=OLAP 
DUPLICATE KEY(dt, p19_col1)
PARTITION BY (dt)
DISTRIBUTED BY HASH(dt, p19_col2) BUCKETS 1 
PROPERTIES (
"replication_num"="1",
"in_memory"="false",
"storage_format"="DEFAULT",
"enable_persistent_index"="false",
"compression"="LZ4"
);


INSERT INTO tbl_0 VALUES  ('2023-01-01', 'a', 'WIZkU', 'x', 100.50), ('2023-01-02', 'b', 'yzUbH', 'y', 200.75), ('2023-02-01', 'c', 'AaViB', 'z', 300.25), ('2023-02-15', 'd', 'fzWAo', 'w', 400.00), ('2023-03-01', 'e', 'DTZfq', 'v', 500.00);
INSERT INTO tbl_1 VALUES  ('2023-01-01', 'a', 'WIZkU'), ('2023-01-02', 'b', 'yzUbH'), ('2023-02-01', 'c', 'AaViB'), ('2023-03-01', 'f', 'GBKdn'), ('2023-03-10', 'g', 'xVQVk');
INSERT INTO tbl_2 VALUES  ('2023-01-01', 'a', 'WIZkU'), ('2023-02-01', 'd', 'LryHQ'), ('2023-02-15', 'e', 'FPaPi'), ('2023-03-01', 'g', 'DBOUn'), ('2023-03-20', 'h', 'arLWO');
INSERT INTO tbl_3 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_4 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_5 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_6 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_7 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_8 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_9 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_10 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_11 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_12 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_13 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_14 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_15 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_16 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_17 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_18 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');
INSERT INTO tbl_19 VALUES  ('2023-01-01', 'a', 'tJioV'), ('2023-02-01', 'b', 'QFtkz'), ('2023-03-01', 'c', 'inflI'), ('2023-03-15', 'd', 'OLerW'), ('2023-03-25', 'e', 'gOnzR');


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_1
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 AS p0 LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_2
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 AS p0 LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_3
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 AS p0 LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
LEFT OUTER JOIN tbl_5 AS p5 ON p5.dt=p1.dt
LEFT OUTER JOIN tbl_6 AS p6 ON p6.dt=p1.dt
LEFT OUTER JOIN tbl_7 AS p7 ON p7.dt=p1.dt
LEFT OUTER JOIN tbl_8 AS p8 ON p8.dt=p1.dt
LEFT OUTER JOIN tbl_9 AS p9 ON p9.dt=p1.dt
LEFT OUTER JOIN tbl_10 AS p10 ON p10.dt=p1.dt
LEFT OUTER JOIN tbl_11 AS p11 ON p11.dt=p1.dt
LEFT OUTER JOIN tbl_12 AS p12 ON p12.dt=p1.dt
LEFT OUTER JOIN tbl_13 AS p13 ON p13.dt=p1.dt
LEFT OUTER JOIN tbl_14 AS p14 ON p14.dt=p1.dt
LEFT OUTER JOIN tbl_15 AS p15 ON p15.dt=p1.dt
LEFT OUTER JOIN tbl_16 AS p16 ON p16.dt=p1.dt
LEFT OUTER JOIN tbl_17 AS p17 ON p17.dt=p1.dt
LEFT OUTER JOIN tbl_18 AS p18 ON p18.dt=p1.dt
LEFT OUTER JOIN tbl_19 AS p19 ON p19.dt=p1.dt
;
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_4
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 AS p0 LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
LEFT OUTER JOIN tbl_5 AS p5 ON p5.dt=p1.dt
LEFT OUTER JOIN tbl_6 AS p6 ON p6.dt=p1.dt
LEFT OUTER JOIN tbl_7 AS p7 ON p7.dt=p1.dt
LEFT OUTER JOIN tbl_8 AS p8 ON p8.dt=p1.dt
LEFT OUTER JOIN tbl_9 AS p9 ON p9.dt=p1.dt
LEFT OUTER JOIN tbl_10 AS p10 ON p10.dt=p1.dt
LEFT OUTER JOIN tbl_11 AS p11 ON p11.dt=p1.dt
LEFT OUTER JOIN tbl_12 AS p12 ON p12.dt=p1.dt
LEFT OUTER JOIN tbl_13 AS p13 ON p13.dt=p1.dt
LEFT OUTER JOIN tbl_14 AS p14 ON p14.dt=p1.dt
LEFT OUTER JOIN tbl_15 AS p15 ON p15.dt=p1.dt
LEFT OUTER JOIN tbl_16 AS p16 ON p16.dt=p1.dt
LEFT OUTER JOIN tbl_17 AS p17 ON p17.dt=p1.dt
LEFT OUTER JOIN tbl_18 AS p18 ON p18.dt=p1.dt
LEFT OUTER JOIN tbl_19 AS p19 ON p19.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_5
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT u0.dt FROM ( SELECT p0.dt FROM tbl_0 p0 WHERE p1_col1 = 'a'  UNION ALL SELECT p0.dt FROM tbl_0 p0 WHERE p1_col2 = 'b') u0
LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_6
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT u0.dt FROM ( SELECT p0.dt FROM tbl_0 p0 WHERE p1_col1 = 'a'  UNION ALL SELECT p0.dt FROM tbl_0 p0 WHERE p1_col2 = 'b') u0
LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
LEFT OUTER JOIN tbl_5 AS p5 ON p5.dt=p1.dt
LEFT OUTER JOIN tbl_6 AS p6 ON p6.dt=p1.dt
LEFT OUTER JOIN tbl_7 AS p7 ON p7.dt=p1.dt
LEFT OUTER JOIN tbl_8 AS p8 ON p8.dt=p1.dt
LEFT OUTER JOIN tbl_9 AS p9 ON p9.dt=p1.dt
LEFT OUTER JOIN tbl_10 AS p10 ON p10.dt=p1.dt
LEFT OUTER JOIN tbl_11 AS p11 ON p11.dt=p1.dt
LEFT OUTER JOIN tbl_12 AS p12 ON p12.dt=p1.dt
LEFT OUTER JOIN tbl_13 AS p13 ON p13.dt=p1.dt
LEFT OUTER JOIN tbl_14 AS p14 ON p14.dt=p1.dt
LEFT OUTER JOIN tbl_15 AS p15 ON p15.dt=p1.dt
LEFT OUTER JOIN tbl_16 AS p16 ON p16.dt=p1.dt
LEFT OUTER JOIN tbl_17 AS p17 ON p17.dt=p1.dt
LEFT OUTER JOIN tbl_18 AS p18 ON p18.dt=p1.dt
LEFT OUTER JOIN tbl_19 AS p19 ON p19.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_7
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT u0.dt FROM ( SELECT p0.dt FROM tbl_0 p0 WHERE p1_col1 = 'a'  UNION ALL SELECT p0.dt FROM tbl_0 p0 WHERE p1_col2 = 'b') u0
LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
LEFT OUTER JOIN tbl_5 AS p5 ON p5.dt=p1.dt
LEFT OUTER JOIN tbl_6 AS p6 ON p6.dt=p1.dt
LEFT OUTER JOIN tbl_7 AS p7 ON p7.dt=p1.dt
LEFT OUTER JOIN tbl_8 AS p8 ON p8.dt=p1.dt
LEFT OUTER JOIN tbl_9 AS p9 ON p9.dt=p1.dt
LEFT OUTER JOIN tbl_10 AS p10 ON p10.dt=p1.dt
LEFT OUTER JOIN tbl_11 AS p11 ON p11.dt=p1.dt
LEFT OUTER JOIN tbl_12 AS p12 ON p12.dt=p1.dt
LEFT OUTER JOIN tbl_13 AS p13 ON p13.dt=p1.dt
LEFT OUTER JOIN tbl_14 AS p14 ON p14.dt=p1.dt
LEFT OUTER JOIN tbl_15 AS p15 ON p15.dt=p1.dt
LEFT OUTER JOIN tbl_16 AS p16 ON p16.dt=p1.dt
LEFT OUTER JOIN tbl_17 AS p17 ON p17.dt=p1.dt
LEFT OUTER JOIN tbl_18 AS p18 ON p18.dt=p1.dt
LEFT OUTER JOIN tbl_19 AS p19 ON p19.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_8
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT u0.dt FROM ( SELECT p0.dt FROM tbl_0 p0 WHERE p1_col1 = 'a'  UNION ALL SELECT p0.dt FROM tbl_0 p0 WHERE p1_col2 = 'b') u0
LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_9
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT u0.dt FROM ( SELECT p0.dt FROM tbl_0 p0 WHERE p1_col1 = 'a'  UNION ALL SELECT p0.dt FROM tbl_0 p0 WHERE p1_col2 = 'b') u0
LEFT OUTER JOIN tbl_1 AS p1 ON p1.dt=p1.dt
LEFT OUTER JOIN tbl_2 AS p2 ON p2.dt=p1.dt
LEFT OUTER JOIN tbl_3 AS p3 ON p3.dt=p1.dt
LEFT OUTER JOIN tbl_4 AS p4 ON p4.dt=p1.dt
LEFT OUTER JOIN tbl_5 AS p5 ON p5.dt=p1.dt
LEFT OUTER JOIN tbl_6 AS p6 ON p6.dt=p1.dt
LEFT OUTER JOIN tbl_7 AS p7 ON p7.dt=p1.dt
LEFT OUTER JOIN tbl_8 AS p8 ON p8.dt=p1.dt
LEFT OUTER JOIN tbl_9 AS p9 ON p9.dt=p1.dt
LEFT OUTER JOIN tbl_10 AS p10 ON p10.dt=p1.dt
LEFT OUTER JOIN tbl_11 AS p11 ON p11.dt=p1.dt
LEFT OUTER JOIN tbl_12 AS p12 ON p12.dt=p1.dt
LEFT OUTER JOIN tbl_13 AS p13 ON p13.dt=p1.dt
LEFT OUTER JOIN tbl_14 AS p14 ON p14.dt=p1.dt
LEFT OUTER JOIN tbl_15 AS p15 ON p15.dt=p1.dt
LEFT OUTER JOIN tbl_16 AS p16 ON p16.dt=p1.dt
LEFT OUTER JOIN tbl_17 AS p17 ON p17.dt=p1.dt
LEFT OUTER JOIN tbl_18 AS p18 ON p18.dt=p1.dt
LEFT OUTER JOIN tbl_19 AS p19 ON p19.dt=p1.dt
;


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_10
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 p0 LEFT OUTER JOIN tbl_1 AS p1 ON p0.dt=p1.dt 
WHERE p0.p1_col1 = 'a'  OR (p0.p1_col1 = 'kI' AND p0.p1_col2 = 'WIZkU' )  OR (p0.p1_col1 = 'bE' AND p0.p1_col2 = 'xrUIf' )  OR (p0.p1_col1 = 'UC' AND p0.p1_col2 = 'QFtkz' )  OR (p0.p1_col1 = 'vH' AND p0.p1_col2 = 'tJioV' )  OR (p0.p1_col1 = 'Ho' AND p0.p1_col2 = 'LryHQ' )  OR (p0.p1_col1 = 'th' AND p0.p1_col2 = 'arLWO' )  OR (p0.p1_col1 = 'ut' AND p0.p1_col2 = 'MMyLS' )  OR (p0.p1_col1 = 'DZ' AND p0.p1_col2 = 'jmHRY' )  OR (p0.p1_col1 = 'QF' AND p0.p1_col2 = 'yzUbH' )  OR (p0.p1_col1 = 'ki' AND p0.p1_col2 = 'AaViB' ) ;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_11
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 p0 LEFT OUTER JOIN tbl_1 AS p1 ON p0.dt=p1.dt 
WHERE p0.p1_col1 = 'a'  OR (p0.p1_col1 = 'Li' AND p0.p1_col2 = 'fzWAo' )  OR (p0.p1_col1 = 'qM' AND p0.p1_col2 = 'DTZfq' )  OR (p0.p1_col1 = 'QN' AND p0.p1_col2 = 'XnVbg' )  OR (p0.p1_col1 = 'FZ' AND p0.p1_col2 = 'MGWGw' )  OR (p0.p1_col1 = 'tm' AND p0.p1_col2 = 'isKgU' ) ;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_12
REFRESH  ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 p0 LEFT OUTER JOIN tbl_1 AS p1 ON p0.dt=p1.dt 
WHERE p0.p1_col1 = 'a'  OR (p0.p1_col1 = 'qZ' AND p0.p1_col2 = 'gOnzR' )  OR (p0.p1_col1 = 'Bz' AND p0.p1_col2 = 'WVUdg' )  OR (p0.p1_col1 = 'fm' AND p0.p1_col2 = 'GuqHW' )  OR (p0.p1_col1 = 'eY' AND p0.p1_col2 = 'TbZWK' )  OR (p0.p1_col1 = 'GB' AND p0.p1_col2 = 'inflI' )  OR (p0.p1_col1 = 'JT' AND p0.p1_col2 = 'OLerW' )  OR (p0.p1_col1 = 'Jm' AND p0.p1_col2 = 'gcxBo' )  OR (p0.p1_col1 = 'Vy' AND p0.p1_col2 = 'fYGHW' )  OR (p0.p1_col1 = 'sB' AND p0.p1_col2 = 'OXiJW' )  OR (p0.p1_col1 = 'uw' AND p0.p1_col2 = 'FPaPi' ) ;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_13
REFRESH ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 p0 LEFT OUTER JOIN tbl_1 AS p1 ON p0.dt=p1.dt 
WHERE p0.p1_col1 = 'a'  OR (p0.p1_col1 = 'XC' AND p0.p1_col2 = 'GBKdn' ) ;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_manyjoin_14
REFRESH ASYNC 
PROPERTIES (
"replication_num"="1"
)
AS SELECT p0.dt FROM tbl_0 p0 LEFT OUTER JOIN tbl_1 AS p1 ON p0.dt=p1.dt 
WHERE p0.p1_col1 = 'a'  OR (p0.p1_col1 = 'DM' AND p0.p1_col2 = 'xVQVk' )  OR (p0.p1_col1 = 'RF' AND p0.p1_col2 = 'gxmOz' )  OR (p0.p1_col1 = 'oG' AND p0.p1_col2 = 'DBOUn' )  OR (p0.p1_col1 = 'oi' AND p0.p1_col2 = 'RwaON' )  OR (p0.p1_col1 = 'pD' AND p0.p1_col2 = 'mJePH' ) ;

