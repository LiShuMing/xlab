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
insert into hive.hive_mv_test.tbl1 values ('1', '1', '1', '1', '20230924');

-- hive style
insert into tbl1 partition(dt='20230926') values ('1', '1', '1', '1');
insert into tbl1 partition(dt='20230927') values ('1', '1', '1', '1');

--alter table tbl1 add partition (dt='20230927');
--alter table tbl1 add partition (dt='20230928');
--alter table tbl1 add partition (dt='20230929');

drop table if exists hive.hive_mv_test.tbl2 force;
CREATE TABLE if not EXISTS hive.hive_mv_test.tbl2 (
    a STRING,
    b STRING,
    c STRING,
    d INT,
    dt date
) PARTITION BY (dt);
insert into hive.hive_mv_test.tbl2 values ('1', '1', '1', '1', '20230924');
insert into hive.hive_mv_test.tbl2 values ('1', '1', '1', '1', '20230926');

-- empty partition
-- alter table tbl2 add partition (dt='2023-09-27');