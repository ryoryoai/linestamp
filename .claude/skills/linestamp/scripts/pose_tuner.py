"""
LINEスタンプ生成スキル - ポーズ対話調整ツール

AIと対話しながらポーズ定義を調整し、1枚ずつテスト生成するツール
"""

import json
import sys
import base64
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

import yaml

from database import init_database, get_connection, get_pose, search_poses
from pose_manager import (
    POSES_DIR,
    export_pose_to_yaml,
    import_pose_from_yaml,
    _save_pose_to_db,
    list_yaml_poses,
)

# 出力ディレクトリ
OUTPUT_DIR = Path(__file__).parent.parent.parent.parent.parent / "output" / "pose_test"


class PoseTuner:
    """ポーズ対話調整クラス"""

    def __init__(self):
        init_database()

    def list_poses(self, source: str = "both") -> List[Dict]:
        """
        ポーズ一覧を取得

        Args:
            source: "db", "yaml", "both"
        """
        poses = []

        if source in ("db", "both"):
            db_poses = search_poses()
            for p in db_poses:
                p["source"] = "db"
                poses.append(p)

        if source in ("yaml", "both"):
            yaml_files = list(POSES_DIR.glob("*.yaml")) + list(POSES_DIR.glob("*.yml"))
            yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

            for yaml_file in yaml_files:
                try:
                    with open(yaml_file, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if data and data.get("name"):
                        # DBに同名のポーズがある場合はスキップ
                        if source == "both" and any(p["name"] == data["name"] for p in poses):
                            continue
                        data["source"] = "yaml"
                        data["yaml_path"] = str(yaml_file)
                        poses.append(data)
                except Exception:
                    pass

        return poses

    def load_pose(self, name: str) -> Optional[Dict]:
        """
        ポーズ定義を読み込み（DB優先、なければYAML）
        """
        # DB から取得
        pose = get_pose(name)
        if pose:
            # hints/avoid を JSON からパース
            if pose.get("hints"):
                try:
                    pose["hints"] = json.loads(pose["hints"])
                except (json.JSONDecodeError, TypeError):
                    pose["hints"] = [pose["hints"]]
            if pose.get("avoid"):
                try:
                    pose["avoid"] = json.loads(pose["avoid"])
                except (json.JSONDecodeError, TypeError):
                    pose["avoid"] = [pose["avoid"]]
            return pose

        # YAML から検索
        yaml_files = list(POSES_DIR.glob("*.yaml")) + list(POSES_DIR.glob("*.yml"))
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and data.get("name") == name:
                    data["yaml_path"] = str(yaml_file)
                    return data
            except Exception:
                pass

        return None

    def create_new_pose(self) -> Dict:
        """新規ポーズの雛形を作成"""
        return {
            "name": "",
            "name_en": "",
            "category": "",
            "gesture": "",
            "expression": "",
            "vibe": "",
            "hints": [],
            "avoid": [],
        }

    def save_pose(
        self,
        pose: Dict,
        to_yaml: bool = True,
        to_db: bool = True
    ) -> str:
        """
        ポーズを保存（YAML/DB 双方向同期）

        Returns:
            保存先のYAMLパス（to_yaml=Trueの場合）
        """
        yaml_path = None

        if to_yaml:
            # YAML に保存
            safe_name = (
                pose["name"]
                .replace(" ", "_")
                .replace("/", "_")
                .replace("（", "_")
                .replace("）", "")
            )
            yaml_path = POSES_DIR / f"{safe_name}.yaml"

            yaml_data = {
                "name": pose["name"],
            }

            if pose.get("name_en"):
                yaml_data["name_en"] = pose["name_en"]
            if pose.get("category"):
                yaml_data["category"] = pose["category"]

            # gesture/expression
            yaml_data["gesture"] = pose.get("gesture", pose.get("gesture_ja", ""))
            yaml_data["expression"] = pose.get("expression", pose.get("expression_ja", ""))

            if pose.get("vibe"):
                yaml_data["vibe"] = pose["vibe"]
            if pose.get("hints"):
                yaml_data["hints"] = pose["hints"]
            if pose.get("avoid"):
                yaml_data["avoid"] = pose["avoid"]

            yaml_path.parent.mkdir(parents=True, exist_ok=True)
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    yaml_data,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )

            yaml_path = str(yaml_path)

        if to_db:
            # DB に保存
            db_data = {
                "name": pose["name"],
                "name_en": pose.get("name_en"),
                "gesture": pose.get("gesture", pose.get("gesture_ja", "")),
                "expression": pose.get("expression", pose.get("expression_ja", "")),
                "vibe": pose.get("vibe"),
                "category": pose.get("category"),
                "hints": pose.get("hints"),
                "avoid": pose.get("avoid"),
            }
            _save_pose_to_db(db_data, yaml_path)

        return yaml_path

    def generate_prompt(self, pose: Dict) -> str:
        """
        ポーズ定義から生成用プロンプトを構築
        """
        gesture = pose.get("gesture", pose.get("gesture_ja", ""))
        expression = pose.get("expression", pose.get("expression_ja", ""))
        vibe = pose.get("vibe")

        # 統合プロンプト生成
        g = gesture.strip().rstrip('。')
        e = expression.strip().rstrip('。') if expression else ""

        prompt = f"{g}。{e}。" if e else f"{g}。"

        if vibe:
            prompt += f"（{vibe}）"

        return prompt

    def generate_single_stamp(
        self,
        pose: Dict,
        reference_image: str,
        emotion: str = "笑顔",
        text: str = "",
        style: str = "sd_25",
        output_path: str = None,
    ) -> str:
        """
        ポーズ定義から1枚のスタンプを生成（pose_locked用）

        Args:
            pose: ポーズ定義
            reference_image: 参照画像パス
            emotion: 感情
            text: スタンプテキスト
            style: スタイルID
            output_path: 出力パス（Noneなら自動生成）

        Returns:
            生成された画像のパス
        """
        import os
        from google import genai
        from google.genai import types
        from generate_stamp import (
            load_image_as_base64,
            CHIBI_STYLES,
            resolve_style_id,
            determine_background_color,
            apply_strict_transparency,
            evaluate_stamp_quality_full,
            QUALITY_CONFIG_STRICT,
            TRANSPARENCY_CONFIG_DEFAULT,
            STAMP_SIZE,
            _extract_hex_color,
        )
        from PIL import Image
        import io

        # Vertex AI クライアント初期化
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "perfect-eon-481715-u3")
        client = genai.Client(
            vertexai=True,
            project=project,
            location="global",
        )

        # スタイル解決
        style_id = resolve_style_id(style)
        style_info = CHIBI_STYLES.get(style_id, CHIBI_STYLES["sd_25"])

        # ポーズからプロンプト生成
        pose_prompt = self.generate_prompt(pose)

        # hints/avoid を追加
        hints_text = ""
        if pose.get("hints"):
            hints = pose["hints"] if isinstance(pose["hints"], list) else [pose["hints"]]
            hints_text = "\n".join([f"- {h}" for h in hints])

        avoid_text = ""
        if pose.get("avoid"):
            avoid = pose["avoid"] if isinstance(pose["avoid"], list) else [pose["avoid"]]
            avoid_text = "\n".join([f"- {a}" for a in avoid])

        # 背景色を自動決定（衣装色から安全な色を選択）
        background_color = determine_background_color(client, reference_image)
        print(f"  背景色: {background_color}")

        # 参照画像を読み込み
        image_data, mime_type = load_image_as_base64(reference_image)

        # テキスト指示（dekaモード）
        text_instruction = ""
        if text:
            text_instruction = f"""
=== TEXT (CRITICAL - MUST INCLUDE) ===
Text to display: "{text}"

LARGE BOLD TEXT REQUIREMENTS:
- Text MUST occupy 40%+ of the image area
- Use THICK, BOLD handwritten Japanese style
- Add strong white outline/shadow for readability
- Text must be clearly visible and readable
- High contrast between text and background
- Place text prominently near the character, floating style
- NO speech bubbles, NO signs - text floats in the air
"""

        # プロンプト構築（pose_locked用に詳細）
        prompt = f"""
Look at this reference image and create a LINE sticker of this character.

=== CHARACTER STYLE ===
{style_info['prompt']}

=== POSE (IMPORTANT - FOLLOW EXACTLY) ===
{pose_prompt}

=== EMOTION ===
{emotion}
{text_instruction}
{"=== GENERATION HINTS ===" if hints_text else ""}
{hints_text}

{"=== MUST AVOID ===" if avoid_text else ""}
{avoid_text}

=== STYLE REQUIREMENTS ===
- Background color: {background_color}
- SOLID, UNIFORM background color (no gradients, no patterns)
- High contrast between subject and background
- Clean, sharp edges on the character
- Bold outlines, cute appearance
- Visible complete hands with correct finger count
- Centered composition
"""

        # 画像付きリクエスト
        contents = [
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ]

        print(f"生成中: {pose.get('name', 'Unknown')}...")

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            )
        )

        # レスポンスから画像データを抽出
        image_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_bytes = part.inline_data.data
                break

        if not image_bytes:
            raise ValueError("画像が生成されませんでした")

        # 背景透過処理（メインパイプラインと同じ厳格方式）
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        bg_hex = _extract_hex_color(background_color)
        transparency_config = TRANSPARENCY_CONFIG_DEFAULT.copy()
        if bg_hex:
            transparency_config["fixed_colors"] = [bg_hex]
        img, bg = apply_strict_transparency(img, config=transparency_config, qc=QUALITY_CONFIG_STRICT)

        # LINE仕様サイズにリサイズ + 中央配置
        img.thumbnail(STAMP_SIZE, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", STAMP_SIZE, (0, 0, 0, 0))
        x = (STAMP_SIZE[0] - img.width) // 2
        y = (STAMP_SIZE[1] - img.height) // 2
        canvas.paste(img, (x, y), img)
        img = canvas

        # QCチェック
        qc_result = evaluate_stamp_quality_full(img, bg, qc=QUALITY_CONFIG_STRICT, text=text)

        # QC結果表示
        if qc_result["ok"]:
            print("  QC: PASS")
        else:
            print("  QC: NG")
            for e in qc_result.get("errors", []):
                print(f"    [NG] {e}")
        if qc_result.get("warnings"):
            for w in qc_result["warnings"]:
                print(f"    [WARN] {w}")

        # 出力パス決定
        if output_path is None:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = pose.get("name", "pose").replace(" ", "_")[:20]
            output_path = OUTPUT_DIR / f"{safe_name}_{timestamp}.png"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 画像保存
        img.save(output_path, "PNG")

        print(f"生成完了: {output_path}")
        return str(output_path)

    def format_pose_for_display(self, pose: Dict) -> str:
        """ポーズをフォーマットして表示用文字列を返す"""
        lines = []
        lines.append(f"【{pose.get('name', '名前なし')}】")

        if pose.get("name_en"):
            lines.append(f"  英語名: {pose['name_en']}")
        if pose.get("category"):
            lines.append(f"  カテゴリ: {pose['category']}")

        lines.append("")
        lines.append("  [ジェスチャー]")
        gesture = pose.get("gesture", pose.get("gesture_ja", ""))
        for line in gesture.strip().split("\n"):
            lines.append(f"    {line}")

        lines.append("")
        lines.append("  [表情]")
        expression = pose.get("expression", pose.get("expression_ja", ""))
        for line in expression.strip().split("\n"):
            lines.append(f"    {line}")

        if pose.get("vibe"):
            lines.append("")
            lines.append(f"  [雰囲気] {pose['vibe']}")

        if pose.get("hints"):
            lines.append("")
            lines.append("  [ヒント]")
            hints = pose["hints"] if isinstance(pose["hints"], list) else [pose["hints"]]
            for h in hints:
                lines.append(f"    - {h}")

        if pose.get("avoid"):
            lines.append("")
            lines.append("  [避けること]")
            avoid = pose["avoid"] if isinstance(pose["avoid"], list) else [pose["avoid"]]
            for a in avoid:
                lines.append(f"    - {a}")

        return "\n".join(lines)


# ==================== CLI ====================

def interactive_tune():
    """対話形式でポーズを調整"""
    tuner = PoseTuner()

    print("\n" + "=" * 60)
    print("ポーズ対話調整ツール")
    print("=" * 60)
    print("\nどのポーズを調整しますか？")
    print("  1. 既存ポーズを選択")
    print("  2. 新規作成")
    print("  3. YAMLをインポート")
    print("  q. 終了")

    choice = input("\n選択 (1-3, q): ").strip()

    if choice == "q":
        print("終了します")
        return

    pose = None

    if choice == "1":
        # 既存ポーズを選択
        poses = tuner.list_poses()
        if not poses:
            print("ポーズが登録されていません。新規作成してください。")
            return

        print("\n" + "-" * 40)
        print("ポーズ一覧:")
        for i, p in enumerate(poses, 1):
            category = p.get("category", "-")
            print(f"  {i}. {p['name']} [{category}]")

        idx_input = input("\n番号を入力: ").strip()
        if not idx_input.isdigit() or int(idx_input) < 1 or int(idx_input) > len(poses):
            print("無効な選択です")
            return

        selected = poses[int(idx_input) - 1]
        pose = tuner.load_pose(selected["name"])

    elif choice == "2":
        # 新規作成
        pose = tuner.create_new_pose()
        name = input("ポーズ名を入力: ").strip()
        if not name:
            print("キャンセルしました")
            return
        pose["name"] = name

    elif choice == "3":
        # YAMLインポート
        yaml_path = input("YAMLファイルパスを入力: ").strip()
        pose = import_pose_from_yaml(yaml_path, update_db=False)
        if not pose:
            return

    else:
        print("無効な選択です")
        return

    # 現在の定義を表示
    print("\n" + "=" * 60)
    print("現在の定義:")
    print("=" * 60)
    print(tuner.format_pose_for_display(pose))

    # 調整ループ
    while True:
        print("\n" + "-" * 40)
        print("調整したい項目を選択:")
        print("  1. ジェスチャーを編集")
        print("  2. 表情を編集")
        print("  3. 雰囲気を編集")
        print("  4. ヒントを追加/編集")
        print("  5. 避けることを追加/編集")
        print("  6. カテゴリを変更")
        print("  7. 名前を変更")
        print("  8. 現在の定義を表示")
        print("  9. プロンプトをプレビュー")
        print("  s. 保存して終了")
        print("  q. 保存せずに終了")

        action = input("\n選択: ").strip().lower()

        if action == "q":
            confirm = input("保存せずに終了しますか？ (y/N): ").strip().lower()
            if confirm == "y":
                print("変更を破棄しました")
                return
            continue

        if action == "s":
            yaml_path = tuner.save_pose(pose, to_yaml=True, to_db=True)
            print(f"\n保存完了: {pose['name']}")
            print(f"  YAML: {yaml_path}")
            print(f"  DB: 同期済み")
            return

        if action == "1":
            print("\n現在のジェスチャー:")
            print(pose.get("gesture", pose.get("gesture_ja", "(未設定)")))
            print("\n新しいジェスチャーを入力（複数行可、空行で終了）:")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            if lines:
                pose["gesture"] = "\n".join(lines)
                print("ジェスチャーを更新しました")

        elif action == "2":
            print("\n現在の表情:")
            print(pose.get("expression", pose.get("expression_ja", "(未設定)")))
            print("\n新しい表情を入力（複数行可、空行で終了）:")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            if lines:
                pose["expression"] = "\n".join(lines)
                print("表情を更新しました")

        elif action == "3":
            print(f"\n現在の雰囲気: {pose.get('vibe', '(未設定)')}")
            vibe = input("新しい雰囲気を入力: ").strip()
            if vibe:
                pose["vibe"] = vibe
                print("雰囲気を更新しました")

        elif action == "4":
            print("\n現在のヒント:")
            hints = pose.get("hints", [])
            if isinstance(hints, list):
                for h in hints:
                    print(f"  - {h}")
            else:
                print(f"  - {hints}")
            print("\n新しいヒントを入力（1行ずつ、空行で終了）:")
            new_hints = []
            while True:
                line = input("  - ").strip()
                if line == "":
                    break
                new_hints.append(line)
            if new_hints:
                pose["hints"] = new_hints
                print("ヒントを更新しました")

        elif action == "5":
            print("\n現在の避けること:")
            avoid = pose.get("avoid", [])
            if isinstance(avoid, list):
                for a in avoid:
                    print(f"  - {a}")
            else:
                print(f"  - {avoid}")
            print("\n新しい避けることを入力（1行ずつ、空行で終了）:")
            new_avoid = []
            while True:
                line = input("  - ").strip()
                if line == "":
                    break
                new_avoid.append(line)
            if new_avoid:
                pose["avoid"] = new_avoid
                print("避けることを更新しました")

        elif action == "6":
            categories = ["肯定", "否定", "愛情", "応援", "喜び", "礼儀", "照れ", "反応", "その他"]
            print(f"\n現在のカテゴリ: {pose.get('category', '(未設定)')}")
            print("カテゴリを選択:")
            for i, cat in enumerate(categories, 1):
                print(f"  {i}. {cat}")
            cat_input = input("番号を入力: ").strip()
            if cat_input.isdigit() and 1 <= int(cat_input) <= len(categories):
                pose["category"] = categories[int(cat_input) - 1]
                print(f"カテゴリを「{pose['category']}」に更新しました")

        elif action == "7":
            print(f"\n現在の名前: {pose.get('name', '(未設定)')}")
            new_name = input("新しい名前を入力: ").strip()
            if new_name:
                pose["name"] = new_name
                print(f"名前を「{new_name}」に更新しました")

        elif action == "8":
            print("\n" + "=" * 60)
            print("現在の定義:")
            print("=" * 60)
            print(tuner.format_pose_for_display(pose))

        elif action == "9":
            prompt = tuner.generate_prompt(pose)
            print("\n" + "=" * 60)
            print("生成用プロンプト:")
            print("=" * 60)
            print(prompt)


def print_usage():
    """使い方を表示"""
    print("""
ポーズ対話調整ツール

使い方:
  python pose_tuner.py              - 対話形式でポーズを調整
  python pose_tuner.py tune         - 対話形式でポーズを調整
  python pose_tuner.py list         - ポーズ一覧を表示
  python pose_tuner.py show <名前>  - ポーズ詳細を表示
  python pose_tuner.py prompt <名前> - 生成用プロンプトを表示

テスト生成:
  python pose_tuner.py test <ポーズ名> <参照画像> [オプション]
    --emotion "笑顔"    - 感情（デフォルト: 笑顔）
    --text "やったー"   - テキスト（省略可）
    --style sd_25       - スタイル（デフォルト: sd_25）
    --output path.png   - 出力パス（省略で自動生成）

例:
  python pose_tuner.py show "OKサイン"
  python pose_tuner.py prompt "OKサイン"
  python pose_tuner.py test "OKサイン" input/ref.jpg
  python pose_tuner.py test "OKサイン" input/ref.jpg --emotion "得意げ" --text "いいね！"
""")


if __name__ == "__main__":
    init_database()

    if len(sys.argv) < 2:
        interactive_tune()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "tune":
        interactive_tune()

    elif cmd == "list":
        tuner = PoseTuner()
        poses = tuner.list_poses()

        print("\n" + "=" * 60)
        print("ポーズ一覧")
        print("=" * 60)
        print(f"{'名前':<25} {'カテゴリ':<10} {'ソース'}")
        print("-" * 60)

        for p in poses:
            name = p.get("name", "不明")[:24]
            category = p.get("category", "-")[:9]
            source = p.get("source", "-")
            print(f"{name:<25} {category:<10} {source}")

        print("=" * 60 + "\n")

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("ポーズ名を指定してください")
            sys.exit(1)

        tuner = PoseTuner()
        pose = tuner.load_pose(sys.argv[2])

        if pose:
            print("\n" + "=" * 60)
            print(tuner.format_pose_for_display(pose))
            print("=" * 60 + "\n")
        else:
            print(f"ポーズが見つかりません: {sys.argv[2]}")

    elif cmd == "prompt":
        if len(sys.argv) < 3:
            print("ポーズ名を指定してください")
            sys.exit(1)

        tuner = PoseTuner()
        pose = tuner.load_pose(sys.argv[2])

        if pose:
            prompt = tuner.generate_prompt(pose)
            print("\n" + "=" * 60)
            print("生成用プロンプト:")
            print("=" * 60)
            print(prompt)
            print("=" * 60 + "\n")
        else:
            print(f"ポーズが見つかりません: {sys.argv[2]}")

    elif cmd == "test":
        # python pose_tuner.py test <ポーズ名> <参照画像> [--emotion X] [--text X] [--style X] [--output X]
        if len(sys.argv) < 4:
            print("使い方: python pose_tuner.py test <ポーズ名> <参照画像> [オプション]")
            sys.exit(1)

        pose_name = sys.argv[2]
        ref_image = sys.argv[3]

        # オプション解析
        emotion = "笑顔"
        text = ""
        style = "sd_25"
        output = None

        i = 4
        while i < len(sys.argv):
            if sys.argv[i] == "--emotion" and i + 1 < len(sys.argv):
                emotion = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--text" and i + 1 < len(sys.argv):
                text = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--style" and i + 1 < len(sys.argv):
                style = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
                output = sys.argv[i + 1]
                i += 2
            else:
                i += 1

        tuner = PoseTuner()
        pose = tuner.load_pose(pose_name)

        if not pose:
            print(f"ポーズが見つかりません: {pose_name}")
            sys.exit(1)

        if not Path(ref_image).exists():
            print(f"参照画像が見つかりません: {ref_image}")
            sys.exit(1)

        print("\n" + "=" * 60)
        print(f"テスト生成: {pose_name}")
        print("=" * 60)
        print(f"参照画像: {ref_image}")
        print(f"感情: {emotion}")
        print(f"テキスト: {text or '(なし)'}")
        print(f"スタイル: {style}")
        print("-" * 60)

        try:
            result = tuner.generate_single_stamp(
                pose=pose,
                reference_image=ref_image,
                emotion=emotion,
                text=text,
                style=style,
                output_path=output,
            )
            print("\n" + "=" * 60)
            print(f"出力: {result}")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"エラー: {e}")
            sys.exit(1)

    else:
        print(f"不明なコマンド: {cmd}")
        print_usage()
