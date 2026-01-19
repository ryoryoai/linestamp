#!/usr/bin/env python3
"""
LINEスタンプ画像生成スクリプト
Vertex AI gemini-3-pro-image-preview を使用
CUDA対応の高速背景除去機能付き
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


# LINEスタンプ仕様
STAMP_SIZE = (370, 320)  # 最大サイズ
MAIN_SIZE = (240, 240)   # メイン画像
TAB_SIZE = (96, 74)      # タブ画像

# ちびキャラスタイル定義（より詳細で差別化されたプロンプト）
# 順序: 選択肢の表示順序に影響
CHIBI_STYLES = {
    # === メイン推奨スタイル ===
    "ultra_sd": {
        "name": "超SD（Ultra SD）",
        "description": "約1頭身。LINEスタンプ向け太線パステル。",
        "prompt": "Ultra-deformed chibi. 1 head tall. Big round head, tiny limbs. Very thick bold outlines. Flat pastel colors. Simple expressive face. LINE sticker style. No realism."
    },
    "face_only": {
        "name": "顔だけタイプ",
        "description": "顔だけ。太線パステルLINEスタンプ風。",
        "prompt": "Ultra-deformed chibi face. Big round head. Very thick bold outlines. Flat pastel colors. Big sparkly eyes. Simple expressive mouth. LINE sticker style. No realism."
    },
    "choi_sd": {
        "name": "ちょいSD（Choi SD）",
        "description": "約1.5〜2頭身。パステル調の柔らかちびキャラ。",
        "prompt": "Cute soft chibi illustration. 1.5–2 heads tall. Big sparkling eyes, small mouth. Pastel colors, thin clean lines. Keep hairstyle and vibe from photo. Full body, gentle pose. No realism, no dark lighting."
    },
    # === その他スタイル ===
    "extreme_chibi": {
        "name": "極端デフォルメ型",
        "description": "約1.5頭身。顔と表情重視。",
        "prompt": "EXTREME CHIBI: 1.5 heads tall ratio, giant head with huge expressive eyes, tiny stick-like body, exaggerated facial expressions dominating the image, minimal body detail, comic manga style"
    },
    "standard_sd": {
        "name": "基本SD（Standard SD）",
        "description": "約2〜2.5頭身の標準ちびキャラ。",
        "prompt": "STANDARD CHIBI: 2.5 heads tall ratio, large round head with big eyes, small but proportionate body, visible hands and feet, classic anime chibi style, cute and balanced proportions, soft shading"
    },
    "tall_sd": {
        "name": "ちょい高SD（Tall SD）",
        "description": "約3頭身。衣装表現しやすい。",
        "prompt": "TALL CHIBI: 3 heads tall ratio, slightly elongated body, visible neck and waist, detailed clothing with folds and patterns, more realistic body proportions while still chibi, elegant pose"
    },
    "mini_chara": {
        "name": "ミニキャラ風（Mini Chara）",
        "description": "約3〜4頭身。子供寄りでディテール多め。",
        "prompt": "MINI CHARACTER: 4 heads tall ratio, childlike proportions, detailed costume with accessories, intricate clothing patterns, more mature chibi style, visible fingers and detailed features"
    },
    "semi_deformed": {
        "name": "ハーフデフォルメ型",
        "description": "約4.5〜5頭身。軽いちび感＋リアル寄り。",
        "prompt": "SEMI-DEFORMED: 5 heads tall ratio, nearly normal anime proportions with slight chibi influence, realistic shading and lighting, detailed anatomy, mature anime style with cute elements"
    },
    "ball_joint": {
        "name": "キューポッシュ型",
        "description": "球体関節フィギュア風のSD。",
        "prompt": "BALL-JOINT DOLL STYLE: 2.5 heads tall, smooth plastic figure appearance, visible sphere joints at shoulders/hips/knees, glossy skin texture, doll-like perfect features, articulated pose"
    },
    "puni": {
        "name": "ぷにキャラ型",
        "description": "柔らか丸み強調でぷに感。",
        "prompt": "PUNI SOFT STYLE: 3 heads tall, extremely soft and squishy appearance, very round plump cheeks, chubby body with no sharp edges, marshmallow-like texture, all curves and roundness, baby-like cuteness"
    },
    "gacha": {
        "name": "ガチャ絵型",
        "description": "ソシャゲ系ガチャ絵風。",
        "prompt": "GACHA GAME STYLE: 3.5 heads tall, flashy mobile game character style, sparkles and effects around character, ornate detailed costume with gems and accessories, dynamic action pose, vibrant saturated colors, glamorous appearance"
    },
    "custom_test": {
        "name": "カスタムテスト",
        "description": "ユーザー指定のカスタムプロンプト",
        "prompt": "super deformed, ultra chibi, 1 head tall, round head, stubby limbs, minimal detail, pastel color palette"
    },
}

# 24種類のリアクションテンプレート（誕生日を祝ってもらう男の子向け）
# ユーザーの要望に応じて、このリストを編集してカスタマイズする
REACTIONS = [
    # === お祝いへの反応 ===
    {"id": "arigatou", "emotion": "感謝の笑顔、嬉しそうな目、キラキラ", "pose": "ペコリとお辞儀、両手を合わせる", "text": "ありがとう！"},
    {"id": "ureshii", "emotion": "大喜び、ハート目、満面の笑み", "pose": "ぴょんぴょん跳ねる、両手を上げる", "text": "うれしい！"},
    {"id": "yatta", "emotion": "大喜び、キラキラ目、口大きく開ける", "pose": "両手を上げて万歳、ジャンプ", "text": "やったー！"},
    {"id": "saikou", "emotion": "最高に幸せな顔、目がキラキラ", "pose": "両手でグッドサイン、輝くエフェクト", "text": "最高！"},

    # === 誕生日系 ===
    {"id": "cake", "emotion": "よだれ、期待に満ちた目、ワクワク", "pose": "ケーキを見つめる、キラキラ目", "text": "ケーキ！"},
    {"id": "present", "emotion": "ワクワク、期待でいっぱい、キラキラ目", "pose": "プレゼント箱を抱える、嬉しそう", "text": "プレゼント！"},
    {"id": "8sai", "emotion": "誇らしげな顔、にっこり笑顔", "pose": "ピースサイン、パーティーハット", "text": "8さい！"},
    {"id": "happy", "emotion": "パーティー気分、目がハート", "pose": "クラッカーを持つ、紙吹雪", "text": "ハッピー！"},

    # === 感情表現 ===
    {"id": "daisuki", "emotion": "ハート目、幸せいっぱいの顔", "pose": "ハートマークを抱える、うっとり", "text": "大好き！"},
    {"id": "tereru", "emotion": "照れ顔、頬が真っ赤、はにかみ", "pose": "頭をかく、照れる", "text": "照れる〜"},
    {"id": "waai", "emotion": "大はしゃぎ、キラキラ目", "pose": "両手を広げてジャンプ", "text": "わーい！"},
    {"id": "matane", "emotion": "名残惜しそう、でも笑顔", "pose": "手を振る、バイバイ", "text": "またね！"},

    # === 日常系 ===
    {"id": "ohayo", "emotion": "元気いっぱいの笑顔、目がキラキラ", "pose": "元気に手を振る", "text": "おはよう！"},
    {"id": "oyasumi", "emotion": "眠そうな顔、zzz、幸せそう", "pose": "枕を抱えて眠る", "text": "おやすみ！"},
    {"id": "ok", "emotion": "ウインク、自信のある顔", "pose": "OKサインを作る、キラッ", "text": "OK！"},
    {"id": "ryokai", "emotion": "きりっとした顔、やる気", "pose": "敬礼ポーズ", "text": "了解！"},

    # === リアクション系 ===
    {"id": "iine", "emotion": "キラキラ目、嬉しそうな顔", "pose": "サムズアップ、笑顔", "text": "いいね！"},
    {"id": "sugoi", "emotion": "感動、目がキラキラ、口あんぐり", "pose": "両手を頬に当てる、驚き", "text": "すごい！"},
    {"id": "punpun", "emotion": "ふくれ顔、怒りマーク", "pose": "ほっぺを膨らませる、むすっと", "text": "ぷんぷん"},
    {"id": "ehehehe", "emotion": "いたずらっぽい笑顔、にやり", "pose": "舌を出す、ピース", "text": "えへへ"},

    # === その他 ===
    {"id": "gohan", "emotion": "よだれ、期待に満ちた目", "pose": "お箸を持つ、キラキラ目", "text": "ごはん！"},
    {"id": "ganbare", "emotion": "応援顔、元気いっぱい", "pose": "拳を振って応援", "text": "がんばれ！"},
    {"id": "niko", "emotion": "目を閉じてにっこり、幸せ顔", "pose": "両手を頬に当てる", "text": "にこっ"},
    {"id": "peace", "emotion": "にっこり笑顔、ウインク", "pose": "ダブルピース", "text": "ピース！"},
]


def create_client(project_id: str = None):
    """Vertex AI クライアントを作成"""
    # 引数 > 環境変数 > デフォルト の優先順位
    DEFAULT_PROJECT = "perfect-eon-481715-u3"
    project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT") or DEFAULT_PROJECT
    if not project:
        print("Error: --project または GOOGLE_CLOUD_PROJECT 環境変数を設定してください")
        sys.exit(1)
    print(f"プロジェクト: {project}")

    # タイムアウト設定（画像生成は時間がかかるため長めに設定）
    import httpx
    custom_timeout = httpx.Timeout(
        timeout=600.0,    # 全体のタイムアウト: 10分
        connect=60.0,     # 接続タイムアウト: 1分
        read=600.0,       # 読み取りタイムアウト: 10分
        write=60.0,       # 書き込みタイムアウト: 1分
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
    """
    Geminiを使ってシンプルなリアクションを詳細化

    Args:
        client: Vertex AI クライアント
        reaction: {"id", "emotion", "pose", "text"}
        character_description: キャラクターの特徴（オプション）

    Returns:
        詳細化されたプロンプト文字列
    """
    prompt = f"""
