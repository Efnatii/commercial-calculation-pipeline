from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "docs" / "codex-ui" / "assets"
ICON_DIR = ASSETS_DIR / "icon-pack"
CANVAS_SIZE = 256
INNER_SIZE = 210


@dataclass(frozen=True)
class IconSource:
    name: str
    filename: str


DEFAULT_SOURCES = [
    IconSource("bridge", "ig_0a3909d77a932cf2016a1288ef9b68819180f8d00058beb10e.png"),
    IconSource("lan-lock", "ig_0a3909d77a932cf2016a12891f72d081918d4943b8df519078.png"),
    IconSource("token", "ig_0a3909d77a932cf2016a128959499c81919435d1201a7e9267.png"),
    IconSource("workspace", "ig_0a3909d77a932cf2016a12899345788191a09c4a633d75079a.png"),
    IconSource("terminal", "ig_0a3909d77a932cf2016a1289c8b28c8191bbdee0d6c670903d.png"),
    IconSource("run", "ig_0a3909d77a932cf2016a1289efce9c8191a6f61bc5d5852ec0.png"),
    IconSource("stop", "ig_0a3909d77a932cf2016a128a316a9081919748cc054237a439.png"),
    IconSource("pages", "ig_0a3909d77a932cf2016a128a6c67e0819198baf9d3c4f49014.png"),
    IconSource("host", "ig_0a3909d77a932cf2016a128a9346f481919bcf0167b9bea98a.png"),
    IconSource("denied", "ig_0a3909d77a932cf2016a128ab271348191a578bb2b868ee906.png"),
    IconSource("health", "ig_0a3909d77a932cf2016a128b38e4ac8191a38df3cd9f148024.png"),
    IconSource("audit", "ig_0a3909d77a932cf2016a128b7ca104819196fe0ee16177efd9.png"),
    IconSource("settings", "ig_0a3909d77a932cf2016a128bbe1d5081919e598a9b640d4e25.png"),
    IconSource("restart", "ig_0a3909d77a932cf2016a128cbf581c8191aba175da108683eb.png"),
    IconSource("tray", "ig_0a3909d77a932cf2016a128c405b588191abcb6c130101bf04.png"),
    IconSource("client", "ig_0a3909d77a932cf2016a128c971dec8191a9a929c00eb74ad4.png"),
    IconSource("eye", "ig_05c1e395f183a7a4016a12e1a8f17081919008180ac4893562.png"),
]


def color_distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    return math.sqrt(sum((int(a[i]) - int(b[i])) ** 2 for i in range(3)))


