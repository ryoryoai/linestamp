#!/usr/bin/env python3
"""
LINE絵文字画像生成スクリプト
Vertex AI gemini-3-pro-image-preview を使用
"""

import argparse
import base64
import json
import os
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
from rembg import remove, new_session
import io

# CUDA/GPU関連
try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

# グローバルセッション（初期化は遅延）
_rembg_session = None
_use_cuda = False


# LINE絵文字仕様
EMOJI_SIZE = (180, 180)  # 絵文字サイズ
TAB_SIZE = (96, 74)      # タブ画像

# ちびキャラスタイル定義（絵文字向けに調整）
CHIBI_STYLES = {
    "face_only": {
        "name": "顔だけタイプ（推奨）",
        "description": "顔だけ。太線パステルLINE絵文字風。",
        "prompt": "Ultra-deformed chibi face only. Big round head fills entire frame. Very thick bold outlines. Flat pastel colors. Big sparkly eyes. Simple expressive mouth. LINE emoji style. No body. No realism."
    },
    "ultra_sd": {
        "name": "超SD（Ultra SD）",
        "description": "約1頭身。LINEスタンプ向け太線パステル。",
        "prompt": "Ultra-deformed chibi. 1 head tall. Big round head, tiny limbs. Very thick bold outlines. Flat pastel colors. Simple expressive face. LINE sticker style. No realism."
    },
    "mini_face": {
        "name": "ミニ顔",
        "description": "顔メインで小さなボディ付き",
        "prompt": "Chibi character with oversized head and tiny body. Face takes up 80% of image. Very thick bold outlines. Flat bright colors. Big eyes, expressive face. Minimal body detail."
    },
    "standard_sd": {
        "name": "基本SD（Standard SD）",
        "description": "約2〜2.5頭身の標準ちびキャラ。",
        "prompt": "STANDARD CHIBI: 2.5 heads tall ratio, large round head with big eyes, small but proportionate body, visible hands and feet, classic anime chibi style, cute and balanced proportions, soft shading"
    },
    "puni": {
        "name": "ぷにキャラ型",
        "description": "柔らか丸み強調でぷに感。",
        "prompt": "PUNI SOFT STYLE: 3 heads tall, extremely soft and squishy appearance, very round plump cheeks, chubby body with no sharp edges, marshmallow-like texture, all curves and roundness, baby-like cuteness"
    },
}

