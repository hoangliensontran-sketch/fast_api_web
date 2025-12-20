import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://media_user:media_password@db:5432/media_db")
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

class ImageCategory(Base):
    __tablename__ = "image_categories"
    filename = Column(String, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

class VideoCategory(Base):
    __tablename__ = "video_categories"
    filename = Column(String, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

class DocumentCategory(Base):
    __tablename__ = "document_categories"
    filename = Column(String, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    can_upload = Column(Boolean, default=True)
    can_download = Column(Boolean, default=True)
    can_delete = Column(Boolean, default=False)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# Ensure "All" category exists
if not session.query(Category).filter_by(id=0, name="All").first():
    all_category = Category(id=0, name="All")
    session.add(all_category)
    session.commit()

# Create default admin user if not exists
if not session.query(User).filter_by(username="admin").first():
    admin_user = User(
        username="admin",
        password="admin",  # In production, this should be hashed
        is_admin=True,
        can_upload=True,
        can_download=True,
        can_delete=True
    )
    session.add(admin_user)
    session.commit()
    print("Default admin user created (username: admin, password: admin)")

session.close()
print("Database initialized successfully")
