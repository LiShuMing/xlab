import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 设置生成数据的数量
num_rows = 2

# 随机生成数据
np.random.seed(42)  # 固定随机种子
data = {
    "data_hour": [f"{datetime.now() - timedelta(hours=i):%Y%m%d%H}" for i in range(num_rows)],
    "event_min": [f"{datetime.now() - timedelta(minutes=i):%Y%m%d%H%M}" for i in range(num_rows)],
    "media_id": np.random.randint(1, 100, size=num_rows),
    "dsp_id": np.random.randint(1, 50, size=num_rows),
    "target_id": np.random.randint(1, 20, size=num_rows),
    "dsp_slot_id": [f"slot_{i}" for i in range(num_rows)],
    "adx_slot_id": np.random.randint(1, 50, size=num_rows),
    "media_slot_type": np.random.randint(1, 5, size=num_rows),
    "media_slot_id": [f"media_slot_{i}" for i in range(num_rows)],
    "dsp_slot_type": np.random.randint(1, 5, size=num_rows),
    "adx_dsp_slot_id": np.random.randint(-1, 50, size=num_rows),
    "conv_type_id": [f"conv_{i}" for i in range(num_rows)],
    "sdkv": [f"sdk_{i}" for i in range(num_rows)],
    "pkg": [f"pkg_{i}" for i in range(num_rows)],
    "dsp_pkg": [f"dsp_pkg_{i}" for i in range(num_rows)],
    "platform": ["Android" if i % 2 == 0 else "iOS" for i in range(num_rows)],
    "integrate_by": np.random.randint(0, 2, size=num_rows),
    "flow_price": np.random.uniform(0.1, 1.0, size=num_rows),
    "media_category": np.random.randint(1, 10, size=num_rows),
    "media_tier": np.random.randint(1, 5, size=num_rows),
    "version": [f"v{np.random.randint(1, 10)}.0" for _ in range(num_rows)],
    "julang_task_id": [f"task_{i}" for i in range(num_rows)],
    "policy_id": np.random.randint(-1, 10, size=num_rows),
    "experiment_id": [f"exp_{i}" for i in range(num_rows)],
    "touch_amount": np.random.randint(1, 10, size=num_rows),
    "ssp_req": np.random.randint(0, 1000, size=num_rows),
    "dsp_req": np.random.randint(0, 1000, size=num_rows),
    "ssp_win": np.random.randint(0, 500, size=num_rows),
    "dsp_win": np.random.randint(0, 500, size=num_rows),
    "imp": np.random.randint(0, 500, size=num_rows),
    "clk": np.random.randint(0, 100, size=num_rows),
    "dsp_floor": np.random.uniform(0.1, 1.0, size=num_rows),
    "dsp_fill_price": np.random.uniform(0.1, 1.0, size=num_rows),
    "dsp_fee_price": np.random.uniform(0, 0.5, size=num_rows),
    "imp_dsp_bid_price": np.random.uniform(0, 1.0, size=num_rows),
    "dsp_req_timeout": np.random.randint(0, 100, size=num_rows),
    "ssp_bid_price": np.random.uniform(0.1, 1.0, size=num_rows),
    "ssp_floor": np.random.uniform(0.1, 1.0, size=num_rows),
    "dsp_win_price": np.random.uniform(0.1, 1.0, size=num_rows),
    "dsp_fill_req": np.random.randint(0, 1000, size=num_rows),
    "dsp_fill_valid": np.random.randint(0, 1000, size=num_rows),
    "used_time": np.random.randint(0, 100, size=num_rows),
    "dsp_used_time": np.random.randint(0, 100, size=num_rows),
    "revenue": np.random.uniform(0.1, 10.0, size=num_rows),
    "revenue_rebate": np.random.uniform(0.1, 5.0, size=num_rows),
    "media_revenue": np.random.uniform(0.1, 5.0, size=num_rows),
    "body_size": np.random.randint(0, 5000, size=num_rows),
    "launch": np.random.randint(0, 100, size=num_rows),
    "media_origin_revenue": np.random.uniform(0.1, 5.0, size=num_rows),
    "data_date": [(datetime.now() - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(num_rows)]
}

# 转换为 DataFrame
df = pd.DataFrame(data)

# 保存到 CSV 文件
df.to_csv("mammut_adx_slot_pkg_hi.csv", index=False, encoding="utf-8")
print("Data saved to mammut_adx_slot_pkg_hi.csv")