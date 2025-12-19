import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
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

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
session = Session()

# Ensure "All" category exists
if not session.query(Category).filter_by(id=0, name="All").first():
    all_category = Category(id=0, name="All")
    session.add(all_category)
    session.commit()

session.close()
print("Database initialized successfully")
