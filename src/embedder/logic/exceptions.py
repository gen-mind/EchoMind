"""
Domain exceptions for the Embedder Service.

These exceptions are raised by the business logic layer and
converted to gRPC status codes by the service layer.
"""


class EncoderError(Exception):
    """Base exception for encoder errors."""

    pass


class ModelNotFoundError(EncoderError):
    """Raised when a requested model cannot be loaded."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model not found: {model_name}")


class EncodingError(EncoderError):
    """Raised when encoding fails."""

    def __init__(self, message: str, texts_count: int):
        self.texts_count = texts_count
        super().__init__(f"Encoding failed for {texts_count} texts: {message}")
