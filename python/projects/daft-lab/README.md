# Daft 本地执行实验室

用可重复的小实验理解 Daft 的列式运算、计划优化、batch、Python UDF、状态复用和进程间搬运。
这是学习环境，耗时用于解释机制，不是 Daft / Ray Data / Spark 的性能排名。

## 运行环境

宿主机是 glibc 2.17。项目使用官方 Python 3.11 Debian Bookworm 镜像的私有 rootfs，
通过 Linux 用户、挂载和 PID 命名空间执行，不需要 Docker daemon、sudo 或替换系统库。
镜像来自 AWS ECR 的 Docker 官方镜像镜像源；`image.lock.json` 固定 manifest digest，
每个镜像层都校验 SHA-256。运行器仅限制 CPU affinity，**没有内存 cgroup 限额**。

当前运行基线是发行包 **Daft 0.7.26**，不是当前 Daft checkout 的源码编译产物。
`source-reference.json` 单独记录 `/home/admin/xwork/Daft` 的阅读参考提交。
`doctor` 与每次实验的环境记录都明确区分这两个身份，避免将参考源码误认为实际加载版本。

最小依赖由 `pyproject.toml` 和 `uv.lock` 固定，使用 HTTPS 阿里云 PyPI 镜像；
已核对所有锁定 wheel 的哈希与最初 PyPI 锁一致。未安装 Ray、Spark、GPU 框架或模型。
Python、虚拟环境、下载缓存、数据、日志和实验结果都位于被 Git 忽略的 `.local/`。

## 快速开始

以下命令在 `/home/admin/xwork/xlab/python/projects/daft-lab` 运行：

```bash
python3 bootstrap.py
./env.sh uv sync --locked
./env.sh python lab.py doctor
./env.sh python lab.py generate --rows 100000 --files 4
./env.sh python lab.py run --case all --mode evidence
./env.sh python lab.py report
```

`bootstrap.py` 默认使用本机 `/etc/pki/tls/certs/ca-bundle.crt`；其他机器用 `--ca` 指定
实际受信任的 CA bundle。不会关闭 TLS 校验。首次启动需要包源与镜像源可达、系统已有
`uv`，并允许无特权用户命名空间、mount 和 chroot。条件不满足时直接报错。

`env.sh` 在本次进程树内挂载 rootfs、项目目录、独立 `/proc` 和 512 MiB `/dev/shm`。
退出时命名空间释放，宿主机原有挂载和服务不变。默认使用允许 CPU 中的前 4 个：

```bash
DAFT_LAB_CPUS=8 ./env.sh python lab.py doctor
```

这层 rootfs 是兼容性与实验环境隔离，不是用于运行不可信代码的安全沙盒。
命名空间中的 root 映射到当前宿主用户，**不代表宿主 root 权限**。

## 学习顺序

| 实验 | 命令的 `--case` | 改变因素 | 重点观察 |
| --- | --- | --- | --- |
| 计划优化 | `plan` | 先写过滤 / 先写 UDF | `plan.txt` 中优化前后顺序、实际进入批 UDF 的行数 |
| 列式与 Python 调用 | `compute` | 内置表达式 / 行 UDF / Arrow 批 UDF | 同结果条件下的耗时、批次调用 |
| 批次大小 | `batch` | 64 / 1024 / 16384 行 | 实际批次分布、调用次数、内存 |
| 状态复用和进程边界 | `state` | 每批初始化 / 类实例复用 / 独立进程 | 初始化次数、instance ID、PID、内存 |
| UDF 错误 | `errors` | 人为抛出固定异常 | 异常是否真实传播；只有看到预期异常才通过 |

计算统一为 `y = x*x + 3*x`。输入是确定性的 `id`、`group`、`x`，
结果检查同时核对完整 ID 集合和每个对应值，不只看行数或 checksum。
状态实验用每次初始化 30 ms 的模拟成本，不代表真实模型加载或推理性能。
批 UDF 使用 PyArrow 计算，这一组不用于证明纯 Python CPU 代码的 GIL 扩展性。
类 UDF 对照刻意不设置 `max_concurrency`：在此版本中，它会选择 actor pool 进程，
即使同时传入 `use_process=False`，也不能将该变体解释为同进程线程执行。