You are an expert at creating detailed prompts for LINE sticker chibi character image generation.

Take the simple reaction specification below and expand it into detailed descriptions that image generation AI can accurately render.

## Input
- emotion: {reaction.get('emotion', '')}
- pose: {reaction.get('pose', '')}
- text: {reaction.get('text', '')}
{f'- character features: {character_description}' if character_description else ''}

## Output Format (in English)
Provide detailed descriptions in this exact format:

Facial Expression:
- Eyes: [specific eye shape, openness, sparkle/shine]
- Eyebrows: [angle, position]
- Mouth: [shape, openness]
- Cheeks: [color, puffiness if any]

Pose:
- Body: [body direction, tilt]
- Arms: [position and movement of both arms]
- Legs: [position and movement of feet/legs]
- Overall movement: [impression of the overall movement]

If the character has unique features (wings, tail, accessories, etc.), add a section for those as well.

Keep descriptions concise but specific. Focus on visual details that can be drawn.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    return response.text


def detect_items_from_image(client, image_path: str) -> list:
    """
    参照画像からアイテムを検出してリストで返す

    Args:
        client: Vertex AI クライアント
        image_path: 参照画像のパス

    Returns:
        検出されたアイテムのリスト（例: [{"name": "花束", "description": "ピンクと白のバラの花束", "category": "gift"}]）
    """
    image_data, mime_type = load_image_as_base64(image_path)

    prompt = """
Analyze this image and detect any items/objects that the person is holding, wearing as accessories, or that are prominently featured alongside them.

## Focus on:
- Items held in hands (flowers, bags, food, toys, etc.)
- Accessories (hats, glasses, jewelry, etc.)
- Pets or stuffed animals
- Notable background objects that are closely associated with the person

## DO NOT include:
- Clothing (shirts, pants, etc.)
- Body parts
- Generic background elements

## Output Format (JSON array):
Return a JSON array of detected items. If no items found, return empty array [].

```json
[
  {
    "name": "花束",
    "name_en": "flower bouquet",
    "description": "ピンクと白のバラの花束、リボン付き",
    "description_en": "pink and white rose bouquet with ribbon",
    "category": "gift",
    "hold_style": "両手で抱える"
  }
]
```

Categories: gift, food, toy, accessory, pet, tool, other

Return ONLY the JSON array, no other text.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ],
    )

    result_text = response.text.strip()

    # JSON部分を抽出（```json ... ``` で囲まれている場合）
    if "```json" in result_text:
        start = result_text.find("```json") + 7
        end = result_text.find("```", start)
        result_text = result_text[start:end].strip()
    elif "```" in result_text:
        start = result_text.find("```") + 3
        end = result_text.find("```", start)
        result_text = result_text[start:end].strip()

    try:
        items = json.loads(result_text)
        if isinstance(items, list):
            return items
        return []
    except json.JSONDecodeError:
        print(f"警告: アイテム検出結果のパースに失敗: {result_text[:100]}")
        return []


def match_items_to_reactions(client, items: list, reactions: list) -> list:
    """
    検出されたアイテムを各リアクションに最適にマッチング

    Args:
        client: Vertex AI クライアント
        items: 検出されたアイテムリスト
        reactions: リアクションリスト

    Returns:
        アイテム情報が追加されたリアクションリスト
    """
    if not items:
        # アイテムがない場合はそのまま返す
        return reactions

    # アイテム一覧を作成
    items_desc = "\n".join([
        f"- {item['name']} ({item.get('category', 'other')}): {item['description']}"
        for item in items
    ])

    # リアクション一覧を作成
    reactions_desc = "\n".join([
        f"{i+1}. {r['text']} - {r['emotion']}"
        for i, r in enumerate(reactions)
    ])

    prompt = f"""
Match the detected items to the most suitable reactions for LINE stickers.
Each reaction can have 0 or 1 item assigned.

## Available Items:
{items_desc}

## Reactions to match:
{reactions_desc}

## Matching Rules:
1. Match items to reactions where holding that item makes sense
   - "ありがとう！" (thank you) → flower bouquet, gift
   - "ケーキ！" (cake) → cake, food
   - "プレゼント！" (present) → gift box
   - "大好き！" (love) → heart, flower