# 40種類の絵文字リアクション（テキストなし・表情重視）
EMOJI_REACTIONS = [
    # === 基本表情（1-8） ===
    {"id": "smile", "emotion": "満面の笑み、目がキラキラ"},
    {"id": "laugh", "emotion": "大笑い、目が線になる、口大きく開く"},
    {"id": "wink", "emotion": "ウインク、にっこり"},
    {"id": "love", "emotion": "ハート目、うっとり"},
    {"id": "happy", "emotion": "幸せそう、目を閉じてにっこり"},
    {"id": "grin", "emotion": "ニカッと笑う、歯を見せる"},
    {"id": "blush", "emotion": "照れ笑い、頬ピンク、はにかみ"},
    {"id": "relieved", "emotion": "ほっとした顔、安堵の表情"},

    # === ポジティブ感情（9-16） ===
    {"id": "excited", "emotion": "大興奮、キラキラ目、頬ピンク"},
    {"id": "sparkle", "emotion": "キラキラ輝く目、期待に満ちた表情"},
    {"id": "proud", "emotion": "ドヤ顔、得意げ、自信満々"},
    {"id": "celebrate", "emotion": "お祝い、パーティー気分、クラッカー"},
    {"id": "starstruck", "emotion": "感動、目が星、憧れの眼差し"},
    {"id": "yay", "emotion": "やったー！両手上げ、万歳"},
    {"id": "thumbsup", "emotion": "いいね、サムズアップ、にっこり"},
    {"id": "peace", "emotion": "ピースサイン、にこにこ"},

    # === ネガティブ感情（17-24） ===
    {"id": "sad", "emotion": "悲しい、涙目、しょんぼり"},
    {"id": "cry", "emotion": "泣き顔、涙がポロポロ"},
    {"id": "sob", "emotion": "号泣、大泣き、滝涙"},
    {"id": "angry", "emotion": "怒り顔、眉つり上げ、怒りマーク"},
    {"id": "pout", "emotion": "ふくれっ面、ぷんぷん、むすっと"},
    {"id": "frustrated", "emotion": "イライラ、歯ぎしり、青筋"},
    {"id": "disappointed", "emotion": "がっかり、落胆、肩を落とす"},
    {"id": "worried", "emotion": "心配、不安、眉を寄せる"},

    # === 驚き・困惑（25-32） ===
    {"id": "shocked", "emotion": "驚き、目が点、口あんぐり"},
    {"id": "surprised", "emotion": "びっくり、目を丸く、わっ"},
    {"id": "scared", "emotion": "怖い、青ざめ、ガタガタ"},
    {"id": "confused", "emotion": "混乱、目が渦巻き、ぐるぐる"},
    {"id": "thinking", "emotion": "考え中、首かしげ、はてなマーク"},
    {"id": "suspicious", "emotion": "疑い、ジト目、うーん"},
    {"id": "nervous", "emotion": "緊張、汗、そわそわ"},
    {"id": "dizzy", "emotion": "目が回る、くらくら、星が飛ぶ"},

    # === 特殊表情（33-40） ===
    {"id": "sleepy", "emotion": "眠そう、目が半開き、zzz"},
    {"id": "sick", "emotion": "体調不良、青い顔、ぐったり"},
    {"id": "cool", "emotion": "クール、サングラス風、キメ顔"},
    {"id": "nerd", "emotion": "メガネ、知的、ふむふむ"},
    {"id": "hungry", "emotion": "お腹すいた、よだれ、食べたい"},
    {"id": "stuffed", "emotion": "お腹いっぱい、満足、ふぅ"},
    {"id": "kiss", "emotion": "投げキス、ちゅっ、ハートマーク"},
    {"id": "hug", "emotion": "ハグ、抱きしめ、両手広げる"},
]

# グリッドレイアウト設定（枚数 → rows x cols）
GRID_LAYOUTS = {
    8: (2, 4),    # 2行4列
    12: (3, 4),   # 3行4列（24枚を2分割時）
    16: (4, 4),   # 4行4列
    20: (4, 5),   # 4行5列（40枚を2分割時）
    24: (4, 6),   # 4行6列
    32: (4, 8),   # 4行8列
    40: (5, 8),   # 5行8列
}


def create_client(project_id: str = None):
    """Vertex AI クライアントを作成"""
    DEFAULT_PROJECT = "perfect-eon-481715-u3"
    project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or DEFAULT_PROJECT
    if not project:
        print("Error: --project または GOOGLE_CLOUD_PROJECT 環境変数を設定してください")
        sys.exit(1)
    print(f"プロジェクト: {project}")

    import httpx
    custom_timeout = httpx.Timeout(
        timeout=600.0,
        connect=60.0,
        read=600.0,
        write=60.0,
    )
    httpx_client = httpx.Client(timeout=custom_timeout)

    http_options = types.HttpOptions(
        httpxClient=httpx_client,
    )

    client = genai.Client(
        vertexai=True,
        project=project,
        location="global",
        http_options=http_options,
    )
    return client


def load_image_as_base64(image_path: str) -> tuple[str, str]:
    """画像をBase64エンコード"""
    img = Image.open(image_path)
    buffer = io.BytesIO()
    img_format = img.format or "PNG"
    img.save(buffer, format=img_format)
    data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    mime_type = f"image/{img_format.lower()}"
    return data, mime_type


