# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a FastAPI-based media management web application that handles video and image uploads, with automatic thumbnail generation, video format conversion (.MOV to .MP4), and category organization. The application runs in Docker and connects to a PostgreSQL database.

## Development Commands

### Docker Operations
```bash
# Build and start containers
docker compose build
docker compose up -d

# Initialize database (run after first start)
docker compose exec web python /opt/scripts/init_db.py

# View logs
docker compose logs -f web

# Stop containers
docker compose down
```

### Local Development
```bash
# Run the web application directly (requires PostgreSQL running)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Run MOV converter service separately
python mov_converter_service.py

# Generate thumbnails for existing videos
python generate_thumbnails.py
```

### Database Setup
The application expects a PostgreSQL database with these credentials (from README.md):
```sql
create database fastapi;
create user fastapi with password '123456';
alter database fastapi owner to fastapi;
grant all privileges on all tables in schema public to fastapi;
grant all privileges on all sequences in schema public to fastapi;
alter default privileges in schema public grant all on tables to fastapi;
alter default privileges in schema public grant all on sequences to fastapi;
```

## Architecture

### Core Components

**main.py** - Main FastAPI application containing:
- Video and image upload endpoints with multi-file support (max 10 files)
- Category management system (create, delete, filter by category)
- Authentication via cookie-based sessions
- Thumbnail generation for videos and images
- Video orientation detection and rotation handling using pymediainfo and ffmpeg
- Pagination for video/image lists
- API endpoints for AJAX requests (`/api/videos`, `/api/images`, `/api/video-metadata/{filename}`)

**mov_converter_service.py** - Background service that:
- Continuously scans `static/videos/` for .MOV files every 5 seconds
- Converts .MOV to .MP4 using ffmpeg with rotation correction
- Preserves video quality (H.264, CRF 23, AAC audio)
- Updates database records to reflect new filenames after conversion
- Automatically removes original .MOV files after successful conversion

**auth.py** - Simple authentication module:
- Cookie-based session management using itsdangerous
- Hard-coded credentials (admin/admin) - stored in `users` dict
- `get_current_user()` - returns username or None
- `require_login()` - dependency that raises 403 if not authenticated

**scripts/init_db.py** - Database initialization:
- Creates tables: `categories`, `image_categories`, `video_categories`
- Ensures "All" category (id=0) exists

### Database Schema

SQLAlchemy models defined in main.py:
- **Category**: id (PK), name
- **ImageCategory**: filename (PK), category_id (FK)
- **VideoCategory**: filename (PK), category_id (FK)

Database connection via `DATABASE_URL` environment variable, defaults to PostgreSQL.

### Video Orientation Handling

The application has sophisticated video orientation detection:
- Uses `pymediainfo` to detect video dimensions and rotation metadata
- Determines if video is portrait/landscape/square after accounting for rotation
- Frontend (`templates/videos.html`) uses rotation metadata to display videos correctly
- Rotation is NOT applied during upload to preserve original metadata
- The `mov_converter_service.py` applies rotation correction during .MOV to .MP4 conversion

### File Organization

```
static/
  videos/       - Uploaded video files (MP4, MOV, AVI, MKV)
  images/       - Uploaded image files (PNG, JPG, JPEG, GIF)
  thumbnails/   - Auto-generated thumbnails (320x240 with white borders)
templates/      - Jinja2 HTML templates
scripts/        - Database initialization and utility scripts
```

### Key Features

1. **Multi-file Upload**: Supports up to 10 files per upload with validation
2. **Automatic Thumbnails**: Generated at 3-second mark for videos, EXIF rotation for images
3. **Category System**: User-defined categories, special "All" category (id=0) for uncategorized items
4. **Pagination**: Configurable items per page
5. **AJAX APIs**: Client-side loading for better UX
6. **Rotation Handling**: Detects and corrects iPhone portrait videos

## Dependencies

Core packages (from requirements.txt):
- fastapi==0.116.1
- uvicorn==0.35.0
- jinja2==3.1.6
- SQLAlchemy==2.0.43
- psycopg2-binary==2.9.10
- Pillow==11.3.0
- pymediainfo==7.0.1
- itsdangerous==2.2.0

External tools:
- FFmpeg (required for video processing and thumbnail generation)

## Important Notes

### Video Processing
- The application does NOT fix rotation during upload to preserve original metadata
- Frontend handles rotation display using CSS transforms based on metadata
- Background converter service applies rotation during .MOV to .MP4 conversion
- Rotation detection uses both `stream_tags=rotate` and `stream_side_data=rotation`

### Authentication
- Very basic authentication system with hard-coded credentials in auth.py
- Session cookies use SECRET_KEY from auth.py
- All video/image management routes require authentication

### File Naming
- Uploaded files are renamed with timestamp suffix: `filename_1766125654.ext`
- Thumbnails for videos: `{base_filename}.jpg`
- Thumbnails for images: `thumb_{filename}`

### Database Migrations
- No migration system - schema defined in SQLAlchemy models
- Run `init_db.py` to create tables on first deployment

### Deployment
- Application exposed on port 8001 (mapped from container port 8000)
- Requires external network `infra_net` for database access
- Uses external PostgreSQL instance (postgres5444:5432)
