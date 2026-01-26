"""Business logic for the Embedder Service."""

from embedder.logic.encoder import SentenceEncoder
from embedder.logic.exceptions import EncoderError, ModelNotFoundError

__all__ = [
    "SentenceEncoder",
    "EncoderError",
    "ModelNotFoundError",
]
