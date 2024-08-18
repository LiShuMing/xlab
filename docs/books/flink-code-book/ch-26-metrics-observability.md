# 第 26 章 · Metrics、REST API 与可观测性

## 导读

- **一句话**：本章从指标采集、外部推送、REST 暴露到历史归档，逐层拆解 Flink 的可观测性体系——让你知道每一个监控数字从哪里来、到哪里去。
- **前置知识**：第 1 章架构总览、Metrics 基本概念（Counter / Gauge / Histogram / Meter）。
- **读完本章你能回答**：
  - Flink Metrics 的四层 Scope 各解决什么运维问题
  - 一个 Counter 从算子注册到 Prometheus `/metrics` 端点经过了哪些环节
  - Web UI 的指标数据为什么不是直接从 TaskManager 读的
  - HistoryServer 如何让已结束的 Job 依然可查

---

## 26.1 — 设计动机

### 为什么这样设计：四层 Scope 而不是一层

Flink 将 Metric 作用域分成四层——System / TaskManager / Job / Operator——对应三种不同运维角色：

| Scope 层级 | 默认格式 | 运维角色 | 典型场景 |
|-----------|---------|---------|---------|
| System（JM/TM 进程级） | `<host>.jobmanager` / `<host>.taskmanager.<tm_id>` | 基础设施 SRE | JVM OOM、GC 停顿 |
| TaskManager | 同上，聚焦 TM 维度 | 平台运维 | 网络缓冲区耗尽、Slot 利用率 |
| Job | `<host>.taskmanager.<tm_id>.<job_name>` | 作业 Owner | Checkpoint 超时、重启次数 |
| Operator | `<host>.taskmanager.<tm_id>.<job_name>.<operator_name>.<subtask_index>` | 作业调优 | 反压定位、数据倾斜、Watermark 延迟 |

**解决的问题**：不同粒度对应不同告警阈值和存储成本。基础设施团队只关心进程级指标，不需要算子的 `numRecordsIn`；作业调优者需要算子粒度，但不能承受全局所有算子指标的高基数存储。**放弃的替代方案**是统一全量采集后由下游过滤——这在 Prometheus 场景下直接导致存储膨胀（见 26.5）。

配置入口在 `MetricOptions` 中：`metrics.scope.jm`、`metrics.scope.tm`、`metrics.scope.task`、`metrics.scope.operator`。`ScopeFormats` 在构造时将 7 种 format 字符串解析为对应的 `ScopeFormat` 子类，形成从 JobManager 到 Operator 的树：

```
JobManagerScopeFormat → JobManagerJobScopeFormat → JobManagerOperatorScopeFormat
TaskManagerScopeFormat → TaskManagerJobScopeFormat → TaskScopeFormat → OperatorScopeFormat
```

`<org.apache.flink.runtime.metrics.scope.ScopeFormats:L#38>`

---

## 26.2 — 核心数据结构

### 26.2.1 Metric 接口层次

```
Metric (org.apache.flink.metrics.Metric)
 ├─ Counter        — inc() / dec() / getCount()       <org.apache.flink.metrics.Counter:L#25>
 ├─ Gauge<T>       — getValue()                       <org.apache.flink.metrics.Gauge:L#25>
 ├─ Meter          — markEvent() / getRate() / getCount()  <org.apache.flink.metrics.Meter:L#25>
 └─ Histogram      — update(long) / getCount() / getStatistics()  <org.apache.flink.metrics.Histogram:L#30>
```

- **Counter**：单调递增计数。`SimpleCounter` 非线程安全（单线程算子），`ThreadSafeSimpleCounter` 提供线程安全版本。
- **Gauge**：瞬时值。典型如 `currentInputWatermark`。
- **Meter**：速率度量。`MeterView` 内置实现，基于 Counter + 滑动窗口计算每秒事件数，同时实现 `View` 接口由后台线程定期更新。`<org.apache.flink.metrics.MeterView:L#39>`
- **Histogram**：分布统计。Flink 不自带实现，需引入 Dropwizard 或 DataSketches。

`OperatorIOMetricGroup` 定义了算子级 IO 核心指标（`<org.apache.flink.metrics.groups.OperatorIOMetricGroup:L#30>`）：`numRecordsIn/Out` + `numBytesIn/Out`，每个 Counter 同时驱动一个 `MeterView` 暴露 `PerSecond` 速率。

