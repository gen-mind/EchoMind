"""
JWT authentication and user extraction utilities.

Provides JWT validation and user context extraction from Authentik tokens.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import jwt
from jwt import PyJWKClient


@dataclass
class TokenUser:
    """User information extracted from JWT token."""
    
    id: int
    email: str
    user_name: str
    first_name: str | None
    last_name: str | None
    roles: list[str]
    groups: list[str]
    external_id: str | None


class JWTValidator:
    """
    JWT token validator for Authentik OIDC tokens.
    
    Usage:
        validator = JWTValidator(
            issuer="https://auth.example.com",
            audience="echomind-api",
            jwks_url="https://auth.example.com/.well-known/jwks.json",
        )
        
        user = validator.validate_token(token)
    """
    
    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_url: str | None = None,
        secret: str | None = None,
        algorithms: list[str] | None = None,
    ):
        """
        Initialize JWT validator.
        
        Args:
            issuer: Expected token issuer (iss claim)
            audience: Expected audience (aud claim)
            jwks_url: URL to fetch JWKS for RS256 validation
            secret: Secret key for HS256 validation (dev only)
            algorithms: Allowed algorithms (default: RS256)
        """
        self._issuer = issuer
        self._audience = audience
        self._algorithms = algorithms or ["RS256"]
        self._secret = secret
        self._jwks_client: PyJWKClient | None = None
        
        if jwks_url:
            self._jwks_client = PyJWKClient(jwks_url)
    
    def validate_token(self, token: str) -> TokenUser:
        """
        Validate a JWT token and extract user information.
        
        Args:
            token: JWT token string
        
        Returns:
            TokenUser with extracted claims
        
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        if self._jwks_client:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            key = signing_key.key
        elif self._secret:
            key = self._secret
        else:
            raise ValueError("No signing key configured")
        
        payload = jwt.decode(
            token,
            key,
            algorithms=self._algorithms,
            issuer=self._issuer,
            audience=self._audience,
            options={"require": ["exp", "iat", "sub"]},
        )
        
        return self._extract_user(payload)
    
    def _extract_user(self, payload: dict[str, Any]) -> TokenUser:
        """Extract user information from token payload."""
        groups = payload.get("groups", [])
        roles = list(payload.get("roles", []))

        # Map Authentik groups to application roles
        # Higher levels include all lower level roles
        if "echomind-admins" in groups:
            if "admin" not in roles:
                roles.append("admin")
            if "user" not in roles:
                roles.append("user")
        elif "echomind-allowed" in groups:
            if "user" not in roles:
                roles.append("user")

        return TokenUser(
            id=payload.get("user_id", 0),
            email=payload.get("email", ""),
            user_name=payload.get("preferred_username", payload.get("sub", "")),
            first_name=payload.get("given_name"),
            last_name=payload.get("family_name"),
            roles=roles,
            groups=groups,
            external_id=payload.get("sub"),
        )
    
    def decode_without_validation(self, token: str) -> dict[str, Any]:
        """
        Decode token without validation (for debugging only).
        
        Args:
            token: JWT token string
        
        Returns:
            Token payload dict
        """
        return jwt.decode(token, options={"verify_signature": False})


_jwt_validator: JWTValidator | None = None


def get_jwt_validator() -> JWTValidator:
    """Get the global JWT validator instance."""
    if _jwt_validator is None:
        raise RuntimeError("JWT validator not initialized. Call init_jwt_validator() first.")
    return _jwt_validator


def init_jwt_validator(
    issuer: str,
    audience: str,
    jwks_url: str | None = None,
    secret: str | None = None,
) -> JWTValidator:
    """Initialize the global JWT validator."""
    global _jwt_validator
    _jwt_validator = JWTValidator(
        issuer=issuer,
        audience=audience,
        jwks_url=jwks_url,
        secret=secret,
    )
    return _jwt_validator


def extract_bearer_token(authorization: str | None) -> str | None:
    """
    Extract token from Authorization header.
    
    Args:
        authorization: Authorization header value
    
    Returns:
        Token string or None
    """
    if not authorization:
        return None
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    
    return parts[1]
