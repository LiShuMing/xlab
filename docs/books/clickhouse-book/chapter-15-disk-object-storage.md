# Chapter 15: DiskObjectStorage 架构 — 元数据策略与多后端支持

## 15.1 存算分离的分层抽象

ClickHouse 的存算分离通过三层抽象实现：

```
应用层:  MergeTree / ReplicatedMergeTree
           │
抽象层:  IDisk (磁盘接口)
           │
           ├── DiskLocal           → 本地磁盘
           └── DiskObjectStorage   → 对象存储抽象
                   │
                   ├── MetadataStorage (元数据策略)
                   │     ├── Local     → 本地磁盘元数据
                   │     ├── Plain     → 对象存储 Plain 布局
                   │     ├── PlainRewritable → 可重写 Plain 布局
                   │     └── Cache    → 缓存模式
                   │
                   └── ObjectStorage (数据存储后端)
                         ├── S3
                         ├── Azure Blob
                         ├── HDFS
                         ├── Local
                         ├── Cached
                         └── Web
```

> **第一性原理**：为什么需要三层抽象而非直接使用 S3 SDK？因为 ClickHouse 的存储引擎（MergeTree）是基于文件系统 API 设计的——它需要 `createFile`、`moveFile`、`removeFile`、`readFile`、`writeFile` 等操作。对象存储（S3）没有文件系统语义（没有 rename、没有目录层级、最终一致性）。`DiskObjectStorage` 将文件系统语义映射到对象存储操作，`MetadataStorage` 管理文件到对象的映射关系。这种分离让上层存储引擎完全不需要知道底层是本地磁盘还是 S3。

## 15.2 DiskObjectStorage

`src/Disks/DiskObjectStorage/DiskObjectStorage.h` — 实现 IDisk 接口，将对对象存储的操作封装为磁盘操作：

```cpp
class DiskObjectStorage : public IDisk
{
    // 元数据存储
    std::unique_ptr<IMetadataStorage> metadata_storage;

    // 对象存储后端
    std::unique_ptr<IObjectStorage> object_storage;

    // 核心操作
    void createFile(const String & path) override;
    void moveFile(const String & from, const String & to) override;
    void removeFile(const String & path) override;
    void removeRecursive(const String & path) override;

    // 读写
    std::unique_ptr<ReadBufferFromFileBase> readFile(
        const String & path, size_t buf_size) override;
    std::unique_ptr<WriteBufferFromFileBase> writeFile(
        const String & path, size_t buf_size) override;

    // 列表操作
    DiskDirectoryIteratorPtr iterateDirectory(const String & path) override;
    bool exists(const String & path) const override;
};
```

### 读取路径

```
readFile("data/all_1_1_0/user_id.bin")
  │
  ├── 1. 查询 MetadataStorage: path → object_key
  │     → metadata: user_id.bin 对应 S3 key: store_1a2b/col_3.bin
  │
  ├── 2. 检查 FileCache（如果启用）
  │     ├── 缓存命中 → 返回本地文件读取器
  │     └── 缓存未命中 → 继续
  │
  ├── 3. 创建 S3 读取器
  │     → S3ObjectStorage::readObject(key)
  │     → 创建 ReadBufferFromS3
  │
  └── 4. 包装为 CachedReadBuffer（可选）
        → 读取时异步缓存到本地
```

### 写入路径

```
writeFile("data/all_1_1_0/user_id.bin")
  │
  ├── 1. 创建 S3 写入器
  │     → S3ObjectStorage::writeObject(key)
  │     → 创建 WriteBufferFromS3 (Multipart Upload)
  │
  ├── 2. 写入数据
  │     → 数据缓存在内存中
  │     → 超过 multipart_upload_part_size (默认 10MB) 时上传一个 part
  │
  ├── 3. 完成写入
  │     → S3 CompleteMultipartUpload
  │
  └── 4. 更新元数据
        → MetadataStorage: addMapping(path, object_key, size)
```

### Move 操作

```
moveFile("tmp_merge_all_1_3_2/", "all_1_3_2/")
  │
  ├── Local 元数据模式:
  │     → 直接 rename 本地元数据目录
  │     → S3 上的对象 key 不变（path 只是元数据映射）
  │
  ├── Plain 元数据模式:
  │     → S3 CopyObject + DeleteObject（对象存储没有 rename）
  │     → 代价：大文件需要复制所有数据
  │
  └── PlainRewritable 元数据模式:
        → 只更新内存中的目录树映射
        → 不涉及 S3 操作（对象 key 不变）
```

## 15.3 MetadataStorage — 四种元数据策略

### Local：本地磁盘元数据

`src/Disks/DiskObjectStorage/MetadataStorages/Local/MetadataStorageFromDisk.h`

