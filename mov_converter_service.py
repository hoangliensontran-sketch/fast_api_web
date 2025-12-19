import os
import time
import subprocess
from pathlib import Path

VIDEO_DIR = "static/videos"
THUMBNAIL_DIR = "static/thumbnails"
CHECK_INTERVAL = 5  # seconds

def convert_mov_to_mp4(mov_path, mp4_path):
    try:
        print(f"Starting conversion: {mov_path} -> {mp4_path}")
        cmd = [
            'ffmpeg',
            '-i', mov_path,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-strict', 'experimental',
            '-movflags', '+faststart',
            mp4_path
        ]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Successfully converted: {mp4_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error converting {mov_path} to mp4: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("FFmpeg not found. Please ensure FFmpeg is installed.")
        return False
    except Exception as e:
        print(f"Error converting video: {str(e)}")
        return False

def scan_and_convert():
    """Continuously scan for .mov files and convert them to .mp4"""
    print(f"MOV converter service started. Scanning {VIDEO_DIR} every {CHECK_INTERVAL} seconds...")

    while True:
        try:
            if not os.path.exists(VIDEO_DIR):
                print(f"Video directory {VIDEO_DIR} does not exist. Waiting...")
                time.sleep(CHECK_INTERVAL)
                continue

            # Find all .mov files
            mov_files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith('.mov')]

            for mov_filename in mov_files:
                mov_path = os.path.join(VIDEO_DIR, mov_filename)
                base_name = os.path.splitext(mov_filename)[0]
                mp4_filename = f"{base_name}.mp4"
                mp4_path = os.path.join(VIDEO_DIR, mp4_filename)

                # Skip if mp4 already exists (conversion in progress or completed)
                if os.path.exists(mp4_path):
                    print(f"MP4 already exists for {mov_filename}, skipping...")
                    continue

                # Convert the file
                if convert_mov_to_mp4(mov_path, mp4_path):
                    # Verify the mp4 was created successfully
                    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 0:
                        print(f"Removing original .mov file: {mov_filename}")
                        os.remove(mov_path)

                        # Update database to reflect the new filename
                        try:
                            from sqlalchemy import create_engine
                            from sqlalchemy.orm import sessionmaker
                            from main import VideoCategory, DATABASE_URL

                            engine = create_engine(DATABASE_URL)
                            Session = sessionmaker(bind=engine)
                            with Session() as session:
                                # Check if there's a category association for the .mov file
                                vc = session.query(VideoCategory).filter(VideoCategory.filename == mov_filename).first()
                                if vc:
                                    # Update to the new .mp4 filename
                                    vc.filename = mp4_filename
                                    session.commit()
                                    print(f"Updated database: {mov_filename} -> {mp4_filename}")
                        except Exception as e:
                            print(f"Error updating database for {mov_filename}: {str(e)}")
                    else:
                        print(f"Conversion failed or produced empty file for {mov_filename}")
                else:
                    print(f"Failed to convert {mov_filename}")

        except Exception as e:
            print(f"Error in scan loop: {str(e)}")

        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    scan_and_convert()
