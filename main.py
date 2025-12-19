from fastapi import FastAPI, File, UploadFile, Request, Form, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import os
import subprocess
from PIL import Image, ExifTags
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional, List
import time
from auth import get_current_user, require_login, COOKIE_NAME, create_session

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

VIDEO_DIR = "static/videos"
IMAGE_DIR = "static/images"
THUMBNAIL_DIR = "static/thumbnails"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://media_user:media_password@localhost:5432/media_db")

os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# SQLAlchemy setup
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

Session = sessionmaker(bind=engine)

def is_valid_video(filename):
    return filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))

def is_valid_image(filename):
    return filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))

def fix_video_rotation(video_path):
    """Fix video rotation by re-encoding if rotation metadata is present."""
    import json
    try:
        # Check for rotation metadata
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream_tags=rotate:stream_side_data=rotation',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        rotation = 0

        if result.stdout:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                stream = streams[0]
                tags = stream.get('tags', {})
                if 'rotate' in tags:
                    rotation = int(tags['rotate'])
                elif 'side_data_list' in stream:
                    for side_data in stream['side_data_list']:
                        if 'rotation' in side_data:
                            rotation = int(side_data['rotation'])
                            break

        if rotation == 0:
            return True  # No rotation needed

        # Determine FFmpeg filter
        if rotation == 90 or rotation == -270:
            vf_filter = 'transpose=2'
        elif rotation == -90 or rotation == 270:
            vf_filter = 'transpose=1'
        elif rotation == 180 or rotation == -180:
            vf_filter = 'transpose=1,transpose=1'
        else:
            print(f"Unsupported rotation: {rotation}")
            return False

        # Re-encode with rotation applied
        temp_output = video_path + '.rotated.mp4'
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-vf', vf_filter,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-metadata:s:v:0', 'rotate=0',
            '-y',
            temp_output
        ]

        print(f"Fixing rotation {rotation}° for {video_path}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(temp_output):
            os.replace(temp_output, video_path)
            print(f"✓ Rotation fixed for {video_path}")
            return True
        else:
            print(f"Failed to fix rotation: {result.stderr}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False

    except Exception as e:
        print(f"Error fixing rotation: {str(e)}")
        return False

def create_thumbnail(video_path, thumbnail_path):
    try:
        temp_path = thumbnail_path + '.tmp.jpg'
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:03',
            '-vframes', '1',
            '-q:v', '2',
            temp_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with Image.open(temp_path) as img:
            new_img = Image.new("RGB", (320, 240), (255, 255, 255))
            img.thumbnail((320, 240), Image.Resampling.LANCZOS)
            width, height = img.size
            offset = ((320 - width) // 2, (240 - height) // 2)
            new_img.paste(img, offset)
            new_img.save(thumbnail_path, "JPEG", quality=85)
        os.remove(temp_path)
        print(f"Thumbnail created for {video_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error creating thumbnail for {video_path}: {e.stderr.decode()}")
    except FileNotFoundError:
        print("FFmpeg not found. Please ensure FFmpeg is installed.")
    except Exception as e:
        print(f"Error adding white border to thumbnail: {str(e)}")

def create_image_thumbnail(image_path, thumbnail_path):
    try:
        with Image.open(image_path) as img:
            try:
                for orientation in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[orientation] == 'Orientation':
                        break
                exif = img._getexif()
                if exif is not None:
                    orientation = exif.get(orientation, 1)
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
            except (AttributeError, KeyError, IndexError):
                pass
            img.thumbnail((320, 240), Image.Resampling.LANCZOS)
            width, height = img.size
            new_img = Image.new("RGB", (320, 240), (255, 255, 255))
            offset = ((320 - width) // 2, (240 - height) // 2)
            new_img.paste(img, offset)
            new_img.save(thumbnail_path, "JPEG", quality=85)
        print(f"Thumbnail created for {image_path}")
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {str(e)}")

def create_fallback_image(fallback_path):
    try:
        new_img = Image.new("RGB", (320, 240), (255, 255, 255))
        new_img.save(fallback_path, "JPEG", quality=85)
        print(f"Fallback image created at {fallback_path}")
    except Exception as e:
        print(f"Error creating fallback image: {str(e)}")

FALLBACK_PATH = os.path.join(THUMBNAIL_DIR, "fallback.jpg")
if not os.path.exists(FALLBACK_PATH):
    create_fallback_image(FALLBACK_PATH)

@app.get("/api/videos")
async def api_video_list(page: int = 1, per_page: int = 6, category_id: Optional[str] = Query(None), user: str = Depends(require_login)):
    with Session() as session:
        all_files = sorted(
            os.listdir(VIDEO_DIR),
            key=lambda f: os.path.getctime(os.path.join(VIDEO_DIR, f)),
            reverse=True
        )
        if category_id == "all":
            pass
        elif category_id and category_id.isdigit():
            filtered_filenames = [vc.filename for vc in session.query(VideoCategory).filter(VideoCategory.category_id == int(category_id)).all()]
            all_files = [f for f in all_files if f in filtered_filenames]
        else:
            filtered_filenames = [vc.filename for vc in session.query(VideoCategory).all()]
            all_files = [f for f in all_files if f not in filtered_filenames]
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        videos = all_files[start:end]
        return JSONResponse({
            "videos": videos,
            "page": page,
            "total": total
        })

@app.get("/api/video-metadata/{filename}")
async def get_video_metadata(filename: str, user: str = Depends(require_login)):
    import json
    video_path = os.path.join(VIDEO_DIR, filename)
    if not os.path.exists(video_path):
        return JSONResponse(status_code=404, content={"error": "Video not found"})

    try:
        # Use JSON format for reliable parsing of rotation metadata
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height:stream_tags=rotate:stream_side_data=rotation',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        rotation = 0

        if result.stdout:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                stream = streams[0]

                # 1. Check stream tags first (most common for MP4 from mobile devices)
                tags = stream.get('tags', {})
                if 'rotate' in tags:
                    rotation = int(tags['rotate'])
                # 2. Check side_data_list as fallback (used by some video formats)
                elif 'side_data_list' in stream:
                    for side_data in stream['side_data_list']:
                        if 'rotation' in side_data:
                            rotation = int(side_data['rotation'])
                            break

        print(f"Video {filename} rotation metadata: {rotation}")
        return JSONResponse({"filename": filename, "rotation": rotation})
    except Exception as e:
        print(f"Error getting video metadata for {filename}: {str(e)}")
        return JSONResponse({"filename": filename, "rotation": 0})

@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    from auth import users
    if username in users and users[username] == password:
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(COOKIE_NAME, create_session(username), httponly=True)
        return response
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password"
        })

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, page: int = 1, per_page: int = 5, user: str = Depends(get_current_user)):
    all_videos = sorted(
        os.listdir(VIDEO_DIR),
        key=lambda f: os.path.getctime(os.path.join(VIDEO_DIR, f)),
        reverse=True
    )
    total_videos = len(all_videos)
    start = (page - 1) * per_page
    end = start + per_page
    videos = all_videos[start:end]
    total_pages = (total_videos + per_page - 1) // per_page
    return templates.TemplateResponse("index.html", {
        "request": request,
        "videos": videos,
        "page": page,
        "total_pages": total_pages,
        "user": user
    })

@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, user: str = Depends(require_login)):
    with Session() as session:
        categories = session.query(Category).order_by(Category.id).all()
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "user": user,
            "categories": categories
        })

