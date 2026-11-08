# Hashmap 策略性能实验

前置条件：支持 C++23 的 Clang/GCC、CMake 3.20+、Python 3.9+ 标准库。
不需要 pip、容器、服务、数据库、网络或管理员权限。当前提供单线程实验。

## 运行

从本目录执行：

```sh
# 默认编译器必须支持 C++23；必要时显式设置 CXX 或 --compiler。
CXX=clang++ python3 tools/run.py --suite quick

# 对照本机 perfect_hash；只包含本地单头文件，不调用其联网 CMake。
CXX=clang++ python3 tools/run.py --suite standard \
  --perfect-hash-root "$HOME/xwork/perfect_hash" --clean-build
```

`--compiler`、`--cxx-flags`、`--linker-flags` 可以显式指定工具链；例如 Clang 需要
libc++ 时传 `--cxx-flags=-stdlib=libc++`。特殊机器上的 GCC 工具链目录、库搜索目录
和运行库路径也通过这些参数传递，不硬编码在源码中。使用与编译器匹配的标准库。
配置失败会停止，日志位于本次结果目录，不能把缺少 perfect 的运行当成包含了该对照。

每次运行创建独立的 `.local/results/<时间>/`，依次构建、测试、绑定当前进程及其子进程到
允许使用的一个 CPU，然后以固定乱序运行实验。可以用 `--cpu N` 指定允许的 CPU。
默认增量构建；`--clean-build` 只清理所选构建目录中的编译目标，重新测整套实验台的构建成本。
`--build-dir` 可选择独立构建目录。不要让多个运行同时使用同一构建目录。

产物：

- `report.html`：自包含离线报告，带耗时柱状图、搜索、筛选、数值排序和每组原始样本。
- `samples.csv`、`summary.json`：实际样本与中位数、范围、std 基线差值。
- `manifest.json`：编译命令、实际编译参数、源码/输入/二进制摘要、perfect 版本、CPU 与测试状态。
- `progress.json`、`events.jsonl`：阶段、已完成项数、最近实验；失败不会记录为完成。
- `configure.log`、`build.log`、`tests.log`：独立证据；可选 GNU time 记录构建峰值内存。

打开程序最终打印的 `REPORT=.../report.html` 即可观察本次结果。页面无需 HTTP 服务。
报告支持关闭 JavaScript 后阅读完整表格和折叠证据。运行数据与编译产物忽略提交。
仅更新展示时可执行 `python3 tools/report.py <结果目录>`，但它会拒绝覆盖已有报告；先保留旧报告。

## 实验契约

| 实现 | 范围 | 哈希与存储 |
| --- | --- | --- |
| std | 查找、构建、动态增删 | `std::unordered_map` + 计数分配器 |
| linear | 查找、构建、动态增删 | 连续槽位、线性探测、删除标记、阈值扩容及删除标记整理 |
| sorted | 固定键查找 | 连续数组排序、二分查找 |
| perfect | 编译期固定字符串集合查找 | 本地 perfect_hash，255 键以内 classic，256 起 wide |
| wide | short8/short64 的固定键查找 | 强制 wide，与 classic 使用同一键集合和值类型 |

std 和 linear 共用字符串 FNV-1a + 整数混合函数；整数键直接使用该混合函数。
这是两种冲突处理方式的控制变量比较。perfect 使用自己的哈希与键检查，属于完整实现对照。
所有值统一为 `uint32_t`。字符串用非持有型 `string_view`，建表键的存储由实验台持有。
查询字符在另一个稳定地址中复制，不能靠相同字符串地址走捷径。

固定数据由 `tools/generate_cases.py` 以固定种子生成，提供 8、64、255、256、1024 个短键，
以及 64 个 48 字节、共同前缀的键。查询轨迹有 0%、50%、100% 命中，均匀和热点两种分布：
热点时 90% 的索引抽样来自前 8 个键。未命中字符串保持长度与前缀，仅替换尾字节。
这是一类有意设计的近似键负载，不代表所有真实业务字符串分布。
动态数据包含整数键和字符串键。标准矩阵包含 4096、65536 个整数键及 4096 个字符串键。
占用率扫描固定线性表为 8192 槽，改变整数键数，使实际占用约为 50%、75%、85%、90%。
不能只改变目标阈值：小表的容量取整可能让不同阈值落到相同实际占用率。
更大规模可以直接调用二进制的 `--case uint64 --n 1048576`，并按目标机器的缓存容量解释结果。

