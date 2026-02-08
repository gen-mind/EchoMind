"""
Central constants for EchoMind platform.

Single source of truth for bucket names and other cross-service constants.
"""


class MinioBuckets:
    """
    Registry of MinIO bucket names used across EchoMind services.

    This is the single source of truth. All services MUST use these
    constants instead of hardcoding bucket names.

    To add a new bucket:
        1. Add a class attribute here
        2. Add it to ``all()`` classmethod
        3. All services will auto-create it on startup
    """

    DOCUMENTS: str = "echomind-documents"

    @classmethod
    def all(cls) -> list[str]:
        """
        Return all bucket names that must exist.

        Returns:
            List of all registered bucket names.
        """
        return [cls.DOCUMENTS]