### 26.2.2 MetricGroup 的树状注册结构

```
JobManagerMetricGroup → JobManagerJobMetricGroup → JobManagerOperatorMetricGroup
TaskManagerMetricGroup → TaskManagerJobMetricGroup → TaskMetricGroup
  ├─ TaskIOMetricGroup (numRecordsIn/Out, backPressuredTime, idleTime...)
  └─ InternalOperatorMetricGroup → OperatorIOMetricGroup
```

`AbstractMetricGroup` 核心字段（`<org.apache.flink.runtime.metrics.groups.AbstractMetricGroup:L#74-92>`）：

```java
protected final A parent;                              // 父 Group
protected volatile Map<String, String>[] variables;    // 每个 Reporter 一份缓存
private final Map<String, Metric> metrics;             // 本 Group 直接包含的 Metric
private final Map<String, AbstractMetricGroup<?>> groups; // 子 Group
private final String[] scopeComponents;                // ["host-7", "taskmanager-2", ...]
```

**为什么 `variables` 是数组？** 每个 Reporter 可配置不同的 `excludedVariables`（通过 `metrics.reporter.<name>.scope.variables.excludes`），位置 0 存通用缓存，1..N 存对应 Reporter 的缓存。

注册一个 Counter：`counter("myCounter")` → `addMetric()` → `metrics.put()` + `registry.register()` `<L#391-459>`

### 26.2.3 MetricRegistry、Reporter 加载与 SPI

`MetricRegistryImpl` 是中枢（`<org.apache.flink.runtime.metrics.MetricRegistryImpl:L#552-586>`）：

```
MetricGroup.addMetric() → MetricRegistryImpl.register()
  → forAllReporters(MetricReporter::notifyOfAddedMetric)  // 通知所有 Reporter
  → queryService.addMetric()                               // 通知 MetricQueryService
  → viewUpdater.notifyOfAddedView()                        // View 定期更新
```

Reporter 加载采用 **SPI 机制**（`<org.apache.flink.runtime.metrics.ReporterSetupBuilder:L#391-405>`）：

1. 用户配置 `metrics.reporters: prometheus`，指定 `metrics.reporter.prometheus.factory.class`
2. `ReporterSetupBuilder` 通过 `ServiceLoader.load(MetricReporterFactory.class)` 扫描 classpath，同时通过 `PluginManager` 加载 `plugins/` 目录
3. 找到 `PrometheusReporterFactory` 后调用 `createMetricReporter(properties)` 实例化
4. 若 Reporter 实现 `Scheduled` 接口，Registry 用 `ScheduledExecutorService` 定期调用 `report()`

SPI 声明文件：`META-INF/services/org.apache.flink.metrics.reporter.MetricReporterFactory`

**为什么用 SPI 而非硬编码工厂？** 解耦——Reporter JAR 可作为 plugin 热加载，第三方 Reporter（Datadog、OTel）可独立发布。

Reporter 接口层次：`Reporter`（`open/close`）← `MetricReporter`（`notifyOfAddedMetric/notifyOfRemovedMetric`）← 可选 `Scheduled`（`report`）。Prometheus Reporter 不实现 `Scheduled`（Pull 模式），InfluxDB/Datadog 等推送型实现 `Scheduled`。

---

## 26.3 — 关键流程走读

### 26.3.1 Metric 注册全流程

从用户代码到 Prometheus 端点：

```
① 算子代码: getRuntimeContext().getMetricGroup().counter("numRecordsIn")
② AbstractMetricGroup.counter() → addMetric() → metrics.put() + registry.register()
③ MetricRegistryImpl.register() → forAllReporters(notifyOfAddedMetric) + queryService.addMetric()
④ AbstractPrometheusReporter.notifyOfAddedMetric()
   → 提取 dimensionKeys/Values，创建 Collector，register(CollectorRegistry)
⑤ Prometheus HTTPServer 处理 scrape → registry.metricFamilySamples() → 文本输出
⑥ Prometheus Server 抓取 /metrics
```

`<org.apache.flink.metrics.prometheus.AbstractPrometheusReporter:L#109-159>`

