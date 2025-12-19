# /home/sonthl/setup/docker/media-lite/auth.py

from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer

SECRET_KEY = "MvmZ9LD3h2GkFdFKOsaGHB59Gi02m1KzpyYZNDl2u3c"
COOKIE_NAME = "session"

s = URLSafeSerializer(SECRET_KEY)

users = {
    "admin": "admin"
}

def create_session(username: str):
    return s.dumps({"user": username})

def get_current_user(request: Request):
    cookie = request.cookies.get(COOKIE_NAME)
    if not cookie:
        return None
    try:
        data = s.loads(cookie)
        return data.get("user")
    except:
        return None

def require_login(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=403, detail="Login required")
    return user

