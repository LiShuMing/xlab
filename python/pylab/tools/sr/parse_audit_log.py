# -*- coding: utf-8 -*-

import re
import csv

# 每个 slot 对应的内存（单位：字节）
BYTES_PER_SLOT = 4 * 1024 ** 3  # 4GB

# 日志解析的正则表达式
FIELD_REGEX = re.compile(r'(\w+)=([^|]+)')

CACHE = set()

# 分析函数
def analyze_log_line(line):
    fields = dict(FIELD_REGEX.findall(line))

    try:
        plan_mem = float(fields.get("PlanMemCost", 0))
        actual_mem = int(fields.get("MemCostBytes", 0))
        slots = int(fields.get("Slots", 0))
        query_id = fields.get("QueryId", "unknown")

        # 误差计算
        if plan_mem <= 0 or actual_mem <= 0:
            return None
        if plan_mem in CACHE:
            return None
        CACHE.add(plan_mem)

        if actual_mem > 0:
            overestimate_ratio = plan_mem / actual_mem
        else:
            overestimate_ratio = float('inf')  # 防止除 0

        # 所需 slot 数（向上取整）
        estimated_slots_by_plan = -(-int(plan_mem) // BYTES_PER_SLOT)
        estimated_slots_by_actual = -(-int(actual_mem) // BYTES_PER_SLOT)

        return f"{query_id} {int(plan_mem)} {actual_mem} {slots} {round(overestimate_ratio,2)} {estimated_slots_by_plan} {estimated_slots_by_actual}"

        # return {
        #     "QueryId": query_id,
        #     "PlanMemCost(Bytes)": int(plan_mem),
        #     "MemCostBytes(Bytes)": actual_mem,
        #     "OverestimateRatio": round(overestimate_ratio, 2),
        #     "SlotsUsed": slots,
        #     "EstimatedSlotsByPlan": estimated_slots_by_plan,
        #     "EstimatedSlotsByActual": estimated_slots_by_actual,
        #     "IsSlotUsageExcessive": slots > estimated_slots_by_plan * 2  # 自定义：高出 2 倍视为过高
        # }

    except Exception as e:
        print(f"Error parsing line: {e}")
        return None

# 主程序
def process_log_file(log_file_path, output_csv_path=None):
    results = []

    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if "PlanMemCost" in line and "MemCostBytes" in line:
                result = analyze_log_line(line)
                if result:
                    results.append(result)
    for line in results:
        print(line)

    if output_csv_path:
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=results[0].keys())
            writer.writeheader()
            for row in results:
                writer.writerow(row)

    return results

# 示例用法
if __name__ == "__main__":
    log_path = "fe.audit.log"
    csv_output = "mem_analysis_results.csv"
    results = process_log_file(log_path, None)

    for r in results:
        print(r)