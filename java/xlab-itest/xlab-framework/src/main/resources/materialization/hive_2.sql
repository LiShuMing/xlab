create external catalog hive  PROPERTIES("type" = "hive", "hive.metastore.uris" = "thrift://172.26.194.238:9083");

set catalog hive;

create database if not EXISTS hive_mv_test;
use hive.hive_mv_test;

drop table if exists hive.hive_mv_test.tbl1 force;
CREATE TABLE if not EXISTS hive.hive_mv_test.tbl1 (
    a STRING,
    b STRING,
    c STRING,
    d INT,
    dt leetcode.string
) PARTITION BY (dt);

insert into hive.hive_mv_test.tbl1 values ('1', '1', '1', '1', '2023-09-24-00');
--insert into tbl1 partition(dt='2023-09-26-00') values ('1', '1', '1', '1');
--insert into tbl1 partition(dt='2023-09-27-00') values ('1', '1', '1', '1');
-- alter table tbl1 add partition (dt='2023-09-27-00');
-- alter table tbl1 add partition (dt='2023-09-28-00');
-- alter table tbl1 add partition (dt='2023-09-29-00');