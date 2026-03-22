# TO-FIX

# FIXED
- 支持指定输出文件目录：`analyze latest/version` 和 `digest weekly/monthly` 均新增 `--output-dir / -o` 选项，指定后报告写入该目录，否则沿用默认 `data/reports/`。
- 在 `/home/lism/work/xlab/python/projects/cron.sh` 中添加每日脚本：sync 全部产品后执行 `pia digest weekly`，输出到 `~/work/my-docs/<date>/`。