"""Projector service exceptions."""


class ProjectorError(Exception):
    """Base exception for projector service."""
    pass


class CheckpointGenerationError(ProjectorError):
    """Raised when TensorFlow checkpoint generation fails."""
    pass


class VectorFetchError(ProjectorError):
    """Raised when fetching vectors from Qdrant fails."""
    pass


class EmptyCollectionError(ProjectorError):
    """Raised when no vectors are found in the collection."""
    pass
