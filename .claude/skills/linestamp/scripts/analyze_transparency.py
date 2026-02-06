"""透過品質分析スクリプト - 出力画像の透過状態を詳細に分析"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from generate_stamp import (
    evaluate_transparency_quality,
    QUALITY_CONFIG_STRICT,
    _dominant_bg_from_band,
    TRANSPARENCY_CONFIG_DEFAULT,
)


def analyze_stamp(img_path: str, original_bg: tuple = (0, 255, 0)) -> dict:
    """単一スタンプの透過品質を分析

    Args:
        img_path: 画像パス
        original_bg: 元の背景色（透過処理前）。デフォルトは緑 #00FF00
    """
    img = Image.open(img_path).convert("RGBA")
    pixels = img.load()
    w, h = img.size

    total = w * h
    transparent = 0
    opaque = 0
    semi_transparent = 0
    green_pixels = 0
    bright_green = 0

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                transparent += 1
            elif a == 255:
                opaque += 1
            else:
                semi_transparent += 1

            # 緑っぽいピクセル検出
            if a > 0:
                if g > 150 and g > r + 30 and g > b + 30:
                    green_pixels += 1
                if g >= 200 and (g - max(r, b)) >= 100:
                    bright_green += 1

    # 元の背景色（緑）を使用して evaluate_transparency_quality を実行
    # 注: 透過済み画像では端から検出すると誤検出するため、明示的に指定
    bg = original_bg
    qc_result = evaluate_transparency_quality(img, bg, QUALITY_CONFIG_STRICT)

    return {
        "size": f"{w}x{h}",
        "total_pixels": total,
        "transparent": transparent,
        "transparent_pct": round(transparent / total * 100, 2),
        "opaque": opaque,
        "opaque_pct": round(opaque / total * 100, 2),
        "semi_transparent": semi_transparent,
        "semi_pct": round(semi_transparent / total * 100, 2),
        "green_pixels": green_pixels,
        "green_pct": round(green_pixels / total * 100, 4),
        "bright_green": bright_green,
        "bright_green_pct": round(bright_green / total * 100, 4),
        "qc_ok": qc_result["ok"],
        "qc_bg_remain_pct": round(qc_result["bg_remain_pct"], 4),
        "qc_semi_pct": round(qc_result["semi_pct"], 4),
        "qc_bottom_green_pct": round(qc_result["bottom_green_pct"], 4),
        "qc_stray_top_white": qc_result["stray_top_white_px"],
        "qc_outline_white_pct": round(qc_result["outline_white_pct"], 2),
        "qc_green_fringe": qc_result.get("green_fringe_count", 0),  # 新規追加
    }


def main():
    output_dir = Path(r"F:\projects\linestamp\output\kimikimi_home_20250203")

    print("=" * 70)
    print("Transparency Quality Analysis")
    print("=" * 70)

    # 全24スタンプを分析
    all_results = []
    failed = []

    for i in range(1, 25):
        img_path = output_dir / f"{i:02d}.png"
        if not img_path.exists():
            print(f"  {i:02d}.png: NOT FOUND")
            continue

        result = analyze_stamp(str(img_path))
        all_results.append((i, result))

        status = "OK" if result["qc_ok"] else "NG"
        if not result["qc_ok"]:
            failed.append(i)

        # 問題があるものだけ詳細表示
        if result["green_pixels"] > 0 or result["semi_transparent"] > 0 or not result["qc_ok"]:
            print(f"\n[{i:02d}.png] {status}")
            print(f"  Size: {result['size']}")
            print(f"  Transparent: {result['transparent_pct']:.1f}%")
            print(f"  Semi-trans: {result['semi_transparent']} px ({result['semi_pct']:.2f}%)")
            print(f"  Green pixels: {result['green_pixels']} ({result['green_pct']:.4f}%)")
            print(f"  Bright green: {result['bright_green']} ({result['bright_green_pct']:.4f}%)")
            print(f"  QC: bg_remain={result['qc_bg_remain_pct']:.4f}%, bottom_green={result['qc_bottom_green_pct']:.4f}%")
            print(f"  QC: outline_white={result['qc_outline_white_pct']:.1f}%, stray_top={result['qc_stray_top_white']}")
            print(f"  QC: green_fringe={result['qc_green_fringe']} (max=0)")  # 新規追加

    # サマリー
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    total_green = sum(r["green_pixels"] for _, r in all_results)
    total_semi = sum(r["semi_transparent"] for _, r in all_results)
    passed = len([r for _, r in all_results if r["qc_ok"]])

    print(f"Total stamps analyzed: {len(all_results)}")
    print(f"QC Passed: {passed}/{len(all_results)}")
    print(f"QC Failed: {failed if failed else 'None'}")
    print(f"Total green pixels: {total_green}")
    print(f"Total semi-transparent: {total_semi}")

    # グリッド画像も分析
    print("\n" + "-" * 70)
    print("GRID IMAGES (for reference)")
    print("-" * 70)

    for grid_name in ["grid_1.png", "grid_2.png"]:
        grid_path = output_dir / grid_name
        if grid_path.exists():
            img = Image.open(grid_path).convert("RGBA")
            pixels = img.load()
            w, h = img.size
            transparent = sum(1 for y in range(h) for x in range(w) if pixels[x, y][3] == 0)
            print(f"{grid_name}: {w}x{h}, transparent={transparent}/{w*h} ({transparent/(w*h)*100:.1f}%)")


if __name__ == "__main__":
    main()
