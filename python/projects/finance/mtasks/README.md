# Git周报生成器

这是一个基于Qwen大模型的Python应用程序，用于分析Git提交历史并生成中文技术周报。

## 功能特性

- 自动收集指定Git仓库的提交历史
- 使用Qwen大模型分析提交内容
- 生成结构化的中文技术周报
- 支持自定义时间范围和字符限制

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

1. 设置环境变量：
   ```bash
   export DASHSCOPE_API_KEY=your_api_key_here
   ```

2. 或者编辑 `config.ini` 文件：
   ```ini
   [qwen]
   api_key = your_api_key_here
   ```

## 使用方法

```bash
python git_report_generator.py
```

## 测试

```bash
python -m pytest test_git_report_generator.py
```