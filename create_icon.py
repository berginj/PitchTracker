#!/usr/bin/env python
"""Generate application icon for PitchTracker."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a simple but professional icon for PitchTracker."""

    # Create directory
    os.makedirs("assets", exist_ok=True)

    # Create a 256x256 base image
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Color scheme - Blue matching launcher UI
    bg_color = (33, 150, 243)  # #2196F3 (Material Blue)
    accent_color = (255, 255, 255)  # White

    # Draw rounded rectangle background
    margin = 20
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=30,
        fill=bg_color
    )

    # Draw baseball/tracking elements
    # Draw a baseball trajectory arc
    center_x = size // 2
    center_y = size // 2

    # Baseball at the end of trajectory
    ball_radius = 25
    ball_x = center_x + 60
    ball_y = center_y - 40
    draw.ellipse(
        [ball_x - ball_radius, ball_y - ball_radius,
         ball_x + ball_radius, ball_y + ball_radius],
        fill=accent_color
    )

    # Stitching on baseball
    stitch_color = (200, 200, 200)
    draw.arc(
        [ball_x - ball_radius + 5, ball_y - ball_radius + 5,
         ball_x + ball_radius - 5, ball_y + ball_radius - 5],
        start=-45, end=135, fill=stitch_color, width=3
    )
    draw.arc(
        [ball_x - ball_radius + 5, ball_y - ball_radius + 5,
         ball_x + ball_radius - 5, ball_y + ball_radius - 5],
        start=135, end=315, fill=stitch_color, width=3
    )

    # Draw trajectory path (dotted line)
    path_points = []
    for i in range(8):
        t = i / 7.0
        x = margin + 40 + t * (ball_x - margin - 40)
        # Quadratic curve for trajectory
        y = size - margin - 40 - t * 60 + (t * t) * 80
        path_points.append((x, y))

    # Draw dots along trajectory
    for point in path_points:
        dot_size = 5
        draw.ellipse(
            [point[0] - dot_size, point[1] - dot_size,
             point[0] + dot_size, point[1] + dot_size],
            fill=accent_color
        )

    # Draw "PT" text at bottom
    try:
        # Try to use a nice font
        font_size = 60
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        # Fallback to default font
        font = ImageFont.load_default()

    text = "PT"
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    text_x = (size - text_width) // 2 - 10
    text_y = size - margin - text_height - 20

    draw.text((text_x, text_y), text, fill=accent_color, font=font)

    # Save as ICO with multiple sizes
    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []

    for icon_size in icon_sizes:
        resized = img.resize(icon_size, Image.Resampling.LANCZOS)
        images.append(resized)

    # Save as .ico
    ico_path = "assets/icon.ico"
    images[0].save(
        ico_path,
        format='ICO',
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:]
    )

    print(f"Created icon: {ico_path}")
    print(f"  Sizes: {', '.join(f'{s[0]}x{s[1]}' for s in icon_sizes)}")

    # Also save as PNG for preview
    png_path = "assets/icon.png"
    img.save(png_path, format='PNG')
    print(f"Created preview: {png_path}")

    return ico_path

if __name__ == "__main__":
    create_icon()
