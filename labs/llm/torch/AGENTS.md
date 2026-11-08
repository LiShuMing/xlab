# PyTorch Learning Project — Agent Guide

遵守仓库根 `AGENTS.md` 与 `labs/README.md` 的 lab 约定。修改前阅读 `README.md` 与
`ARCHITECTURE.md`，每次变更记入 `CHANGES_LOG.md`。

## 设计约定

- **接口优先**：抽象契约放 `micrograd/interfaces/`，实现放 `micrograd/*.py`，两者分开演进。
- **强类型**：公开函数与方法标注类型；示例与教程同步保持可运行。
- **注释与文档用英文**；教学说明写在 `ARCHITECTURE.md`，`README.md` 只写已实现的入口。
- **测试**：`pytest tests/ -v`；micrograd 核心用例必须全绿（当前 26 项），新增算子补边界用例。
- **依赖与产物**：`requirements.txt` 固定版本；虚拟环境、缓存与运行产物不入库。

## 已完成基线

接口层（`ValueInterface`/`ModuleInterface`/`OptimizerInterface`）、micrograd 强类型重写
（`engine.py`/`nn.py`/`optim.py`/`utils.py`）、26 项测试通过、`ARCHITECTURE.md` 与
`README.md` 文档、demo 脚本验证通过。

## 可选后续

- [ ] 教程脚本补齐类型标注：`tutorials/01_tensors.py` … `05_cifar10.py`
- [ ] 添加 mypy 配置（`mypy.ini`）并纳入检查
- [ ] 添加 CI 工作流
- [ ] 增加更多激活函数与 Adam 优化器实现
