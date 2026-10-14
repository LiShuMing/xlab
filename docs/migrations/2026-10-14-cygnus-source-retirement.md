# Cygnus 已迁移文档源正文退役

2026-10-14：将已完成迁移的 184 份历史文档统一归属 Cygnus，清理 xlab 中对应正文，按用户要求完整移除九个文档旧目录，不保留跳转文件。同时移除此前已经退役的六个项目旧目录及剩余 15 个文件。保留未退役资料，不改变仓库可见性。

## 验收证据

- xlab 基线：`e0dbbee95730e7d1a006290169c3eac52baf7aae`。
- Cygnus 核验版本：`f7183f6bd554ed4054e253347243c18f65b0a4f8`；该版本的知识库检查 [38491061275](https://github.com/LiShuMing/cygnus/actions/runs/38491061275) 成功。
- 逐文件重新读取两批迁移清单和目标文件：184 个源 SHA-256、184 个目标 SHA-256 均匹配。182 份正文逐字节保留；Flink SPEC 的开发机路径已泛化，附录类索引修复一处代码围栏，两项均在原迁移清单中记录。
- 已验证备份分支 `backup/pre-constellation-cleanup-2026-10-14` 仍指向 `fd15e65059ff7d0d01ed48b6347cd75881fb4b36`，本批源文件哈希与该版本迁移清单一致。
- 文件级范围、哈希、转换说明见 [机器可读清单](2026-10-14-cygnus-source-retirement.json)。这是迁移完整性验收，不是技术事实审阅；目标稿件仍为 `needs-review`。

## 范围与链接

六套书籍：ClickHouse、JDK、LLVM、DuckDB、Flink、Spark。三类研究：DataFusion、Umbra、Velox。九个原目录整体移除，维护入口统一放在根 PROJECTS.md 与 docs/README.md。Velox 尚未迁移的 reading-velox.md 原样移动到 docs/reading-open-source/velox/，不随退役目录删除。此前已退役的 liminalis、panming、optimizer-learning、cc/projects/kv-store、cc/projects/query-engine、python/projects/tech-radar 六个目录也完整移除，不再保留 README、配置或生成资料。其旧内容仍可从 Git 历史恢复。

Cygnus 为私有仓库，只有已有权限的读者能打开维护入口。公开 xlab 读者仍可从备份分支和 Git 历史访问原公开版本；这不是历史清除或隐私擦除。此批没有把 Cygnus 新增的私有正文复制回公开仓库。

## 回退与后续

可通过普通 Git revert 本批提交恢复；不要 reset 或强制推送。DayLog、其他书籍和未退役的小项目不在本批删除范围。后续源码迁移仍需独立构建、测试、数据兼容性和文件级验收，再提交对应清理 PR。
