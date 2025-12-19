import os
import subprocess

VIDEO_DIR = '/home/sonthl/setup/docker/media-lite/static/videos'
THUMBNAIL_DIR = '/home/sonthl/setup/docker/media-lite/static/thumbnails'

os.makedirs(THUMBNAIL_DIR, exist_ok=True)

for filename in os.listdir(VIDEO_DIR):
    if filename.endswith('.mp4'):
        video_path = os.path.join(VIDEO_DIR, filename)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, filename.replace('.mp4', '.jpg'))
        if not os.path.exists(thumbnail_path):
            try:
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-ss', '00:00:03',
                    '-vframes', '1',
                    '-q:v', '2',
                    '-s', '320x240',
                    thumbnail_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print(f"Thumbnail created for {filename}")
            except subprocess.CalledProcessError as e:
                print(f"Error creating thumbnail for {filename}: {e.stderr.decode()}")
            except FileNotFoundError:
                print("FFmpeg not found. Please ensure FFmpeg is installed.")