def enhance_reaction_with_ai(client, reaction: dict, character_description: str = "") -> str:
    """Geminiを使ってシンプルなリアクションを詳細化"""
    prompt = f"""
You are an expert at creating detailed prompts for LINE emoji character image generation.

Take the simple reaction specification below and expand it into detailed descriptions that image generation AI can accurately render.

## Input
- emotion: {reaction.get('emotion', '')}
- pose: {reaction.get('pose', '')}
{f'- character features: {character_description}' if character_description else ''}

## Output Format (in English)
Provide detailed descriptions in this exact format:

Facial Expression:
- Eyes: [specific eye shape, openness, sparkle/shine]
- Eyebrows: [angle, position]
- Mouth: [shape, openness]
- Cheeks: [color, puffiness if any]

Special Effects (if any):
- [hearts, sparkles, sweat drops, anger marks, etc.]

Keep descriptions concise but specific. Focus on visual details that can be drawn at small size (180x180px).
Avoid complex details that won't be visible at emoji size.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    return response.text


def determine_background_color(client, character_path: str) -> str:
    """キャラクター画像を分析して最適な背景色を決定"""
    image_data, mime_type = load_image_as_base64(character_path)

    prompt = """
Analyze this character and suggest the best background color for LINE emoji.

## Considerations
- Harmonize with the character's colors
- Use pastel colors for a soft impression
- Ensure good contrast so the character stands out
- Avoid colors too similar to the character's main colors

## Output Format
Respond with exactly ONE line in this format:
color_name #HEXCODE

Examples:
soft pastel blue #E8F4FC
warm cream #FFF8E7
light lavender #F0E6FA

Just one line, nothing else.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ],
    )

    result = response.text.strip()
    if '\n' in result:
        result = result.split('\n')[0].strip()
    return result


def generate_character_from_reference(client, image_path: str, output_path: str, chibi_style: str = "face_only") -> str:
    """Step 1: 参照写真からサンプルキャラクターを生成"""
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["face_only"])
    style_prompt = style_info["prompt"]

    image_data, mime_type = load_image_as_base64(image_path)

    prompt = f"""
Look at this reference photo and create a SINGLE character illustration based on it for LINE emoji.

## STYLE (MUST FOLLOW EXACTLY)
{style_prompt}

## REQUIREMENTS
- Transform the person in the photo into the style specified above
- Keep the same hair color, eye color, and general appearance
- Neutral happy expression
- Plain white background
- NO text, just the character face/head
- The character should fill most of the frame (180x180px final size)
- Use THICK bold outlines for visibility at small size
- Keep design SIMPLE - avoid fine details

## OUTPUT
Single character illustration only. No grid, no multiple views.
"""

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            img = Image.open(io.BytesIO(part.inline_data.data))
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            print(f"キャラクター画像生成: {output_path}")
            return output_path

    raise ValueError("キャラクター画像が生成されませんでした")