关键映射：Counter/Meter → `io.prometheus.client.Gauge`，Histogram → `HistogramSummaryProxy`（Summary 含分位数）。指标名转换：`flink_` 前缀 + scope 用 `_` 连接 + 非法字符替换为 `_`。`<L#161-166>`

### 26.3.2 REST API 端点与典型用法

`WebMonitorEndpoint.initializeHandlers()` 注册所有 Handler（`<org.apache.flink.runtime.webmonitor.WebMonitorEndpoint:L#316-580>`）：

| 端点 | 方法 | 用途 |
|------|------|------|
| `/jobs` | GET | Job 列表 |
| `/jobs/:jobid` | GET | Job 详情 |
| `/jobs/:jobid/checkpoints` | GET | Checkpoint 统计 |
| `/jobs/:jobid/vertices/:vid/backpressure` | GET | 反压比例 |
| `/jobs/:jobid/metrics` | GET | Job 级指标 |
| `/jobs/:jobid/vertices/:vid/metrics` | GET | 算子级指标 |
| `/jobs/:jobid/savepoints` | POST | 触发 Savepoint |
| `/taskmanagers` | GET | TM 列表 |
| `/taskmanagers/:tmid/metrics` | GET | TM 级指标 |
| `/jobmanager/metrics` | GET | JM 级指标 |

典型用法：`curl http://jm:8081/jobs/<jobid>/metrics?get=numRecordsIn,numRecordsOut`

### 26.3.3 Web UI 数据来源走读

Web UI 不直接连 TM，而是经过 `MetricFetcherImpl` 缓存层：

```
浏览器 → REST Handler → MetricStore（缓存）→ MetricFetcherImpl.update()
  → 获取所有 TM 的 MetricQueryServiceGateway 地址
  → RPC queryMetrics() → MetricDumpSerializer 序列化 → 反序列化写入 MetricStore
```

**为什么这样设计？** 直接逐个 RPC 调 TM 会导致请求放大（1 REST → N RPC）。`MetricFetcherImpl` 维护 `MetricStore` 缓存，按 `updateInterval`（默认 5s）定期刷新，REST Handler 读缓存即可。

`<org.apache.flink.runtime.rest.handler.legacy.metrics.MetricFetcherImpl:L#61-78>`

### 26.3.4 HistoryServer 归档与扫描

Job 结束时，Dispatcher 调用 `HistoryServerArchivist.archiveExecutionGraph()` → `FsJsonArchivist.writeArchivedJsons()` 写入归档目录（`<org.apache.flink.runtime.history.FsJsonArchivist:L#62-80>`）。

HistoryServer 端：`HistoryServerArchiveFetcher` 定时扫描 `historyserver.archive.dirs`（默认 10s），对比本地缓存识别新增/删除，将 JSON 展开为 REST API 风格目录结构，提供只读端点（`/config`、`/joboverview`、`/jobs/:jobid/*`）。

**为什么归档用文件而非数据库？** 简化部署——只需一个文件目录（支持 HDFS/S3），无需数据库依赖。缺点是大量历史 Job 时扫描性能有限。

`<org.apache.flink.runtime.webmonitor.history.HistoryServerArchiveFetcher:L#63-100>`

### 26.3.5 关键系统指标清单

| 指标 | Scope | 类型 | 用途 |
|------|-------|------|------|
| `Status.JVM.Memory.Heap.Used` | JM/TM | Gauge | 堆内存，OOM 预警 |
| `Status.JVM.GarbageCollector.*.Time` | JM/TM | Gauge | GC 累计耗时 |
| `Status.Network.AvailableMemorySegments` | TM | Gauge | 网络缓冲区可用数 |
| `numRecordsIn/Out` | Operator | Counter | 算子吞吐量 |
| `numRecordsInPerSecond/OutPerSecond` | Operator | Meter | 算子吞吐速率 |
| `currentInputWatermark` | Operator | Gauge | Watermark 进度 |
| `lastCheckpointDuration` | Job | Gauge | 最近 Checkpoint 耗时 |
| `backPressuredTimeMsPerSecond` | Task | Gauge | 反压占比 |
| `busyTimeMsPerSecond` / `idleTimeMsPerSecond` | Task | Gauge | 繁忙/空闲占比 |
| `numBytesIn/Out` | Task | Counter | 网络 IO 字节数 |
| `fullRestarts` | Job | Counter | 作业重启次数 |