```
元数据存储在本地磁盘
  /metadata/path/to/file.meta
    → {object_key: "abc123", size: 1024, ...}

文件映射:
  metadata/data/all_1_1_0/user_id.bin.meta
    → object_key: store_1a2b3c/col_3.bin
    → size: 1024
    → last_modified: 2024-01-01T00:00:00Z

优点: 低延迟，强一致性
缺点: 本地磁盘是单点故障
      → 节点宕机后元数据丢失
      → 需要从其他副本恢复
```

### Plain：对象存储 Plain 布局

`src/Disks/DiskObjectStorage/MetadataStorages/Plain/MetadataStorageFromPlainObjectStorage.h`

```
元数据直接编码在对象存储路径中
  s3://bucket/path/to/file.bin

映射规则:
  文件路径 = 对象 key
  /data/all_1_1_0/user_id.bin → s3://bucket/data/all_1_1_0/user_id.bin

优点: 无需本地元数据
缺点: 不支持 rename（需要 S3 CopyObject + DeleteObject）
      不支持硬链接
```

### PlainRewritable：可重写 Plain 布局

`src/Disks/DiskObjectStorage/MetadataStorages/PlainRewritable/MetadataStorageFromPlainRewritableObjectStorage.h`

```
使用内存中的目录树 + 对象存储持久化
  支持原地重命名和删除
  InMemoryDirectoryTree → 定期序列化到对象存储

映射规则:
  内部维护一个 path → object_key 的映射表
  rename 只修改映射表，不修改 S3 对象

内存中的目录树:
  /
  ├── data/
  │     ├── all_1_1_0/
  │     │     ├── user_id.bin → store_abc/col_3.bin
  │     │     └── date.bin → store_abc/col_1.bin
  │     └── all_2_2_0/
  └── metadata/

持久化:
  定期将目录树序列化为 JSON
  存储在 S3 的特殊路径: .meta/directory_tree.json

优点: 无需本地元数据 + 支持 rename
缺点: 内存开销，启动时需要从对象存储恢复目录树
```

### Cache：缓存模式

`src/Disks/DiskObjectStorage/MetadataStorages/Cache/MetadataStorageFromCacheObjectStorage.h`

```
元数据缓存在本地，对象存储为权威来源
  本地缓存 → 按需从对象存储拉取

读取流程:
  1. 检查本地缓存
  2. 缓存命中 → 直接返回
  3. 缓存未命中 → 从对象存储列出对象 → 更新缓存 → 返回

缓存失效:
  TTL 过期后重新从对象存储获取
  显式刷新: SYSTEM DROP FILESYSTEM CACHE

优点: 低延迟 + 无单点故障
缺点: 缓存一致性复杂
      对象存储的最终一致性可能导致短暂的不一致
```

### 元数据策略选择

| 策略 | 延迟 | 一致性 | rename 支持 | 单点故障 | 适用场景 |
|------|------|--------|-------------|----------|----------|
| Local | 最低 | 强 | 支持 | 有 | ClickHouse Cloud (有副本) |
| Plain | 中 | 最终 | 不支持 | 无 | 只读场景 |
| PlainRewritable | 中 | 最终 | 支持 | 无 | 读写场景 |
| Cache | 低 | 最终 | 支持 | 无 | 混合场景 |

## 15.4 ObjectStorage — 六种数据后端

| 后端 | 文件 | 适用场景 |
|------|------|----------|
| S3 | `S3/S3ObjectStorage.h` | AWS S3 / MinIO / Ceph |
| Azure | `AzureBlobStorage/AzureObjectStorage.h` | Azure Blob Storage |
| HDFS | `HDFS/HDFSObjectStorage.h` | Hadoop HDFS |
| Local | `Local/LocalObjectStorage.h` | 本地磁盘（开发/测试） |
| Cached | `Cached/CachedObjectStorage.h` | 带缓存的装饰器 |
| Web | `Web/WebObjectStorage.h` | HTTP 只读数据源 |

### S3ObjectStorage

`src/Disks/DiskObjectStorage/ObjectStorages/S3/S3ObjectStorage.h` — 最常用的对象存储后端：

```cpp
class S3ObjectStorage : public IObjectStorage
{
    // S3 客户端（基于 AWS SDK）
    std::shared_ptr<S3::Client> client;
    String bucket;

    // 核心操作
    void copyObject(const String & from, const String & to) override;
    void removeObject(const String & path) override;
    void removeObjects(const Strings & paths) override;
    ObjectStorageIteratorPtr iterate(const String & prefix) override;

    // 多部分上传支持
    std::unique_ptr<WriteBufferFromFileBase> writeObject(
        const String & path, size_t buf_size) override;

    // 读取
    std::unique_ptr<ReadBufferFromFileBase> readObject(
        const String & path, size_t buf_size) override;
};
```

