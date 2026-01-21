"""
Business logic exceptions.

These exceptions are raised by service classes and converted to HTTP responses
by the error handlers in middleware/error_handler.py.
"""

from typing import Any

from fastapi import status


class APIError(Exception):
    """Base API exception."""
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: list[dict[str, str]] | None = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found error."""
    
    def __init__(self, resource: str, id: Any = None):
        message = f"{resource} not found"
        if id:
            message = f"{resource} with id '{id}' not found"
        super().__init__(
            code="NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class DuplicateError(APIError):
    """Duplicate resource error."""
    
    def __init__(self, resource: str, field: str):
        super().__init__(
            code="DUPLICATE",
            message=f"{resource} with this {field} already exists",
            status_code=status.HTTP_409_CONFLICT,
        )


class ValidationError(APIError):
    """Validation error."""
    
    def __init__(self, message: str, details: list[dict[str, str]] | None = None):
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class UnauthorizedError(APIError):
    """Unauthorized error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code="UNAUTHORIZED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(APIError):
    """Forbidden error."""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            code="FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class ServiceUnavailableError(APIError):
    """Service unavailable error."""
    
    def __init__(self, service: str):
        super().__init__(
            code="SERVICE_UNAVAILABLE",
            message=f"{service} is currently unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
