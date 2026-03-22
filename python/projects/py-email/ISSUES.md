# TO-FIX

# FIXED
- 将该项目依赖的credentials，移动到~/.credentials/my-email/；并修改 config.py 默认路径和 .env.example 示例路径。
- 支持指定输出文件目录：`digest --output-dir <dir>` 将报告写入 `<dir>/digest-<date>.json`。
- 在 `/home/lism/work/xlab/python/projects/cron.sh` 中添加每日 my-email sync/summarize/digest 脚本，输出到 `$OUT_DIR`。