每次查询轨迹包含 16384 项。显式 Fisher-Yates 洗牌保持不同标准库之间输入一致；同一对照中的
每个种子必须具有相同轨迹摘要，否则运行停止。标准矩阵使用 3 个种子、5 次重复、每个样本
至少 20ms；quick 使用 1 个种子、3 次重复、至少 10ms。竞争实现以固定乱序交错运行。

四种阶段：

- `lookup`：预热后独立查询吞吐，包含结果累加；批量总时间 / 总查询数。
- `build-reserved`：预留容量、逐键插入、销毁的完整周期，按每个插入键计费。
- `build-growing`：从空表扩容、插入、销毁的完整周期，按每个插入键计费。
- `churn`：随机选已有键，删除、插入替代键、删除替代键、恢复原键；四次操作后回到相同逻辑状态。
  它测成对替换，不覆盖所有长期增删历史。

编译期表没有运行期建表、动态增删成绩，明确不参与这些阶段。perfect 的常量求值发生在
编译中，不能据此认为总构建成本为零。报告记录整套实验台构建耗时、峰值 RSS、二进制节区，
尚未隔离各个数据集合的编译成本。classic 与 wide 的同集合对照只在 short8、short64 提供。

## 正确性、计时与诊断分开

`ctest` 包含 80 万次随机操作与标准库逐步核对、碰撞及环绕、删除标记、重复更新、零值、
空字符串、内嵌 NUL、查询地址分离、命中率、轨迹复现与报告工具测试。
每个工作进程在计时前额外核对所有键、所有未命中键与所有查询。
查找计时后的累加校验和必须与预期一致；动态阶段之后再次核对完整表。
构建样本消费末键和表大小，完整插入语义另由正确性检查验证。

线性表的平均/最大探测次数、键比较次数在计时结束后单独诊断，不在查找循环内插桩。
最大探测次数针对查询轨迹，不是所有可能键的上界。其它实现没有这个统计时显示未采集。

表存储口径：std 的存活分配请求字节 + 对象大小；linear/sorted 的数组容量字节 + 对象大小；
perfect 的 `sizeof(table)`。键载荷单列。它们不含分配器元数据、查询轨迹或共享字面量，
不是物理驻留内存的精确对照。std 桶数、linear 槽数和 perfect 槽数分别展示，不能把相同
目标负载率理解成相同实际占用率或内存预算。

最小值到最大值的范围是批量样本波动，不是操作 P99，也不是统计置信区间。
共享机器上的 CPU 频率、缓存、调度干扰仍可能影响结果；绑定 CPU 不代表独占 CPU。
本实验不自动调用 sudo、修改系统设置或采集硬件计数器。

## 手工验证与继续迭代

```sh
cmake -S . -B .local/build -DCMAKE_BUILD_TYPE=Release
cmake --build .local/build --parallel 2
ctest --test-dir .local/build --output-on-failure

# 地址与未定义行为检查使用独立构建；不要拿此构建跑性能。
cmake -S . -B .local/sanitize -DCMAKE_BUILD_TYPE=Debug -DHASHMAP_SANITIZE=ON
cmake --build .local/sanitize --parallel 2
ctest --test-dir .local/sanitize --output-on-failure

.local/build/hashmap_bench --method linear --case uint64 --n 65536 \
  --mode lookup --hit 50 --distribution uniform --load 0.85 --seed 42
```

每次迭代只改一个策略因素，使用同一 case 配置、编译器、CPU 和输入摘要，保留独立结果目录。
先检查正确性，再比较同场景耗时和存储，最后用独立诊断解释观察。
源码快照与二进制摘要可用于确认成绩对应哪个版本；旧成绩不能当成新源码的测量。

下一阶段再加入 Robin Hood 搬移、向后移位删除、指纹元数据和 SIMD 分组探测。
这些策略尚未实现；首版保留三条可审计主线：标准库、线性探测与 perfect hash，另有排序数组参照。

报告样式与交互复用了 html-report-design 的离线主题，资源均保存在本实验 `assets/` 下，
运行和生成报告不依赖技能目录。
