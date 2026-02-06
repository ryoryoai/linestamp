"""緑フリンジ除去機能をテストするスクリプト"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from PIL import Image
from generate_stamp import (
    apply_strict_transparency,
    evaluate_transparency_quality,
    split_grid_image,
    QUALITY_CONFIG_STRICT,
    TRANSPARENCY_CONFIG_DEFAULT,
)


def test_single_stamp(stamp_path: str, output_path: str = None):
    """単一スタンプに新しい透過処理を適用してテスト"""
    print(f"\nProcessing: {stamp_path}")

    # グリッドセルを読み込み（既存の透過済み画像ではなく、グリッドから切り出す）
    img = Image.open(stamp_path).convert("RGBA")

    # 新しい透過処理を適用
    processed, bg = apply_strict_transparency(img, TRANSPARENCY_CONFIG_DEFAULT, QUALITY_CONFIG_STRICT)

    # QCチェック（緑背景を明示的に指定）
    bg_green = (0, 255, 0)
    qc_result = evaluate_transparency_quality(processed, bg_green, QUALITY_CONFIG_STRICT)

    print(f"  QC OK: {qc_result['ok']}")
    print(f"  Green fringe: {qc_result.get('green_fringe_count', 'N/A')}")
    print(f"  BG remain: {qc_result['bg_remain_pct']:.4f}%")

    if output_path:
        processed.save(output_path, "PNG")
        print(f"  Saved: {output_path}")

    return qc_result


def main():
    grid_dir = Path(r"F:\projects\linestamp\output\kimikimi_home_20250203")
    output_dir = grid_dir / "transparency_fixed"
    output_dir.mkdir(exist_ok=True)

    print("=" * 70)
    print("Testing Green Fringe Removal")
    print("=" * 70)

    # グリッド画像から再分割して透過処理
    grid_files = [grid_dir / "grid_1.png", grid_dir / "grid_2.png"]

    all_results = []
    stamp_idx = 1

    for grid_file in grid_files:
        if not grid_file.exists():
            print(f"Grid not found: {grid_file}")
            continue

        print(f"\n--- Processing {grid_file.name} ---")
        grid_img = Image.open(grid_file).convert("RGBA")
        stamps = split_grid_image(grid_img, rows=3, cols=4, clean_edges=True)

        for i, cell in enumerate(stamps):
            out_path = output_dir / f"{stamp_idx:02d}.png"

            # 新しい透過処理を適用
            processed, bg = apply_strict_transparency(cell, TRANSPARENCY_CONFIG_DEFAULT, QUALITY_CONFIG_STRICT)

            # QCチェック（緑背景を明示的に指定）
            bg_green = (0, 255, 0)
            qc_result = evaluate_transparency_quality(processed, bg_green, QUALITY_CONFIG_STRICT)

            status = "OK" if qc_result["ok"] else "NG"
            fringe = qc_result.get("green_fringe_count", 0)

            if not qc_result["ok"] or fringe > 0:
                print(f"  [{stamp_idx:02d}] {status} - fringe={fringe}")

            processed.save(out_path, "PNG")
            all_results.append({"idx": stamp_idx, "ok": qc_result["ok"], "fringe": fringe})
            stamp_idx += 1

    # サマリー
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in all_results if r["ok"])
    total_fringe = sum(r["fringe"] for r in all_results)
    failed = [r["idx"] for r in all_results if not r["ok"]]

    print(f"Total stamps: {len(all_results)}")
    print(f"QC Passed: {passed}/{len(all_results)}")
    print(f"QC Failed: {failed if failed else 'None'}")
    print(f"Total green fringe: {total_fringe}")
    print(f"\nOutput saved to: {output_dir}")


if __name__ == "__main__":
    main()
