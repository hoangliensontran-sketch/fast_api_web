#!/usr/bin/env python3
"""
Fix video rotation by re-encoding videos with rotation metadata.
This script detects rotation metadata and applies it to the video stream itself.
"""

import subprocess
import json
import os
import sys
from pathlib import Path

VIDEO_DIR = "static/videos"
THUMBNAIL_DIR = "static/thumbnails"

def get_video_rotation(video_path):
    """Extract rotation metadata from video."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height:stream_tags=rotate:stream_side_data=rotation',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                stream = streams[0]
                width = stream.get('width', 0)
                height = stream.get('height', 0)

                # Check stream tags first
                tags = stream.get('tags', {})
                if 'rotate' in tags:
                    return int(tags['rotate']), width, height

                # Check side_data_list as fallback
                if 'side_data_list' in stream:
                    for side_data in stream['side_data_list']:
                        if 'rotation' in side_data:
                            return int(side_data['rotation']), width, height

        return 0, 0, 0
    except Exception as e:
        print(f"Error getting rotation for {video_path}: {str(e)}")
        return 0, 0, 0

def fix_video_rotation(video_path, rotation):
    """Re-encode video with rotation applied to the stream."""
    try:
        temp_output = video_path + '.rotated.mp4'

        # Determine FFmpeg filter based on rotation
        # transpose values: 0=90° counterclockwise, 1=90° clockwise, 2=90° counterclockwise and vertical flip, 3=90° clockwise and vertical flip
        # For rotation metadata: positive = counterclockwise, negative = clockwise
        if rotation == 90 or rotation == -270:
            # 90° counterclockwise
            vf_filter = 'transpose=2'  # 90° counterclockwise
        elif rotation == -90 or rotation == 270:
            # 90° clockwise (this is your case)
            vf_filter = 'transpose=1'  # 90° clockwise
        elif rotation == 180 or rotation == -180:
            # 180°
            vf_filter = 'transpose=1,transpose=1'  # Two 90° rotations
        else:
            print(f"Unsupported rotation: {rotation}")
            return False

        # Re-encode video with rotation applied
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
            '-metadata:s:v:0', 'rotate=0',  # Remove rotation metadata
            '-y',
            temp_output
        ]

        print(f"Re-encoding {video_path} with rotation {rotation}...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(temp_output):
            # Replace original with rotated version
            os.replace(temp_output, video_path)
            print(f"✓ Successfully fixed rotation for {video_path}")
            return True
        else:
            print(f"✗ Failed to fix rotation: {result.stderr}")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False

    except Exception as e:
        print(f"Error fixing rotation for {video_path}: {str(e)}")
        return False

def regenerate_thumbnail(video_path, thumbnail_path):
    """Regenerate thumbnail after rotation fix."""
    try:
        temp_path = thumbnail_path + '.tmp.jpg'
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', '00:00:03',
            '-vframes', '1',
            '-q:v', '2',
            '-y',
            temp_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Resize with white padding
        from PIL import Image
        with Image.open(temp_path) as img:
            new_img = Image.new("RGB", (320, 240), (255, 255, 255))
            img.thumbnail((320, 240), Image.Resampling.LANCZOS)
            width, height = img.size
            offset = ((320 - width) // 2, (240 - height) // 2)
            new_img.paste(img, offset)
            new_img.save(thumbnail_path, "JPEG", quality=85)

        os.remove(temp_path)
        print(f"✓ Regenerated thumbnail for {video_path}")
        return True
    except Exception as e:
        print(f"Error regenerating thumbnail: {str(e)}")
        return False

def main():
    if len(sys.argv) > 1:
        # Fix specific video
        filename = sys.argv[1]
        video_path = os.path.join(VIDEO_DIR, filename)

        if not os.path.exists(video_path):
            print(f"Error: Video not found: {video_path}")
            return

        rotation, width, height = get_video_rotation(video_path)
        print(f"Video: {filename}")
        print(f"  Dimensions: {width}x{height}")
        print(f"  Rotation: {rotation}°")

        if rotation != 0:
            if fix_video_rotation(video_path, rotation):
                # Regenerate thumbnail
                base, ext = os.path.splitext(filename)
                thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{base}.jpg")
                regenerate_thumbnail(video_path, thumbnail_path)
        else:
            print("No rotation metadata found - video is already correct")
    else:
        # Scan all videos
        print("Scanning all videos for rotation metadata...\n")
        videos_to_fix = []

        for filename in os.listdir(VIDEO_DIR):
            if filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                video_path = os.path.join(VIDEO_DIR, filename)
                rotation, width, height = get_video_rotation(video_path)

                if rotation != 0:
                    videos_to_fix.append((filename, video_path, rotation, width, height))
                    print(f"Found: {filename} - {width}x{height} - Rotation: {rotation}°")

        if not videos_to_fix:
            print("No videos with rotation metadata found.")
            return

        print(f"\nFound {len(videos_to_fix)} video(s) that need rotation fix.")
        response = input("Fix all these videos? (y/n): ")

        if response.lower() == 'y':
            for filename, video_path, rotation, width, height in videos_to_fix:
                print(f"\n--- Processing {filename} ---")
                if fix_video_rotation(video_path, rotation):
                    base, ext = os.path.splitext(filename)
                    thumbnail_path = os.path.join(THUMBNAIL_DIR, f"{base}.jpg")
                    regenerate_thumbnail(video_path, thumbnail_path)

if __name__ == "__main__":
    main()
