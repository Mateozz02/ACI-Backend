from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.services.auth import decode_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id


async def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None
    return decode_token(credentials.credentials)