@app.post("/upload")
async def upload_video(files: List[UploadFile] = File(...), category_id: Optional[str] = Form(None), user: str = Depends(require_login)):
    if not files:
        return JSONResponse(status_code=400, content={"message": "No files uploaded"})
    if len(files) > 10:
        return JSONResponse(status_code=400, content={"message": "Cannot upload more than 10 files at once"})
    
    invalid_files = [file.filename for file in files if not is_valid_video(file.filename)]
    if invalid_files:
        return JSONResponse(status_code=400, content={"message": f"Invalid video format for: {', '.join(invalid_files)}"})
    
    with Session() as session:
        for file in files:
            timestamp = int(time.time())
            base, ext = os.path.splitext(file.filename)
            unique_filename = f"{base}_{timestamp}{ext}"
            video_path = os.path.join(VIDEO_DIR, unique_filename)
            thumbnail_path = os.path.join(THUMBNAIL_DIR, unique_filename.replace(ext, '.jpg'))
            try:
                with open(video_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                # Fix rotation if present (applies rotation to video stream)
                fix_video_rotation(video_path)

                # Note: .mov files will be converted to .mp4 by the background converter service
                create_thumbnail(video_path, thumbnail_path)
                if category_id and category_id.isdigit() and int(category_id) != 0:
                    session.add(VideoCategory(filename=unique_filename, category_id=int(category_id)))
            except Exception as e:
                print(f"Error processing file {file.filename}: {str(e)}")
                continue
        try:
            session.commit()
        except Exception as e:
            print(f"Error updating database: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error updating database"})
    
    return RedirectResponse(url="/videos", status_code=303)