系统指标在 `TaskIOMetricGroup` 中自动注册（`<org.apache.flink.runtime.metrics.groups.TaskIOMetricGroup:L#90-117>`），用户无需手动操作。

---

## 26.4 — 横向对比（Spark / StarRocks / MaxCompute）

### vs Spark Metrics System

| 维度 | Flink | Spark |
|------|-------|-------|
| 指标层级 | 4 层 Scope（JM/TM/Job/Operator），树状 MetricGroup | 2 层（Application/Executor），`MetricsSystem` + `Source`/`Sink` |
| 注册方式 | `getRuntimeContext().getMetricGroup().counter()` | `MetricsSystem.registerSource()`，自定义需实现 `Source` |
| Prometheus | 内置 `PrometheusReporter`，每 TM 独立端口 | 需 `spark-metrics` + Prometheus Sink 或 JMX Exporter |
| 自定义 | `MetricReporter` + `MetricReporterFactory` + SPI | `Sink` 接口 + `metrics.properties` |

核心差异：Flink 的 MetricGroup 是结构化树，天然支持 per-Reporter 变量过滤；Spark 的命名是扁平字符串拼接。

### vs StarRocks Monitor

| 维度 | Flink | StarRocks |
|------|-------|-----------|
| 架构 | JM + 多 TM | FE + 多 BE |
| 指标粒度 | 算子级（per subtask） | BE 节点级 + Query 级 |
| Prometheus | 每 TM 一个端口 | BE/FE 各一个端口 |
| 告警 | 依赖外部 Reporter | FE 内置告警引擎 |

核心差异：StarRocks 指标偏存储引擎（Compaction、IO 吞吐），Flink 偏流计算语义（Watermark、反压、Checkpoint），由引擎类型决定。

---

## 26.5 — 调优与实战陷阱

### 26.5.1 高基数 Metric 导致 Prometheus 存储膨胀

100 并行 × 10 算子 × 5 指标 = 5000 条 time series，多作业集群轻松突破百万。

对策：(1) 配置 `metrics.scope.operator` 去掉 `<tm_id>`；(2) 用 `metrics.reporter.prometheus.filter.includes` 只暴露关键指标；(3) Prometheus 端 `metric_relabel_configs` 丢弃不需要的 series；(4) 考虑 OTel Reporter + VictoriaMetrics 等高基数后端。

### 26.5.2 REST API 频繁轮询导致 JobManager 压力

高频轮询 `/jobs/:id/metrics` 使 `MetricFetcherImpl` 对所有 TM 发起 RPC。

对策：(1) 增大 `web.refresh-interval`（5s → 30s）；(2) 调大 `metrics.internal.query-service.message-size-limit`；(3) 直接用 Prometheus Reporter 抓取 TM 指标，绕过 JM；(4) 启用 `rest.cache.enabled`。

### 26.5.3 MetricReporter 的延迟和可靠性

推送型 Reporter（InfluxDB/Datadog）后端不可达时，`Scheduled.report()` 阻塞导致 `ReporterTask` 延迟（`<org.apache.flink.runtime.metrics.MetricRegistryImpl:L#717-733>`）。

对策：(1) 确保 `report()` 非阻塞（异步 HTTP 或 buffer）；(2) `metrics.reporter.<name>.interval` 不要设太小（默认 10s）；(3) 考虑 Prometheus Pull 模式替代 Push。

### 26.5.4 HistoryServer 归档目录配置

本地路径 JM 重启后丢失；HDFS/S3 大目录扫描慢。

对策：(1) 生产必须用 HDFS/S3/OSS；(2) `historyserver.archive.clean-expired-jobs: true` + `historyserver.retained-jobs` 限制数量；(3) 增大 `historyserver.archive.refresh-interval`；(4) 独立部署，不与 JM 混合。

```yaml
jobmanager.archive.fs.dir: hdfs:///flink/completed-jobs/
historyserver.archive.dirs: hdfs:///flink/completed-jobs/
historyserver.archive.refresh-interval: 30s
historyserver.web.port: 8082
historyserver.retained-jobs: 1000
```

