import os
import time
import subprocess
import json
from pathlib import Path

VIDEO_DIR = "static/videos"
THUMBNAIL_DIR = "static/thumbnails"
CHECK_INTERVAL = 5  # seconds

def get_video_rotation(video_path):
    """Extract rotation metadata from video."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream_tags=rotate:stream_side_data=rotation',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                stream = streams[0]
                tags = stream.get('tags', {})
                if 'rotate' in tags:
                    return int(tags['rotate'])
                if 'side_data_list' in stream:
                    for side_data in stream['side_data_list']:
                        if 'rotation' in side_data:
                            return int(side_data['rotation'])
        return 0
    except Exception as e:
        print(f"Error getting rotation: {str(e)}")
        return 0

def convert_mov_to_mp4(mov_path, mp4_path):
    try:
        print(f"Starting conversion with rotation fix: {mov_path} -> {mp4_path}")

        # Detect rotation (có thể là 90, -90, 270, 180)
        rotation = get_video_rotation(mov_path)
        print(f"Detected rotation metadata: {rotation} degrees")
        
        # Detect dimensions gốc
        probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', mov_path]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        data = json.loads(probe_result.stdout)
        width = data['streams'][0]['width']
        height = data['streams'][0]['height']
        print(f"Original dimensions: {width}x{height} (usually landscape for iPhone portrait)")
        
        # Logic xoay: iPhone portrait thường width > height + rotation = 90 hoặc -90
        transpose_filter = ""
        if rotation in [90, -90, 270, 180] or width > height:  # Force cho portrait
            if rotation in [90, -90]:
                transpose_filter = "transpose=1"  # Clockwise 90° - đúng cho hầu hết iPhone quay dọc (home button phải)
                print("Applying transpose=1 (clockwise 90°)")
            elif rotation == 270:
                transpose_filter = "transpose=2"  # Counter-clockwise
                print("Applying transpose=2")
            elif rotation == 180:
                transpose_filter = "hflip,vflip"
            else:
                transpose_filter = "transpose=1"  # Force mặc định
        
        # Build lệnh ffmpeg
        cmd = ['ffmpeg', '-i', mov_path]
        if transpose_filter:
            cmd += ['-vf', transpose_filter]
        
        cmd += [
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-metadata:s:v:0', 'rotate=0',  # Xóa metadata
            '-y',  # Overwrite
            mp4_path
        ]
        
        subprocess.run(cmd, check=True)
        print(f"Conversion and rotation fix completed: {mp4_path}")
        return True
        
    except Exception as e:
        print(f"Error during conversion/rotation: {str(e)}")
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
