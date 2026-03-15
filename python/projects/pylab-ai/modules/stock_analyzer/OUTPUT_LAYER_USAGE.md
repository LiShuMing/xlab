# Stock Analyzer Output Layer 使用说明

## 概述

Stock Analyzer 模块现在使用通用的 `utils.output` 输出层进行报告生成和分发。该设计遵循 design_doc.md 中的**输出层 (Output Layer)** 规范。

## 架构

```
utils/output/                    # 通用输出层库
├── base.py                      # 抽象基类 (BaseRenderer, BaseDispatcher)
├── renderers.py                 # 渲染器实现 (Markdown, HTML, JSON, Text)
├── dispatchers.py               # 分发器实现 (File, Streamlit, Memory)
└── __init__.py                  # 公共接口和便捷函数

modules/stock_analyzer/
└── stock_module.py              # 使用 output 层生成和分发报告
```

## 核心概念

### 1. Report 数据模型

```python
from utils.output import Report, ReportMetadata

report = Report(
    ticker="AAPL",
    company_name="Apple Inc.",
    metadata=ReportMetadata(title="Investment Analysis Report"),
    content="# Report Content\n...",  # Markdown content
    sections={                      # Optional structured sections
        ReportSection.TECHNICAL: "...",
        ReportSection.RATING: "...",
    },
    data={}  # Additional data for JSON output
)
```

### 2. 渲染器 (Renderers)

将 Report 转换为目标格式：

```python
from utils.output import MarkdownRenderer, HtmlRenderer, JsonRenderer, ReportFormat

# Markdown (默认)
md_renderer = MarkdownRenderer()
markdown_content = md_renderer.render(report)

# HTML (带样式)
html_renderer = HtmlRenderer()
html_content = html_renderer.render(report)

# JSON (结构化数据)
json_renderer = JsonRenderer()
json_content = json_renderer.render(report)
```

### 3. 分发器 (Dispatchers)

将内容发送到目标位置：

```python
from utils.output import FileDispatcher, StreamlitDispatcher

# 保存到文件
file_dispatcher = FileDispatcher(base_dir="./reports")
file_dispatcher.dispatch(content, "AAPL_report.md")

# 显示在 Streamlit
st_dispatcher = StreamlitDispatcher()
st_dispatcher.dispatch(content, "markdown")  # 或 "html"
```

## 便捷用法

### 快速输出 (quick_output)

最常用的方式，一行代码完成渲染、保存和显示：

```python
from utils.output import quick_output, ReportFormat

# 生成并输出报告
result = quick_output(
    report=report,
    format=ReportFormat.MARKDOWN,  # 或 HTML, JSON
    filename="AAPL_analysis_20260314.md",
    show_streamlit=True,           # 在 UI 中显示
    show_download=True,            # 显示下载按钮
)

# 结果包含生成的内容
print(result["content"])   # 渲染后的内容
print(result["filepath"])  # 保存的文件路径
print(result["success"])   # 是否成功
```

### 创建股票报告 (create_stock_report)

工厂函数快速创建股票分析报告：

```python
from utils.output import create_stock_report

report = create_stock_report(
    ticker="AAPL",
    company_name="Apple Inc.",
    content="# Analysis Report\n...",
    title="AAPL Investment Analysis",  # 可选，默认自动生成
)
```

## 在 Stock Analyzer 中的使用

### 重构后的流程

```python
def _run_analysis(self, query, temperature, max_tokens, data_range, output_format):
    # 1. 提取股票代码
    company_name, ticker = self._extract_ticker(query)
    
    # 2. 收集数据
    data_package = self._collect_data(ticker, data_range)
    
    # 3. 生成报告内容 (LLM)
    report_content = self._generate_report(...)
    
    # 4. 创建 Report 对象
    report = create_stock_report(
        ticker=ticker,
        company_name=company_name,
        content=report_content,
        data={...}  # 附加数据
    )
    
    # 5. 使用输出层渲染和分发
    result = quick_output(
        report=report,
        format=ReportFormat(output_format),  # markdown/html/json
        filename=f"{ticker}_analysis_{date}.md",
    )
```

### UI 中的格式选择

用户可以在分析配置中选择输出格式：

```python
output_format = st.selectbox(
    "Report Output Format",
    options=["markdown", "html", "json"],
    index=0,
)
```

## HTML 输出格式说明

HTML 渲染器支持以下特性：

1. **换行符处理**
   - Markdown 中的单行换行会被转换为 `<br>` 标签
   - 段落之间保留空行分隔

2. **列表支持**
   - 无序列表（`-`, `*`, `+`）转换为 `<ul>` / `<li>`
   - 有序列表（`1.`, `2.` 等）转换为 `<ol>` / `<li>`

3. **文本格式**
   - `**粗体**` 转换为 `<strong>`
   - `*斜体*` 转换为 `<em>`
   - `` `代码` `` 转换为 `<code>`

4. **标题**
   - `#` 到 `######` 转换为 `<h1>` 到 `<h6>`

### 安装 markdown2 获得更好体验

```bash
pip install markdown2
```

安装后 HTML 输出将支持：
- 表格渲染
- 代码高亮
- 自动换行（break-on-newline）
- 更多 Markdown 扩展语法

## 扩展输出层

### 添加新的渲染器

```python
from utils.output import BaseRenderer, Report, ReportFormat

class PdfRenderer(BaseRenderer):
    format = ReportFormat.PDF
    
    def render(self, report: Report) -> str:
        # 实现 PDF 渲染
        return pdf_bytes
    
    def get_content_type(self) -> str:
        return "application/pdf"
```

### 添加新的分发器

```python
from utils.output import BaseDispatcher

class EmailDispatcher(BaseDispatcher):
    def dispatch(self, content: str, destination: str, metadata=None) -> bool:
        # 实现邮件发送
        return success
    
    def validate_destination(self, destination: str) -> bool:
        # 验证邮箱格式
        return is_valid_email(destination)
```

## 文件结构

```
reports/                         # 生成的报告保存目录
├── AAPL_analysis_20260314.md
├── AAPL_analysis_20260314.html
└── AAPL_analysis_20260314.json
```

## 依赖

- `markdown2`: 用于 Markdown 到 HTML 的转换（可选，有简单回退方案）
  - 安装：`pip install markdown2`
  - 启用更完整的 Markdown 支持（表格、代码块等）
- 其他依赖已在项目 requirements.txt 中

## 迁移说明

旧代码直接输出 Markdown 字符串：
```python
# 旧方式
st.markdown(report_content)
st.download_button(...)
```

新代码使用 Report 对象和输出层：
```python
# 新方式
report = create_stock_report(ticker, company_name, report_content)
quick_output(report, format=ReportFormat.MARKDOWN)
```

新方式的优势：
1. **标准化**: 所有报告使用统一的数据模型
2. **多格式支持**: 轻松切换 Markdown/HTML/JSON
3. **可扩展**: 添加新格式无需修改业务代码
4. **关注点分离**: 业务逻辑与输出逻辑解耦
5. **HTML 优化**: 自动处理换行符和列表格式