### 26.5.5 常见配置陷阱速查

| 陷阱 | 现象 | 修正 |
|------|------|------|
| TM 端口冲突 | Reporter 启动失败 | `portRange: 9249-9259` |
| scope 太长 | Prometheus 指标名被截断 | 简化 `metrics.scope.operator` |
| 未配 Reporter | Web UI 有指标但 Prometheus 无数据 | 检查 `metrics.reporters` 和 `factory.class` |
| 反压指标为空 | BackPressure 页面 N/A | 检查 `web.backpressure.refresh-interval` |
| HistoryServer 空白 | 已结束 Job 不可查 | 检查 archive.dir 与 archive.dirs 一致 |

---

## 本章要点回顾

1. **四层 Scope**（JM/TM/Job/Operator）对应不同运维角色，`<tm_id>` 等高基数字段是 Prometheus 存储膨胀的根源。
2. **Metric 接口层次**（Counter/Gauge/Meter/Histogram）在 `AbstractMetricGroup` 中注册，经 `MetricRegistryImpl` 分发给 Reporter 和 MetricQueryService。
3. **Reporter 加载**采用 SPI（`ServiceLoader` + `PluginManager`），可实现 `Scheduled` 接口由 Registry 定期调度。
4. **Prometheus Reporter** 将 Counter/Meter 映射为 Gauge，Histogram 映射为 Summary，每 TM 暴露独立 HTTP 端口。
5. **REST API** 通过 `MetricFetcherImpl` 从 TM 的 `MetricQueryService` RPC 拉取指标，缓存在 `MetricStore` 中供 Handler 读取。
6. **HistoryServer** 定时扫描归档目录，将已结束 Job 的 ExecutionGraph JSON 展开到本地，提供只读 REST API。

## 源码导航

| 组件 | 路径 |
|------|------|
| Metric 接口（Counter/Gauge/Meter/Histogram） | `flink-metrics/flink-metrics-core/src/main/java/org/apache/flink/metrics/` |
| MetricGroup / OperatorMetricGroup / OperatorIOMetricGroup | `flink-metrics/flink-metrics-core/src/main/java/org/apache/flink/metrics/groups/` |
| MetricReporter / MetricReporterFactory / Scheduled | `flink-metrics/flink-metrics-core/src/main/java/org/apache/flink/metrics/reporter/` |
| AbstractMetricGroup（树状注册核心） | `flink-runtime/.../metrics/groups/AbstractMetricGroup.java` |
| TaskIOMetricGroup（系统指标注册） | `flink-runtime/.../metrics/groups/TaskIOMetricGroup.java` |
| MetricRegistryImpl（中枢分发） | `flink-runtime/.../metrics/MetricRegistryImpl.java` |
| ReporterSetupBuilder（SPI 加载） | `flink-runtime/.../metrics/ReporterSetupBuilder.java` |
| ScopeFormats（Scope 格式定义） | `flink-runtime/.../metrics/scope/ScopeFormats.java` |
| MetricOptions（配置项） | `flink-core/.../configuration/MetricOptions.java` |
| Prometheus Reporter | `flink-metrics/flink-metrics-prometheus/src/main/java/org/apache/flink/metrics/prometheus/` |
| MetricQueryService（RPC 查询服务） | `flink-runtime/.../metrics/dump/MetricQueryService.java` |
| MetricFetcherImpl（Web UI 数据来源） | `flink-runtime/.../rest/handler/legacy/metrics/MetricFetcherImpl.java` |
| WebMonitorEndpoint（REST Handler 注册） | `flink-runtime/.../webmonitor/WebMonitorEndpoint.java` |
| HistoryServer | `flink-runtime-web/.../webmonitor/history/HistoryServer.java` |
| HistoryServerArchiveFetcher（归档扫描） | `flink-runtime-web/.../webmonitor/history/HistoryServerArchiveFetcher.java` |
| HistoryServerArchivist（归档写入接口） | `flink-runtime/.../dispatcher/HistoryServerArchivist.java` |
| FsJsonArchivist（JSON 文件读写） | `flink-runtime/.../history/FsJsonArchivist.java` |
