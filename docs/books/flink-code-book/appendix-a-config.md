# 附录 A · 关键配置项速查

## TaskManager 内存

```yaml
taskmanager.memory.process.size: 1728m
taskmanager.memory.flink.size: 1280m
taskmanager.memory.task.heap.size: 512m
taskmanager.memory.managed.size: 512m
taskmanager.memory.managed.fraction: 0.4
taskmanager.memory.network.min: 64m
taskmanager.memory.network.max: 1g
taskmanager.memory.network.fraction: 0.1
taskmanager.memory.segment-size: 32kb
taskmanager.numberOfTaskSlots: 1
```

## Checkpoint & State

```yaml
execution.checkpointing.mode: EXACTLY_ONCE
execution.checkpointing.interval: 10min
execution.checkpointing.timeout: 30min
execution.checkpointing.max-concurrent-checkpoints: 1
execution.checkpointing.min-pause: 0s
execution.checkpointing.aligned-checkpoint-timeout: 0s
execution.checkpointing.unaligned.enabled: false

state.backend.type: hashmap | rocksdb
state.backend.incremental: true
state.backend.rocksdb.checkpoint.transfer.thread.num: 4
state.backend.changelog.enabled: false
state.backend.changelog.storage: memory
state.backend.changelog.periodic-materialize.interval: 10min

state.backend.local-recovery: false

state.ttl.default: never

state.checkpoints.dir: hdfs:///flink/checkpoints
state.savepoints.dir: hdfs:///flink/savepoints
```

## HA & RPC

```yaml
high-availability.type: zookeeper | kubernetes | NONE
high-availability.zookeeper.quorum: zk1:2181,zk2:2181,zk3:2181
high-availability.zookeeper.path.root: /flink
high-availability.zookeeper.session-timeout: 60000
high-availability.cluster-id: /my-flink-cluster

heartbeat.interval: 10000
heartbeat.timeout: 50000
heartbeat.rpc-failure-threshold: 2

akka.ask.timeout: 60s
akka.framesize: 10485760b
```

## Network & Backpressure

```yaml
taskmanager.network.credit-based-flow-control.buffers-per-channel: 2
taskmanager.network.credit-model.floating-buffers-per-gate: 8
taskmanager.network.credit-model.exclusive-buffers-per-channel: 0
taskmanager.network.blocking-shuffle.type: file | hybrid

taskmanager.network.compression.type: LZ4
taskmanager.network.compression.buffer-ratio: 0.5
```

## Scheduler

```yaml
jobmanager.scheduler: adaptive | adaptivebatch | default
execution.batch.adaptive.auto-parallelism.enabled: true
execution.batch.adaptive.auto-parallelism.max-parallelism: 128
execution.batch.adaptive.auto-parallelism.min-parallelism: 1
execution.batch.speculative.enabled: false
execution.batch.speculative.threshold-multiplier: 1.5
execution.batch.speculative.max-concurrent-executions: 2
```

## Event Time

```yaml
pipeline.auto-watermark-configuration.interval: 200ms
pipeline.auto-watermark-configuration.default-idleness: 0ms
```

## Metrics

```yaml
metrics.reporters: prometheus
metrics.reporter.prometheus.class: org.apache.flink.metrics.prometheus.PrometheusReporter
metrics.reporter.prometheus.port: 9249
metrics.reporter.prometheus.interval: 10s

metrics.scope.jm: <host>.jobmanager
metrics.scope.tm: <host>.taskmanager.<tm_id>
metrics.scope.task: <host>.taskmanager.<tm_id>.<job_name>.<task_name>.<subtask_index>
metrics.scope.operator: <host>.taskmanager.<tm_id>.<job_name>.<operator_name>.<subtask_index>
```

## Deployment

```yaml
jobmanager.rpc.address: localhost
jobmanager.rpc.port: 6123
jobmanager.bind-host: 0.0.0.0
rest.address: localhost
rest.port: 8081
rest.bind-address: 0.0.0.0
blob.server.port: 0
blob.fetch.retries: 5

kubernetes.cluster-id: my-flink-cluster
kubernetes.namespace: flink
kubernetes.container.image: flink:latest
kubernetes.jobmanager.service-account: flink
kubernetes.taskmanager.cpu: 1
kubernetes.taskmanager.memory: 1728m
```
