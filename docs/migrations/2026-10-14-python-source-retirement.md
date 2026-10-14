# Python 源码退役记录

本次仅移除六个已完成迁移并合入目标 main 的 Python 源码目录，共 282 个跟踪文件，不保留占位 README 或旧目录。目标与路径如下。

| 原 xlab 路径 | 当前维护位置 |
| --- | --- |
| `python/projects/py-cli/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-tools/` | [lyra/modules/developer-tools](https://github.com/LiShuMing/lyra/tree/main/modules/developer-tools) |
| `python/projects/py-optimizer1/` | [vela/research/optimizer-evidence](https://github.com/LiShuMing/vela/tree/main/research/optimizer-evidence) |
| `python/projects/py-optimizer2/` | [vela/research/optimizer-scanner](https://github.com/LiShuMing/vela/tree/main/research/optimizer-scanner) |
| `python/projects/py-pia/` | [carina/modules/product-intelligence](https://github.com/LiShuMing/carina/tree/main/modules/product-intelligence) |
| `python/projects/py-report/` | [carina/modules/research-report](https://github.com/LiShuMing/carina/tree/main/modules/research-report) |

## 验证与边界

源快照：`fe977671e60ea46a7d6805402b4b51c3cc023dfd`。每个源 Git blob 与目标迁移 manifest 对应；复制、适配、明确排除三类均逐项核对。适配后的目标内容与已审查工作树、目标 main blob 一致，不以原始源文件字节相等替代迁移验证。详细哈希与处置见 [机器可读记录](2026-10-14-python-source-retirement.json)。

- lyra: [`d8cb18b2a306dfc28d11a6c2de0fea8a6ee3e3bb`](https://github.com/LiShuMing/lyra/commit/d8cb18b2a306dfc28d11a6c2de0fea8a6ee3e3bb)；合并后检查全部成功。 [CI 38552150382](https://github.com/LiShuMing/lyra/actions/runs/38552150382)
- vela: [`824cf61812e66a5eb91a14776bcb73e8eefc04a7`](https://github.com/LiShuMing/vela/commit/824cf61812e66a5eb91a14776bcb73e8eefc04a7)；合并后检查全部成功。 [CI 38552201086](https://github.com/LiShuMing/vela/actions/runs/38552201086)
- carina: [`76ac13d9049969f5fbff3e363654d0f5d676e0d1`](https://github.com/LiShuMing/carina/commit/76ac13d9049969f5fbff3e363654d0f5d676e0d1)；合并后检查全部成功。 [CI 38553413380](https://github.com/LiShuMing/carina/actions/runs/38553413380) [CI 38553413383](https://github.com/LiShuMing/carina/actions/runs/38553413383) [CI 38553413390](https://github.com/LiShuMing/carina/actions/runs/38553413390)

明确排除的旧资料没有被宣称为已迁移：Lyra 的生成式个人仓库清单，Vela 的生成研究报告/数据与空占位，Carina 的历史指令/计划、抓取快照、旧站点配置及环境专用脚本。根据目录清理要求，它们随旧源码退出当前 Git 树；这里仅记录路径、哈希和分类，不复制私有清单或内容。迁移时 manifest 的“source retained”描述的是当时 copy-first 阶段，本记录描述后续退役阶段。

未改动实际用户运行目录、凭据、数据库、调度设置或 Git 历史。未运行真实网络同步、LLM 或邮件发送。其他 Python 项目、语言实验、待审书籍、`.gitmodules` 和两个 gitlink 保持不变。

`python/projects/cron.sh` 同时调用 PIA 和 py-email，本次保持原样；其中旧 PIA 路径已不再是有效安装说明。它需在 py-email 的独立迁移和调度配置评审后处理，切勿直接执行以验证本次变更。

## 恢复

备份 `backup/pre-constellation-cleanup-2026-10-14` 固定为 `fd15e65059ff7d0d01ed48b6347cd75881fb4b36`，未移动。需要回滚时先检查工作区，再对本次退役提交执行 `git revert <retirement-commit>`；也可在单独 worktree 中从上述源快照查看旧文件。不要强推、清理历史或覆盖用户运行状态。

## 本地验证

离线维护测试、导航链接、源码清单与目标树哈希、仅允许范围内的 base-plus-delta 校验和 shell 语法检查。根依赖健康检查仍有既有 67 项孤立声明；这不是整个多语言仓库构建通过。当前变更不执行目标应用的实时服务，应用测试以目标合并后的 CI 为依据。
