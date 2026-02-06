"""緑残りピクセルを可視化するスクリプト"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image, ImageDraw


def detect_green_pixels(img: Image.Image, threshold: dict = None) -> list:
    """緑っぽいピクセルを検出して座標リストを返す"""
    if threshold is None:
        threshold = {
            "green_min": 150,      # G成分の最小値
            "green_gap": 30,       # G - max(R, B) の最小差
            "bright_green_min": 200,
            "bright_green_gap": 100,
        }

    pixels = img.load()
    w, h = img.size

    green_coords = []
    bright_green_coords = []

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue

            # 緑っぽい
            if g >= threshold["green_min"] and (g - max(r, b)) >= threshold["green_gap"]:
                green_coords.append((x, y, r, g, b, a))

            # 明らかな緑（背景緑に近い）
            if g >= threshold["bright_green_min"] and (g - max(r, b)) >= threshold["bright_green_gap"]:
                bright_green_coords.append((x, y, r, g, b, a))

    return green_coords, bright_green_coords


def visualize_green(img_path: str, output_path: str = None):
    """緑残りを赤でマーキングした画像を出力"""
    img = Image.open(img_path).convert("RGBA")
    green_coords, bright_green_coords = detect_green_pixels(img)

    if not green_coords and not bright_green_coords:
        print(f"  No green pixels detected")
        return None

    # マーキング用の画像を作成
    marked = img.copy()
    draw = ImageDraw.Draw(marked)

    # 緑っぽいピクセルを黄色でマーク
    for x, y, r, g, b, a in green_coords:
        draw.rectangle([x-1, y-1, x+1, y+1], outline=(255, 255, 0, 255))

    # 明らかな緑を赤でマーク
    for x, y, r, g, b, a in bright_green_coords:
        draw.rectangle([x-2, y-2, x+2, y+2], outline=(255, 0, 0, 255))

    if output_path:
        marked.save(output_path, "PNG")

    return {
        "green_count": len(green_coords),
        "bright_green_count": len(bright_green_coords),
        "green_samples": green_coords[:5],
        "bright_green_samples": bright_green_coords[:5],
    }


def main():
    output_dir = Path(r"F:\projects\linestamp\output\kimikimi_home_20250203")
    debug_dir = output_dir / "debug_green"
    debug_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("Green Pixel Detection - Detailed Analysis")
    print("=" * 70)

    total_green = 0
    total_bright = 0
    problem_stamps = []

    for i in range(1, 25):
        img_path = output_dir / f"{i:02d}.png"
        if not img_path.exists():
            continue

        output_path = debug_dir / f"{i:02d}_green_marked.png"
        result = visualize_green(str(img_path), str(output_path))

        if result:
            total_green += result["green_count"]
            total_bright += result["bright_green_count"]

            if result["green_count"] > 0 or result["bright_green_count"] > 0:
                problem_stamps.append(i)
                print(f"\n[{i:02d}.png]")
                print(f"  Green pixels: {result['green_count']}")
                print(f"  Bright green: {result['bright_green_count']}")
                if result["green_samples"]:
                    print(f"  Sample coords: {[(x, y) for x, y, *_ in result['green_samples'][:3]]}")
                if result["bright_green_samples"]:
                    print(f"  Sample RGB: {[(r, g, b) for x, y, r, g, b, a in result['bright_green_samples'][:3]]}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total green pixels: {total_green}")
    print(f"Total bright green: {total_bright}")
    print(f"Problem stamps: {problem_stamps}")
    print(f"\nDebug images saved to: {debug_dir}")


if __name__ == "__main__":
    main()
