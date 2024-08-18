"""Application-specific exceptions."""


class InvestAIError(Exception):
    """Base exception for Invest-AI application.

    Attributes:
        message: Error message.
        code: Error code for programmatic handling.
    """

    def __init__(self, message: str, code: str = "INVEST_AI_ERROR"):
        """Initialize exception.

        Args:
            message: Human-readable error message.
            code: Machine-readable error code.
        """
        self.message = message
        self.code = code
        super().__init__(self.message)


class DataCollectionError(InvestAIError):
    """Exception raised when data collection fails."""

    def __init__(self, message: str, source: str = ""):
        """Initialize exception.

        Args:
            message: Error message.
            source: Data source that failed.
        """
        super().__init__(
            message=f"Data collection failed [{source}]: {message}",
            code="DATA_COLLECTION_ERROR",
        )


class LLMError(InvestAIError):
    """Exception raised when LLM invocation fails."""

    def __init__(self, message: str, model: str = ""):
        """Initialize exception.

        Args:
            message: Error message.
            model: Model that failed.
        """
        super().__init__(
            message=f"LLM invocation failed [{model}]: {message}",
            code="LLM_ERROR",
        )


class ReportGenerationError(InvestAIError):
    """Exception raised when report generation fails."""

    def __init__(self, message: str, step: str = ""):
        """Initialize exception.

        Args:
            message: Error message.
            step: Generation step that failed.
        """
        super().__init__(
            message=f"Report generation failed [{step}]: {message}",
            code="REPORT_GENERATION_ERROR",
        )


class StockNotFoundError(InvestAIError):
    """Exception raised when stock is not found."""

    def __init__(self, stock_code: str):
        """Initialize exception.

        Args:
            stock_code: Stock code that was not found.
        """
        super().__init__(
            message=f"Stock not found: {stock_code}",
            code="STOCK_NOT_FOUND",
        )


class APIError(InvestAIError):
    """Exception raised for API errors."""

    def __init__(self, message: str, status_code: int = 500):
        """Initialize exception.

        Args:
            message: Error message.
            status_code: HTTP status code.
        """
        super().__init__(message=message, code="API_ERROR")
        self.status_code = status_code
