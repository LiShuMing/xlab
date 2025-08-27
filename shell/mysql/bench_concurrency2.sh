#/bin/bash
mysql --user=root  --skip-password  --host=172.26.80.41 --port=9030  -D test -e "alter warehouse default_warehouse set('enable_query_queue' = 'true');"
mysql --user=root  --skip-password  --host=172.26.80.41 --port=9030  -D test -e "ADMIN SET FRONTEND CONFIG('max_query_queue_history_slots_number' = '200');"
mysql --user=root  --skip-password  --host=172.26.80.41 --port=9030  -D test -e "ADMIN SET FRONTEND CONFIG('enable_plan_feature_collection' = 'true');"

mysql --user=root  --skip-password  --host=172.26.80.41 --port=9030  -D test -e "ADMIN SET FRONTEND CONFIG('enable_query_cost_prediction' = 'true');"

for i in `seq 1 3`;
do
python3 -u /home/disk1/lishuming/work/test_tool/sql-bench/run.py --concurrency=22 \
    --sql_dir="/home/disk1/lishuming/work/test_tool/sql-bench/tpch" \
    --host="172.26.80.41" \
    --db="hive_catalog.tpch_100g_orc_lz4" \
    --start_query_id=0 \
    --ssh_endpoint='sr@172.26.80.42'
done