### S3 Multipart Upload

```
写入大文件时的 Multipart Upload 流程:

1. CreateMultipartUpload → 获得 upload_id
2. 循环:
   while (有更多数据):
     buffer 达到 multipart_upload_part_size (默认 10MB)
     → UploadPart(upload_id, part_number, data)
     → 记录 ETag
3. CompleteMultipartUpload(upload_id, [ETag1, ETag2, ...])
   → S3 将所有 Part 合并为一个对象

设置:
  s3_min_upload_part_size = 16MB    ← 单个 Part 最小大小
  s3_upload_part_size_multiply_factor = 2 ← Part 大小倍增因子
  s3_max_upload_part_size = 5GB     ← 单个 Part 最大大小
  s3_max_single_part_upload_size = 64MB ← 小于此值直接 PutObject
```

### S3 读取优化

```
1. Range 请求: 只读取需要的字节范围
   → 适用于列裁剪后的按需读取

2. 并行读取: 同一个对象的多个 Range 请求并行执行
   → 适用于宽列的大文件读取

3. 预取: 预测下一个读取范围，提前发起请求
   → 适用于顺序扫描

4. 连接复用: S3 客户端使用连接池
   → 减少 TLS 握手开销
```

### CachedObjectStorage

装饰器模式：为任意 ObjectStorage 添加本地文件缓存：

```
CachedObjectStorage(S3ObjectStorage)
  │
  ├── 读取:
  │     1. 检查本地缓存 (FileCache)
  │     2. 命中 → 直接返回本地文件读取器
  │     3. 未命中 → 从 S3 下载 → 写入缓存 → 返回
  │
  └── 写入:
        1. 写入 S3
        2. 异步更新缓存（或跳过缓存）
```

## 15.5 FileCache — 数据缓存

`src/Interpreters/FileCache/` — 与 CachedObjectStorage 配合的文件级缓存：

```cpp
class FileCache
{
    // 缓存结构:
    // base_path/<cache_type>/<key>/<offset>
    // key = hash(object_storage_path)
    // offset = 文件偏移量（按固定大小切块）

    // 缓存策略: SLRU (Segmented LRU)
    // - Protected segment: 被多次访问的热数据
    // - Probationary segment: 只被访问一次的数据
    // - 新数据先进入 Probationary，再次访问后提升到 Protected

    // 设置:
    // cache_base_path = /var/lib/clickhouse/cache
    // maximum_cache_size = 100GB
    // cache_policy = SLRU
};
```

### SLRU 缓存策略

```
SLRU (Segmented LRU):
  ┌─────────────────────┐  ┌─────────────────────┐
  │  Probationary (80%)  │  │  Protected (20%)     │
  │  新数据/冷数据        │  │  热数据               │
  └──────────┬──────────┘  └──────────┬──────────┘
             │                        │
  新数据 → 入 Probationary → 再次访问 → 提升到 Protected
             │                        │
             └── 淘汰 ←─── Probationary 满 ←─── 淘汰最冷数据

比 LRU 更好的原因:
  - 避免一次性扫描污染缓存（scan resistance）
  - 只被读一次的数据不会挤掉真正的热数据
```

### FileCache 动态 Resize

`src/Interpreters/FileCache/LRUFileCache.h` — 缓存支持动态调整大小：

```
动态调整:
  1. 增大: 立即生效，新空间可写入
  2. 缩小: 逐步淘汰超出新容量的缓存项
     → 不立即删除，等下次访问时检查是否超出容量
     → 避免一次性大量删除导致的 I/O 峰值

修复 (PR #102396):
  → 修复了 SLRU 动态 resize 时共享 eviction stat 导致的异常
  → 修复了降级过程中的竞争条件
```

### 缓存预热

```
场景: 新的计算节点启动时，本地缓存为空
  → 所有读取都直接命中 S3
  → 性能差

预热策略:
  1. 手动预热: SYSTEM WARMUP FILE CACHE
  2. 自动预热: 启动时扫描系统表，预热最近访问的数据
  3. 复制预热: 从其他节点的缓存列表中预热
```

## 15.6 复制层：BlobCopier / BlobKiller

`src/Disks/DiskObjectStorage/Replication/` — 对象存储上的 Blob 管理：

```
ObjectStorageRouter
  ├── BlobCopierThread  → 跨区域复制 Blob
  └── BlobKillerThread  → 回收已删除的 Blob

BlobCopierThread:
  场景: 数据需要在多个 S3 区域之间复制
  流程:
    1. 监控新写入的 Blob
    2. 使用 S3 Cross-Region Replication 或主动复制
    3. 验证目标区域数据完整性

BlobKillerThread:
  场景: Part 被 Merge 替代后，旧的 Blob 需要回收
  流程:
    1. 扫描不再被任何元数据引用的 Blob
    2. 批量删除这些 Blob
    3. 记录回收的空间
```

