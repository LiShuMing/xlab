"""异常定义 - 应用级异常类"""


class InvestAIError(Exception):
    """应用基础异常"""

    def __init__(self, message: str, code: str = "INVEST_AI_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class DataCollectionError(InvestAIError):
    """数据收集异常"""

    def __init__(self, message: str, source: str = ""):
        super().__init__(
            message=f"数据收集失败 [{source}]: {message}",
            code="DATA_COLLECTION_ERROR",
        )


class LLMError(InvestAIError):
    """LLM 调用异常"""

    def __init__(self, message: str, model: str = ""):
        super().__init__(
            message=f"LLM 调用失败 [{model}]: {message}",
            code="LLM_ERROR",
        )


class ReportGenerationError(InvestAIError):
    """报告生成异常"""

    def __init__(self, message: str, step: str = ""):
        super().__init__(
            message=f"报告生成失败 [{step}]: {message}",
            code="REPORT_GENERATION_ERROR",
        )


class StockNotFoundError(InvestAIError):
    """股票未找到异常"""

    def __init__(self, stock_code: str):
        super().__init__(
            message=f"未找到股票：{stock_code}",
            code="STOCK_NOT_FOUND",
        )


class APIError(InvestAIError):
    """API 异常"""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message=message, code="API_ERROR")
        self.status_code = status_code
