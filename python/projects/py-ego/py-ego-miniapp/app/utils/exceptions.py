"""Custom exception classes for the application."""

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base exception class for application-specific errors.

    Args:
        code: Error code identifier.
        message: Human-readable error message.
        status_code: HTTP status code.
    """

    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.code = code
        self.message = message
        super().__init__(status_code=status_code, detail={"code": code, "message": message})


class UnauthorizedException(AppException):
    """Exception raised for authentication/authorization errors."""

    def __init__(self, message: str = "Unauthorized"):
        super().__init__(code="UNAUTHORIZED", message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class NotFoundException(AppException):
    """Exception raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(code="NOT_FOUND", message=message, status_code=status.HTTP_404_NOT_FOUND)


class ValidationException(AppException):
    """Exception raised for validation errors."""

    def __init__(self, message: str = "Validation error"):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class WechatAuthException(AppException):
    """Exception raised when WeChat authentication fails."""

    def __init__(self, message: str = "WeChat authentication failed"):
        super().__init__(code="WECHAT_AUTH_FAILED", message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class RateLimitException(AppException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, message: str = "Too many requests"):
        super().__init__(code="RATE_LIMITED", message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)