"""
api/auth.py: Autenticación por token de sesión en loopback (Sección 4.2 y 10).
"""

import secrets
from typing import Optional
from fastapi import Header, HTTPException, status

# Variable global del proceso que almacena el secreto generado en el arranque
CURRENT_SESSION_TOKEN: Optional[str] = None


def generate_session_token() -> str:
    global CURRENT_SESSION_TOKEN
    CURRENT_SESSION_TOKEN = secrets.token_urlsafe(32)
    return CURRENT_SESSION_TOKEN


def set_session_token(token: str) -> None:
    global CURRENT_SESSION_TOKEN
    CURRENT_SESSION_TOKEN = token


def get_current_session_token() -> str:
    global CURRENT_SESSION_TOKEN
    if not CURRENT_SESSION_TOKEN:
        CURRENT_SESSION_TOKEN = secrets.token_urlsafe(32)
    return CURRENT_SESSION_TOKEN


async def verify_bearer_token(authorization: Optional[str] = Header(None)) -> str:
    """Valida que la solicitud incluya el token de sesión loopback en el header Authorization."""
    expected = get_current_session_token()
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header Authorization no proporcionado.",
        )
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de autorización inválido. Utilice 'Bearer <token>'.",
        )
    provided_token = parts[1]
    if not secrets.compare_digest(provided_token, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token de sesión inválido o expirado.",
        )
    return provided_token