2. Some reactions should have NO item (e.g., sleeping, basic emotions)
3. Don't force items - only assign when it genuinely enhances the sticker

## Output Format (JSON):
Return a JSON object mapping reaction index (1-based) to item name or null.

```json
{{
  "1": "花束",
  "2": null,
  "3": "ケーキ",
  ...
}}
```

Return ONLY the JSON object, no other text.
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )

    result_text = response.text.strip()

    # JSON部分を抽出
    if "```json" in result_text:
        start = result_text.find("```json") + 7
        end = result_text.find("```", start)
        result_text = result_text[start:end].strip()
    elif "```" in result_text:
        start = result_text.find("```") + 3
        end = result_text.find("```", start)
        result_text = result_text[start:end].strip()

    try:
        matching = json.loads(result_text)
    except json.JSONDecodeError:
        print(f"警告: マッチング結果のパースに失敗: {result_text[:100]}")
        return reactions

    # アイテム情報をリアクションに追加
    items_dict = {item['name']: item for item in items}
    enhanced_reactions = []

    for i, reaction in enumerate(reactions):
        idx = str(i + 1)
        item_name = matching.get(idx)

        enhanced_reaction = reaction.copy()
        if item_name and item_name in items_dict:
            item = items_dict[item_name]
            enhanced_reaction['item'] = {
                'name': item['name'],
                'name_en': item.get('name_en', item['name']),
                'description': item['description'],
                'description_en': item.get('description_en', item['description']),
                'hold_style': item.get('hold_style', '片手で持つ')
            }
        else:
            enhanced_reaction['item'] = None

        enhanced_reactions.append(enhanced_reaction)

    return enhanced_reactions


