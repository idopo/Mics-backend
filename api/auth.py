# api/auth.py

import os
from typing import Any, Dict

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError


security = HTTPBearer()

JWT_SECRET = os.getenv("JWT_SECRET", "change_me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "mics-clients")
JWT_ISSUER = os.getenv("JWT_ISSUER", "mics-api")


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Reads the header: Authorization: Bearer <token>
    and validates the JWT.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={"leeway": 60}
)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
        )

    return payload