def generate_grid_from_character(client, character_path: str, reactions: list, chibi_style: str = "face_only", background_color: str = None, grid_layout: tuple = None) -> bytes:
    """サンプルキャラクターからリアクショングリッドを生成（可変枚数対応）"""
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["face_only"])
    style_prompt = style_info["prompt"]

    image_data, mime_type = load_image_as_base64(character_path)

    bg_color = background_color or "light blue #E8F4FC"

    # グリッドレイアウトを決定
    emoji_count = len(reactions)
    if grid_layout:
        rows, cols = grid_layout
    else:
        rows, cols = GRID_LAYOUTS.get(emoji_count, (4, 5))  # デフォルト: 4x5=20

    # リアクションの説明を作成
    reactions_text_parts = []
    for i, r in enumerate(reactions):
        if 'enhanced_prompt' in r and r['enhanced_prompt']:
            reactions_text_parts.append(
                f"Cell {i+1}: {r['emotion']}\n{r['enhanced_prompt']}"
            )
        else:
            reactions_text_parts.append(
                f"Cell {i+1}: {r['emotion']}"
            )
    reactions_text = "\n\n".join(reactions_text_parts)

    # グリッド配置の説明を生成
    grid_arrangement = ""
    cell_num = 1
    for row in range(rows):
        row_cells = " ".join([f"[{cell_num + col}]" for col in range(cols)])
        grid_arrangement += f"{row_cells}    <- Row {row + 1}\n"
        cell_num += cols

    prompt = f"""
Create a SINGLE IMAGE containing exactly {emoji_count} LINE emoji faces.

## CRITICAL: IMAGE LAYOUT (MUST FOLLOW)
- Grid: {cols} COLUMNS × {rows} ROWS = {emoji_count} cells
- Output image aspect ratio: {cols}:{rows}

## GRID ARRANGEMENT:
```
{grid_arrangement}```

## CRITICAL: EMOJI DESIGN RULES
- ALL {emoji_count} cells MUST be EXACTLY EQUAL SIZE
- Character MUST be PERFECTLY CENTERED in each cell
- Character should FILL the cell (minimal padding)
- Use VERY THICK BOLD OUTLINES (visible at 180px)
- Keep design SIMPLE - no fine details
- NO TEXT in any cell
- Focus on FACIAL EXPRESSIONS only

## CHARACTER
Use the character from the reference image exactly.
Style: {style_prompt}

## {emoji_count} EMOJI EXPRESSIONS:
{reactions_text}

## VISUAL STYLE
- SAME character in ALL {emoji_count} cells
- Background color: {bg_color}
- THICK bold black outlines
- Simple, clear expressions
- NO grid lines between cells
- High contrast, flat colors
- Each emoji should be recognizable at 180x180px
"""

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )

    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise ValueError("リアクショングリッドが生成されませんでした")


def split_grid_image(grid_img: Image.Image, rows: int = 4, cols: int = 4) -> list:
    """グリッド画像を個別の絵文字に分割"""
    width, height = grid_img.size
    cell_width = width // cols
    cell_height = height // rows

    emojis = []
    for row in range(rows):
        for col in range(cols):
            left = col * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height

            cell = grid_img.crop((left, top, right, bottom))
            emojis.append(cell)

    return emojis


def check_cuda_availability() -> dict:
    """CUDAの利用可能状況をチェック"""
    info = {
        "cuda_available": False,
        "device_name": None,
        "providers": [],
    }

    if not ONNX_AVAILABLE:
        return info

    providers = ort.get_available_providers()
    info["providers"] = providers

    if "CUDAExecutionProvider" in providers:
        info["cuda_available"] = True
        try:
            import torch
            if torch.cuda.is_available():
                info["device_name"] = torch.cuda.get_device_name(0)
        except ImportError:
            pass

    return info


def init_rembg_session(use_cuda: bool = False):
    """rembgセッションを初期化（CUDA対応）"""
    global _rembg_session, _use_cuda

    cuda_info = check_cuda_availability()

    if use_cuda and cuda_info["cuda_available"]:
        print(f"[CUDA] GPU を使用します: {cuda_info['device_name'] or 'GPU detected'}")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        _use_cuda = True
    else:
        if use_cuda:
            print("[WARN] CUDA が利用できません。CPUモードで実行します。")
        else:
            print("[CPU] CPUモードで実行します")
        providers = ["CPUExecutionProvider"]
        _use_cuda = False

    _rembg_session = new_session("isnet-anime", providers=providers)
    return _rembg_session


def remove_background(img: Image.Image) -> Image.Image:
    """AI背景除去"""
    global _rembg_session

    device_info = "GPU (CUDA)" if _use_cuda else "CPU"
    print(f"背景を除去中... [{device_info}]")

    return remove(
        img,
        session=_rembg_session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=200,
        alpha_matting_background_threshold=20,
        alpha_matting_erode_size=3,
    )


