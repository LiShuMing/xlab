# Changelog

## 2026-09-19

- 创建文档骨架、阶段清单和跨语言模型产物契约草案。
- 尚未添加可执行实现、依赖环境或模型产物。

## 2026-09-19 — v0.1 可运行实现

- 增加 byte tokenizer、Bigram、Tiny Transformer、训练恢复、验证和无缓存生成 CLI。
- 安装项目本地 Python 3.12 / PyTorch，锁定依赖；提供 setup.sh。
- CPU 9 项测试、MPS 训练与 logits 对照通过，记录本机验收。
- KV Cache 和跨语言导出仍未实现。
