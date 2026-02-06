"""グリッド再生成スクリプト - 白枠強調版"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# .envファイルから環境変数を読み込み
from dotenv import load_dotenv
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# サービスアカウントキー認証（環境変数から取得）
if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set. Check .env file.")

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "gen-lang-client-0336845315")

import yaml
from generate_stamp import (
    generate_grid_from_character,
    REACTIONS,
    DEFAULT_MODIFIERS,
)
from google import genai

# 出力ディレクトリ
OUTPUT_DIR = Path(r"F:\projects\linestamp\output\kimikimi_home_20250203")
CHARACTER_PATH = OUTPUT_DIR / "_character.png"
CHARACTER_YAML_PATH = OUTPUT_DIR / "_character.yaml"

# キャラクターYAML読み込み
with open(CHARACTER_YAML_PATH, "r", encoding="utf-8") as f:
    character_yaml = yaml.safe_load(f)

# モディファイア設定（白枠を強調）
modifiers = DEFAULT_MODIFIERS.copy()
modifiers["outline"] = "bold"  # 太い白枠

# 白枠を追加強調するためのカスタム設定
extra_outline_prompt = """
CRITICAL OUTLINE REQUIREMENTS - MUST FOLLOW:
- ALL characters MUST have THICK WHITE OUTLINE (6-8px) around the entire body
- ALL text MUST have THICK WHITE OUTLINE (4-6px) around every letter
- The outline must be PURE WHITE (#FFFFFF), not off-white or cream
- NO BLACK OUTLINES on characters - only WHITE outlines
- Outline must be clearly visible against the green background
- This is MANDATORY for proper transparency processing
"""

# Vertex AIクライアント初期化（gemini-3-pro-image-previewはglobalリージョンが必要）
client = genai.Client(vertexai=True, project=GCP_PROJECT_ID, location="global")

print("=" * 60)
print("Grid Regeneration with White Outline")
print("=" * 60)

# リアクション24個を準備
reactions = REACTIONS[:24]

# グリッド1生成（1-12）
print("\n[Grid 1] Generating stamps 1-12...")
try:
    grid1_data = generate_grid_from_character(
        client=client,
        character_path=str(CHARACTER_PATH),
        reactions=reactions[:12],
        chibi_style="sd_25",
        background_color="bright green #00FF00",
        character_yaml=character_yaml,
        modifiers=modifiers,
        model="gemini-3-pro-image-preview",
    )
    grid1_path = OUTPUT_DIR / "grid_1_white_outline.png"
    with open(grid1_path, "wb") as f:
        f.write(grid1_data)
    print(f"  Saved: {grid1_path}")
except Exception as e:
    print(f"  Error: {e}")

# グリッド2生成（13-24）
print("\n[Grid 2] Generating stamps 13-24...")
try:
    grid2_data = generate_grid_from_character(
        client=client,
        character_path=str(CHARACTER_PATH),
        reactions=reactions[12:24],
        chibi_style="sd_25",
        background_color="bright green #00FF00",
        character_yaml=character_yaml,
        modifiers=modifiers,
        model="gemini-3-pro-image-preview",
    )
    grid2_path = OUTPUT_DIR / "grid_2_white_outline.png"
    with open(grid2_path, "wb") as f:
        f.write(grid2_data)
    print(f"  Saved: {grid2_path}")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 60)
print("Done!")
print("=" * 60)