def process_emoji(img: Image.Image, remove_bg: bool = True) -> Image.Image:
    """絵文字をLINE絵文字仕様に処理"""
    # RGBAに変換
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 背景除去
    if remove_bg:
        img = remove_background(img)

    # 正方形にクロップ（中央から）
    width, height = img.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))

    # 180x180にリサイズ（絵文字は余白不要なのでそのままリサイズ）
    img = img.resize(EMOJI_SIZE, Image.Resampling.LANCZOS)

    return img


def generate_tab_image(emoji_path: str, output_path: str):
    """タブ画像（96×74px）を生成"""
    img = Image.open(emoji_path)

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # アスペクト比を維持してリサイズ
    img.thumbnail(TAB_SIZE, Image.Resampling.LANCZOS)

    # 中央配置用の新しい画像を作成（透過背景）
    new_img = Image.new("RGBA", TAB_SIZE, (0, 0, 0, 0))
    x = (TAB_SIZE[0] - img.width) // 2
    y = (TAB_SIZE[1] - img.height) // 2
    new_img.paste(img, (x, y), img)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    new_img.save(output_path, "PNG", optimize=True)
    print(f"タブ画像保存: {output_path}")


def create_submission_zip(output_dir: str, emoji_count: int = 16) -> str:
    """申請用ZIPパッケージを作成"""
    output_path = Path(output_dir)
    zip_path = output_path / "submission.zip"

    files_to_zip = []

    # tab.png
    tab_file = output_path / "tab.png"
    if tab_file.exists():
        files_to_zip.append(("tab.png", tab_file))

    # 絵文字画像（001.png ~ 016.png）
    for i in range(1, emoji_count + 1):
        emoji_file = output_path / f"{i:03d}.png"
        if emoji_file.exists():
            files_to_zip.append((f"{i:03d}.png", emoji_file))

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arcname, filepath in files_to_zip:
            zf.write(filepath, arcname)

    print(f"申請用ZIP作成: {zip_path}")
    print(f"  含まれるファイル: {len(files_to_zip)}個")
    return str(zip_path)


