"""The app icon (blue magnifier, same as the floating symbol), drawn with Pillow."""

from PIL import Image, ImageDraw

COLOR = (37, 99, 235, 255)  # matches bubble.COLOR


def icon_image(size: int = 256) -> Image.Image:
    scale = 4  # draw large, then downsample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, s - 1, s - 1), fill=COLOR)
    cx = cy = s * 0.44
    r = s * 0.19
    w = max(1, int(s * 0.07))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline="white", width=w)
    d.line((cx + r * 0.72, cy + r * 0.72, s * 0.74, s * 0.74), fill="white",
           width=int(w * 1.4))
    return img.resize((size, size), Image.LANCZOS)


def write_ico(path) -> None:
    icon_image(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                      (128, 128), (256, 256)])
