# py-tools

个人常用的小工具脚本集合（无额外 Python 依赖，仅用标准库）。

## collect_git_repos.py

在指定根目录下**递归**查找 Git 工作区（含子目录中的嵌套仓库），读取远程地址，生成 Markdown，每个仓库一段可复制的 `git clone …` 命令。

### 依赖

- Python 3.10+
- 系统已安装 `git`，且可在 `PATH` 中调用

### 命令行

```bash
python3 collect_git_repos.py -r ~/work -o git-repos.md
```

| 参数 | 说明 |
|------|------|
| `-r` / `--root` | 扫描根目录，默认 `~/work` |
| `-o` / `--output` | 输出 Markdown 路径（**必填**） |
| `--remote` | 优先使用的 remote 名称，默认 `origin` |
| `--include-hidden` | 同时进入路径中名为 `.xxx` 的目录（默认跳过，减少缓存等目录干扰） |
| `--title` | 文档一级标题，默认 `Git repositories` |

示例：只扫当前工程并指定标题。

```bash
python3 collect_git_repos.py -r ~/work/xlab -o repos.md --title "xlab 下的 Git 仓库"
```

### 行为说明

- 判定仓库：目录下存在 `.git`（普通目录、子模块或 linked worktree 的 `.git` 文件均算）。
- 遍历时**不会**进入 `.git` 内部。
- 远程 URL：先取 `--remote`（默认 `origin`）；若没有，再取 `git remote` 列表中的第一个。
- 未配置任何 remote 或 `git` 调用失败时，对应小节会标注无 remote，而不会中断整个扫描。

### 作为模块使用

```python
from pathlib import Path
from collect_git_repos import GitRepoCollector, render_markdown

collector = GitRepoCollector(Path("~/work"), skip_hidden_dirs=True)
items = collector.collect()
md = render_markdown(collector.root, items)
Path("out.md").write_text(md, encoding="utf-8")
```

### 注意

构建产物或依赖拉取目录（例如 CMake `build/_deps/…-src`）若包含完整 `.git`，也会被列出。若需要排除特定路径，可在脚本基础上增加过滤规则。