@app.post("/delete")
async def delete_video(filename: str = Form(...), user: str = Depends(require_login)):
    filepath = os.path.join(VIDEO_DIR, filename)
    base, ext = os.path.splitext(filename)
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{base}.jpg")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            with Session() as session:
                session.query(VideoCategory).filter(VideoCategory.filename == filename).delete()
                session.commit()
            return RedirectResponse(url="/videos", status_code=303)
        except Exception as e:
            print(f"Error deleting video {filename}: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error deleting video"})
    return JSONResponse(status_code=404, content={"message": "File not found"})

@app.get("/videos", response_class=HTMLResponse)
async def video_page(request: Request, page: int = 1, per_page: int = 5, user: str = Depends(require_login)):
    with Session() as session:
        categories = session.query(Category).order_by(Category.id).all()
        all_files = sorted(
            os.listdir(VIDEO_DIR),
            key=lambda f: os.path.getctime(os.path.join(VIDEO_DIR, f)),
            reverse=True
        )
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        videos = all_files[start:end]
        total_pages = (total + per_page - 1) // per_page
        return templates.TemplateResponse("videos.html", {
            "request": request,
            "videos": videos,
            "page": page,
            "total_pages": total_pages,
            "user": user,
            "categories": categories
        })

@app.get("/images", response_class=HTMLResponse)
async def image_page(request: Request, page: int = 1, per_page: int = 10, user: str = Depends(require_login)):
    with Session() as session:
        categories = session.query(Category).order_by(Category.id).all()
        all_files = [f for f in sorted(
            os.listdir(IMAGE_DIR),
            key=lambda f: os.path.getctime(os.path.join(IMAGE_DIR, f)),
            reverse=True
        ) if is_valid_image(f)]
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        images = all_files[start:end]
        total_pages = (total + per_page - 1) // per_page
        return templates.TemplateResponse("images.html", {
            "request": request,
            "images": images,
            "page": page,
            "total_pages": total_pages,
            "user": user,
            "categories": categories
        })

@app.get("/upload-image", response_class=HTMLResponse)
async def upload_image_form(request: Request, user: str = Depends(require_login)):
    with Session() as session:
        categories = session.query(Category).order_by(Category.id).all()
        return templates.TemplateResponse("upload_image.html", {
            "request": request,
            "user": user,
            "categories": categories
        })

