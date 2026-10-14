# DayLog 源码退役

2026-10-14：DayLog / 刻白的维护入口统一为 [Carina apps/daylog](https://github.com/LiShuMing/carina/tree/main/apps/daylog)。本批从 xlab 移除原目录全部 97 个受 Git 跟踪的文件，不保留 README、跳转文件或其他资料；因此原本只包含 DayLog 的 `swift/projects/` 和 `swift/` 命名空间也不再保留。

## 文件级核验

- xlab 退役前主线：`f3510a9d05848e02e01eb07dbf3d5b295522cabb`。
- 原迁移取源版本：`e0dbbee95730e7d1a006290169c3eac52baf7aae`；逐文件重新核验，97 个源文件内容和模式均未变化。
- Carina 已合并主线：`09c7225ea904150c5205d5bc2d540b66d8715254`，目标 `apps/daylog/` 的 97 个对应文件完整。96 个逐字节一致；仅设计 README 将开发机绝对路径泛化，转换及 SHA-256 见[机器可读清单](2026-10-14-daylog-source-retirement.json)。
- 备份分支 `backup/pre-constellation-cleanup-2026-10-14` 已重新确认仍指向 `fd15e65059ff7d0d01ed48b6347cd75881fb4b36`。

## 构建与 UI 验收边界

Carina 上述精确主线提交的 Linux 检查和 macOS 构建/测试均通过：
[Carina checks](https://github.com/LiShuMing/carina/actions/runs/38529437670)、
[DayLog macOS checks](https://github.com/LiShuMing/carina/actions/runs/38529437565)。
这是自动化构建与测试证据，不等于原生 UI 的交互验收。

原生 UI 验收未运行。所有者于 2026-10-14 明确允许删除 xlab DayLog 源码，豁免此前“完成原生 UI 验收后才退役源目录”的前置条件。该豁免不是 UI 测试通过，也不取消后续在目标仓库进行交互验收的必要性。

本批只改变 xlab 源码副本、维护入口和退役检查；没有读取、修改或删除用户本机的运行数据库、Keychain 或其他运行数据，没有修改或删除 Carina 文件。xlab 仓库导航检查不代表所有语言项目整体构建通过。

## 可见性与恢复

Carina 是私有仓库，目标链接仅对已有权限的读者可用。本记录只保存路径、哈希、状态和目标链接，不复制目标仓库新增的私有内容。原 xlab 公开源码仍在 Git 历史和备份分支中；此次删除不是历史擦除。

需要完整回滚时，对本批退役提交执行普通 `git revert`，再更新导航；不要 reset 或强制推送。仅需取回原始源码时，可从上述退役前提交恢复 `swift/projects/daylog/`：

```sh
git restore --source=f3510a9d05848e02e01eb07dbf3d5b295522cabb -- swift/projects/daylog/
```

正式恢复需另建普通提交并重新检查维护入口，不应悄悄重新建立两套活跃源码。
