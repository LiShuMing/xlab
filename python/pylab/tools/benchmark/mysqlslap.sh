#!/bin/bash

set -e
set -x
# MySQL 连接信息
HOST="172.26.80.159"
PORT="9030"
USER="root"
SCHEMA="db1"

# 定义并发数和查询数的数组
concurrency_values=(1 10 20)           # 并发数
query_numbers=(30 300 600)            # 每个并发的查询数
sqls=(4 5 6 7 8 9)            # 每个并发的查询数

# 颜色打印函数（用于高亮显示）
function print_info() {
    echo -e "\e[1;32m$1\e[0m"
}

# 开始测试
print_info "开始执行 mysqlslap 循环压测脚本...\n"
# 遍历并发数和查询数
for i in "${!concurrency_values[@]}"; do
    for j in "${!sqls[@]}"; do
        concurrency=${concurrency_values[$i]}   # 当前并发数
        queries=${query_numbers[$i]}            # 当前查询数
        sql_file="sqls/${sqls[$j]}.sql"          # 当前 SQL 文件
        print_info "[Step $(($i+1))] 并发数：$concurrency | 查询数：$queries | SQL 文件：$sql_file"
        if (( j % 3 == 1 )); then
            mv_check_modes=("NOCHECK" "LOOSE" "FORCE_MV") 
            enable_mv_rewrite="set global enable_materialized_view_rewrite=true;"
            disable_mv_rewrite="set global enable_materialized_view_rewrite=false;"
            mysql -h $HOST -P $PORT -u root -e "$enable_mv_rewrite" db1
            for mode in "${mv_check_modes[@]}"; do
                print_info "当前 MV 检查模式：$mode"
                ALTER_MV="alter materialized view lineitem_days_1000_mv set('query_rewrite_consistency' = '$mode');"
                mysql -h $HOST -P $PORT -u root -e "$ALTER_MV" db1
                mysqlslap \
                    --concurrency=$concurrency \
                    --number-of-queries=$queries \
                    --query="$sql_file" \
                    -h "$HOST" -P "$PORT" -u "$USER" --create-schema="$SCHEMA"
            done
            print_info "关闭 MV 重写"
            mysql -h $HOST -P $PORT -u root -e "$disable_mv_rewrite" db1
            mysqlslap \
                    --concurrency=$concurrency \
                    --number-of-queries=$queries \
                    --query="$sql_file" \
                    -h "$HOST" -P "$PORT" -u "$USER" --create-schema="$SCHEMA"
        else
            mysqlslap \
                --concurrency=$concurrency \
                --number-of-queries=$queries \
                --query="$sql_file" \
                -h "$HOST" -P "$PORT" -u "$USER" --create-schema="$SCHEMA"
        fi
        echo "------------------------------------------"
    done
done

# 测试完成
print_info "\n所有 mysqlslap 测试执行完成！"