def edge_samples(image: Image.Image) -> list[tuple[int, int, int, int]]:
    width, height = image.size
    pixels = image.load()
    samples = []
    for x in range(0, width, max(1, width // 32)):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(0, height, max(1, height // 32)):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])
    return samples


def dominant_edge_color(image: Image.Image) -> tuple[int, int, int, int]:
    samples = edge_samples(image)
    channels = []
    for channel in range(4):
        values = sorted(sample[channel] for sample in samples)
        channels.append(values[len(values) // 2])
    return tuple(channels)  # type: ignore[return-value]


def remove_connected_background(image: Image.Image, tolerance: int = 48) -> Image.Image:
    image = image.convert("RGBA")
    width, height = image.size
    bg = dominant_edge_color(image)
    pixels = image.load()
    visited = bytearray(width * height)
    stack: list[tuple[int, int]] = []

    def enqueue(x: int, y: int) -> None:
        idx = y * width + x
        if visited[idx]:
            return
        if color_distance(pixels[x, y], bg) <= tolerance:
            visited[idx] = 1
            stack.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)

    while stack:
        x, y = stack.pop()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height:
                enqueue(nx, ny)

    output = image.copy()
    out = output.load()
    remove_chroma_globally = bg[0] > 150 and bg[1] < 130 and bg[2] > 140
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            is_chroma_shadow = (
                remove_chroma_globally
                and pixel[0] > 80
                and pixel[1] < 100
                and pixel[2] > 80
                and pixel[0] - pixel[1] > 25
                and pixel[2] - pixel[1] > 25
            )
            if visited[y * width + x] or (remove_chroma_globally and color_distance(pixel, bg) <= 96) or is_chroma_shadow:
                out[x, y] = (255, 255, 255, 0)
    return output


def trim_and_center(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError("source image has no foreground after background removal")
    cropped = image.crop(bbox)
    cropped.thumbnail((INNER_SIZE, INNER_SIZE), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
    x = (CANVAS_SIZE - cropped.width) // 2
    y = (CANVAS_SIZE - cropped.height) // 2
    canvas.alpha_composite(cropped, (x, y))
    return canvas


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_sheet(icons: dict[str, Image.Image]) -> Image.Image:
    cell = 260
    title = 78
    columns = 4
    rows = math.ceil(len(icons) / columns)
    sheet = Image.new("RGBA", (cell * columns, title + cell * rows), (247, 250, 253, 255))
    draw = ImageDraw.Draw(sheet)
    title_font = load_font(24, bold=True)
    label_font = load_font(15)
    draw.text((24, 22), "Codex Bridge Imagegen Icon Pack", fill=(20, 32, 48, 255), font=title_font)
    draw.text((24, 50), "AI-generated source icons normalized to transparent 256x256 PNG", fill=(82, 100, 122, 255), font=load_font(13))
    for index, (name, icon) in enumerate(icons.items()):
        row, col = divmod(index, columns)
        x = col * cell
        y = title + row * cell
        draw.rounded_rectangle(
            (x + 16, y + 16, x + cell - 16, y + cell - 16),
            radius=16,
            fill=(255, 255, 255, 255),
            outline=(209, 223, 236, 255),
            width=2,
        )
        preview = icon.resize((160, 160), Image.Resampling.LANCZOS)
        sheet.alpha_composite(preview, (x + 50, y + 38))
        bounds = draw.textbbox((0, 0), name, font=label_font)
        draw.text((x + (cell - (bounds[2] - bounds[0])) / 2, y + 210), name, fill=(20, 32, 48, 255), font=label_font)
    return sheet


def make_contact_sheet(source_dir: Path, output_path: Path) -> None:
    cell = 260
    title = 42
    columns = 4
    rows = math.ceil(len(DEFAULT_SOURCES) / columns)
    sheet = Image.new("RGBA", (cell * columns, title + cell * rows), (247, 250, 253, 255))
    draw = ImageDraw.Draw(sheet)
    draw.text((20, 12), "Imagegen sources used for Codex Bridge icon pack", fill=(20, 32, 48, 255), font=load_font(18, bold=True))
    for index, source in enumerate(DEFAULT_SOURCES):
        row, col = divmod(index, columns)
        x = col * cell
        y = title + row * cell
        image = Image.open(source_dir / source.filename).convert("RGBA")
        image.thumbnail((184, 184), Image.Resampling.LANCZOS)
        draw.rounded_rectangle((x + 12, y + 12, x + cell - 12, y + cell - 12), radius=14, fill=(255, 255, 255, 255), outline=(209, 223, 236, 255))
        sheet.alpha_composite(image, (x + (cell - image.width) // 2, y + 28))
        label = source.name
        bounds = draw.textbbox((0, 0), label, font=load_font(14))
        draw.text((x + (cell - (bounds[2] - bounds[0])) / 2, y + 216), label, fill=(20, 32, 48, 255), font=load_font(14))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def process(source_dir: Path) -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    icons: dict[str, Image.Image] = {}
    for source in DEFAULT_SOURCES:
        source_path = source_dir / source.filename
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        image = Image.open(source_path)
        cleaned = trim_and_center(remove_connected_background(image))
        output = ICON_DIR / f"{source.name}.png"
        cleaned.save(output)
        icons[source.name] = cleaned

    make_sheet(icons).save(ICON_DIR / "codex-bridge-icon-pack-sheet.png")
    make_contact_sheet(source_dir, ICON_DIR / "codex-bridge-imagegen-sources-sheet.png")

    bridge = icons["bridge"]
    for size in (16, 32, 48, 64, 128, 256):
        bridge.resize((size, size), Image.Resampling.LANCZOS).save(ASSETS_DIR / f"codex-bridge-icon-{size}.png")
    bridge.save(ASSETS_DIR / "codex-bridge-logo.png")
    bridge.save(ASSETS_DIR / "codex-bridge.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize imagegen-generated Codex Bridge icons into project assets.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path(r"C:\Users\Efnatii\Workspaces\__EGOR_GOROKHOVITSKY_WORKBENCH__\.codex\generated_images\019e5707-e693-71c0-af58-42da482e90b7"),
    )
    args = parser.parse_args()
    process(args.source_dir)
    print(f"processed {len(DEFAULT_SOURCES)} imagegen icons into {ICON_DIR}")


if __name__ == "__main__":
    main()
