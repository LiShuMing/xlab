#/bin/bash
mysql --user=root  --skip-password  --host=172.26.92.227 --port=9131 -D test -e "alter warehouse default_warehouse set('enable_query_queue' = 'true');"

python3 -u /home/disk1/lishuming/work/test_tool/sql-bench/run.py --concurrency=22 \
    --sql_dir="/home/disk1/lishuming/work/test_tool/sql-bench/tpch" \
    --host="172.26.92.227" \
    --port="9131" \
    --db="hive_catalog.tpch_1g_orc" \
    --start_query_id=0 \
    --ssh_endpoint='sr@172.26.92.227'