def determine_background_color(client, character_path: str) -> str:
    """
    キャラクター画像を分析して最適な背景色を決定

    Args:
        client: Vertex AI クライアント
        character_path: キャラクター画像のパス

    Returns:
        背景色の説明（例: "soft pink pastel #FFE4E1"）
    """
    image_data, mime_type = load_image_as_base64(character_path)

    prompt = """
Analyze this character and suggest the best background color for LINE stickers.

## Considerations
- Harmonize with the character's clothing and hair colors
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
mint green #E8F5E9

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
    # 複数行の場合は最初の行のみ取得
    if '\n' in result:
        result = result.split('\n')[0].strip()
    return result


def generate_image(client, prompt: str, transparent_bg: bool = True) -> bytes:
    """Gemini で画像を生成"""

    # 背景指示（rembgで後処理するため、純白背景を指定してコントラスト最大化）
    bg_instruction = """
    - Pure white background (#FFFFFF)
    - High contrast between subject and background
    - Clean, sharp edges on the character
    - Subject only, no complex background elements
    """ if transparent_bg else "- Simple solid color background"

    # LINEスタンプ向けにプロンプトを最適化
    optimized_prompt = f"""
    Create a LINE sticker style image:
    {prompt}

    Style requirements:
    - Simple, clean design suitable for messaging stickers
    - High contrast and bold outlines
    - Centered composition
    - Cute and expressive
    - Solid colored clothing with clear defined edges
    - Visible complete hands and feet
    - High saturation colors for character (avoid white/pale colors)
    - Strong contrast between character outline and background
    {bg_instruction}
    """

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=optimized_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )

    # レスポンスから画像データを抽出
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise ValueError("画像が生成されませんでした")


def generate_from_reference(client, image_path: str, reaction: dict, transparent_bg: bool = True) -> bytes:
    """参照画像からリアクションスタンプを生成"""

    # 画像を読み込み
    image_data, mime_type = load_image_as_base64(image_path)

    # 背景指示（rembgで後処理するため、純白背景を指定してコントラスト最大化）
    bg_instruction = """
    - Pure white background (#FFFFFF)
    - High contrast between subject and background
    - Clean, sharp edges on the character
    - Subject only, no complex background elements
    """ if transparent_bg else "- Simple solid color background"

    # プロンプト構築
    prompt = f"""
    Look at this reference image and create a cute anime-style deformed (chibi/SD) character version of it as a LINE sticker.

    This sticker should show:
    - Emotion/Expression: {reaction['emotion']}
    - Pose: {reaction['pose']}
    - Handwritten-style text: "{reaction['text']}"

    Style requirements:
    - Cute chibi/super-deformed anime style (big head, small body)
    - Simple, clean design suitable for messaging stickers
    - High contrast and bold outlines
    - The text should look handwritten, placed naturally near the character
    - Expressive and exaggerated features
    - Solid colored clothing with clear defined edges
    - Visible complete hands and feet
    - High saturation colors for character (avoid white/pale colors)
    - Strong contrast between character outline and background
    {bg_instruction}
    """

    # 画像付きリクエスト
    contents = [
        types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
        prompt
    ]

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )

    # レスポンスから画像データを抽出
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise ValueError("画像が生成されませんでした")


def generate_character_from_reference(client, image_path: str, output_path: str, chibi_style: str = "ultra_sd") -> str:
    """Step 1: 参照写真からサンプルキャラクターを生成（2段階生成の第1段階）

    Args:
        client: Vertex AI クライアント
        image_path: 参照画像のパス
        output_path: 生成したキャラクター画像の保存先
        chibi_style: CHIBI_STYLES のキー

    Returns:
        生成されたキャラクター画像のパス
    """
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["standard_sd"])
    style_prompt = style_info["prompt"]

    image_data, mime_type = load_image_as_base64(image_path)

    prompt = f"""
Look at this reference photo and create a SINGLE character illustration based on it.

## STYLE (MUST FOLLOW EXACTLY)
{style_prompt}

## REQUIREMENTS
- Transform the person in the photo into the style specified above
- Keep the same hair color, eye color, and general appearance
- Simple standing pose, facing forward
- Neutral happy expression
- Plain white background
- NO text, NO accessories, just the character
- The character should fill most of the frame

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


def generate_grid_from_character(client, character_path: str, reactions: list, chibi_style: str = "ultra_sd", background_color: str = None) -> bytes:
    """Step 2: サンプルキャラクターからリアクショングリッドを生成（2段階生成の第2段階）

    Args:
        client: Vertex AI クライアント
        character_path: Step 1で生成したキャラクター画像のパス
        reactions: リアクションリスト（12個）- enhanced_promptキーがあれば詳細化版を使用
        chibi_style: CHIBI_STYLES のキー
        background_color: 背景色（例: "soft pastel blue #E8F4FC"）

    Returns:
        グリッド画像のバイトデータ
    """
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["standard_sd"])
    style_prompt = style_info["prompt"]

    image_data, mime_type = load_image_as_base64(character_path)

    # 背景色を決定（指定がなければデフォルト）
    bg_color = background_color or "light blue #E8F4FC"

    # 12個のリアクションの説明を作成（詳細化版・アイテム情報があれば使用）
    reactions_text_parts = []
    for i, r in enumerate(reactions[:12]):
        # アイテム情報を追加
        item_text = ""
        if r.get('item'):
            item = r['item']
            item_text = f"\n  Item: {item['name_en']} ({item['description_en']})\n  Hold style: {item.get('hold_style', 'holding in hands')}"

        if 'enhanced_prompt' in r and r['enhanced_prompt']:
            # 詳細化されたプロンプトがある場合
            reactions_text_parts.append(
                f"Cell {i+1}: \"{r['text']}\"\n{r['enhanced_prompt']}{item_text}"
            )
        else:
            # 従来形式（フォールバック）
            reactions_text_parts.append(
                f"Cell {i+1}: \"{r['text']}\" - {r['emotion']}, {r['pose']}{item_text}"
            )
    reactions_text = "\n\n".join(reactions_text_parts)

    prompt = f"""
Create a SINGLE HORIZONTAL IMAGE containing exactly 12 LINE stickers.

## CRITICAL: IMAGE LAYOUT (MUST FOLLOW)
- Output image: LANDSCAPE orientation (WIDTH > HEIGHT)
- Grid: 4 COLUMNS × 3 ROWS = 12 cells
- Aspect ratio: approximately 4:3 landscape

## GRID ARRANGEMENT:
```
[1] [2] [3] [4]    <- Row 1
[5] [6] [7] [8]    <- Row 2
[9] [10][11][12]   <- Row 3
```

## CRITICAL: CENTERING & CELL SIZE
- ALL 12 cells MUST be EXACTLY EQUAL SIZE (divide image into perfect 4x3 grid)
- Character MUST be PERFECTLY CENTERED in each cell (equal margins on all sides)
- Keep margins MINIMAL (only 5% padding) - character should be LARGE within the cell
- If character is off-center, the entire image is REJECTED
- Text should be placed near character but within cell bounds

## CHARACTER
Use the character from the reference image exactly.
Style: {style_prompt}

## 12 STICKER CONTENTS (with detailed expressions and poses):
{reactions_text}

## VISUAL STYLE
- SAME character in ALL 12 cells
- Japanese text (handwritten, floating near character)
- Background color: {bg_color}
- Bold outlines
- NO grid lines between cells
- Characters should be LARGE and fill most of each cell (minimal margins)
- Follow the detailed facial expressions and poses described above for each cell

## ITEMS (if specified in cell contents)
- When an item is specified for a cell, the character MUST be holding/interacting with that item
- Draw the item in the chibi style matching the character
- Item should be clearly visible and recognizable
- Adjust the character's pose to naturally hold the item as described in "Hold style"
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


def generate_grid_from_reference(client, image_path: str, reactions: list, transparent_bg: bool = True, prompt_style: str = "markdown", chibi_style: str = "ultra_sd") -> bytes:
    """参照画像から12枚のスタンプを1枚のグリッド画像として生成（省エネモード）

    Args:
        prompt_style: "markdown" または "yaml" を指定
        chibi_style: CHIBI_STYLES のキー（例: "standard_sd", "puni", "gacha"）
    """
    # スタイル取得
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["standard_sd"])
    style_prompt = style_info["prompt"]

    # 画像を読み込み
    image_data, mime_type = load_image_as_base64(image_path)

    # 背景指示
    bg_instruction = """
    - Pure white background (#FFFFFF) for each cell
    - High contrast between subject and background
    - Clean, sharp edges on the character
    """ if transparent_bg else "- Simple solid color background"

    # 12個のリアクションの説明を作成（行・列位置を明示）
    reaction_descriptions = []
    for i, r in enumerate(reactions[:12]):
        row = (i // 4) + 1  # 1, 2, 3
        col = (i % 4) + 1   # 1, 2, 3, 4
        text_part = f' Text: "{r["text"]}"' if r["text"] else " (no text)"
        reaction_descriptions.append(f"[Row{row}-Col{col}] {r['emotion']}, {r['pose']}.{text_part}")

    reactions_text = "\n".join(reaction_descriptions)

    # YAML形式のリアクション説明
    yaml_cells = []
    for i, r in enumerate(reactions[:12]):
        row = (i // 4) + 1
        col = (i % 4) + 1
        text_val = f'"{r["text"]}"' if r["text"] else "null"
        yaml_cells.append(f"""  cell_{i+1}:
    position: [row_{row}, col_{col}]
    emotion: "{r['emotion']}"
    pose: "{r['pose']}"
    text: {text_val}""")
    yaml_reactions = "\n".join(yaml_cells)

    if prompt_style == "yaml":
        # YAML形式プロンプト
        prompt = f"""
Generate a LINE sticker grid image based on this specification:

```yaml
output:
  type: single_image
  format: grid

grid:
  columns: 4
  rows: 3
  total_cells: 12
  aspect_ratio: "4:3"
  cell_size: equal

character:
  style: "{style_prompt}"
  source: reference_image_only
  add_extra_characters: false

cells:
{yaml_reactions}

style:
  outline: bold_black
  contrast: high
  colors: high_saturation
  text_style: handwritten_floating
  background: {'"white"' if transparent_bg else '"solid_color"'}
```

Create exactly this 4x3 grid layout with 12 sticker cells.
"""
    else:
        # Markdown形式プロンプト（デフォルト）
        prompt = f"""
Create a SINGLE IMAGE containing exactly 12 LINE stickers in a STRICT 4x3 GRID layout.

## CRITICAL: CHARACTER STYLE (MUST FOLLOW)
**Art Style: {style_prompt}**
This style MUST be consistently applied to ALL 12 sticker cells.
- The character proportions and art style defined above are MANDATORY
- Do NOT deviate from this style specification

## GRID STRUCTURE
- Layout: 4 COLUMNS (horizontal) × 3 ROWS (vertical) = 12 cells total
- Aspect ratio: The output image must be WIDER than tall (approximately 4:3 ratio)
- Each cell must be EQUAL SIZE
- NO grid lines, NO borders, NO separating lines between cells
- Cell arrangement (left to right, top to bottom):
  Row 1: [Cell 1] [Cell 2] [Cell 3] [Cell 4]
  Row 2: [Cell 5] [Cell 6] [Cell 7] [Cell 8]
  Row 3: [Cell 9] [Cell 10] [Cell 11] [Cell 12]

## CHARACTER
Create {style_prompt} versions based ONLY on the reference image.
Keep the same character(s) in every cell - do NOT add any extra characters.

## 12 STICKER CONTENTS (one per cell):
{reactions_text}

## VISUAL STYLE
- Art style: {style_prompt}
- Bold black outlines, high contrast
- Handwritten-style floating text (NO speech bubbles, NO signs held)
- High saturation colors (avoid white/pale)
- ALL cells must have the SAME background color (use light pastel blue #E8F4FC or white #FFFFFF)
{bg_instruction}

## OUTPUT FORMAT
Single image, 4 columns × 3 rows grid, 12 equal-sized sticker cells with {style_prompt} art style.
"""

    # 画像付きリクエスト
    contents = [
        types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
        prompt
    ]

    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
        )
    )

    # レスポンスから画像データを抽出
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            return part.inline_data.data

    raise ValueError("グリッド画像が生成されませんでした")


def split_grid_image(grid_img: Image.Image, rows: int = 3, cols: int = 4) -> list:
    """グリッド画像を個別のスタンプに分割"""
    width, height = grid_img.size
    cell_width = width // cols
    cell_height = height // rows

    stamps = []
    for row in range(rows):
        for col in range(cols):
            left = col * cell_width
            top = row * cell_height
            right = left + cell_width
            bottom = top + cell_height

            cell = grid_img.crop((left, top, right, bottom))
            stamps.append(cell)

    return stamps


def center_character_in_cell(cell_img: Image.Image) -> Image.Image:
    """セル内のキャラクターを中央に再配置

    1. 背景色を検出（四隅のピクセルから推定）
    2. 非背景領域（キャラクター）のバウンディングボックスを取得
    3. キャラクターをセル中央に再配置
    """
    # RGBAに変換
    if cell_img.mode != "RGBA":
        cell_img = cell_img.convert("RGBA")

    width, height = cell_img.size

    # 四隅のピクセルから背景色を推定
    corners = [
        cell_img.getpixel((0, 0)),
        cell_img.getpixel((width - 1, 0)),
        cell_img.getpixel((0, height - 1)),
        cell_img.getpixel((width - 1, height - 1)),
    ]

    # 最も多い色を背景色とする（簡易的な方法）
    # RGB部分のみで比較（アルファを除く）
    corner_rgb = [c[:3] for c in corners]
    bg_color = Counter(corner_rgb).most_common(1)[0][0]

    # 背景色との差が閾値以上のピクセルを「キャラクター」と判定
    threshold = 30  # RGB各成分の差の閾値

    # バウンディングボックスを計算
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    has_content = False

    for y in range(height):
        for x in range(width):
            pixel = cell_img.getpixel((x, y))
            r, g, b = pixel[:3]
            bg_r, bg_g, bg_b = bg_color

            # 背景色との差を計算
            diff = abs(r - bg_r) + abs(g - bg_g) + abs(b - bg_b)

            if diff > threshold:
                has_content = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    # キャラクターが見つからない場合はそのまま返す
    if not has_content or max_x <= min_x or max_y <= min_y:
        return cell_img

    # キャラクター部分を切り出し
    char_width = max_x - min_x + 1
    char_height = max_y - min_y + 1
    character = cell_img.crop((min_x, min_y, max_x + 1, max_y + 1))

    # 新しいセル画像を作成（背景色で塗りつぶし）
    new_cell = Image.new("RGBA", (width, height), (*bg_color, 255))

    # キャラクターを中央に配置
    paste_x = (width - char_width) // 2
    paste_y = (height - char_height) // 2

    # アルファチャンネルを考慮してペースト
    new_cell.paste(character, (paste_x, paste_y), character)

    return new_cell


def process_grid_image(image_data: bytes, remove_bg: bool = True) -> list:
    """グリッド画像を処理して12枚のスタンプに分割"""

    # バイトデータから画像を読み込み
    grid_img = Image.open(io.BytesIO(image_data))

    # RGBAに変換
    if grid_img.mode != "RGBA":
        grid_img = grid_img.convert("RGBA")

    # 先に12分割（背景除去は各スタンプ個別に適用）
    stamps = split_grid_image(grid_img, rows=3, cols=4)

    # 各スタンプを個別に処理
    processed_stamps = []
    for i, stamp in enumerate(stamps):
        print(f"  スタンプ {i+1}/12 を処理中...")

        # 各スタンプ個別に背景除去
        if remove_bg:
            stamp = remove_background(stamp)

        # アスペクト比を維持してリサイズ
        stamp.thumbnail(STAMP_SIZE, Image.Resampling.LANCZOS)

        # 中央配置用の新しい画像を作成（透過背景）
        new_img = Image.new("RGBA", STAMP_SIZE, (0, 0, 0, 0))
        x = (STAMP_SIZE[0] - stamp.width) // 2
        y = (STAMP_SIZE[1] - stamp.height) // 2
        new_img.paste(stamp, (x, y), stamp)

        processed_stamps.append(new_img)

    return processed_stamps


def generate_eco_sticker_set(client, image_path: str, output_dir: str, remove_bg: bool = True):
    """省エネモード: 1回のAPI呼び出しで12枚のスタンプを生成"""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 最初の12個のリアクションを使用
    reactions = REACTIONS[:12]

    print(f"省エネモード: 12枚を1回のAPI呼び出しで生成します")
    print("グリッド画像を生成中...")

    try:
        # グリッド画像を生成
        grid_data = generate_grid_from_reference(client, image_path, reactions, transparent_bg=remove_bg)

        # グリッド画像を保存（デバッグ用）
        grid_img = Image.open(io.BytesIO(grid_data))
        grid_path = f"{output_dir}/_grid_original.png"
        grid_img.save(grid_path, "PNG")
        print(f"グリッド画像保存: {grid_path}")

        # 透過処理と分割
        print("背景透過処理と分割中...")
        stamps = process_grid_image(grid_data, remove_bg=remove_bg)

        # 各スタンプを保存
        for i, (stamp, reaction) in enumerate(zip(stamps, reactions)):
            output_path = f"{output_dir}/{i + 1:02d}_{reaction['id']}.png"
            save_image(stamp, output_path)

        print(f"\n完了! {output_dir} に12枚のスタンプを保存しました")
        print(f"API呼び出し: 1回（通常モードの12分の1）")

    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        raise


def generate_24_stickers(client, image_path: str, output_dir: str, remove_bg: bool = False, chibi_style: str = "ultra_sd", detect_items: bool = True):
    """24パターン生成（2段階方式）: キャラクター生成→リアクショングリッド生成

    改善版ワークフロー:
    1. 参照写真からアイテムを検出（オプション）
    2. 参照写真からサンプルキャラクターを生成（スタイルを確実に適用）
    3. キャラクターに基づいて背景色を自動決定
    4. 各リアクションをAIで詳細化
    5. アイテムとリアクションをマッチング
    6. サンプルキャラクターを参照してリアクショングリッドを生成

    Args:
        detect_items: Trueの場合、写真からアイテムを検出してスタンプに反映
    """

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    style_name = CHIBI_STYLES.get(chibi_style, {}).get('name', chibi_style)
    style_info = CHIBI_STYLES.get(chibi_style, CHIBI_STYLES["standard_sd"])
    style_prompt = style_info["prompt"]
    print(f"スタイル: {style_name}")
    print("=" * 50)

    # プロンプト記録用辞書
    prompts_log = {
        "generated_at": datetime.now().isoformat(),
        "style": chibi_style,
        "style_name": style_name,
        "style_prompt": style_prompt,
        "character_prompt": None,
        "background_color": None,
        "detected_items": [],
        "reactions": [],
        "grid_prompts": []
    }

    # Step 0: アイテム検出（オプション）
    detected_items = []
    if detect_items:
        print("\n[Step 0/6] 写真からアイテムを検出中...")
        try:
            detected_items = detect_items_from_image(client, image_path)
            if detected_items:
                print(f"  検出されたアイテム: {len(detected_items)}個")
                for item in detected_items:
                    print(f"    - {item['name']}: {item['description']}")
                prompts_log["detected_items"] = detected_items

                # items.json を保存
                items_path = f"{output_dir}/_items.json"
                with open(items_path, "w", encoding="utf-8") as f:
                    json.dump(detected_items, f, ensure_ascii=False, indent=2)
                print(f"  アイテム情報保存: {items_path}")
            else:
                print("  アイテムは検出されませんでした")
        except Exception as e:
            print(f"  警告: アイテム検出に失敗 ({e})")
            detected_items = []

    # Step 1: サンプルキャラクター生成
    print("\n[Step 1/6] サンプルキャラクターを生成中...")
    character_path = f"{output_dir}/_character.png"

    # キャラクター生成プロンプトを記録
    character_prompt = f"""
Look at this reference photo and create a SINGLE character illustration based on it.

## STYLE (MUST FOLLOW EXACTLY)
{style_prompt}

## REQUIREMENTS
- Transform the person in the photo into the style specified above
- Keep the same hair color, eye color, and general appearance
- Simple standing pose, facing forward
- Neutral happy expression
- Plain white background
- NO text, NO accessories, just the character
- The character should fill most of the frame

## OUTPUT
Single character illustration only. No grid, no multiple views.
"""
    prompts_log["character_prompt"] = character_prompt.strip()

    generate_character_from_reference(client, image_path, character_path, chibi_style=chibi_style)

    # Step 2: 背景色を自動決定
    print("\n[Step 2/6] キャラクターに最適な背景色を決定中...")
    try:
        background_color = determine_background_color(client, character_path)
        print(f"  決定した背景色: {background_color}")
    except Exception as e:
        print(f"  警告: 背景色決定に失敗、デフォルトを使用 ({e})")
        background_color = "light blue #E8F4FC"

    prompts_log["background_color"] = background_color

    # Step 3: リアクションを詳細化
    print("\n[Step 3/6] 各リアクションを詳細化中...")
    reactions_part1 = REACTIONS[:12]
    reactions_part2 = REACTIONS[12:24]

    enhanced_reactions_all = []
    for i, reaction in enumerate(REACTIONS[:24]):
        print(f"  リアクション {i+1}/24: {reaction['text']}...")
        try:
            enhanced_prompt = enhance_reaction_with_ai(client, reaction)
            enhanced_reaction = {**reaction, 'enhanced_prompt': enhanced_prompt}
        except Exception as e:
            print(f"    警告: 詳細化に失敗、元のプロンプトを使用 ({e})")
            enhanced_reaction = {**reaction, 'enhanced_prompt': None}
        enhanced_reactions_all.append(enhanced_reaction)

        # プロンプトを記録
        prompts_log["reactions"].append({
            "index": i + 1,
            "id": reaction["id"],
            "text": reaction["text"],
            "original_emotion": reaction["emotion"],
            "original_pose": reaction["pose"],
            "enhanced_prompt": enhanced_reaction.get("enhanced_prompt")
        })

    # Step 4: アイテムとリアクションのマッチング
    if detected_items:
        print("\n[Step 4/6] アイテムとリアクションをマッチング中...")
        try:
            enhanced_reactions_all = match_items_to_reactions(client, detected_items, enhanced_reactions_all)
            # マッチング結果をログに追加
            for i, r in enumerate(enhanced_reactions_all):
                if r.get('item'):
                    prompts_log["reactions"][i]["matched_item"] = r['item']['name']
                    print(f"  {r['text']} → {r['item']['name']}")
                else:
                    prompts_log["reactions"][i]["matched_item"] = None
        except Exception as e:
            print(f"  警告: アイテムマッチングに失敗 ({e})")
    else:
        print("\n[Step 4/6] アイテムなし（スキップ）")

    enhanced_part1 = enhanced_reactions_all[:12]
    enhanced_part2 = enhanced_reactions_all[12:24]

    # Step 5: リアクショングリッド生成（キャラクター画像を参照）
    print("\n[Step 5/6] リアクショングリッドを生成中...")

    for grid_num, reactions_list in enumerate([enhanced_part1, enhanced_part2], 1):
        print(f"  グリッド {grid_num}/2 を生成中...")

        # グリッドプロンプトを構築・記録（アイテム情報を含む）
        bg_color = background_color or "light blue #E8F4FC"
        reactions_text_parts = []
        for idx, r in enumerate(reactions_list):
            # アイテム情報を追加
            item_text = ""
            if r.get('item'):
                item = r['item']
                item_text = f"\n  Item: {item['name_en']} ({item['description_en']})\n  Hold style: {item.get('hold_style', 'holding in hands')}"

            if 'enhanced_prompt' in r and r['enhanced_prompt']:
                reactions_text_parts.append(f"Cell {idx+1}: \"{r['text']}\"\n{r['enhanced_prompt']}{item_text}")
            else:
                reactions_text_parts.append(f"Cell {idx+1}: \"{r['text']}\" - {r['emotion']}, {r['pose']}{item_text}")
        reactions_text = "\n\n".join(reactions_text_parts)

        grid_prompt = f"""
Create a SINGLE HORIZONTAL IMAGE containing exactly 12 LINE stickers.

## CRITICAL: IMAGE LAYOUT (MUST FOLLOW)
- Output image: LANDSCAPE orientation (WIDTH > HEIGHT)
- Grid: 4 COLUMNS × 3 ROWS = 12 cells
- Aspect ratio: approximately 4:3 landscape

## GRID ARRANGEMENT:
```
[1] [2] [3] [4]    <- Row 1
[5] [6] [7] [8]    <- Row 2
[9] [10][11][12]   <- Row 3
```

## CRITICAL: CENTERING & CELL SIZE
- ALL 12 cells MUST be EXACTLY EQUAL SIZE (divide image into perfect 4x3 grid)
- Character MUST be PERFECTLY CENTERED in each cell (equal margins on all sides)
- Keep margins MINIMAL (only 5% padding) - character should be LARGE within the cell
- If character is off-center, the entire image is REJECTED
- Text should be placed near character but within cell bounds

## CHARACTER
Use the character from the reference image exactly.
Style: {style_prompt}

## 12 STICKER CONTENTS (with detailed expressions and poses):
{reactions_text}

## VISUAL STYLE
- SAME character in ALL 12 cells
- Japanese text (handwritten, floating near character)
- Background color: {bg_color}
- Bold outlines
- NO grid lines between cells
- Characters should be LARGE and fill most of each cell (minimal margins)
- Follow the detailed facial expressions and poses described above for each cell
"""
        prompts_log["grid_prompts"].append({
            "grid_num": grid_num,
            "prompt": grid_prompt.strip()
        })

        # キャラクター画像を参照してグリッド生成（詳細化プロンプトと背景色を使用）
        grid_data = generate_grid_from_character(
            client, character_path, reactions_list,
            chibi_style=chibi_style, background_color=background_color
        )

        # グリッド画像を保存
        grid_img = Image.open(io.BytesIO(grid_data))
        grid_path = f"{output_dir}/grid_{grid_num}.png"
        grid_img.save(grid_path, "PNG")
        print(f"  グリッド画像保存: {grid_path}")

        # 12分割
        stamps = split_grid_image(grid_img, rows=3, cols=4)

        # 各スタンプをセンタリング
        print(f"  各スタンプをセンタリング中...")
        stamps = [center_character_in_cell(s) for s in stamps]

        # 各スタンプを保存
        original_reactions = reactions_part1 if grid_num == 1 else reactions_part2
        for i, (stamp, reaction) in enumerate(zip(stamps, original_reactions)):
            idx = (grid_num - 1) * 12 + i + 1
            output_path = f"{output_dir}/{idx:02d}_{reaction['id']}.png"
            stamp.save(output_path, "PNG")
            print(f"  保存: {output_path}")

    # プロンプトをJSONで保存
    prompts_path = f"{output_dir}/_prompts.json"
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts_log, f, ensure_ascii=False, indent=2)
    print(f"\n  プロンプト保存: {prompts_path}")

    print("\n[Step 6/6] 完了!")
    print(f"出力先: {output_dir}")
    print(f"  - キャラクター画像: _character.png")
    print(f"  - 背景色: {background_color}")
    if detected_items:
        print(f"  - 検出アイテム: {len(detected_items)}個 (_items.json)")
    print(f"  - プロンプト: _prompts.json")
    print(f"  - スタンプ: 24枚")
    api_calls = 28 + (2 if detected_items else 0)  # アイテム検出1回 + マッチング1回
    print(f"API呼び出し: {api_calls}回（キャラクター1回 + 背景色1回 + 詳細化24回 + グリッド2回" + (" + アイテム検出1回 + マッチング1回）" if detected_items else "）"))


def generate_main_image(stamp_path: str, output_path: str):
    """メイン画像（240×240px）を生成 - 1枚目のスタンプをリサイズ"""
    img = Image.open(stamp_path)

    # RGBAモードを維持
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 正方形にクロップ（中央から）
    width, height = img.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))

    # 240x240にリサイズ
    img = img.resize(MAIN_SIZE, Image.Resampling.LANCZOS)

    # 保存
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"メイン画像保存: {output_path}")


def generate_tab_image(main_path: str, output_path: str):
    """タブ画像（96×74px）を生成 - メイン画像をリサイズ"""
    img = Image.open(main_path)

    # RGBAモードを維持
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # アスペクト比を維持してリサイズ（TAB_SIZEに収まるように）
    img.thumbnail(TAB_SIZE, Image.Resampling.LANCZOS)

    # 中央配置用の新しい画像を作成（透過背景）
    new_img = Image.new("RGBA", TAB_SIZE, (0, 0, 0, 0))
    x = (TAB_SIZE[0] - img.width) // 2
    y = (TAB_SIZE[1] - img.height) // 2
    new_img.paste(img, (x, y), img)

    # 保存
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    new_img.save(output_path, "PNG", optimize=True)
    print(f"タブ画像保存: {output_path}")


def create_submission_zip(output_dir: str) -> str:
    """申請用ZIPパッケージを作成"""
    output_path = Path(output_dir)
    zip_path = output_path / "submission.zip"

    # 必要なファイルを収集
    files_to_zip = []

    # main.png
    main_file = output_path / "main.png"
    if main_file.exists():
        files_to_zip.append(("main.png", main_file))

    # tab.png
    tab_file = output_path / "tab.png"
    if tab_file.exists():
        files_to_zip.append(("tab.png", tab_file))

    # スタンプ画像（01.png ~ 24.png）
    for i in range(1, 25):
        stamp_file = output_path / f"{i:02d}.png"
        if stamp_file.exists():
            files_to_zip.append((f"{i:02d}.png", stamp_file))

    # ZIPファイルを作成
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for arcname, filepath in files_to_zip:
            zf.write(filepath, arcname)

    print(f"申請用ZIP作成: {zip_path}")
    print(f"  含まれるファイル: {len(files_to_zip)}個")
    return str(zip_path)


def generate_submission_package(client, image_path: str, output_dir: str, chibi_style: str = "ultra_sd", detect_items: bool = True):
    """LINE審査申請用パッケージを生成

    Args:
        detect_items: Trueの場合、写真からアイテムを検出してスタンプに反映
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("LINE スタンプ申請パッケージ生成")
    print("=" * 50)

    # Step 1: 24枚のスタンプを生成（--eco24と同様）
    print("\n[Step 1/4] 24枚のスタンプを生成中...")
    generate_24_stickers(client, image_path, output_dir, remove_bg=False, chibi_style=chibi_style, detect_items=detect_items)

    # Step 2: スタンプファイル名を申請用に変更（01_ok.png → 01.png）
    print("\n[Step 2/4] ファイル名を申請形式に変更中...")
    output_path = Path(output_dir)
    for i, reaction in enumerate(REACTIONS[:24], 1):
        src = output_path / f"{i:02d}_{reaction['id']}.png"
        dst = output_path / f"{i:02d}.png"
        if src.exists():
            # 既存ファイルがある場合は削除してからリネーム
            if dst.exists():
                dst.unlink()
            src.rename(dst)
            print(f"  {src.name} → {dst.name}")

    # Step 3: メイン画像を生成（1枚目をリサイズ）
    print("\n[Step 3/4] メイン画像・タブ画像を生成中...")
    first_stamp = output_path / "01.png"
    main_path = output_path / "main.png"
    tab_path = output_path / "tab.png"

    if first_stamp.exists():
        generate_main_image(str(first_stamp), str(main_path))
        generate_tab_image(str(main_path), str(tab_path))
    else:
        print("警告: 1枚目のスタンプが見つかりません")

    # Step 4: ZIPパッケージを作成
    print("\n[Step 4/4] 申請用ZIPパッケージを作成中...")
    create_submission_zip(output_dir)

    # 結果サマリー
    print("\n" + "=" * 50)
    print("完了! 生成されたファイル:")
    print("=" * 50)
    print(f"  ディレクトリ: {output_dir}")
    print(f"  main.png     : 240×240px (メイン画像)")
    print(f"  tab.png      : 96×74px (タブ画像)")
    print(f"  01.png～24.png: 370×320px (スタンプ画像)")
    print(f"  submission.zip: 申請用パッケージ")
    print("\nLINE Creators Marketで申請時にsubmission.zipをアップロードしてください。")


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
        # CUDAプロバイダーを優先
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        _use_cuda = True
    else:
        if use_cuda:
            print("[WARN] CUDA が利用できません。CPUモードで実行します。")
            print(f"   利用可能なプロバイダー: {cuda_info['providers']}")
        else:
            print("[CPU] CPUモードで実行します")
        providers = ["CPUExecutionProvider"]
        _use_cuda = False

    # isnet-anime モデルでセッション作成（アニメ/イラスト特化）
    _rembg_session = new_session("isnet-anime", providers=providers)
    return _rembg_session


def remove_background(img: Image.Image) -> Image.Image:
    """AI背景除去（CUDA対応・アニメ/イラスト最適化）"""
    global _rembg_session

    device_info = "GPU (CUDA)" if _use_cuda else "CPU"
    print(f"背景を除去中... [{device_info}]")

    return remove(
        img,
        session=_rembg_session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=200,  # より多くを前景として保持（240→200）
        alpha_matting_background_threshold=20,   # 背景判定を控えめに（10→20）
        alpha_matting_erode_size=3,              # 細部を保護（10→3）
    )


def process_image(image_data: bytes, size: tuple = STAMP_SIZE, remove_bg: bool = True) -> Image.Image:
    """画像をLINEスタンプ仕様に処理"""

    # バイトデータから画像を読み込み
    img = Image.open(io.BytesIO(image_data))

    # RGBAに変換（透過対応）
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    # 背景除去
    if remove_bg:
        img = remove_background(img)

    # アスペクト比を維持してリサイズ
    img.thumbnail(size, Image.Resampling.LANCZOS)

    # 中央配置用の新しい画像を作成（透過背景）
    new_img = Image.new("RGBA", size, (0, 0, 0, 0))

    # 中央に配置
    x = (size[0] - img.width) // 2
    y = (size[1] - img.height) // 2
    new_img.paste(img, (x, y), img)

    return new_img


def save_image(img: Image.Image, output_path: str):
    """PNG形式で保存"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG", optimize=True)
    print(f"保存完了: {output_path}")


def generate_sticker_set(client, image_path: str, output_dir: str, remove_bg: bool = True):
    """24種類のリアクションスタンプを一括生成"""
    import random

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # リアクションをシャッフル
    reactions = REACTIONS.copy()
    random.shuffle(reactions)

    for i, reaction in enumerate(reactions):
        print(f"生成中... ({i + 1}/{len(reactions)}) - {reaction['id']}: {reaction['text']}")

        try:
            image_data = generate_from_reference(client, image_path, reaction, transparent_bg=remove_bg)
            img = process_image(image_data, STAMP_SIZE, remove_bg=remove_bg)

            output_path = f"{output_dir}/{i + 1:02d}_{reaction['id']}.png"
            save_image(img, output_path)

        except Exception as e:
            print(f"エラー ({reaction['id']}): {e}", file=sys.stderr)
            continue

    print(f"\n完了! {output_dir} に保存されました")


def main():
    parser = argparse.ArgumentParser(description="LINEスタンプ画像生成")

    # モード選択（--check-cuda使用時は不要）
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--prompt", "-p", help="プロンプトから生成")
    mode_group.add_argument("--sticker-set", "-s", metavar="IMAGE",
                            help="参照画像から24種類のスタンプセットを生成")
    mode_group.add_argument("--eco", "-e", metavar="IMAGE",
                            help="省エネモード: 1回のAPI呼び出しで12枚生成（グリッド方式）")
    mode_group.add_argument("--eco24", metavar="IMAGE",
                            help="24パターン生成: 12枚x2グリッドを生成し、24個に分割（透過処理なし）")
    mode_group.add_argument("--package", metavar="IMAGE",
                            help="LINE審査申請用パッケージ生成（24スタンプ + メイン/タブ画像 + ZIP）")

    # 共通オプション
    parser.add_argument("--output", "-o", help="出力先（ファイルまたはディレクトリ）")
    parser.add_argument("--style", choices=list(CHIBI_STYLES.keys()),
                        default="ultra_sd", help="ちびキャラスタイル（例: ultra_sd, choi_sd, standard_sd）")
    parser.add_argument("--type", "-t", choices=["stamp", "main", "tab"],
                        default="stamp", help="画像タイプ")
    parser.add_argument("--count", "-c", type=int, default=1,
                        help="生成枚数（--promptモード時）")
    parser.add_argument("--project", help="Google Cloud プロジェクトID")
    parser.add_argument("--no-remove-bg", action="store_true",
                        help="背景除去をスキップ")
    parser.add_argument("--no-items", action="store_true",
                        help="アイテム検出をスキップ（デフォルトは写真からアイテムを自動検出）")
    parser.add_argument("--cpu", action="store_true",
                        help="CUDAを使用せずCPUで処理（デフォルトはCUDA優先）")
    parser.add_argument("--check-cuda", action="store_true",
                        help="CUDA環境をチェックして終了")

    args = parser.parse_args()

    # CUDA環境チェックモード
    if args.check_cuda:
        cuda_info = check_cuda_availability()
        print("=== CUDA 環境チェック ===")
        print(f"CUDA利用可能: {'はい' if cuda_info['cuda_available'] else 'いいえ'}")
        if cuda_info['device_name']:
            print(f"GPUデバイス: {cuda_info['device_name']}")
        print(f"利用可能プロバイダー: {', '.join(cuda_info['providers'])}")
        return

    # 生成モードの場合は --prompt, --sticker-set, --eco, --eco24, --package のいずれかが必須
    if not args.prompt and not args.sticker_set and not args.eco and not args.eco24 and not args.package:
        parser.error("--prompt, --sticker-set, --eco, --eco24, --package のいずれかを指定してください")

    # クライアント作成
    client = create_client(args.project)
    remove_bg = not getattr(args, 'no_remove_bg', False)

    # rembgセッション初期化（CUDA対応）
    if remove_bg:
        init_rembg_session(use_cuda=False)  # CPUモード固定

    # スタンプセット生成モード
    if args.sticker_set:
        if not os.path.exists(args.sticker_set):
            print(f"Error: 画像が見つかりません: {args.sticker_set}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/linestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        generate_sticker_set(client, args.sticker_set, output_dir, remove_bg)
        return

    # 省エネモード（グリッド生成）
    if args.eco:
        if not os.path.exists(args.eco):
            print(f"Error: 画像が見つかりません: {args.eco}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/linestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        generate_eco_sticker_set(client, args.eco, output_dir, remove_bg)
        return

    # 24パターン生成モード
    if args.eco24:
        if not os.path.exists(args.eco24):
            print(f"Error: 画像が見つかりません: {args.eco24}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/linestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        detect_items_flag = not getattr(args, 'no_items', False)
        generate_24_stickers(client, args.eco24, output_dir, remove_bg=False, chibi_style=args.style, detect_items=detect_items_flag)
        return

    # 申請パッケージ生成モード
    if args.package:
        if not os.path.exists(args.package):
            print(f"Error: 画像が見つかりません: {args.package}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/linestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        detect_items_flag = not getattr(args, 'no_items', False)
        generate_submission_package(client, args.package, output_dir, chibi_style=args.style, detect_items=detect_items_flag)
        return

    # 通常の生成モード
    sizes = {
        "stamp": STAMP_SIZE,
        "main": MAIN_SIZE,
        "tab": TAB_SIZE
    }
    size = sizes[args.type]

    for i in range(args.count):
        print(f"生成中... ({i + 1}/{args.count})")

        try:
            image_data = generate_image(client, args.prompt, transparent_bg=remove_bg)
            img = process_image(image_data, size, remove_bg=remove_bg)

            if args.output:
                if args.count > 1:
                    base, ext = os.path.splitext(args.output)
                    output_path = f"{base}_{i + 1:03d}{ext}"
                else:
                    output_path = args.output
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"./output/linestamp_{timestamp}_{i + 1:03d}.png"

            save_image(img, output_path)

        except Exception as e:
            print(f"エラー: {e}", file=sys.stderr)
            sys.exit(1)

    print("完了!")


if __name__ == "__main__":
    main()