def generate_emojis(client, image_path: str, output_dir: str, emoji_count: int = 40, remove_bg: bool = True, chibi_style: str = "face_only"):
    """絵文字生成（可変枚数対応・2段階方式）

    Args:
        emoji_count: 生成する絵文字の枚数（8, 16, 24, 32, 40）
    """
    if emoji_count not in [8, 16, 24, 32, 40]:
        print(f"警告: {emoji_count}枚は非標準です。8/16/24/32/40枚を推奨します。")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    style_name = CHIBI_STYLES.get(chibi_style, {}).get('name', chibi_style)
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["face_only"])
    style_prompt = style_info["prompt"]
    print(f"スタイル: {style_name}")
    print(f"生成枚数: {emoji_count}枚")
    print("=" * 50)

    prompts_log = {
        "generated_at": datetime.now().isoformat(),
        "emoji_count": emoji_count,
        "style": chibi_style,
        "style_name": style_name,
        "style_prompt": style_prompt,
        "character_prompt": None,
        "background_color": None,
        "reactions": [],
    }

    # Step 1: サンプルキャラクター生成
    print("\n[Step 1/4] サンプルキャラクターを生成中...")
    character_path = f"{output_dir}/_character.png"
    generate_character_from_reference(client, image_path, character_path, chibi_style=chibi_style)

    # Step 2: 背景色を自動決定
    print("\n[Step 2/4] キャラクターに最適な背景色を決定中...")
    try:
        background_color = determine_background_color(client, character_path)
        print(f"  決定した背景色: {background_color}")
    except Exception as e:
        print(f"  警告: 背景色決定に失敗、デフォルトを使用 ({e})")
        background_color = "light blue #E8F4FC"

    prompts_log["background_color"] = background_color

    # Step 3: リアクションを詳細化
    print(f"\n[Step 3/4] 各リアクションを詳細化中...")
    reactions = EMOJI_REACTIONS[:emoji_count]

    enhanced_reactions = []
    for i, reaction in enumerate(reactions):
        print(f"  リアクション {i+1}/{emoji_count}: {reaction['id']}...")
        try:
            enhanced_prompt = enhance_reaction_with_ai(client, reaction)
            enhanced_reaction = {**reaction, 'enhanced_prompt': enhanced_prompt}
        except Exception as e:
            print(f"    警告: 詳細化に失敗 ({e})")
            enhanced_reaction = {**reaction, 'enhanced_prompt': None}
        enhanced_reactions.append(enhanced_reaction)

        prompts_log["reactions"].append({
            "index": i + 1,
            "id": reaction["id"],
            "emotion": reaction["emotion"],
            "enhanced_prompt": enhanced_reaction.get("enhanced_prompt")
        })

    # Step 4: リアクショングリッド生成（20枚以下なら1回、それ以上なら分割）
    print("\n[Step 4/4] リアクショングリッドを生成中...")

    # グリッド分割戦略: 20枚以下なら1回、それ以上なら20枚ずつ
    if emoji_count <= 20:
        grid_batches = [(enhanced_reactions, GRID_LAYOUTS.get(emoji_count, (4, 5)))]
    else:
        # 20枚ずつに分割
        grid_batches = []
        for start in range(0, emoji_count, 20):
            end = min(start + 20, emoji_count)
            batch = enhanced_reactions[start:end]
            batch_count = len(batch)
            layout = GRID_LAYOUTS.get(batch_count, (4, 5))
            grid_batches.append((batch, layout))

    all_emojis = []
    for batch_idx, (batch_reactions, layout) in enumerate(grid_batches):
        rows, cols = layout
        batch_count = len(batch_reactions)
        print(f"  グリッド {batch_idx + 1}/{len(grid_batches)} ({batch_count}枚, {rows}x{cols}) を生成中...")

        grid_data = generate_grid_from_character(
            client, character_path, batch_reactions,
            chibi_style=chibi_style, background_color=background_color,
            grid_layout=layout
        )

        # グリッド画像を保存
        grid_img = Image.open(io.BytesIO(grid_data))
        grid_path = f"{output_dir}/_grid_{batch_idx + 1}.png"
        grid_img.save(grid_path, "PNG")
        print(f"    グリッド画像保存: {grid_path}")

        # 分割
        emojis = split_grid_image(grid_img, rows=rows, cols=cols)
        all_emojis.extend(zip(emojis[:batch_count], batch_reactions))

    # 各絵文字を処理・保存
    print("  各絵文字を処理中...")
    for i, (emoji, reaction) in enumerate(all_emojis):
        # 背景除去とリサイズ
        processed = process_emoji(emoji, remove_bg=remove_bg)

        # ID付きファイル名で保存（デバッグ用）
        debug_path = f"{output_dir}/{i+1:03d}_{reaction['id']}.png"
        processed.save(debug_path, "PNG", optimize=True)

        # 申請用ファイル名でも保存
        submit_path = f"{output_dir}/{i+1:03d}.png"
        processed.save(submit_path, "PNG", optimize=True)
        print(f"  保存: {submit_path}")

    # プロンプトをJSONで保存
    prompts_path = f"{output_dir}/_prompts.json"
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts_log, f, ensure_ascii=False, indent=2)

    grid_count = len(grid_batches)
    api_calls = 1 + 1 + emoji_count + grid_count  # キャラ + 背景色 + 詳細化 + グリッド

    print(f"\n完了!")
    print(f"出力先: {output_dir}")
    print(f"  - キャラクター画像: _character.png")
    print(f"  - グリッド画像: {grid_count}枚")
    print(f"  - 絵文字: {emoji_count}枚 (001.png ~ {emoji_count:03d}.png)")
    print(f"API呼び出し: {api_calls}回（キャラクター1回 + 背景色1回 + 詳細化{emoji_count}回 + グリッド{grid_count}回）")