@app.post("/upload-image")
async def upload_image(files: List[UploadFile] = File(...), category_id: Optional[str] = Form(None), user: str = Depends(require_login)):
    if not files:
        return JSONResponse(status_code=400, content={"message": "No files uploaded"})
    if len(files) > 10:
        return JSONResponse(status_code=400, content={"message": "Cannot upload more than 10 files at once"})
    
    invalid_files = [file.filename for file in files if not is_valid_image(file.filename)]
    if invalid_files:
        return JSONResponse(status_code=400, content={"message": f"Invalid image format for: {', '.join(invalid_files)}"})
    
    with Session() as session:
        for file in files:
            timestamp = int(time.time())
            base, ext = os.path.splitext(file.filename)
            unique_filename = f"{base}_{timestamp}{ext}"
            filepath = os.path.join(IMAGE_DIR, unique_filename)
            thumbnail_path = os.path.join(THUMBNAIL_DIR, f"thumb_{unique_filename}")
            try:
                with open(filepath, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                create_image_thumbnail(filepath, thumbnail_path)
                if category_id and category_id.isdigit() and int(category_id) != 0:
                    session.add(ImageCategory(filename=unique_filename, category_id=int(category_id)))
            except Exception as e:
                print(f"Error processing file {file.filename}: {str(e)}")
                continue
        try:
            session.commit()
        except Exception as e:
            print(f"Error updating database: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error updating database"})
    
    return RedirectResponse(url="/images", status_code=303)

@app.post("/delete-image")
async def delete_image(filename: str = Form(...), user: str = Depends(require_login)):
    filepath = os.path.join(IMAGE_DIR, filename)
    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"thumb_{filename}")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            if os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            with Session() as session:
                session.query(ImageCategory).filter(ImageCategory.filename == filename).delete()
                session.commit()
            return RedirectResponse(url="/images", status_code=303)
        except Exception as e:
            print(f"Error deleting image {filename}: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error deleting image"})
    return JSONResponse(status_code=404, content={"message": "File not found"})

@app.get("/api/images")
async def api_image_list(page: int = 1, per_page: int = 12, category_id: Optional[str] = Query(None), user: str = Depends(require_login)):
    with Session() as session:
        all_files = [
            f for f in sorted(
                os.listdir(IMAGE_DIR),
                key=lambda f: os.path.getctime(os.path.join(IMAGE_DIR, f)),
                reverse=True
            ) if is_valid_image(f)
        ]
        if category_id == "all":
            pass
        elif category_id and category_id.isdigit():
            filtered_filenames = [ic.filename for ic in session.query(ImageCategory).filter(ImageCategory.category_id == int(category_id)).all()]
            all_files = [f for f in all_files if f in filtered_filenames]
        else:
            filtered_filenames = [ic.filename for ic in session.query(ImageCategory).all()]
            all_files = [f for f in all_files if f not in filtered_filenames]
        total = len(all_files)
        start = (page - 1) * per_page
        end = start + per_page
        images = all_files[start:end]
        return JSONResponse({
            "images": images,
            "page": page,
            "total": total
        })

@app.get("/manage-categories", response_class=HTMLResponse)
async def manage_categories_form(request: Request, user: str = Depends(require_login)):
    with Session() as session:
        categories = session.query(Category).order_by(Category.id).all()
        return templates.TemplateResponse("manage_categories.html", {
            "request": request,
            "user": user,
            "categories": categories
        })

@app.post("/create-category")
async def create_category(name: str = Form(...), user: str = Depends(require_login)):
    if name.lower() == "all":
        return JSONResponse(status_code=400, content={"message": "Category name 'All' is reserved"})
    with Session() as session:
        max_id = session.query(Category.id).order_by(Category.id.desc()).first()
        new_id = (max_id[0] + 1) if max_id else 1
        session.add(Category(id=new_id, name=name))
        try:
            session.commit()
        except Exception as e:
            print(f"Error creating category: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error creating category"})
    return RedirectResponse(url="/manage-categories", status_code=303)

@app.post("/delete-category")
async def delete_category(category_id: int = Form(...), user: str = Depends(require_login)):
    if category_id == 0:
        return JSONResponse(status_code=400, content={"message": "Cannot delete 'All' category"})
    with Session() as session:
        session.query(ImageCategory).filter(ImageCategory.category_id == category_id).delete()
        session.query(VideoCategory).filter(VideoCategory.category_id == category_id).delete()
        session.query(Category).filter(Category.id == category_id).delete()
        try:
            session.commit()
        except Exception as e:
            print(f"Error deleting category: {str(e)}")
            return JSONResponse(status_code=500, content={"message": "Error deleting category"})
    return RedirectResponse(url="/manage-categories", status_code=303)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)