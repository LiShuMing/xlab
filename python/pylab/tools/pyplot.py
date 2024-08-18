import matplotlib.pyplot as plt
import numpy as np

# 生成时间数据（X 轴）
time = np.linspace(0, 600, 600)  # 0 到 600 秒，生成 600 个点

# 模拟数据
ndirty = np.sin(0.01 * time) * 50000 + 50000       # 脏页数量
allocated_bytes = np.abs(np.sin(0.005 * time)) * 1e11  # 分配的字节数（高值，单位较大）
page_8192B = np.random.rand(600) * 0.5e11          # 8192B 页面脏数据
page_12288B = np.random.rand(600) * 0.1e11         # 12288B 页面脏数据

# 创建图表和轴
fig, ax1 = plt.subplots()

# 绘制 ndirty 数据（左侧 Y 轴）
ax1.set_xlabel('second')         # X 轴标签
ax1.set_ylabel('ndirty', color='tab:blue')  # 左侧 Y 轴
ax1.plot(time, ndirty, 'tab:blue', label='ndirty')
ax1.tick_params(axis='y', labelcolor='tab:blue')

# 添加右侧 Y 轴
ax2 = ax1.twinx()
ax2.set_ylabel('bytes', color='tab:red')   # 右侧 Y 轴
ax2.plot(time, allocated_bytes, 'r--', label='allocated_bytes')  # 红色虚线
ax2.plot(time, page_8192B, 'orange', label='8192B')              # 橙色线
ax2.plot(time, page_12288B, 'green', label='12288B')             # 绿色线
ax2.tick_params(axis='y', labelcolor='tab:red')

# 添加图例
fig.tight_layout()
fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.9))

# 保存和展示图表
plt.savefig('output_plot.png')
plt.show()