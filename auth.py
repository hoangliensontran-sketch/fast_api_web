# /home/sonthl/setup/docker/media-lite/auth.py

from fastapi import Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeSerializer
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

SECRET_KEY = "MvmZ9LD3h2GkFdFKOsaGHB59Gi02m1KzpyYZNDl2u3c"
COOKIE_NAME = "session"

s = URLSafeSerializer(SECRET_KEY)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://media_user:media_password@localhost:5432/media_db")
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    can_upload = Column(Boolean, default=True)
    can_download = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)
    # Navigation permissions
    can_view_videos = Column(Boolean, default=True)
    can_view_images = Column(Boolean, default=True)
    can_view_documents = Column(Boolean, default=True)
    can_view_categories = Column(Boolean, default=False)  # Only for admins by default
    can_view_users = Column(Boolean, default=False)  # Only for admins by default

Session = sessionmaker(bind=engine)

# Ensure all table columns are recognized by SQLAlchemy
Base.metadata.create_all(engine)

# Fallback for legacy authentication
users = {
    "admin": "admin"
}

def get_user_from_db(username: str):
    """Get user from database"""
    try:
        with Session() as session:
            return session.query(User).filter(User.username == username).first()
    except:
        return None

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

def require_permission(permission: str):
    """Decorator factory to check if user has specific permission"""
    def permission_checker(request: Request):
        username = require_login(request)
        user = get_user_from_db(username)

        if not user:
            # Fallback: if user not in DB but logged in, allow admin
            if username == "admin":
                return username
            raise HTTPException(status_code=403, detail="Permission denied")

        # Admin can do everything
        if user.is_admin:
            return username

        # Check specific permission
        if permission == "download" and not user.can_download:
            raise HTTPException(status_code=403, detail="You don't have permission to download files")
        if permission == "delete" and not user.can_delete:
            raise HTTPException(status_code=403, detail="You don't have permission to delete files")
        if permission == "upload" and not user.can_upload:
            raise HTTPException(status_code=403, detail="You don't have permission to upload files")

        return username
    return permission_checker

def get_user_with_permissions(request: Request):
    """Get user object with all permission fields for template rendering"""
    username = get_current_user(request)
    if not username:
        return None

    user_obj = get_user_from_db(username)
    if not user_obj:
        # Fallback for hardcoded admin user
        if username == "admin":
            return {
                "username": username,
                "is_admin": True,
                "can_upload": True,
                "can_download": True,
                "can_delete": True,
                "can_view_videos": True,
                "can_view_images": True,
                "can_view_documents": True,
                "can_view_categories": True,
                "can_view_users": True
            }
        return None

    return {
        "username": user_obj.username,
        "is_admin": user_obj.is_admin,
        "can_upload": user_obj.can_upload,
        "can_download": user_obj.can_download,
        "can_delete": user_obj.can_delete,
        "can_view_videos": user_obj.can_view_videos,
        "can_view_images": user_obj.can_view_images,
        "can_view_documents": user_obj.can_view_documents,
        "can_view_categories": user_obj.can_view_categories,
        "can_view_users": user_obj.can_view_users
    }