### 垃圾回收

```
对象存储中的垃圾 Blob:
  1. Part 被 Merge 替代 → 旧 Blob 不再被引用
  2. Mutation 重写 Part → 旧 Blob 不再被引用
  3. DROP PARTITION → 所有相关 Blob 不再被引用

回收流程:
  1. 元数据删除时标记关联的 object_key
  2. BlobKillerThread 定期扫描标记
  3. 确认无引用后删除对象
  4. 列出 S3 前缀 → 发现未被元数据引用的对象 → 删除

安全机制:
  → 不会立即删除，有延迟窗口（防止误删）
  → 使用引用计数确认安全后删除
```

## 15.7 启动与恢复

### 节点启动流程

```
1. 加载配置
   → 识别 DiskObjectStorage 类型的磁盘
   → 初始化 MetadataStorage 和 ObjectStorage

2. 恢复元数据
   ├── Local 模式: 从本地磁盘加载元数据
   ├── Plain 模式: 从对象存储列出所有对象
   ├── PlainRewritable: 从 S3 加载 directory_tree.json
   └── Cache 模式: 清空缓存，按需从 S3 恢复

3. 加载 Data Parts
   → 遍历元数据中的 Part 列表
   → 加载每个 Part 的列定义、索引等
   → 注册到 MergeTree 的 DataPartsSet

4. 启动后台任务
   → Merge、Mutation、TTL、BlobKiller

5. 开始服务查询
```

### 配置示例

```xml
<clickhouse>
    <storage_configuration>
        <disks>
            <s3_disk>
                <type>s3</type>
                <endpoint>https://s3.amazonaws.com/my-bucket/clickhouse/</endpoint>
                <access_key_id>...</access_key_id>
                <secret_access_key>...</secret_access_key>
                <metadata_path>/var/lib/clickhouse/disks/s3_disk/</metadata_path>
                <cache_enabled>true</cache_enabled>
            </s3_disk>

            <s3_cache>
                <type>cache</type>
                <disk>s3_disk</disk>
                <path>/var/lib/clickhouse/disks/s3_cache/</path>
                <max_size>100GiB</max_size>
            </s3_cache>
        </disks>

        <policies>
            <tiered>
                <volumes>
                    <hot>
                        <disk>default</disk>
                        <max_data_part_size_bytes>10GiB</max_data_part_size_bytes>
                    </hot>
                    <cold>
                        <disk>s3_cache</disk>
                    </cold>
                </volumes>
                <move_factor>0.2</move_factor>
            </tiered>
        </policies>
    </storage_configuration>
</clickhouse>
```

## 15.8 本章小结

```
DiskObjectStorage
  ├── MetadataStorage (4 种策略)
  │     ├── Local           → 本地磁盘元数据 (低延迟，有单点)
  │     ├── Plain           → 路径即元数据 (无 rename)
  │     ├── PlainRewritable → 内存目录树 + S3 持久化 (支持 rename)
  │     └── Cache           → 本地缓存 + S3 权威 (最终一致)
  │
  ├── ObjectStorage (6 种后端)
  │     ├── S3 (Multipart Upload + Range Read)
  │     ├── Azure / HDFS / Local / Web
  │     └── Cached (装饰器模式)
  │
  ├── FileCache → SLRU 本地缓存
  │     ├── Probationary (80%) → 新数据
  │     ├── Protected (20%) → 热数据
  │     └── 动态 Resize + 缓存预热
  │
  └── Replication → Blob 复制和回收
        ├── BlobCopierThread → 跨区域复制
        └── BlobKillerThread → 垃圾回收
```

**关键文件地图**：
```
src/Disks/DiskObjectStorage/DiskObjectStorage.h                         → 核心实现
src/Disks/DiskObjectStorage/MetadataStorages/Local/                     → 本地元数据
src/Disks/DiskObjectStorage/MetadataStorages/Plain/                     → Plain 布局
src/Disks/DiskObjectStorage/MetadataStorages/PlainRewritable/           → 可重写布局
src/Disks/DiskObjectStorage/MetadataStorages/Cache/                     → 缓存模式
src/Disks/DiskObjectStorage/ObjectStorages/S3/S3ObjectStorage.h         → S3 后端
src/Disks/DiskObjectStorage/ObjectStorages/Cached/CachedObjectStorage.h → 缓存装饰器
src/Interpreters/FileCache/                                             → 文件缓存
src/Disks/DiskObjectStorage/Replication/                                → Blob 复制/回收
```