def generate_submission_package(client, image_path: str, output_dir: str, emoji_count: int = 40, chibi_style: str = "face_only"):
    """LINE審査申請用パッケージを生成"""
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("LINE 絵文字申請パッケージ生成")
    print(f"生成枚数: {emoji_count}枚")
    print("=" * 50)

    # Step 1: 絵文字を生成
    print(f"\n[Step 1/3] {emoji_count}枚の絵文字を生成中...")
    generate_emojis(client, image_path, output_dir, emoji_count=emoji_count, remove_bg=True, chibi_style=chibi_style)

    # Step 2: タブ画像を生成（1枚目をリサイズ）
    print("\n[Step 2/3] タブ画像を生成中...")
    output_path = Path(output_dir)
    first_emoji = output_path / "001.png"
    tab_path = output_path / "tab.png"

    if first_emoji.exists():
        generate_tab_image(str(first_emoji), str(tab_path))
    else:
        print("警告: 1枚目の絵文字が見つかりません")

    # Step 3: ZIPパッケージを作成
    print("\n[Step 3/3] 申請用ZIPパッケージを作成中...")
    create_submission_zip(output_dir, emoji_count=emoji_count)

    print("\n" + "=" * 50)
    print("完了! 生成されたファイル:")
    print("=" * 50)
    print(f"  ディレクトリ: {output_dir}")
    print(f"  tab.png      : 96×74px (タブ画像)")
    print(f"  001.png～{emoji_count:03d}.png: 180×180px (絵文字画像)")
    print(f"  submission.zip: 申請用パッケージ")
    print("\nLINE Creators Marketで申請時にsubmission.zipをアップロードしてください。")


def main():
    parser = argparse.ArgumentParser(description="LINE絵文字画像生成")

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--generate", "-g", metavar="IMAGE",
                            help="絵文字生成（--countで枚数指定、デフォルト40枚）")
    mode_group.add_argument("--package", metavar="IMAGE",
                            help="LINE審査申請用パッケージ生成（絵文字 + タブ画像 + ZIP）")

    parser.add_argument("--count", "-c", type=int, default=40, choices=[8, 16, 24, 32, 40],
                        help="生成する絵文字の枚数（デフォルト: 40）")
    parser.add_argument("--output", "-o", help="出力先ディレクトリ")
    parser.add_argument("--style", choices=list(CHIBI_STYLES.keys()),
                        default="face_only", help="ちびキャラスタイル")
    parser.add_argument("--project", help="Google Cloud プロジェクトID")
    parser.add_argument("--no-remove-bg", action="store_true",
                        help="背景除去をスキップ")
    parser.add_argument("--check-cuda", action="store_true",
                        help="CUDA環境をチェックして終了")

    args = parser.parse_args()

    if args.check_cuda:
        cuda_info = check_cuda_availability()
        print("=== CUDA 環境チェック ===")
        print(f"CUDA利用可能: {'はい' if cuda_info['cuda_available'] else 'いいえ'}")
        if cuda_info['device_name']:
            print(f"GPUデバイス: {cuda_info['device_name']}")
        print(f"利用可能プロバイダー: {', '.join(cuda_info['providers'])}")
        return

    if not args.generate and not args.package:
        parser.error("--generate または --package のいずれかを指定してください")

    client = create_client(args.project)
    remove_bg = not getattr(args, 'no_remove_bg', False)

    if remove_bg:
        init_rembg_session(use_cuda=False)

    if args.generate:
        if not os.path.exists(args.generate):
            print(f"Error: 画像が見つかりません: {args.generate}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/lineemoji_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        generate_emojis(client, args.generate, output_dir, emoji_count=args.count, remove_bg=remove_bg, chibi_style=args.style)
        return

    if args.package:
        if not os.path.exists(args.package):
            print(f"Error: 画像が見つかりません: {args.package}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/lineemoji_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        generate_submission_package(client, args.package, output_dir, emoji_count=args.count, chibi_style=args.style)
        return


if __name__ == "__main__":
    main()
