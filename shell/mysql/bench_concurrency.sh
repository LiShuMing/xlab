#!/bin/bash
set -x


HOST="172.26.80.41"
PORT=9030
USER="root"
PASSWORD_OPTION="--skip-password"
SCHEMA="hive_catalog.tpch_100g_orc_lz4"
QUERY="select count(1) from region;"
ITERATIONS=5
QUERIES=1000

# 控制并发度
CONCURRENCIES=(4 8 16 32 64 128 256)
# 封装函数
run_mysqlslap() {
  local concurrency=$1
  echo "Running test with concurrency = $concurrency"

  mysqlslap --user=$USER --host=$HOST --port=$PORT $PASSWORD_OPTION \
    --concurrency=$concurrency --iterations=$ITERATIONS \
    --query="${QUERY}" --create-schema=$SCHEMA \
    --number-of-queries=$QUERIES

  echo "done..."
}

# 关闭 query queue
mysql --user=$USER $PASSWORD_OPTION --host=$HOST --port=$PORT -D test \
  -e "alter warehouse default_warehouse set('enable_query_queue' = 'false');"


for c in "${CONCURRENCIES[@]}"; do
  run_mysqlslap "$c"
done

# 关闭 query queue
mysql --user=$USER $PASSWORD_OPTION --host=$HOST --port=$PORT -D test \
  -e "alter warehouse default_warehouse set('enable_query_queue' = 'true');"

for c in "${CONCURRENCIES[@]}"; do
  run_mysqlslap "$c"
done


