TinyKV 项目 Promoting 的“增强版”（更详尽，适合长期迭代）

下面这个更像你要的“详尽 promoting”：它把项目拆成 模块、阶段、技能点、工程技巧，并且约束模型每次输出你能直接编码的东西。

0) 总体工作方式（强约束）
	•	你每次只实现一个 slice：一个模块 + 一条关键不变量 + 测试 + 基准
	•	所有优化必须以 benchmark/ profile 为依据：先写 假设，再验证

1) 代码组织（强制产出）

要求模型每次都输出以下结构之一（新增模块必须给 CMake）：

tinykv/
  CMakeLists.txt
  include/tinykv/...
  src/...
  tests/...
  bench/...
  tools/...
  docs/...

建议模块边界（模型必须按此拆分，除非给出理由）：
	•	common/：Status, Result, Slice, CRC32, varint, logging
	•	memtable/：SkipList, Arena, MemTable, WriteBatch
	•	wal/：WALWriter/WALReader, record format, recovery
	•	sst/：BlockBuilder, TableBuilder, TableReader, BloomFilter
	•	lsm/：VersionSet, Manifest, CompactionPicker, DBImpl
	•	util/：Env (pwrite/pread/fsync abstraction), File, ThreadPool
	•	bench/：gbm microbench + workload runner
	•	tests/：gtest + crash tests

2) 阶段计划（模型每次必须落到可编码 task）

Phase 1：MemTable + Put/Get（正确性优先）
目标： 单线程 KV 可用
技能点：
	•	Arena 分配（减少 malloc）
	•	SkipList（更贴近 LSM）
	•	Slice/string_view 生命周期管理
	•	单元测试驱动

产出清单：
	•	MemTable::Put/Get/Delete
	•	SkipList（支持迭代器）
	•	gtest：随机对照 std::map（reference model）
	•	microbench：Put/Get 吞吐 vs std::map

Phase 2：WAL + 崩溃恢复（耐久性）
目标： 崩溃后不丢 committed writes
技能点：
	•	record framing（len + type + crc）
	•	fsync/fdatasync 成本
	•	group commit（可选）
	•	crash replay correctness

产出清单：
	•	WALWriter: Append(record)
	•	WALReader: ReadNext()
	•	Recovery: replay WAL -> MemTable
	•	crash test：写一半 kill -9 再恢复

Phase 3：Flush -> SSTable（磁盘结构）
目标： MemTable 落盘可读
技能点：
	•	block format（prefix-compression 可后置）
	•	index block / footer / checksum
	•	pread/pwrite vs mmap tradeoff

产出清单：
	•	TableBuilder + TableReader
	•	DataBlock + IndexBlock + Footer
	•	gtest：round-trip + corruption detection
	•	bench：sequential write/read, random read latency

Phase 4：VersionSet + Manifest（元数据与多文件）
目标： 多 SST 文件可管理
技能点：
	•	metadata log（manifest）
	•	atomic CURRENT switch
	•	file number allocation

Phase 5：Compaction（性能与空间）
目标： 控制读放大、空间放大
技能点：
	•	leveled compaction
	•	merging iterators
	•	tombstone处理
	•	compaction throttling

每个 Phase，模型必须输出：API + 不变量 + tests + bench + profiling checklist。

3) “项目技巧 & 编程技巧”要求（模型每次都要给）
	•	接口设计技巧： 让未来扩展不破坏 ABI（PImpl / stable API）
	•	性能技巧：
	•	hot path 减少分配（Arena、small object）
	•	分支预测友好（fast path）
	•	cache locality（连续存储、避免指针跳转）
	•	syscalls 合并（batch write）
	•	调试技巧：
	•	可复现 seed
	•	assert + invariant checking
	•	--verify mode（额外校验）
	•	工程技巧：
	•	clang-tidy/asan/ubsan/tsan
	•	CMake presets + ccache
	•	CI（可选）

⸻

你这段 TinyKV 描述，我建议补强的“关键约束”（让练手更像工业）

你给的版本很棒，但为了让它真的锻炼“系统编程肌肉”，建议补上这些“必须做”：
	1.	一致性语义：Put/Delete 的可见性（比如：单线程线性化即可）
	2.	Key Comparator：自定义 comparator（后续 prefix、user key / internal key）
	3.	InternalKey：user_key + seq + type（解决多版本/覆盖）
	4.	Tombstone 规则：delete 如何在 compaction 中清除
	5.	Iterator 合并：MemTable + SSTables 多路归并的正确性