每个变体都在新进程中执行，先单独初始化引擎，再构建和执行实验查询。
计时包含本次查询内的 UDF 初始化、执行和完整 Arrow 结果物化，不包含结果断言；
不表示模型已经常驻后的稳态吞吐。状态和进程数量由实际事件证明，不假设固定数目。

### 证据采集与计时分开

`evidence` 模式按批次和实例写事件。它可以回答“实际调用了多少次、在哪个进程执行”。
`timing` 模式关闭 UDF 事件写入；进程内存监控在两种模式中均保留。

```bash
./env.sh python lab.py run --case compute --mode timing --repeats 3
./env.sh python lab.py run --case state --mode timing --repeats 3
```

内存每 50 ms 采样，记录本进程及子进程的 PSS 和 RSS。PSS 按共享比例分摊内存，
更适合合计多进程；RSS 相加会重复计算共享页。采样可能漏掉很短的峰值。
这些实验读取已生成的本地数据，不清宿主页缓存，不将结果称为冷读性能。

### 空输入和热点数据

生成器仅替换其 manifest 中记录且哈希未改变的自有文件；修改过的文件会被保留并报错。
未登记分片与符号链接也会保留并拒绝覆盖。生成、运行实验须串行执行；当前没有并发
数据目录隔离或中断后的自动恢复。镜像锁与已安装 rootfs 的 digest 不符时拒绝继续，
保留旧环境供人工检查，不自动删除重建。
每次运行都会复制输入 manifest 和哈希，历史记录不依赖当前数据目录的状态。

```bash
./env.sh python lab.py generate --rows 0 --files 1
./env.sh python lab.py run --case all
./env.sh python lab.py generate --rows 10000 --files 4 --skew
./env.sh python lab.py run --case plan
./env.sh python lab.py generate --rows 100000 --files 4
```

`skew` 将大部分键设为 0；native 计划实验能观察过滤比例变化，不能据此证明分布式
shuffle 倾斜。生成器限制最多 1000 万行、128 个目标文件，避免无意创建过大的实验。

## 结果位置和判定

每次运行写入 `.local/runs/<UTC时间>-<随机标识>/`：

- `environment.json`：实际版本、导入路径、CPU affinity、镜像 digest、依赖锁哈希。
- `input.json`、`code.json`：输入文件与实验代码哈希。
- 每个变体的 `plan.txt`、`result.json`、`memory.json`、按 PID 分开的事件文件及外层日志。事件中的 PID 是当次容器内 PID，不能直接作为宿主进程身份。
- `summary.json`：本次运行状态；遇到失败立即停止，不继续运行后续变体。
- `report.md`：便于阅读的实验结果表。

`passed` 表示查询输出或预期错误通过了检查；优化是否发生、是否跨进程、实例是否复用，
仍需要查看对应计划和事件。未采集事件或未覆盖的观测字段为 `null`，不能读作 0。
单个变体超时 180 秒会终止其独立进程组；整个容器退出时其 PID 命名空间内的进程终止。

检查 rootfs 解包的路径边界和白化删除行为：

```bash
./env.sh python -m unittest discover -p 'test_*.py' -v
```

## 对照源码

阅读参考 checkout：`/home/admin/xwork/Daft`，完整提交见 `source-reference.json`。

| 问题 | 参考源码位置，相对 Daft checkout |
| --- | --- |
| native 入口与优化 | `daft/runners/native_runner.py` |
| 批次与算子流水线 | `src/daft-local-execution/src/pipeline.rs` |
| 数据单元 | `src/daft-micropartition/src/micropartition.rs` |
| UDF 的线程 / 进程路径 | `src/daft-local-execution/src/intermediate_ops/udf.rs` |
| 共享内存与 Arrow IPC | `daft/execution/udf.py`、`daft/execution/udf_worker.py` |

发行包与参考提交可能不同，定位实现时应先确认运行版本对应的源码。
本项目未编译、修改或安装该参考 checkout。

## 后续实验边界

当前完成 native 基础实验。单机 Ray 分区、object store、shuffle、背压时间线和
Ray Data / Spark 对照需要另行加入运行适配与结果检查；当前报告不声称覆盖这些机制。
跨节点网络成本必须使用至少两个真实节点验证，不能由本机 rootfs 或单机 Ray 推断。

所有运行都是前台短任务，无常驻服务和公开端口。回退代码不需要删除实验数据；
清理 `.local/` 前应先确认没有该项目的活动运行，并选择要保留的证据目录。
