import os
from PIL import Image, ExifTags

IMAGE_DIR = '/home/sonthl/setup/docker/media-lite/static/images'
THUMBNAIL_DIR = '/home/sonthl/setup/docker/media-lite/static/thumbnails'

os.makedirs(THUMBNAIL_DIR, exist_ok=True)

# Xóa thumbnail cũ
for filename in os.listdir(THUMBNAIL_DIR):
    if filename.startswith('thumb_'):
        os.remove(os.path.join(THUMBNAIL_DIR, filename))
        print(f"Deleted old thumbnail: {filename}")

# Tạo lại thumbnail với tỷ lệ 4:3, thu nhỏ và padding trắng
for filename in os.listdir(IMAGE_DIR):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        image_path = os.path.join(IMAGE_DIR, filename)
        thumbnail_path = os.path.join(THUMBNAIL_DIR, f"thumb_{filename}")
        try:
            with Image.open(image_path) as img:
                # Xử lý metadata EXIF để xoay ảnh đúng hướng
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

                # Thu nhỏ ảnh để vừa khung 320x240, giữ tỷ lệ gốc
                img.thumbnail((320, 240), Image.Resampling.LANCZOS)
                width, height = img.size

                # Tạo ảnh mới với nền trắng, kích thước 320x240
                new_img = Image.new("RGB", (320, 240), (255, 255, 255))
                # Dán ảnh gốc vào giữa
                offset = ((320 - width) // 2, (240 - height) // 2)
                new_img.paste(img, offset)

                # Lưu thumbnail
                new_img.save(thumbnail_path, "JPEG", quality=85)
            print(f"Thumbnail created for {filename}")
        except Exception as e:
            print(f"Error creating thumbnail for {filename}: {str(e)}")