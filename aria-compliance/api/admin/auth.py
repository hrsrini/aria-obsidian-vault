"""Admin authentication — X-Admin-Key header validation."""
import os
from fastapi import Header, HTTPException


def require_admin(x_admin_key: str = Header(...)):
    expected = os.environ.get("ARIA_ADMIN_KEY", "")
    if not expected:
        raise HTTPException(status_code=500, detail="ARIA_ADMIN_KEY not configured")
    if x_admin_key != expected:
        raise HTTPException(status_code=401, detail="Invalid admin key")
