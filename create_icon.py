"""Create application icon for WF Firmware Uploader."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_icon():
    """Create a simple but professional icon for the application."""

    # Create multiple sizes for Windows ICO file
    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        # Create image with transparent background
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Color scheme - professional blue/white
        bg_color = (41, 128, 185)  # Professional blue
        text_color = (255, 255, 255)  # White
        accent_color = (52, 152, 219)  # Light blue

        # Draw rounded rectangle background
        margin = size // 10
        draw.rounded_rectangle(
            [(margin, margin), (size - margin, size - margin)],
            radius=size // 8,
            fill=bg_color,
            outline=accent_color,
            width=max(1, size // 32)
        )

        # Draw circuit board pattern (simplified)
        if size >= 64:
            # Draw connection lines
            line_width = max(1, size // 64)
            padding = size // 4

            # Horizontal lines
            draw.line([(padding, padding * 2), (size - padding, padding * 2)],
                     fill=accent_color, width=line_width)
            draw.line([(padding, size - padding * 2), (size - padding, size - padding * 2)],
                     fill=accent_color, width=line_width)

            # Vertical line
            draw.line([(size // 2, padding * 2), (size // 2, size - padding * 2)],
                     fill=accent_color, width=line_width)

            # Connection points (circles)
            dot_radius = max(2, size // 32)
            positions = [
                (padding, padding * 2),
                (size - padding, padding * 2),
                (size // 2, padding * 2),
                (size // 2, size // 2),
                (padding, size - padding * 2),
                (size - padding, size - padding * 2),
            ]

            for pos in positions:
                draw.ellipse(
                    [pos[0] - dot_radius, pos[1] - dot_radius,
                     pos[0] + dot_radius, pos[1] + dot_radius],
                    fill=text_color
                )

        # Draw "WF" text in the center
        if size >= 32:
            try:
                # Try to use a nice font, fallback to default if not available
                font_size = size // 3
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    font = ImageFont.load_default()

                text = "WF"

                # Get text bounding box
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                # Center the text
                text_x = (size - text_width) // 2
                text_y = (size - text_height) // 2 - bbox[1]

                # Draw text with shadow for depth
                if size >= 64:
                    shadow_offset = max(1, size // 64)
                    draw.text((text_x + shadow_offset, text_y + shadow_offset),
                             text, fill=(0, 0, 0, 128), font=font)

                draw.text((text_x, text_y), text, fill=text_color, font=font)

            except Exception as e:
                print(f"Font rendering issue for size {size}: {e}")
                # Fallback: just draw a simple shape
                center = size // 2
                rect_size = size // 4
                draw.rectangle(
                    [center - rect_size, center - rect_size,
                     center + rect_size, center + rect_size],
                    fill=text_color
                )

        images.append(img)

    # Save as ICO file with multiple sizes
    output_path = "assets/icon.ico"
    os.makedirs("assets", exist_ok=True)

    # Save ICO file
    images[0].save(
        output_path,
        format='ICO',
        sizes=[(s, s) for s in sizes]
    )

    print(f"Icon created successfully: {output_path}")
    print(f"Sizes included: {sizes}")

    # Also save a PNG version for preview
    images[0].save("assets/icon_256.png", format='PNG')
    print("PNG preview created: assets/icon_256.png")

if __name__ == "__main__":
    create_icon()
