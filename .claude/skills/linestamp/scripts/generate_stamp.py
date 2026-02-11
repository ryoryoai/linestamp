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
import yaml
import zipfile
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image, ImageFilter
from rembg import remove, new_session
import io

# ポーズマスタ参照
try:
    from database import (
        get_pose as db_get_pose,
        get_pose_master,
        get_text_master,
        get_reactions_master,
        select_reactions_for_persona,
        record_generation_log,
        update_pose_master_stats,
        get_persona_config,
    )
    POSE_DB_AVAILABLE = True
    MASTER_DB_AVAILABLE = True
except ImportError:
    POSE_DB_AVAILABLE = False
    MASTER_DB_AVAILABLE = False
    get_pose_master = None
    get_text_master = None
    get_reactions_master = None
    select_reactions_for_persona = None
    record_generation_log = None
    update_pose_master_stats = None
    get_persona_config = None
    db_get_pose = None

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

# ============================================================
# ちびキャラスタイル定義（統合版 v2.0）
# - コアスタイル: 5種（デフォルト表示）
# - Advancedスタイル: 3種（詳細設定で表示）
# - 旧スタイルIDはエイリアスで互換性維持
# ============================================================

# コアスタイル（デフォルト表示）
CHIBI_STYLES = {
    # === コアスタイル（5種）===
    "sd_10": {
        "name": "超デフォルメ（1頭身）",
        "description": "1-1.5頭身。感情パーツ最大、表情ドン系。",
        "category": "core",
        "prompt": """ULTRA CHIBI STYLE (1-1.5 heads tall):
        - Giant round head (90% of body mass)
        - Tiny stubby limbs, minimal body
        - Huge expressive eyes (40%+ of face)
        - Very thick bold outlines (5-8px)
        - Flat pastel colors, no gradients
        - Exaggerated facial expressions
        - Simple geometric shapes
        - LINE sticker optimized
        - Maximum cuteness, minimal detail"""
    },
    "sd_25": {
        "name": "標準ちびキャラ（2.5頭身）",
        "description": "2-2.5頭身。バランス良く汎用性高い。推奨。",
        "category": "core",
        "prompt": """STANDARD CHIBI STYLE (2-2.5 heads tall):
        - Large round head with big expressive eyes
        - Small but proportionate body
        - Visible hands and feet (simple shapes)
        - Classic anime chibi proportions
        - Bold outlines, soft shading
        - Cute and balanced appearance
        - Suitable for various emotions and poses
        - Most versatile for LINE stickers"""
    },
    "sd_30": {
        "name": "ジェスチャー重視（3頭身）",
        "description": "3-4頭身。衣装やジェスチャーを表現しやすい。",
        "category": "core",
        "prompt": """TALL CHIBI STYLE (3-4 heads tall):
        - Slightly elongated proportions
        - Visible neck and waist definition
        - Detailed clothing with folds
        - Expressive body language
        - Dynamic poses possible
        - More costume detail visible
        - Good for action stickers
        - Maintains chibi cuteness"""
    },
    "face_only": {
        "name": "顔だけ（表情ドン）",
        "description": "顔のみ。表情で勝負、文字なしに最適。",
        "category": "core",
        "prompt": """FACE ONLY CHIBI STYLE:
        - Just the face/head, no body
        - Giant expressive eyes (50%+ of face)
        - Very thick bold outlines
        - Flat pastel colors
        - Big sparkly eyes with highlights
        - Simple expressive mouth
        - Floating head design
        - Perfect for emotion-focused stickers
        - Best without text overlay"""
    },
    "yuru_line": {
        "name": "ゆる線画",
        "description": "手描き風のゆるいタッチ。10代に人気。",
        "category": "core",
        "prompt": """YURU (LOOSE) LINE ART STYLE:
        - Simple, hand-drawn look with thin sketchy lines
        - 2-3 heads tall ratio
        - Minimal shading, mostly line work
        - Soft, gentle expressions
        - Pastel or muted colors
        - Imperfect, organic line quality (not too clean)
        - Cute but understated aesthetic
        - White or very light background
        - Relaxed, casual vibe
        - Popular with teens"""
    },

    # === Advancedスタイル（3種）===
    "semi_50": {
        "name": "衣装重視（5頭身）",
        "description": "4.5-5頭身。衣装重視だがシンプル寄せ必須。",
        "category": "advanced",
        "prompt": """SEMI-DEFORMED STYLE (4.5-5 heads tall):
        - Nearly normal anime proportions
        - Slight chibi influence for cuteness
        - Detailed clothing and accessories
        - Visible fingers and features
        - Soft realistic shading
        - Mature anime style
        - Keep simple for LINE stickers
        - Avoid over-detailing"""
    },
    "pixel_art": {
        "name": "ピクセルアート",
        "description": "ドット絵スタイル。レトロゲーム風。遊び枠。",
        "category": "advanced",
        "prompt": """PIXEL ART STYLE:
        - 16-bit retro game sprite aesthetic
        - Pixelated blocky appearance
        - Limited color palette (8-16 colors)
        - Crisp pixel edges, no anti-aliasing
        - Chunky visible pixels
        - Simple flat shading with dithering
        - Nostalgic game character feel
        - Note: Hard to maintain likeness"""
    },
    "illustration_rich": {
        "name": "イラストリッチ",
        "description": "旧gacha。華やかだが失敗率高め。デフォルトOFF。",
        "category": "advanced",
        "prompt": """ILLUSTRATION RICH STYLE (Gacha-game inspired):
        - 3.5 heads tall, flashy appearance
        - Sparkles and effects around character
        - Ornate costume with gems/accessories
        - Dynamic dramatic pose
        - Vibrant saturated colors
        - Glamorous mobile game aesthetic
        - Warning: High failure rate
        - May get too detailed for stickers"""
    },
}

# 旧スタイルIDのエイリアス（互換性維持）
STYLE_ALIASES = {
    # sd_10に統合
    "ultra_sd": "sd_10",
    "extreme_chibi": "sd_10",
    "choi_sd": "sd_10",
    # sd_25に統合
    "standard_sd": "sd_25",
    "puni": "sd_25",
    "ball_joint": "sd_25",
    # sd_30に統合
    "tall_sd": "sd_30",
    "mini_chara": "sd_30",
    # semi_50に統合
    "semi_deformed": "semi_50",
    # illustration_richに統合
    "gacha": "illustration_rich",
    # 削除（custom_testは不要）
    "custom_test": "sd_25",
}


def resolve_style_id(style_id: str) -> str:
    """スタイルIDを解決（エイリアス対応）"""
    if style_id in STYLE_ALIASES:
        resolved = STYLE_ALIASES[style_id]
        print(f"スタイル '{style_id}' → '{resolved}' にエイリアス解決")
        return resolved
    return style_id


def get_style(style_id: str) -> dict:
    """スタイル情報を取得（エイリアス対応、フォールバック付き）"""
    resolved_id = resolve_style_id(style_id)
    if resolved_id in CHIBI_STYLES:
        return CHIBI_STYLES[resolved_id]
    # フォールバック: sd_25
    print(f"警告: スタイル '{style_id}' が見つかりません。sd_25を使用します。")
    return CHIBI_STYLES["sd_25"]


def list_styles(category: str = None) -> list:
    """スタイル一覧を取得（カテゴリでフィルタ可能）"""
    styles = []
    for style_id, info in CHIBI_STYLES.items():
        if category is None or info.get("category") == category:
            styles.append({
                "id": style_id,
                "name": info["name"],
                "description": info["description"],
                "category": info.get("category", "core"),
            })
    return styles


# ============================================================
# モディファイアシステム（テキスト・アウトライン・丁寧さ）
# でか文字がデフォルトON、太フチがデフォルトON
# ============================================================

MODIFIERS = {
    "text_mode": {
        "none": {
            "name": "なし",
            "description": "テキストなし（face_only向け）",
            "prompt": "No text on sticker. Expression only."
        },
        "small": {
            "name": "通常",
            "description": "小さめの手書きテキスト",
            "prompt": "Small handwritten text near character, subtle placement."
        },
        "deka": {
            "name": "でか文字（デフォルト）",
            "description": "40%以上の大きな太文字、縁取り付き",
            "prompt": """LARGE BOLD TEXT REQUIREMENTS (CRITICAL):
            - Text MUST occupy 40%+ of the image area
            - Use THICK, BOLD handwritten style (thick brush strokes)
            - Text MUST have THICK WHITE OUTLINE (at least 4-6px) around EVERY letter
            - The white outline around text must be clearly visible and uniform
            - Text must be readable at 96x74px (tab size)
            - High contrast: dark text (black/dark color) with thick white border
            - Place text prominently, not hidden
            - Text outline is SEPARATE from character outline - both must be thick"""
        }
    },
    "outline": {
        "none": {
            "name": "なし",
            "description": "アウトラインなし",
            "prompt": "No outline around character."
        },
        "white": {
            "name": "白フチ",
            "description": "標準的な白フチ（2-3px）",
            "prompt": "White outline around character (2-3px width). Text MUST also have clear white outline (3-4px) around every letter for readability."
        },
        "bold": {
            "name": "太フチ（デフォルト）",
            "description": "どの背景でも見やすい太フチ（5-8px）",
            "prompt": """THICK OUTLINE REQUIREMENTS:
            - Character MUST have thick white outline (5-8px)
            - Text MUST ALSO have thick white outline (4-6px) around every letter
            - Ensures visibility on ANY background color
            - Clean, crisp edge separation
            - No feathering or soft edges"""
        }
    },
    "politeness": {
        "casual": {
            "name": "カジュアル",
            "description": "くだけた友達言葉",
            "prompt": "Casual, friendly language style."
        },
        "polite": {
            "name": "丁寧",
            "description": "敬語・丁寧語",
            "prompt": "Polite, respectful language style."
        }
    }
}

# デフォルトモディファイア設定
DEFAULT_MODIFIERS = {
    "text_mode": "deka",
    "outline": "bold",
    "politeness": "casual"
}

# MVP品質プロファイル（固定パラメータ）
# これらの値は品質を安定させるためにロックされる
MVP_QUALITY = {
    "style": "sd_25",
    "text_mode": "deka",
    "outline": "bold",
    "stamps": 24,
    "output_zip": True,
    "remove_bg": True,
    "detect_items": True,
}


def apply_mvp_quality(args) -> dict:
    """MVP品質プロファイルを適用し、上書きがあれば警告する

    Returns:
        適用された設定のdict
    """
    overrides = []

    # スタイル固定
    resolved_style = STYLE_ALIASES.get(args.style, args.style) if args.style else "sd_25"
    if resolved_style != MVP_QUALITY["style"]:
        overrides.append(f"style: {resolved_style} → {MVP_QUALITY['style']}")
    args.style = MVP_QUALITY["style"]

    # テキストモード固定
    if getattr(args, 'text_mode', 'deka') != MVP_QUALITY["text_mode"]:
        overrides.append(f"text_mode: {args.text_mode} → {MVP_QUALITY['text_mode']}")
    args.text_mode = MVP_QUALITY["text_mode"]

    # アウトライン固定
    if getattr(args, 'outline', 'bold') != MVP_QUALITY["outline"]:
        overrides.append(f"outline: {args.outline} → {MVP_QUALITY['outline']}")
    args.outline = MVP_QUALITY["outline"]

    # 背景透過は常にON
    if getattr(args, 'no_remove_bg', False):
        overrides.append("no_remove_bg: True → False (透過は必須)")
    args.no_remove_bg = False

    # アイテム検出は常にON
    if getattr(args, 'no_items', False):
        overrides.append("no_items: True → False (アイテム検出は必須)")
    args.no_items = False

    if overrides:
        print("[MVP品質] 以下の設定をMVPプロファイルで上書きしました:")
        for o in overrides:
            print(f"  - {o}")

    # 適用結果をログ
    applied = {
        "style": args.style,
        "text_mode": args.text_mode,
        "outline": args.outline,
        "remove_bg": True,
        "detect_items": True,
        "stamps": 24,
    }
    print(f"[MVP品質] style={applied['style']}, text={applied['text_mode']}, "
          f"outline={applied['outline']}, 透過=ON, アイテム検出=ON")
    return applied


def build_modifier_prompt(modifiers: dict = None) -> str:
    """モディファイア設定からプロンプト文字列を構築"""
    if modifiers is None:
        modifiers = DEFAULT_MODIFIERS.copy()

    prompt_parts = []

    # テキストモード
    text_mode = modifiers.get("text_mode", DEFAULT_MODIFIERS["text_mode"])
    if text_mode in MODIFIERS["text_mode"]:
        prompt_parts.append(MODIFIERS["text_mode"][text_mode]["prompt"])

    # アウトライン
    outline = modifiers.get("outline", DEFAULT_MODIFIERS["outline"])
    if outline in MODIFIERS["outline"]:
        prompt_parts.append(MODIFIERS["outline"][outline]["prompt"])

    return "\n\n".join(prompt_parts)


def get_modifier_info(modifier_type: str, value: str) -> dict:
    """モディファイア情報を取得"""
    if modifier_type in MODIFIERS and value in MODIFIERS[modifier_type]:
        return MODIFIERS[modifier_type][value]
    return None


# 24種類のリアクションテンプレート
# ペルソナ: Teen, Friend, ツッコミ・反応強化, 強度3
REACTIONS = [
    # === コア枠 8枚（30s × Friend） ===
    {"id": "ryo", "emotion": "軽くうなずく笑顔、即レス感", "pose": "ピースサイン", "text": "りょ！"},
    {"id": "oke", "emotion": "明るい笑顔、にっこり", "pose": "サムズアップ", "text": "おけ！"},
    {"id": "sorena", "emotion": "大きくうなずく、共感の表情", "pose": "指さしポーズ", "text": "それな！"},
    {"id": "wakaru", "emotion": "やさしく頷く、わかるの顔", "pose": "両手を胸に当てて共感", "text": "わかる〜"},
    {"id": "arigato", "emotion": "感謝の笑顔、嬉しそう", "pose": "軽くお辞儀", "text": "ありがとう！"},
    {"id": "gomenne", "emotion": "申し訳なさそう、てへぺろ", "pose": "頭をかく、てへぺろ", "text": "ごめんね"},
    {"id": "chottomatte", "emotion": "焦り顔、待って！", "pose": "両手を前に出してストップ", "text": "ちょっと待って"},
    {"id": "otsukare", "emotion": "にこやか、お疲れ", "pose": "手を振る", "text": "おつかれ！"},

    # === 応援テーマ枠 12枚（強度3特化） ===
    {"id": "ganbare", "emotion": "力強い笑顔、応援", "pose": "ガッツポーズ", "text": "がんばれ！"},
    {"id": "fight", "emotion": "元気いっぱい、拳を掲げる", "pose": "片手で拳を上げる", "text": "ファイト！"},
    {"id": "ouenshiteru", "emotion": "温かい笑顔、応援の気持ち", "pose": "両手でメガホンを作る", "text": "応援してる！"},
    {"id": "murishinaide", "emotion": "心配そうな優しい目、気遣い", "pose": "両手を合わせて祈るポーズ", "text": "無理しないでね"},
    {"id": "daijoubu", "emotion": "安心させる微笑み、優しい", "pose": "頭をなでるジェスチャー", "text": "大丈夫だよ"},
    {"id": "sugoijan", "emotion": "目をキラキラ、称賛", "pose": "拍手", "text": "すごいじゃん！"},
    {"id": "sasuga", "emotion": "感心した顔、さすが", "pose": "サムズアップ", "text": "さすが！"},
    {"id": "shinjiteru", "emotion": "真っすぐな目、信頼の笑顔", "pose": "胸に手を当てる", "text": "信じてる！"},
    {"id": "iijan", "emotion": "自信満々の笑顔、肯定", "pose": "右手で親指と人差し指を使った『ＯＫサイン』のジェスチャー。親指と人差し指で丸をつくり、中指・薬指・小指は軽く曲げる。手のひらはやや正面向き、手は顔の横に位置。", "text": "いいじゃん！", "pose_locked": True},
    {"id": "yarujan", "emotion": "驚きと嬉しさ混じりの笑顔", "pose": "指さしポーズ", "text": "やるじゃん！"},
    {"id": "kimikimi", "emotion": "元気いっぱい、応援、満面の笑み", "pose": "両手を胸の前で握り、全身で応援するポーズ", "text": "きみきみ"},
    {"id": "isshoni", "emotion": "仲間意識、温かい笑顔", "pose": "両手を広げて誘う", "text": "一緒にがんばろ！"},

    # === 反応枠 4枚 ===
    {"id": "eh", "emotion": "目まんまる、軽い驚き", "pose": "目を見開く", "text": "えっ"},
    {"id": "majide", "emotion": "目を見開く、驚き", "pose": "口を手で覆う", "text": "マジで？"},
    {"id": "ukeru", "emotion": "爆笑、涙出る", "pose": "笑い転げる", "text": "ウケる！"},
    {"id": "nantokanaru", "emotion": "前向きな笑顔、力強い", "pose": "万歳", "text": "なんとかなる！"},
]


def expand_pose_ref(reaction: dict) -> dict:
    """pose_refがある場合、DBからポーズ詳細を取得して展開する

    Args:
        reaction: リアクション辞書（pose_refを含む可能性あり）

    Returns:
        展開済みのリアクション辞書
        - pose_refが見つかった場合: pose, pose_locked=Trueを設定
        - 見つからない場合: 元のreactionをそのまま返す

    検索順序:
        1. pose_master (v2.0 マスタテーブル) - IDで検索
        2. pose_master - nameで検索
        3. pose_dictionary (レガシーテーブル) - nameで検索
    """
    if not POSE_DB_AVAILABLE or not reaction.get('pose_ref'):
        return reaction

    pose_name = reaction['pose_ref']
    pose_data = None

    # 1. pose_master からIDで検索 (v2.0)
    if MASTER_DB_AVAILABLE and get_pose_master:
        pose_data = get_pose_master(pose_name)

    # 2. pose_dictionary から検索（レガシー互換）
    if not pose_data:
        pose_data = db_get_pose(pose_name)

    if not pose_data:
        print(f"  警告: ポーズ '{pose_name}' がDBに見つかりません。pose_refをスキップします。")
        return reaction

    # DBから取得したポーズ詳細を展開
    expanded = reaction.copy()

    # prompt_full (v2.0) > prompt_ja (legacy) > gesture+expression の順で使用
    if pose_data.get('prompt_full'):
        expanded['pose'] = pose_data['prompt_full']
    elif pose_data.get('prompt_ja'):
        expanded['pose'] = pose_data['prompt_ja']
    else:
        parts = []
        if pose_data.get('gesture'):
            parts.append(pose_data['gesture'].strip())
        if pose_data.get('expression'):
            parts.append(pose_data['expression'].strip())
        if pose_data.get('vibe'):
            parts.append(f"（{pose_data['vibe']}）")
        expanded['pose'] = '\n'.join(parts)

    expanded['pose_locked'] = True
    del expanded['pose_ref']

    print(f"  ポーズ展開: '{pose_name}' → {len(expanded['pose'])}文字のプロンプト")
    return expanded


def expand_all_pose_refs(reactions: list) -> list:
    """リアクションリスト内の全てのpose_refを展開する"""
    return [expand_pose_ref(r) for r in reactions]


def get_reactions_from_db(
    age: str = "20s",
    target: str = "Friend",
    theme: str = None,
    intensity: int = 2,
    limit: int = 24
) -> list:
    """データベースからペルソナに合ったリアクションを取得

    Args:
        age: Teen / 20s / 30s / 40s / 50s+
        target: Friend / Family / Partner / Work
        theme: ツッコミ強化 / 褒め強化 / 応援強化 など
        intensity: 1(控えめ) / 2(バランス) / 3(特化)
        limit: 取得件数

    Returns:
        リアクションリスト (REACTIONS形式)
        DBが利用不可の場合はハードコードのREACTIONSを返す
    """
    if not MASTER_DB_AVAILABLE or not select_reactions_for_persona:
        print("  DBマスタが利用不可のため、ハードコードREACTIONSを使用")
        return REACTIONS[:limit]

    try:
        db_reactions = select_reactions_for_persona(
            age=age,
            target=target,
            theme=theme,
            intensity=intensity,
            limit=limit
        )

        if not db_reactions:
            print("  DBから該当リアクションが見つからず、ハードコードREACTIONSを使用")
            return REACTIONS[:limit]

        # DB結果をREACTIONS形式に変換
        reactions = []
        for r in db_reactions:
            reaction = {
                "id": r.get("id"),
                "emotion": r.get("emotion", ""),
                "text": r.get("text", ""),
                "pose_locked": True,  # DBからの取得は常にロック
                "_pose_id": r.get("pose_id"),  # 生成ログ用
                "_text_id": r.get("text_id"),  # 生成ログ用
            }

            # ポーズ詳細を設定 (prompt_full優先)
            if r.get("prompt_full"):
                reaction["pose"] = r["prompt_full"]
            elif r.get("gesture"):
                parts = [r["gesture"]]
                if r.get("expression"):
                    parts.append(r["expression"])
                if r.get("vibe"):
                    parts.append(f"（{r['vibe']}）")
                reaction["pose"] = "\n".join(parts)
            else:
                reaction["pose"] = r.get("pose_name", "")

            # オプション項目
            if r.get("outfit"):
                reaction["outfit"] = r["outfit"]
            if r.get("item_hint"):
                reaction["item"] = {"type": r["item_hint"]}

            reactions.append(reaction)

        print(f"  DBから{len(reactions)}件のリアクションを取得 (persona: {age}/{target}/{theme})")
        return reactions

    except Exception as e:
        print(f"  DB取得エラー: {e}、ハードコードREACTIONSを使用")
        return REACTIONS[:limit]


def load_reactions_from_file(file_path: str) -> list:
    """JSON/YAMLファイルからカスタムリアクションを読み込む

    Args:
        file_path: リアクションファイルパス (.json or .yaml/.yml)

    Returns:
        リアクションリスト (24件に満たない場合はデフォルトで補完)
    """
    import json
    path = Path(file_path)
    if not path.exists():
        print(f"  Error: リアクションファイルが見つかりません: {file_path}")
        return None

    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            import yaml
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)

        if not isinstance(data, list):
            print(f"  Error: リアクションファイルはリスト形式である必要があります")
            return None

        # バリデーションと正規化
        required_keys = {"id", "emotion", "pose", "text"}
        reactions = []
        for i, item in enumerate(data):
            missing = required_keys - set(item.keys())
            if missing:
                print(f"  Warning: リアクション[{i}]に必須キーがありません: {missing}、スキップ")
                continue

            reaction = {
                "id": item["id"],
                "emotion": item["emotion"],
                "pose": item["pose"],
                "text": item["text"],
                "pose_locked": item.get("pose_locked", False),
            }

            # pose_refがあればDB展開
            if "pose_ref" in item:
                reaction["pose_ref"] = item["pose_ref"]
                reaction = expand_pose_ref(reaction)

            reactions.append(reaction)

        # 24件に満たない場合はデフォルトから補完
        if len(reactions) < 24:
            used_ids = {r["id"] for r in reactions}
            for default_r in REACTIONS:
                if len(reactions) >= 24:
                    break
                if default_r["id"] not in used_ids:
                    reactions.append(default_r)

        print(f"  ファイルから{len(reactions)}件のリアクションを読み込み: {file_path}")
        return reactions[:24]

    except Exception as e:
        print(f"  Error: リアクションファイルの読み込みに失敗: {e}")
        return None


def log_generation_result(
    session_id: str,
    slot_index: int,
    reaction: dict,
    success: bool,
    retry_count: int = 0,
    failure_reason: str = None,
    execution_time_ms: int = None,
    transparency_ok: bool = None,
    size_ok: bool = None,
    quality_score: float = None
):
    """生成結果をDBに記録するヘルパー関数

    Args:
        session_id: セッションID
        slot_index: スロット番号 (0-23)
        reaction: リアクション辞書
        success: 成功/失敗
        retry_count: リトライ回数
        failure_reason: 失敗理由
        execution_time_ms: 実行時間(ms)
        transparency_ok: 透過処理成功
        size_ok: サイズチェック成功
        quality_score: 品質スコア (0-100)
    """
    if not MASTER_DB_AVAILABLE or not record_generation_log:
        return

    try:
        reaction_id = reaction.get("id")
        pose_id = reaction.get("_pose_id")  # DBからの取得時に設定される
        text_id = reaction.get("_text_id")  # DBからの取得時に設定される

        record_generation_log(
            session_id=session_id,
            slot_index=slot_index,
            reaction_id=reaction_id,
            pose_id=pose_id,
            text_id=text_id,
            prompt_text=reaction.get("pose", "")[:500],  # 長すぎる場合は切り詰め
            success=success,
            retry_count=retry_count,
            failure_reason=failure_reason,
            execution_time_ms=execution_time_ms,
            transparency_ok=transparency_ok,
            size_ok=size_ok,
            quality_score=quality_score
        )

        # ポーズ統計も更新
        if pose_id and update_pose_master_stats:
            update_pose_master_stats(pose_id, success, quality_score)

    except Exception as e:
        print(f"  警告: 生成ログ記録に失敗: {e}")


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


def generate_reactions_with_ai(
    client,
    persona_age: str = "20s",
    persona_target: str = "Friend",
    persona_theme: str = "共感強化",
    persona_intensity: int = 2,
    context: str = "",
) -> list:
    """
    ペルソナ情報を元にGeminiでリアクション24個を自動生成

    Args:
        client: Vertex AI クライアント
        persona_age: Teen / 20s / 30s / 40s / 50s+
        persona_target: Friend / Family / Partner / Work
        persona_theme: 共感強化 / ツッコミ強化 / 褒め強化 / 家族強化
        persona_intensity: 1(控えめ) / 2(バランス) / 3(特化)
        context: 自由テキスト（例: "関西弁×エンジニアネタ"）

    Returns:
        24個の {"id", "emotion", "pose", "text"} リスト
    """
    # 年代別語彙ガイド
    age_vocab = {
        "Teen": "カジュアル/煽り系。線が細めシンプル、イジり系。文字量少なめ。例: りょ、草、それな、は？、おい",
        "20s": "カジュアル。カップル系、白ベースシンプル。文字量普通。例: おけ、わかる〜、ありがとー",
        "30s": "敬語混じり。気遣い、使い勝手重視。文字量普通〜多め。例: ありがとね、了解〜、気をつけて",
        "40s": "丁寧。家族連絡、生活会話の実用。文字量多め。例: おつかれさま、了解です、ありがとうございます",
        "50s+": "丁寧・優しい。季節/天気の気づかい、色鮮やか。文字量多め。例: お体に気をつけて、ありがとうございます",
    }

    # 相手別語彙ガイド
    target_vocab = {
        "Friend": "カジュアル、即レス感。例: りょ、おけ、それな、わかる〜、草",
        "Family": "丁寧だが堅くない。例: ありがとね、おつかれ、了解〜、気をつけて",
        "Partner": "甘め、応援系。例: すき、会いたい、おやすみ、がんばれ",
        "Work": "敬語ベース。例: 承知しました、お疲れ様です、確認します",
    }

    # テーマ別枠配分
    theme_guide = {
        "共感強化": "共感系+3(わかる〜、それな、ほんとそれ)、慰め系+2(どんまい、大丈夫、がんばったね)、リアクション系+3(えっ、マジで、うそ)",
        "ツッコミ強化": "ツッコミ系+4(おい、なんでやねん、ちょ)、煽り系+2(草、ｗｗｗ、知らんけど)、驚き系+2(は？、えぇ…、マジか)",
        "褒め強化": "褒め系+3(いいじゃん、さすが、すごい)、応援系+3(がんばれ、ファイト、応援してる)、感謝系+2(ありがとう、神、助かる)",
        "家族強化": "生活会話+3(ごはんできた、帰るよ、買い物行く)、気遣い系+3(気をつけて、暑いね、寒いね)、連絡系+2(今どこ？、何時？、了解)",
    }

    # 強度別の枠配分
    intensity_guide = {
        1: "テーマ枠4 + コア枠16 + 反応枠4（テーマ控えめ、汎用性重視）",
        2: "テーマ枠8 + コア枠12 + 反応枠4（バランス型）",
        3: "テーマ枠12 + コア枠8 + 反応枠4（テーマ特化、個性重視）",
    }

    age_info = age_vocab.get(persona_age, age_vocab["20s"])
    target_info = target_vocab.get(persona_target, target_vocab["Friend"])
    theme_info = theme_guide.get(persona_theme, theme_guide["共感強化"])
    intensity_info = intensity_guide.get(persona_intensity, intensity_guide[2])

    context_section = f"\n追加コンテキスト: {context}\nこの要素を語彙やテーマに自然に織り込んでください。" if context else ""

    prompt = f"""あなたはLINEスタンプのリアクション設計の専門家です。
以下のペルソナ情報に基づいて、24個のリアクションをJSON配列で生成してください。

## ペルソナ
- 年代: {persona_age} → {age_info}
- 相手: {persona_target} → {target_info}
- テーマ: {persona_theme} → {theme_info}
- 強度: {persona_intensity} → {intensity_info}
{context_section}

## 枠構成（合計24個）
強度設定に従い、コア枠・テーマ枠・反応枠を配分してください。
- コア枠: 挨拶、返事、感謝、謝罪、別れなど基本的な用途
- テーマ枠: 指定テーマに沿った特化リアクション
- 反応枠: 喜び、驚き、応援など汎用リアクション

## 出力形式
JSON配列のみを出力してください。説明は不要です。
各要素は以下の形式:
{{"id": "英語snake_case", "emotion": "表情・感情の説明（日本語）", "pose": "ポーズ・ジェスチャーの説明（日本語）", "text": "スタンプに表示するテキスト（日本語）"}}

## 注意事項
- idは英語のsnake_caseで、リアクションの内容を端的に表すもの
- emotionは画像生成AIに渡す表情指示（具体的に）
- poseは画像生成AIに渡すポーズ指示（具体的に）
- textはスタンプに重ねる日本語テキスト（短く、年代・相手に合った語彙で）
- 24個ちょうど生成すること
- idの重複は不可
"""

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )

            text = response.text.strip()
            # コードブロックの除去
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            reactions = json.loads(text)

            # バリデーション
            if not isinstance(reactions, list) or len(reactions) != 24:
                raise ValueError(f"リアクション数が不正: {len(reactions) if isinstance(reactions, list) else 'not a list'}")

            required_keys = {"id", "emotion", "pose", "text"}
            ids_seen = set()
            for i, r in enumerate(reactions):
                missing = required_keys - set(r.keys())
                if missing:
                    raise ValueError(f"リアクション[{i}]にキーが不足: {missing}")
                if r["id"] in ids_seen:
                    raise ValueError(f"idが重複: {r['id']}")
                ids_seen.add(r["id"])

            print(f"ペルソナベースのリアクションを生成しました（{persona_age}/{persona_target}/{persona_theme}/強度{persona_intensity}）")
            return reactions

        except (json.JSONDecodeError, ValueError) as e:
            if attempt < max_retries:
                print(f"リアクション生成リトライ ({attempt + 1}/{max_retries}): {e}")
                continue
            print(f"Warning: AI リアクション生成に失敗、デフォルトREACTIONSを使用: {e}")
            return None

    return None


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


def enhance_reactions_batch(client, reactions: list, character_description: str = "") -> list:
    """
    複数リアクションを一括でAI詳細化（APIコール削減）

    pose_locked=Falseのリアクションのみ抽出し、1回のAPI呼び出しで全て詳細化する。
    失敗時は個別呼び出しにフォールバック。

    Args:
        client: Vertex AI クライアント
        reactions: リアクションリスト
        character_description: キャラクター特徴

    Returns:
        enhanced_prompt付きリアクションリスト
    """
    # ロックされていないリアクションのインデックスを収集
    unlocked_indices = [i for i, r in enumerate(reactions) if not r.get('pose_locked', False)]

    if not unlocked_indices:
        print("  全リアクションがポーズロック済み、バッチ詳細化スキップ")
        return [{**r, 'enhanced_prompt': None} for r in reactions]

    print(f"  バッチ詳細化: {len(unlocked_indices)}件をまとめてAPI送信...")

    # バッチプロンプト構築
    reaction_entries = []
    for idx in unlocked_indices:
        r = reactions[idx]
        reaction_entries.append(
            f'  {{"index": {idx}, "emotion": "{r.get("emotion", "")}", '
            f'"pose": "{r.get("pose", "")}", "text": "{r.get("text", "")}"}}'
        )
    reactions_json = "[\n" + ",\n".join(reaction_entries) + "\n]"

    prompt = f"""You are an expert at creating detailed prompts for LINE sticker chibi character image generation.

Take each reaction specification below and expand it into detailed descriptions that image generation AI can accurately render.

## Input reactions
{reactions_json}
{f'## Character features: {character_description}' if character_description else ''}

## Output Format
Return a JSON array with one object per input reaction, in the same order.
Each object must have:
- "index": the original index number
- "enhanced_prompt": a detailed English description containing:
  - Facial Expression (Eyes, Eyebrows, Mouth, Cheeks)
  - Pose (Body direction, Arms position, Legs position, Overall movement)

Keep descriptions concise but specific. Focus on visual details that can be drawn.

IMPORTANT: Return ONLY the JSON array, no markdown code blocks, no extra text.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        response_text = response.text.strip()

        # マークダウンコードブロックの除去
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # 最初と最後の```行を除去
            start = 1 if lines[0].startswith("```") else 0
            end = -1 if lines[-1].strip() == "```" else len(lines)
            response_text = "\n".join(lines[start:end]).strip()

        import json
        enhanced_list = json.loads(response_text)

        # インデックスでマッピング
        enhanced_map = {item["index"]: item["enhanced_prompt"] for item in enhanced_list}

        # 結果を構築
        result = []
        matched = 0
        for i, r in enumerate(reactions):
            if r.get('pose_locked', False):
                result.append({**r, 'enhanced_prompt': None})
            elif i in enhanced_map:
                result.append({**r, 'enhanced_prompt': enhanced_map[i]})
                matched += 1
            else:
                # バッチ結果にない場合は個別フォールバック
                try:
                    ep = enhance_reaction_with_ai(client, r, character_description)
                    result.append({**r, 'enhanced_prompt': ep})
                    matched += 1
                except Exception:
                    result.append({**r, 'enhanced_prompt': None})

        print(f"  バッチ詳細化完了: {matched}/{len(unlocked_indices)}件成功")
        return result

    except Exception as e:
        print(f"  バッチ詳細化失敗、個別フォールバックに切り替え: {e}")
        result = []
        for i, r in enumerate(reactions):
            if r.get('pose_locked', False):
                result.append({**r, 'enhanced_prompt': None})
            else:
                try:
                    ep = enhance_reaction_with_ai(client, r, character_description)
                    result.append({**r, 'enhanced_prompt': ep})
                except Exception as e2:
                    print(f"    個別詳細化も失敗 ({r['id']}): {e2}")
                    result.append({**r, 'enhanced_prompt': None})
        return result


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


def _extract_dominant_colors(character_path: str, n_colors: int = 5) -> list:
    """
    キャラクター画像の中央領域から支配色を抽出

    Args:
        character_path: キャラクター画像のパス
        n_colors: 返す色数（デフォルト5）

    Returns:
        [(r, g, b), ...] 上位N色のリスト
    """
    img = Image.open(character_path).convert("RGB")
    w, h = img.size

    # 中央60%領域をクロップ（キャラクター本体を狙う）
    margin_x = int(w * 0.2)
    margin_y = int(h * 0.2)
    cropped = img.crop((margin_x, margin_y, w - margin_x, h - margin_y))

    # 量子化用にリサイズ（高速化）
    cropped = cropped.resize((100, 100), Image.LANCZOS)

    # ピクセルを量子化（各チャネルを32刻みに丸める）
    pixels = list(cropped.getdata())
    quantized = []
    for r, g, b in pixels:
        qr = (r // 32) * 32 + 16
        qg = (g // 32) * 32 + 16
        qb = (b // 32) * 32 + 16
        quantized.append((min(qr, 255), min(qg, 255), min(qb, 255)))

    # ヒストグラムで上位N色を取得
    counter = Counter(quantized)
    return [color for color, _ in counter.most_common(n_colors)]


def _select_safe_background_color(dominant_colors: list, min_distance: int = 150) -> str:
    """
    衣装色と最も距離が遠い安全な背景色を選択

    Args:
        dominant_colors: [(r, g, b), ...] キャラクターの支配色リスト
        min_distance: 最低保証距離

    Returns:
        背景色の文字列（例: "green #00FF00"）
    """
    import math

    # クロマキー定番2色のみ（目・アイテムとの誤爆リスクが最小）
    GREEN = ("green", (0, 255, 0))
    MAGENTA = ("magenta", (255, 0, 255))

    def color_distance(c1, c2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

    # デフォルトはgreen（キャラクターで最も使われにくい）
    if not dominant_colors:
        name, rgb = GREEN
        hex_str = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        print(f"  支配色: なし")
        print(f"  選択背景色: {name} {hex_str} (デフォルト)")
        return f"{name} {hex_str}"

    # greenとの最小距離を算出
    green_min_dist = min(color_distance(GREEN[1], dc) for dc in dominant_colors)

    # greenが十分安全（距離>=min_distance）ならgreen採用
    if green_min_dist >= min_distance:
        name, rgb = GREEN
        hex_str = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
        print(f"  支配色: {dominant_colors[:3]}")
        print(f"  選択背景色: {name} {hex_str} (最小距離: {green_min_dist:.0f})")
        return f"{name} {hex_str}"

    # greenが危険（緑系衣装）→ magentaにフォールバック
    name, rgb = MAGENTA
    magenta_min_dist = min(color_distance(MAGENTA[1], dc) for dc in dominant_colors)
    hex_str = f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
    print(f"  支配色: {dominant_colors[:3]}")
    print(f"  選択背景色: {name} {hex_str} (green距離={green_min_dist:.0f}で危険、magenta距離={magenta_min_dist:.0f})")
    return f"{name} {hex_str}"


def determine_background_color(client, character_path: str) -> str:
    """
    キャラクター画像の衣装色を分析し、衝突しない安全な背景色を決定。
    API呼び出しなし（ローカル画像処理のみ）。

    Args:
        client: 未使用（後方互換のため残す）
        character_path: キャラクター画像のパス

    Returns:
        背景色の文字列（例: "green #00FF00"）
    """
    dominant_colors = _extract_dominant_colors(character_path)
    return _select_safe_background_color(dominant_colors)


def validate_grid(client, grid_data: bytes, expected_cells: int = 12) -> dict:
    """
    グリッド画像を検証（4x3レイアウト、重複なし）
    
    Args:
        client: Vertex AI クライアント
        grid_data: グリッド画像のバイトデータ
        expected_cells: 期待するセル数（デフォルト12）
    
    Returns:
        {"valid": bool, "reason": str, "details": dict}
    """
    prompt = f"""
Analyze this sticker grid image and validate it.

## Check the following:
1. LAYOUT: Is it a 4 columns × 3 rows grid (landscape orientation)?
2. CELL COUNT: Does it have exactly {expected_cells} distinct sticker cells?
3. DUPLICATES: Are there any duplicate/repeated stickers? (same pose and expression)
4. COMPLETENESS: Is each cell filled with a character (no empty cells)?

## Output Format (JSON only):
```json
{{
  "layout_correct": true/false,
  "actual_columns": <number>,
  "actual_rows": <number>,
  "cell_count": <number>,
  "has_duplicates": true/false,
  "duplicate_details": "description if any duplicates found",
  "all_cells_filled": true/false,
  "overall_valid": true/false,
  "reason": "explanation if invalid"
}}
```

Return ONLY the JSON, no other text.
"""
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(data=grid_data, mime_type="image/png"),
                prompt
            ],
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
        
        details = json.loads(result_text)
        
        is_valid = details.get("overall_valid", False)
        reason = details.get("reason", "")
        
        # 追加チェック: 4x3でない場合
        if details.get("actual_columns") != 4 or details.get("actual_rows") != 3:
            is_valid = False
            reason = f"レイアウトが4x3ではない ({details.get('actual_columns')}x{details.get('actual_rows')})"
        
        # 重複がある場合
        if details.get("has_duplicates"):
            is_valid = False
            reason = f"重複あり: {details.get('duplicate_details', '詳細不明')}"
        
        return {
            "valid": is_valid,
            "reason": reason,
            "details": details
        }
        
    except Exception as e:
        return {
            "valid": False,
            "reason": f"検証エラー: {str(e)}",
            "details": {}
        }


def validate_stamp_quality(stamp_img: Image.Image, check_all: bool = True) -> dict:
    """
    個別スタンプの品質を検証

    Args:
        stamp_img: スタンプ画像（PILのImage）
        check_all: 全項目をチェックするか（Falseの場合は基本項目のみ）

    Returns:
        {
            "valid": bool,
            "checks": {
                "tab_visibility": {"passed": bool, "message": str},
                "margin_ok": {"passed": bool, "message": str},
                "file_size_ok": {"passed": bool, "message": str},
                "transparency_ok": {"passed": bool, "message": str},
            },
            "warnings": [str]
        }
    """
    results = {
        "valid": True,
        "checks": {},
        "warnings": []
    }

    # 1. 透過PNG確認
    has_transparency = stamp_img.mode == "RGBA" and stamp_img.getchannel("A").getextrema()[0] < 255
    results["checks"]["transparency_ok"] = {
        "passed": has_transparency or stamp_img.mode == "RGBA",
        "message": "透過PNG確認OK" if (has_transparency or stamp_img.mode == "RGBA") else "アルファチャンネルがありません"
    }

    # 2. タブサイズ視認性チェック（96×74pxにリサイズして評価）
    tab_size = (96, 74)
    tab_img = stamp_img.copy()
    tab_img.thumbnail(tab_size, Image.Resampling.LANCZOS)

    # タブサイズで非透明ピクセルの面積を計算
    if tab_img.mode == "RGBA":
        alpha = tab_img.getchannel("A")
        non_transparent_pixels = sum(1 for p in alpha.getdata() if p > 128)
        total_pixels = tab_img.width * tab_img.height
        fill_ratio = non_transparent_pixels / total_pixels

        # 30%以上埋まっていれば視認性OK
        tab_visible = fill_ratio >= 0.30
        results["checks"]["tab_visibility"] = {
            "passed": tab_visible,
            "message": f"タブサイズ視認性: {fill_ratio*100:.1f}%（30%以上推奨）",
            "fill_ratio": fill_ratio
        }
        if not tab_visible:
            results["warnings"].append(f"タブサイズ(96x74px)での視認性が低い可能性があります（{fill_ratio*100:.1f}%）")
    else:
        results["checks"]["tab_visibility"] = {
            "passed": True,
            "message": "タブサイズ視認性: 透過なしのため判定スキップ"
        }

    # 3. 余白チェック（外枠から10px以上の余白があるか）
    if stamp_img.mode == "RGBA":
        alpha = stamp_img.getchannel("A")
        width, height = stamp_img.size
        min_margin = 10

        # 各辺の余白をチェック
        margins = {"top": 0, "bottom": 0, "left": 0, "right": 0}

        # 上辺
        for y in range(height):
            row = [alpha.getpixel((x, y)) for x in range(width)]
            if any(p > 128 for p in row):
                margins["top"] = y
                break

        # 下辺
        for y in range(height - 1, -1, -1):
            row = [alpha.getpixel((x, y)) for x in range(width)]
            if any(p > 128 for p in row):
                margins["bottom"] = height - 1 - y
                break

        # 左辺
        for x in range(width):
            col = [alpha.getpixel((x, y)) for y in range(height)]
            if any(p > 128 for p in col):
                margins["left"] = x
                break

        # 右辺
        for x in range(width - 1, -1, -1):
            col = [alpha.getpixel((x, y)) for y in range(height)]
            if any(p > 128 for p in col):
                margins["right"] = width - 1 - x
                break

        all_margins_ok = all(m >= min_margin for m in margins.values())
        results["checks"]["margin_ok"] = {
            "passed": all_margins_ok,
            "message": f"余白: 上{margins['top']}px 下{margins['bottom']}px 左{margins['left']}px 右{margins['right']}px（{min_margin}px以上推奨）",
            "margins": margins
        }
        if not all_margins_ok:
            results["warnings"].append(f"余白が不足している辺があります（{min_margin}px以上推奨）")
    else:
        results["checks"]["margin_ok"] = {
            "passed": True,
            "message": "余白チェック: 透過なしのため判定スキップ"
        }

    # 4. ファイルサイズチェック（1MB以下）
    if check_all:
        buffer = io.BytesIO()
        stamp_img.save(buffer, format="PNG", optimize=True)
        file_size_kb = len(buffer.getvalue()) / 1024

        size_ok = file_size_kb <= 1024  # 1MB = 1024KB
        results["checks"]["file_size_ok"] = {
            "passed": size_ok,
            "message": f"ファイルサイズ: {file_size_kb:.1f}KB（1024KB以下）",
            "size_kb": file_size_kb
        }
        if not size_ok:
            results["warnings"].append(f"ファイルサイズが大きすぎます（{file_size_kb:.1f}KB > 1024KB）")

    # 総合判定
    critical_checks = ["transparency_ok", "margin_ok"]
    results["valid"] = all(
        results["checks"].get(check, {}).get("passed", True)
        for check in critical_checks
    )

    return results


def validate_stamp_batch(stamps: list, verbose: bool = True) -> dict:
    """
    複数スタンプを一括検証

    Args:
        stamps: スタンプ画像のリスト（PILのImage）
        verbose: 詳細ログを出力するか

    Returns:
        {
            "all_valid": bool,
            "passed_count": int,
            "failed_count": int,
            "results": [validate_stamp_quality結果]
        }
    """
    all_results = []
    passed = 0
    failed = 0

    for i, stamp in enumerate(stamps):
        result = validate_stamp_quality(stamp)
        all_results.append(result)

        if result["valid"]:
            passed += 1
            if verbose:
                print(f"  スタンプ {i+1}: [OK]")
        else:
            failed += 1
            if verbose:
                print(f"  スタンプ {i+1}: [NG] {', '.join(result['warnings'])}")

    return {
        "all_valid": failed == 0,
        "passed_count": passed,
        "failed_count": failed,
        "results": all_results
    }


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
    style_info = get_style(chibi_style)
    style_prompt = style_info["prompt"]

    image_data, mime_type = load_image_as_base64(image_path)

    prompt = f"""
Look at this reference photo and create a SINGLE character illustration based on it.

## STYLE (MUST FOLLOW EXACTLY)
{style_prompt}

## REQUIREMENTS
- Transform the person in the photo into the style specified above
- Keep the same hair color, eye color, and general appearance
- CRITICAL: If the person is wearing a MASK, the character MUST wear a mask too. The mask must fully cover the mouth and nose area. NO mouth or lips should be visible under any circumstances.
- Simple standing pose, facing forward
- Show emotion through EYES only (if wearing mask)
- Plain white background
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


def extract_character_yaml(client, character_path: str, output_path: str = None) -> dict:
    """キャラクター画像から特徴を抽出してYAML形式で保存

    Args:
        client: Vertex AI クライアント
        character_path: キャラクター画像のパス
        output_path: YAML保存先（Noneの場合は保存しない）

    Returns:
        キャラクター特徴の辞書
    """
    import yaml
    from datetime import datetime

    image_data, mime_type = load_image_as_base64(character_path)

    prompt = """Analyze this character illustration and extract its visual features in YAML format.

Output ONLY valid YAML (no markdown code blocks, no explanations):

version: "1.0"
extracted_at: "<current timestamp>"

face:
  shape: "<oval/round/square/heart>"
  skin_tone: "<fair/light/medium/tan/dark>"

hair:
  color: "<specific color, e.g. black, dark brown, blonde>"
  style: "<length and style, e.g. short spiky, medium wavy>"
  bangs: "<straight/side swept/none/parted>"

eyes:
  color: "<specific color>"
  shape: "<large round/small round/almond/etc>"
  style: "<anime sparkle/simple/realistic>"

outfit:
  type: "<type of clothing, e.g. sports uniform, casual, school uniform>"
  primary_color: "<main color>"
  secondary_color: "<accent color or none>"
  details: "<specific details like jersey number, patterns, accessories>"

body:
  build: "<slim/average/stocky>"
  age_impression: "<child/teen/young adult/adult>"

accessories: []
distinctive_features: []

Be specific and accurate. This will be used to maintain character consistency across multiple images."""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=base64.b64decode(image_data), mime_type=mime_type),
            prompt
        ],
    )

    yaml_text = response.text.strip()
    # Remove markdown code blocks if present
    if yaml_text.startswith("```"):
        yaml_text = yaml_text.split("```")[1]
        if yaml_text.startswith("yaml"):
            yaml_text = yaml_text[4:]
        yaml_text = yaml_text.strip()

    try:
        character_data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        print(f"  警告: YAML解析エラー、デフォルト値を使用: {e}")
        character_data = {
            "version": "1.0",
            "extracted_at": datetime.now().isoformat(),
            "face": {"shape": "oval", "skin_tone": "fair"},
            "hair": {"color": "black", "style": "short", "bangs": "none"},
            "eyes": {"color": "dark brown", "shape": "large round", "style": "anime sparkle"},
            "outfit": {"type": "casual", "primary_color": "unknown", "secondary_color": "none", "details": ""},
            "body": {"build": "average", "age_impression": "child"},
            "accessories": [],
            "distinctive_features": []
        }

    # タイムスタンプを更新
    character_data["extracted_at"] = datetime.now().isoformat()
    character_data["source_image"] = str(character_path)

    # YAML保存
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(character_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"キャラクターYAML保存: {output_path}")

    return character_data


def build_character_prompt_from_yaml(character_yaml: dict) -> str:
    """キャラクターYAMLからプロンプト用の説明文を生成"""
    if not character_yaml:
        return ""

    parts = []

    # 髪
    hair = character_yaml.get("hair", {})
    if hair:
        hair_desc = f"{hair.get('color', 'black')} {hair.get('style', 'short')} hair"
        if hair.get('bangs') and hair.get('bangs') != 'none':
            hair_desc += f" with {hair.get('bangs')} bangs"
        parts.append(f"Hair: {hair_desc}")

    # 目
    eyes = character_yaml.get("eyes", {})
    if eyes:
        parts.append(f"Eyes: {eyes.get('color', 'brown')} {eyes.get('shape', 'round')} eyes")

    # 肌
    face = character_yaml.get("face", {})
    if face.get("skin_tone"):
        parts.append(f"Skin: {face.get('skin_tone')}")

    # 服装
    outfit = character_yaml.get("outfit", {})
    if outfit:
        outfit_desc = outfit.get('type', 'casual')
        if outfit.get('primary_color'):
            outfit_desc += f" in {outfit.get('primary_color')}"
        if outfit.get('secondary_color') and outfit.get('secondary_color') != 'none':
            outfit_desc += f" and {outfit.get('secondary_color')}"
        if outfit.get('details'):
            outfit_desc += f", {outfit.get('details')}"
        parts.append(f"Outfit: {outfit_desc}")

    # 体型
    body = character_yaml.get("body", {})
    if body:
        parts.append(f"Build: {body.get('build', 'average')} {body.get('age_impression', 'child')}")

    # アクセサリー
    accessories = character_yaml.get("accessories", [])
    if accessories:
        acc_strs = [a.get("name", str(a)) if isinstance(a, dict) else str(a) for a in accessories]
        parts.append(f"Accessories: {', '.join(acc_strs)}")

    # 特徴
    features = character_yaml.get("distinctive_features", [])
    if features:
        feat_strs = [f.get("name", str(f)) if isinstance(f, dict) else str(f) for f in features]
        parts.append(f"Distinctive features: {', '.join(feat_strs)}")

    return "\n".join(parts)


def generate_grid_from_character(client, character_path: str, reactions: list,
                                  chibi_style: str = "sd_25", background_color: str = None,
                                  character_yaml: dict = None,
                                  modifiers: dict = None, force_full_body: bool = False,
                                  model: str = "gemini-3-pro-image-preview") -> bytes:
    """Step 2: サンプルキャラクターからリアクショングリッドを生成（2段階生成の第2段階）

    Args:
        client: Vertex AI クライアント
        character_path: Step 1で生成したキャラクター画像のパス
        reactions: リアクションリスト（12個）- enhanced_promptキーがあれば詳細化版を使用
        chibi_style: CHIBI_STYLES のキー
        background_color: 背景色（例: "soft pastel blue #E8F4FC"）
        modifiers: モディファイア設定 {"text_mode": "deka", "outline": "bold"}

    Returns:
        グリッド画像のバイトデータ
    """
    # モディファイアのデフォルト設定
    if modifiers is None:
        modifiers = DEFAULT_MODIFIERS.copy()

    style_info = get_style(chibi_style)
    style_prompt = style_info["prompt"]
    modifier_prompt = build_modifier_prompt(modifiers)

    image_data, mime_type = load_image_as_base64(character_path)

    # 背景色を決定（指定がなければデフォルト）
    bg_color = background_color or "light blue #E8F4FC"

    # キャラクター仕様を生成（YAMLがあれば使用）
    character_spec = ""
    if character_yaml:
        character_spec = build_character_prompt_from_yaml(character_yaml)
        if character_spec:
            character_spec = f"\n\n### Character Features (MUST MATCH):\n{character_spec}"

    # 12個のリアクションの説明を作成（詳細化版・アイテム情報があれば使用）
    reactions_text_parts = []
    for i, r in enumerate(reactions[:12]):
        # アイテム情報を追加
        item_text = ""
        if r.get('item'):
            item = r['item']
            item_text = f"\n  Item: {item['name_en']} ({item['description_en']})\n  Hold style: {item.get('hold_style', 'holding in hands')}"

        # 衣装情報を追加
        outfit_text = ""
        if r.get('outfit'):
            outfit_text = f"\n  Outfit: {r['outfit']} (MUST wear this specific outfit in this cell)"

        if 'enhanced_prompt' in r and r['enhanced_prompt']:
            # 詳細化されたプロンプトがある場合
            reactions_text_parts.append(
                f"Cell {i+1}: \"{r['text']}\"\n{r['enhanced_prompt']}{item_text}{outfit_text}"
            )
        elif r.get('pose_locked'):
            # pose_locked: 詳細なポーズ指示をそのまま使用（圧縮しない）
            reactions_text_parts.append(
                f"Cell {i+1}: \"{r['text']}\"\n  Emotion: {r['emotion']}\n  EXACT POSE (MUST FOLLOW PRECISELY): {r['pose']}{item_text}{outfit_text}"
            )
        else:
            # 従来形式（フォールバック）
            reactions_text_parts.append(
                f"Cell {i+1}: \"{r['text']}\" - {r['emotion']}, {r['pose']}{item_text}{outfit_text}"
            )
    reactions_text = "\n\n".join(reactions_text_parts)

    full_body_rule = ""
    margin_rule = "Keep margins MINIMAL (only 5% padding) - character should be LARGE within the cell"
    if force_full_body:
        full_body_rule = """
## FULL BODY VISIBILITY (CRITICAL)
- The ENTIRE body (head to feet) MUST be visible in each cell
- Do NOT crop any part of the body, face, hands, or feet
- Leave at least 10-15% padding around the character
"""
        margin_rule = "Leave at least 10-15% padding around the character to avoid cropping"

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
- {margin_rule}
- If character is off-center, the entire image is REJECTED
- Text should be placed near character but within cell bounds
{full_body_rule}

## CHARACTER SPECIFICATION (MUST MATCH EXACTLY IN ALL CELLS)
Use the character from the reference image exactly.
Style: {style_prompt}
{character_spec}

## CRITICAL: CHARACTER CONSISTENCY
- This EXACT character with the features described above must appear in ALL 12 cells
- Do NOT change hair color, eye color, outfit, or any features between cells
- The only differences between cells should be pose and expression

## CRITICAL: FACE AND EXPRESSION RULE
- IMPORTANT: Do NOT add masks, face coverings, or any accessories not present in the reference image
- The character's face should be FULLY VISIBLE with clear facial expressions (eyes, eyebrows, mouth)
- Express emotions through facial expressions, especially eyes, eyebrows, and MOUTH
- Keep the character's face consistent with the reference image AND the specification above

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
- Express emotions through eyes, eyebrows, and mouth

## TEXT AND OUTLINE MODIFIERS (CRITICAL)
{modifier_prompt}

## ITEMS (if specified in cell contents)
- When an item is specified for a cell, the character MUST be holding/interacting with that item
- Draw the item in the chibi style matching the character
- Item should be clearly visible and recognizable
- Adjust the character's pose to naturally hold the item as described in "Hold style"
"""

    response = client.models.generate_content(
        model=model,
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
    style_info = get_style(chibi_style)
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
        outfit_part = f' Outfit: {r["outfit"]}.' if r.get("outfit") else ""
        reaction_descriptions.append(f"[Row{row}-Col{col}] {r['emotion']}, {r['pose']}.{outfit_part}{text_part}")

    reactions_text = "\n".join(reaction_descriptions)

    # YAML形式のリアクション説明
    yaml_cells = []
    for i, r in enumerate(reactions[:12]):
        row = (i // 4) + 1
        col = (i % 4) + 1
        text_val = f'"{r["text"]}"' if r["text"] else "null"
        outfit_line = f'\n    outfit: "{r["outfit"]}"' if r.get("outfit") else ""
        yaml_cells.append(f"""  cell_{i+1}:
    position: [row_{row}, col_{col}]
    emotion: "{r['emotion']}"
    pose: "{r['pose']}"
    text: {text_val}{outfit_line}""")
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


def _grid_bounds(length: int, count: int) -> list:
    """分割境界を丸めで決定（端まで必ず到達）"""
    if count <= 0:
        return [0, length]
    bounds = [0]
    for i in range(1, count):
        bounds.append(int(round(i * length / count)))
    bounds.append(length)
    # 単調増加に補正
    for i in range(1, len(bounds)):
        if bounds[i] < bounds[i - 1]:
            bounds[i] = bounds[i - 1]
    return bounds


def _quantize_rgb_simple(rgb: tuple, step: int) -> tuple:
    return tuple(int(round(v / step) * step) for v in rgb)


def _dominant_color_from_band(img: Image.Image, skip: int = 1,
                              band_ratio: float = 0.08, max_band: int = 24,
                              quant_step: int = 8, alpha_threshold: int = 8) -> tuple:
    """外周帯（skip外側は除外）から背景色を推定"""
    w, h = img.size
    band = max(2, int(min(w, h) * band_ratio))
    band = min(band, max_band)

    pixels = img.load()
    counts = Counter()

    for y in range(h):
        for x in range(w):
            if x < skip or x >= w - skip or y < skip or y >= h - skip:
                continue
            if x < skip + band or x >= w - skip - band or y < skip + band or y >= h - skip - band:
                r, g, b, a = pixels[x, y]
                if a <= alpha_threshold:
                    continue
                counts[_quantize_rgb_simple((r, g, b), quant_step)] += 1

    if counts:
        return max(counts, key=counts.get)

    # フォールバック: 中央の色
    r, g, b, _ = pixels[w // 2, h // 2]
    return (r, g, b)


def _edge_uniform_stats(edge_pixels: list, tol: int = 6,
                        quant_step: int = 8, alpha_threshold: int = 8) -> tuple:
    """エッジの支配色と均一率を返す"""
    if not edge_pixels:
        return None, 0.0
    filtered = [p for p in edge_pixels if p[3] > alpha_threshold]
    if len(filtered) < max(1, int(len(edge_pixels) * 0.5)):
        return None, 0.0

    counts = Counter(_quantize_rgb_simple(p[:3], quant_step) for p in filtered)
    dom = max(counts, key=counts.get)

    good = 0
    for p in filtered:
        r, g, b = p[:3]
        if abs(r - dom[0]) + abs(g - dom[1]) + abs(b - dom[2]) <= tol:
            good += 1
    return dom, good / len(filtered)


def clean_edge_lines(img: Image.Image, max_layers: int = 2,
                     min_ratio: float = 0.98, edge_tol: int = 6,
                     bg_tol: int = 12, white_min: int = 245,
                     band_ratio: float = 0.08, max_band: int = 24,
                     quant_step: int = 8, alpha_threshold: int = 8) -> Image.Image:
    """外周の均一な線（白枠など）を背景色で埋める"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    pixels = img.load()

    for layer in range(max_layers):
        bg = _dominant_color_from_band(
            img, skip=layer + 1,
            band_ratio=band_ratio, max_band=max_band,
            quant_step=quant_step, alpha_threshold=alpha_threshold
        )

        edges = {
            "top": [pixels[x, layer] for x in range(w)],
            "bottom": [pixels[x, h - 1 - layer] for x in range(w)],
            "left": [pixels[layer, y] for y in range(h)],
            "right": [pixels[w - 1 - layer, y] for y in range(h)],
        }

        for side, edge in edges.items():
            dom, ratio = _edge_uniform_stats(
                edge, tol=edge_tol, quant_step=quant_step, alpha_threshold=alpha_threshold
            )
            if dom is None or ratio < min_ratio:
                continue

            # 白系 or 背景色から大きく離れていれば埋める
            if min(dom) >= white_min or (
                abs(dom[0] - bg[0]) + abs(dom[1] - bg[1]) + abs(dom[2] - bg[2]) > bg_tol
            ):
                if side == "top":
                    y = layer
                    for x in range(w):
                        r, g, b, a = pixels[x, y]
                        pixels[x, y] = (bg[0], bg[1], bg[2], a)
                elif side == "bottom":
                    y = h - 1 - layer
                    for x in range(w):
                        r, g, b, a = pixels[x, y]
                        pixels[x, y] = (bg[0], bg[1], bg[2], a)
                elif side == "left":
                    x = layer
                    for y in range(h):
                        r, g, b, a = pixels[x, y]
                        pixels[x, y] = (bg[0], bg[1], bg[2], a)
                else:
                    x = w - 1 - layer
                    for y in range(h):
                        r, g, b, a = pixels[x, y]
                        pixels[x, y] = (bg[0], bg[1], bg[2], a)

    return img


def _split_grid_with_layout(grid_img: Image.Image, rows: int, cols: int,
                            clean_edges: bool, trim_border: int = 2) -> list:
    """指定レイアウトでグリッドを分割（内部用）

    Args:
        trim_border: 各セルの境界から除去するピクセル数（デフォルト2px）
    """
    width, height = grid_img.size
    x_bounds = _grid_bounds(width, cols)
    y_bounds = _grid_bounds(height, rows)

    stamps = []
    for row in range(rows):
        for col in range(cols):
            left = x_bounds[col] + trim_border
            right = x_bounds[col + 1] - trim_border
            top = y_bounds[row] + trim_border
            bottom = y_bounds[row + 1] - trim_border

            cell = grid_img.crop((left, top, right, bottom))
            if clean_edges:
                cell = clean_edge_lines(cell)
            stamps.append(cell)

    return stamps


def split_grid_image(grid_img: Image.Image, rows: int = 3, cols: int = 4,
                     clean_edges: bool = True) -> list:
    """グリッド画像を個別のスタンプに分割

    両方のレイアウト（指定通り / 行列入れ替え）で分割を試行し、
    セルのアスペクト比がスタンプ仕様（370×320 ≒ 1.156:1）に
    近い方を採用する。
    """
    # スタンプの目標アスペクト比（width/height）
    TARGET_RATIO = 370.0 / 320.0  # ≒ 1.156

    # レイアウト1: 指定通り (cols×rows)
    stamps_normal = _split_grid_with_layout(grid_img, rows, cols, clean_edges)
    cell_normal = stamps_normal[0]
    ratio_normal = cell_normal.width / cell_normal.height

    # レイアウト2: 行列入れ替え (rows×cols)
    if rows != cols:
        stamps_swapped = _split_grid_with_layout(grid_img, cols, rows, clean_edges)
        cell_swapped = stamps_swapped[0]
        ratio_swapped = cell_swapped.width / cell_swapped.height

        diff_normal = abs(ratio_normal - TARGET_RATIO)
        diff_swapped = abs(ratio_swapped - TARGET_RATIO)

        if diff_swapped < diff_normal:
            print(f"  [レイアウト自動検出] セル比率 {ratio_normal:.2f}(指定) vs {ratio_swapped:.2f}(入替) → 入替採用 ({rows}cols×{cols}rows)")
            return stamps_swapped
        else:
            print(f"  [レイアウト自動検出] セル比率 {ratio_normal:.2f}(指定) vs {ratio_swapped:.2f}(入替) → 指定採用 ({cols}cols×{rows}rows)")

    return stamps_normal


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

    # 最初の12個のリアクションを使用（pose_refを展開）
    reactions = expand_all_pose_refs(REACTIONS[:12])

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


def generate_24_stickers(client, image_path: str, output_dir: str, remove_bg: bool = False,
                         chibi_style: str = "sd_25", detect_items: bool = True,
                         modifiers: dict = None, reactions: list = None):
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
        modifiers: モディファイア設定 {"text_mode": "deka", "outline": "bold"}
        reactions: リアクションリスト（セッションから渡す）。Noneの場合はデフォルトのREACTIONSを使用
    """
    # REACTIONSを決定（引数 > グローバル）、pose_refを展開
    if reactions is None:
        reactions = expand_all_pose_refs(REACTIONS[:24])
    else:
        reactions = expand_all_pose_refs(reactions[:24])  # 最大24件
    # モディファイアのデフォルト設定
    if modifiers is None:
        modifiers = DEFAULT_MODIFIERS.copy()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    style_info = get_style(chibi_style)
    style_name = style_info.get('name', chibi_style)
    style_prompt = style_info["prompt"]

    # モディファイアプロンプトを構築
    modifier_prompt = build_modifier_prompt(modifiers)

    print(f"スタイル: {style_name}")
    print(f"テキストモード: {modifiers.get('text_mode', 'deka')}")
    print(f"アウトライン: {modifiers.get('outline', 'bold')}")
    print("=" * 50)

    # プロンプト記録用辞書
    prompts_log = {
        "generated_at": datetime.now().isoformat(),
        "style": chibi_style,
        "style_name": style_name,
        "style_prompt": style_prompt,
        "modifiers": modifiers,
        "modifier_prompt": modifier_prompt,
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

    # Step 1.5: キャラクターYAMLを抽出（一貫性のため）
    print("\n[Step 1.5/6] キャラクター特徴を抽出中...")
    character_yaml_path = f"{output_dir}/_character.yaml"
    try:
        character_yaml = extract_character_yaml(client, character_path, character_yaml_path)
        prompts_log["character_yaml"] = character_yaml
        print(f"  髪: {character_yaml.get('hair', {}).get('color', '?')} {character_yaml.get('hair', {}).get('style', '?')}")
        print(f"  目: {character_yaml.get('eyes', {}).get('color', '?')}")
        print(f"  服装: {character_yaml.get('outfit', {}).get('type', '?')}")
    except Exception as e:
        print(f"  警告: キャラクターYAML抽出に失敗 ({e})")
        character_yaml = None

    # Step 2: 背景色を自動決定（衣装色から安全な色をローカル選択）
    print("\n[Step 2/6] 衣装色を分析し安全な背景色を選択中...")
    try:
        background_color = determine_background_color(client, character_path)
        print(f"  決定した背景色: {background_color}")
    except Exception as e:
        print(f"  警告: 背景色決定に失敗、デフォルトを使用 ({e})")
        background_color = "green #00FF00"

    prompts_log["background_color"] = background_color

    # Step 3: リアクションを詳細化（バッチ処理）
    print("\n[Step 3/6] リアクションをバッチ詳細化中...")
    enhanced_reactions_all = enhance_reactions_batch(client, reactions)

    # プロンプトを記録
    for i, enhanced_reaction in enumerate(enhanced_reactions_all):
        prompts_log["reactions"].append({
            "index": i + 1,
            "id": enhanced_reaction["id"],
            "text": enhanced_reaction["text"],
            "original_emotion": enhanced_reaction["emotion"],
            "original_pose": enhanced_reaction["pose"],
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

            # 衣装情報を追加
            outfit_text = ""
            if r.get('outfit'):
                outfit_text = f"\n  Outfit: {r['outfit']} (MUST wear this specific outfit in this cell)"

            if 'enhanced_prompt' in r and r['enhanced_prompt']:
                reactions_text_parts.append(f"Cell {idx+1}: \"{r['text']}\"\n{r['enhanced_prompt']}{item_text}{outfit_text}")
            elif r.get('pose_locked'):
                # pose_locked: 詳細なポーズ指示をそのまま使用（圧縮しない）
                reactions_text_parts.append(f"Cell {idx+1}: \"{r['text']}\"\n  Emotion: {r['emotion']}\n  EXACT POSE (MUST FOLLOW PRECISELY): {r['pose']}{item_text}{outfit_text}")
            else:
                reactions_text_parts.append(f"Cell {idx+1}: \"{r['text']}\" - {r['emotion']}, {r['pose']}{item_text}{outfit_text}")
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

## CRITICAL: FACE AND EXPRESSION RULE
- IMPORTANT: Do NOT add masks, face coverings, or any accessories not present in the reference image
- The character's face should be FULLY VISIBLE with clear facial expressions (eyes, eyebrows, mouth)
- Express emotions through facial expressions, especially eyes, eyebrows, and MOUTH
- Keep the character's face consistent with the reference image

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
- Express emotions through eyes, eyebrows, and mouth
"""
        prompts_log["grid_prompts"].append({
            "grid_num": grid_num,
            "prompt": grid_prompt.strip()
        })

        # キャラクター画像を参照してグリッド生成（詳細化プロンプトと背景色を使用）
        # 検証付きリトライループ
        max_retries = 3
        grid_data = None

        for attempt in range(max_retries):
            grid_data = generate_grid_from_character(
                client, character_path, reactions_list,
                chibi_style=chibi_style, background_color=background_color,
                character_yaml=character_yaml,
                modifiers=modifiers
            )
            
            # グリッド検証
            print(f"    検証中 (試行 {attempt + 1}/{max_retries})...")
            validation = validate_grid(client, grid_data, expected_cells=12)
            
            if validation["valid"]:
                print(f"    [OK] 検証OK")
                break
            else:
                print(f"    [NG] 検証NG: {validation['reason']}")
                if attempt < max_retries - 1:
                    print(f"    → 再生成します...")
                else:
                    print(f"    → 最大リトライ回数に達しました。最後の結果を使用します。")

        # グリッド画像を保存
        grid_img = Image.open(io.BytesIO(grid_data))
        grid_path = f"{output_dir}/grid_{grid_num}.png"
        grid_img.save(grid_path, "PNG")
        print(f"  グリッド画像保存: {grid_path}")

        # 12分割
        stamps = split_grid_image(grid_img, rows=3, cols=4)

        # 各スタンプを背景透過（分割直後に実行、文字を守るため）
        print(f"  背景透過処理中...")
        transparency_config = TRANSPARENCY_CONFIG_DEFAULT.copy()
        if background_color:
            bg_hex = _extract_hex_color(background_color)
            if bg_hex:
                transparency_config["fixed_colors"] = [bg_hex]
        for j, stamp in enumerate(stamps):
            transparentize_image_background(stamp, transparency_config)

        # フリンジ除去 + 白アウトライン追加
        bg_rgb_for_fringe = (0, 255, 0)  # デフォルト：緑背景
        if background_color:
            bg_rgb = _extract_hex_color(background_color)
            if bg_rgb:
                bg_rgb_for_fringe = bg_rgb
        print(f"  フリンジ除去 + 白アウトライン追加中...")
        for stamp in stamps:
            _remove_fringe_and_add_outline(stamp, bg_rgb_for_fringe)

        # 各スタンプをセンタリング
        print(f"  各スタンプをセンタリング中...")
        stamps = [center_character_in_cell(s) for s in stamps]

        # 各スタンプを保存
        original_reactions = reactions[:12] if grid_num == 1 else reactions[12:24]
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
    api_calls = 28 + (2 if detected_items else 0) + 2  # +2 for grid validation
    print(f"API呼び出し: {api_calls}回（キャラクター1回 + 背景色1回 + 詳細化24回 + グリッド2回 + 検証2回" + (" + アイテム検出1回 + マッチング1回）" if detected_items else "）"))
    print(f"  ※リトライが発生した場合は追加呼び出しあり")


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


def generate_submission_package(client, image_path: str, output_dir: str,
                                chibi_style: str = "sd_25", detect_items: bool = True,
                                modifiers: dict = None, reactions: list = None):
    """LINE審査申請用パッケージを生成

    Args:
        detect_items: Trueの場合、写真からアイテムを検出してスタンプに反映
        modifiers: モディファイア設定 {"text_mode": "deka", "outline": "bold"}
        reactions: リアクションリスト（セッションから渡す）。Noneの場合はデフォルトのREACTIONSを使用
    """
    # REACTIONSを決定（引数 > グローバル）
    if reactions is None:
        reactions_to_use = REACTIONS[:24]
    else:
        reactions_to_use = reactions[:24]

    # モディファイアのデフォルト設定
    if modifiers is None:
        modifiers = DEFAULT_MODIFIERS.copy()

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("LINE スタンプ申請パッケージ生成")
    print("=" * 50)

    # Step 1: 24枚のスタンプを生成（--eco24と同様）
    print("\n[Step 1/5] 24枚のスタンプを生成中...")
    generate_24_stickers(client, image_path, output_dir, remove_bg=False,
                         chibi_style=chibi_style, detect_items=detect_items,
                         modifiers=modifiers, reactions=reactions_to_use)

    # Step 2: スタンプファイル名を申請用に変更（01_ok.png → 01.png）
    print("\n[Step 2/5] ファイル名を申請形式に変更中...")
    output_path = Path(output_dir)
    for i, reaction in enumerate(reactions_to_use, 1):
        src = output_path / f"{i:02d}_{reaction['id']}.png"
        dst = output_path / f"{i:02d}.png"
        if src.exists():
            # 既存ファイルがある場合は削除してからリネーム
            if dst.exists():
                dst.unlink()
            src.rename(dst)
            print(f"  {src.name} → {dst.name}")

    # Step 3: メイン画像を生成（1枚目をリサイズ）
    print("\n[Step 3/5] メイン画像・タブ画像を生成中...")
    first_stamp = output_path / "01.png"
    main_path = output_path / "main.png"
    tab_path = output_path / "tab.png"

    if first_stamp.exists():
        generate_main_image(str(first_stamp), str(main_path))
        generate_tab_image(str(main_path), str(tab_path))
    else:
        print("警告: 1枚目のスタンプが見つかりません")

    # Step 4: 背景透過の再処理
    print("\n[Step 4/5] 背景透過を最適化中...")
    postprocess_transparency_dir(output_dir, mode="package", update_zip=False)

    # Step 5: ZIPパッケージを作成
    print("\n[Step 5/5] 申請用ZIPパッケージを作成中...")
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


# ============================================================
# 非AI背景透過（境界帯の支配色 + フラッドフィル）
# ============================================================

TRANSPARENCY_CONFIG_DEFAULT = {
    "band_ratio": 0.08,         # 画像端からの帯幅（短辺比）
    "max_band": 24,             # 帯幅の上限px
    "quantize_step": 6,         # 色量子化の刻み
    "tolerance": 40,            # 背景判定の色距離（RGB平方距離のsqrt）。AI生成の背景色はずれるため余裕を持たせる
    "alpha_threshold": 8,       # これ以下は透明とみなす
    "candidate_ratio": 0.5,     # 支配色に対する最低比率
    "max_candidates": 3,        # 背景候補色の上限数
    "fixed_colors": None        # 明示的な背景色（[(r,g,b), ...]）
}


def _quantize_rgb(rgb: tuple, step: int) -> tuple:
    return tuple(int(round(v / step) * step) for v in rgb)


def _collect_band_candidates(img: Image.Image, config: dict) -> tuple[int, list]:
    """画像端の帯から背景候補色を抽出"""
    w, h = img.size
    band = max(2, int(min(w, h) * config["band_ratio"]))
    band = min(band, config["max_band"])

    pixels = img.load()
    counts = Counter()
    alpha_threshold = config["alpha_threshold"]
    qstep = config["quantize_step"]

    for y in range(h):
        for x in range(w):
            if x < band or x >= w - band or y < band or y >= h - band:
                r, g, b, a = pixels[x, y]
                if a <= alpha_threshold:
                    continue
                counts[_quantize_rgb((r, g, b), qstep)] += 1

    if not counts:
        return band, []

    most_count = counts.most_common(1)[0][1]
    min_count = max(1, int(most_count * config["candidate_ratio"]))

    candidates = [
        color for color, count in counts.most_common(config["max_candidates"])
        if count >= min_count
    ]
    return band, candidates


def _is_close_to_candidates(rgb: tuple, candidates: list, tol2: int) -> bool:
    r, g, b = rgb
    for c in candidates:
        dr = r - c[0]
        dg = g - c[1]
        db = b - c[2]
        if (dr * dr + dg * dg + db * db) <= tol2:
            return True
    return False


def transparentize_image_background(img: Image.Image, config: dict = None) -> dict:
    """背景を透明化（インプレース）。統計情報を返す。"""
    if config is None:
        config = TRANSPARENCY_CONFIG_DEFAULT

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    pixels = img.load()

    fixed_colors = config.get("fixed_colors")
    if fixed_colors:
        band = 0
        candidates = fixed_colors
    else:
        band, candidates = _collect_band_candidates(img, config)
    if not candidates:
        return {
            "band": band,
            "candidates": [],
            "background_pixels": 0,
            "total_pixels": w * h,
        }

    tol2 = config["tolerance"] * config["tolerance"]
    alpha_threshold = config["alpha_threshold"]

    visited = bytearray(w * h)
    bg_coords = []
    dq = deque()

    # 帯領域全体をシードにする（外周が背景色でないケースに対応）
    if band > 0:
        for x in range(w):
            for y in range(band):
                dq.append((x, y))
                dq.append((x, h - 1 - y))
        for y in range(h):
            for x in range(band):
                dq.append((x, y))
                dq.append((w - 1 - x, y))
    else:
        # fixed_colors 使用時は外周1pxをシード
        for x in range(w):
            dq.append((x, 0))
            dq.append((x, h - 1))
        for y in range(h):
            dq.append((0, y))
            dq.append((w - 1, y))

    while dq:
        x, y = dq.popleft()
        idx = y * w + x
        if visited[idx]:
            continue
        visited[idx] = 1

        r, g, b, a = pixels[x, y]

        if a <= alpha_threshold:
            bg_coords.append((x, y))
        elif _is_close_to_candidates((r, g, b), candidates, tol2):
            bg_coords.append((x, y))
        else:
            continue

        if x > 0:
            dq.append((x - 1, y))
        if x < w - 1:
            dq.append((x + 1, y))
        if y > 0:
            dq.append((x, y - 1))
        if y < h - 1:
            dq.append((x, y + 1))

    for x, y in bg_coords:
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)

    return {
        "band": band,
        "candidates": candidates,
        "background_pixels": len(bg_coords),
        "total_pixels": w * h,
    }


def _remove_fringe_and_add_outline(img: Image.Image, bg_rgb: tuple, outline_px: int = 2):
    """透過後のフリンジ除去 + 白アウトライン拡張（in-place変更）

    Step 1: 背景色に近い半透明/境界ピクセルを透明化してフリンジ除去
    Step 2: アルファ膨張で白アウトラインを追加
    """
    import math

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    pixels = img.load()
    w, h = img.size
    fringe_tol = 60  # 背景色との色距離閾値

    def _color_dist(c1, c2):
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(c1, c2)))

    # --- Step 1: フリンジ除去 ---
    # 半透明ピクセルで背景色に近いものを透明化
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if 0 < a < 255:
                if _color_dist((r, g, b), bg_rgb) < fringe_tol:
                    pixels[x, y] = (r, g, b, 0)

    # 不透明ピクセルで透明隣接かつ背景色に近いものを透明化
    to_clear = []
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 255:
                continue
            if _color_dist((r, g, b), bg_rgb) >= fringe_tol:
                continue
            # 隣接に透明ピクセルがあるかチェック
            has_transparent_neighbor = False
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    if pixels[nx, ny][3] == 0:
                        has_transparent_neighbor = True
                        break
            if has_transparent_neighbor:
                to_clear.append((x, y))

    for x, y in to_clear:
        r, g, b, _ = pixels[x, y]
        pixels[x, y] = (r, g, b, 0)

    # --- Step 2: 白アウトライン拡張 ---
    alpha = img.getchannel("A")
    filter_size = outline_px * 2 + 1
    expanded = alpha.filter(ImageFilter.MaxFilter(size=filter_size))

    # 白背景レイヤーを作成（膨張分のみ白で描画）
    outline_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    outline_pixels = outline_layer.load()
    alpha_data = alpha.load()
    expanded_data = expanded.load()

    for y in range(h):
        for x in range(w):
            orig_a = alpha_data[x, y]
            exp_a = expanded_data[x, y]
            if orig_a == 0 and exp_a > 0:
                outline_pixels[x, y] = (255, 255, 255, exp_a)

    # アウトラインレイヤーの上に元画像を合成
    result = Image.alpha_composite(outline_layer, img)
    img.paste(result, (0, 0))


def transparentize_file(src_path: Path, dst_path: Path = None, config: dict = None) -> dict:
    """ファイルを背景透過し、同名 or 別名で保存（厳格透過パイプライン使用）"""
    if dst_path is None:
        dst_path = src_path

    img = Image.open(src_path).convert("RGBA")
    img, bg = apply_strict_transparency(img, config=config, qc=QUALITY_CONFIG_STRICT)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst_path, "PNG", optimize=True)
    return {"bg": bg}


# ============================================================
# グリッド分割 + 透過（厳格） + 品質テスト
# ============================================================

QUALITY_CONFIG_STRICT = {
    # 背景色残り判定
    "bg_tol": 30,              # 背景色に近い判定（RGB差分の合計）
    # アルファ二値化
    "alpha_cut": 8,            # これ以下は完全透明
    # 下端の緑ライン対策
    "bottom_band": 4,          # 下端の監視帯（px）
    "green_min": 200,          # G成分下限（明るい緑検出用）
    "green_gap": 120,          # G - max(R,B) の最小差（純粋な緑）
    # 緑フリンジ検出（画像全体）
    "fringe_green_min": 150,   # フリンジ検出のG成分下限
    "fringe_green_gap": 30,    # フリンジ検出のG差分閾値
    "fringe_max_pixels": 50,   # 許容する緑フリンジピクセル数（微量は許容）
    # アウトラインの白化
    "outline_thickness": 4,    # 白化する境界の厚み
    "white_min": 245,          # 白判定の下限
    # 上端の浮き白ライン対策
    "top_strip": 6,            # 上端の監視帯（px）
    # 白の緑かぶり除去
    "degreen_min": 200,
    "degreen_gap": 5,
    # 品質テスト
    "outline_white_min_ratio": 0.98,
    # 内部空洞の緑残り
    "interior_green_max_pct": 0.1,
    # キャラ内部の半透明（ゴースト）
    "interior_ghost_max_pct": 0.5,
    # キャラ切れ/余白
    "min_margin_px": 5,
    # LINE仕様
    "max_width": 370,
    "max_height": 320,
    "min_width": 50,
    "min_height": 50,
    "max_file_size_kb": 1024,
    # エッジ白線検出（グリッド境界線の残り）
    "edge_band_px": 3,         # 検出するエッジ幅（px）
    "edge_white_min": 240,     # 白と判定するRGB値の下限
    "edge_white_max_ratio": 0.3,  # 許容する白線比率（エッジピクセルの30%まで）
    # クリッピング（切れ）検出
    "clipping_check_content": True,  # コンテンツ切れもチェック
}


QUALITY_CRITERIA_SUMMARY = [
    "背景が除去されている（可視ピクセルに背景色が残らない）",
    "背景色が画像内に残らない（全域チェック）",
    "輪郭がはっきりしている（アルファ二値化）",
    "下端の緑ラインが残らない",
    "上端の浮き白ラインが残らない",
    "アウトラインは白（白化バンド）",
]


def _dominant_bg_from_band(img: Image.Image, config: dict) -> tuple:
    band, candidates = _collect_band_candidates(img, config)
    if candidates:
        return candidates[0]
    w, h = img.size
    band = max(2, int(min(w, h) * config["band_ratio"]))
    band = min(band, config["max_band"])
    pixels = img.load()
    counts = Counter()
    qstep = config["quantize_step"]
    alpha_threshold = config["alpha_threshold"]
    for y in range(h):
        for x in range(w):
            if x < band or x >= w - band or y < band or y >= h - band:
                r, g, b, a = pixels[x, y]
                if a <= alpha_threshold:
                    continue
                counts[_quantize_rgb((r, g, b), qstep)] += 1
    if counts:
        return max(counts, key=counts.get)
    # フォールバック: 中央
    r, g, b, _ = pixels[w // 2, h // 2]
    return (r, g, b)


def _build_opaque_mask(img: Image.Image) -> list:
    w, h = img.size
    pixels = img.load()
    mask = [[False] * w for _ in range(h)]
    for y in range(h):
        row = mask[y]
        for x in range(w):
            row[x] = pixels[x, y][3] > 0
    return mask


def _boundary_band(mask: list, thickness: int) -> list:
    h = len(mask)
    w = len(mask[0]) if h else 0
    boundary = [[False] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            if x == 0 or y == 0 or x == w - 1 or y == h - 1:
                boundary[y][x] = True
                continue
            if not (mask[y][x - 1] and mask[y][x + 1] and mask[y - 1][x] and mask[y + 1][x]):
                boundary[y][x] = True

    band = boundary
    for _ in range(max(0, thickness - 1)):
        new_band = [row[:] for row in band]
        for y in range(h):
            for x in range(w):
                if not band[y][x]:
                    continue
                if y > 0 and mask[y - 1][x]:
                    new_band[y - 1][x] = True
                if y < h - 1 and mask[y + 1][x]:
                    new_band[y + 1][x] = True
                if x > 0 and mask[y][x - 1]:
                    new_band[y][x - 1] = True
                if x < w - 1 and mask[y][x + 1]:
                    new_band[y][x + 1] = True
        band = new_band

    return band


def _remove_bottom_green_line(img: Image.Image, qc: dict) -> Image.Image:
    img = img.copy()
    pixels = img.load()
    w, h = img.size
    band = qc["bottom_band"]
    for y in range(max(0, h - band), h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if g >= qc["green_min"] and (g - max(r, b)) >= qc["green_gap"]:
                pixels[x, y] = (r, g, b, 0)
    return img


def _whiten_outline_band(img: Image.Image, qc: dict) -> Image.Image:
    img = img.copy()
    pixels = img.load()
    mask = _build_opaque_mask(img)
    band = _boundary_band(mask, qc["outline_thickness"])
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if not band[y][x]:
                continue
            r, g, b, a = pixels[x, y]
            if a > 0:
                pixels[x, y] = (255, 255, 255, a)
    return img


def _degreen_white(img: Image.Image, qc: dict) -> Image.Image:
    img = img.copy()
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if r >= qc["degreen_min"] and g >= qc["degreen_min"] and b >= qc["degreen_min"]:
                if g - max(r, b) >= qc["degreen_gap"]:
                    pixels[x, y] = (255, 255, 255, a)
    return img


def _remove_green_fringe(img: Image.Image, qc: dict, max_iterations: int = 10) -> Image.Image:
    """全画像から緑フリンジを透過させる

    2段階で処理:
    1. 全体から明らかな緑ピクセルを透過
    2. 境界帯から薄い緑フリンジを繰り返し透過
    """
    img = img.copy()
    pixels = img.load()
    w, h = img.size

    # 緑フリンジ検出の閾値
    fringe_green_min = qc.get("fringe_green_min", 150)
    fringe_green_gap = qc.get("fringe_green_gap", 30)

    # Phase 1: 全体から明らかな緑ピクセルを透過
    # より厳しい基準で全体をスキャン
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            # 明らかな緑（背景緑に近い）を透過
            if g >= 180 and (g - max(r, b)) >= 80:
                pixels[x, y] = (r, g, b, 0)

    # Phase 2: 境界帯から緑フリンジを繰り返し透過
    for iteration in range(max_iterations):
        # 不透明マスクを再構築
        opaque = [[pixels[x, y][3] > 0 for x in range(w)] for y in range(h)]

        # 境界帯（透明ピクセルに隣接する不透明ピクセル）を検出
        # 2ピクセル幅の境界帯を使用
        boundary = [[False] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                if not opaque[y][x]:
                    continue
                for dist in range(1, 3):  # 1-2ピクセル範囲
                    for dy in range(-dist, dist + 1):
                        for dx in range(-dist, dist + 1):
                            if dy == 0 and dx == 0:
                                continue
                            ny, nx = y + dy, x + dx
                            if 0 <= ny < h and 0 <= nx < w:
                                if not opaque[ny][nx]:
                                    boundary[y][x] = True
                                    break
                        if boundary[y][x]:
                            break
                    if boundary[y][x]:
                        break

        # 境界帯の緑フリンジを透過
        removed = 0
        for y in range(h):
            for x in range(w):
                if not boundary[y][x]:
                    continue
                r, g, b, a = pixels[x, y]
                if a == 0:
                    continue
                # 緑フリンジ判定（緩い基準）
                if g >= fringe_green_min and (g - max(r, b)) >= fringe_green_gap:
                    pixels[x, y] = (r, g, b, 0)
                    removed += 1

        if removed == 0:
            break

    return img


def _remove_stray_top_white(img: Image.Image, qc: dict) -> Image.Image:
    img = img.copy()
    pixels = img.load()
    w, h = img.size
    top = min(qc["top_strip"], h - 1)
    for y in range(top):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if r < qc["white_min"] or g < qc["white_min"] or b < qc["white_min"]:
                continue
            # 直下に不透明が無い場合は浮き白として除去
            has_below = False
            for dy in (1, 2):
                if y + dy < h and pixels[x, y + dy][3] > 0:
                    has_below = True
                    break
            if not has_below:
                pixels[x, y] = (r, g, b, 0)
    return img


def apply_strict_transparency(cell_img: Image.Image, config: dict = None, qc: dict = None) -> tuple:
    """厳格な透過処理を適用し、(img, bg_color) を返す"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    if config is None:
        config = TRANSPARENCY_CONFIG_DEFAULT.copy()

    img = cell_img.convert("RGBA")
    bg = _dominant_bg_from_band(img, config)
    cfg = config.copy()
    cfg["fixed_colors"] = [bg]

    transparentize_image_background(img, cfg)

    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= qc["bg_tol"]:
                pixels[x, y] = (r, g, b, 0)
                continue
            # アルファ二値化
            pixels[x, y] = (r, g, b, 255 if a > qc["alpha_cut"] else 0)

    try:
        img = clean_edge_lines(img)
    except Exception:
        pass

    img = _remove_bottom_green_line(img, qc)
    img = _whiten_outline_band(img, qc)
    img = _degreen_white(img, qc)
    # _remove_green_fringe は過剰にキャラクターを破壊するため無効化
    # 緑フリンジはQCで検出し、必要に応じて手動修正または閾値調整
    # img = _remove_green_fringe(img, qc)
    img = _fill_interior_green_cavities(img, bg, qc)
    img = _remove_stray_top_white(img, qc)
    # エッジ白線（グリッド境界線の残り）を除去
    img = _remove_edge_white_lines(img, qc)
    return img, bg


def evaluate_transparency_quality(img: Image.Image, bg: tuple, qc: dict = None) -> dict:
    """品質テストを実行し、判定結果を返す"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT

    pixels = img.load()
    w, h = img.size
    visible = 0
    bg_remain = 0
    semi = 0
    bottom_green = 0
    green_fringe = 0  # 緑フリンジピクセル数

    # 緑フリンジ検出の閾値（設定がなければデフォルト値を使用）
    fringe_green_min = qc.get("fringe_green_min", 150)
    fringe_green_gap = qc.get("fringe_green_gap", 30)

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            visible += 1
            if a < 255:
                semi += 1
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) <= qc["bg_tol"]:
                bg_remain += 1
            # 下端の緑ライン（厳格な閾値）
            if y >= h - qc["bottom_band"]:
                if g >= qc["green_min"] and (g - max(r, b)) >= qc["green_gap"]:
                    bottom_green += 1
            # 緑フリンジ検出（画像全体、緩い閾値）
            if g >= fringe_green_min and (g - max(r, b)) >= fringe_green_gap:
                green_fringe += 1

    bg_remain_pct = (bg_remain / visible * 100) if visible else 0
    semi_pct = (semi / (w * h) * 100) if (w * h) else 0
    bottom_green_pct = (bottom_green / (qc["bottom_band"] * w) * 100) if w else 0

    # 上端の浮き白ライン
    top = min(qc["top_strip"], h - 1)
    stray_top_white = 0
    for y in range(top):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            if r < qc["white_min"] or g < qc["white_min"] or b < qc["white_min"]:
                continue
            has_below = False
            for dy in (1, 2):
                if y + dy < h and pixels[x, y + dy][3] > 0:
                    has_below = True
                    break
            if not has_below:
                stray_top_white += 1

    # アウトライン白率
    mask = _build_opaque_mask(img)
    band = _boundary_band(mask, qc["outline_thickness"])
    band_total = 0
    band_white = 0
    for y in range(h):
        for x in range(w):
            if not band[y][x]:
                continue
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            band_total += 1
            if r >= qc["white_min"] and g >= qc["white_min"] and b >= qc["white_min"]:
                band_white += 1
    outline_white_pct = (band_white / band_total * 100) if band_total else 100.0

    # 緑フリンジの許容値（設定がなければ0=完全除去）
    fringe_max = qc.get("fringe_max_pixels", 0)

    ok = (
        bg_remain_pct == 0
        and semi_pct == 0
        and bottom_green_pct == 0
        and stray_top_white == 0
        and outline_white_pct >= qc["outline_white_min_ratio"] * 100
        and green_fringe <= fringe_max  # 緑フリンジチェック追加
    )

    return {
        "ok": ok,
        "bg_remain_pct": bg_remain_pct,
        "semi_pct": semi_pct,
        "bottom_green_pct": bottom_green_pct,
        "stray_top_white_px": stray_top_white,
        "outline_white_pct": outline_white_pct,
        "green_fringe_count": green_fringe,  # 緑フリンジ数を追加
    }


# ============================================================
# 拡張QCチェック（個別スタンプ品質検証）
# ============================================================

def _fill_interior_green_cavities(img: Image.Image, bg: tuple, qc: dict = None) -> Image.Image:
    """キャラ内部の穴に残る緑ピクセルを透過させる（apply_strict_transparency用）"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()

    # 外部透明ピクセルをエッジからフラッドフィルで特定
    exterior = bytearray(w * h)
    dq = deque()
    for x in range(w):
        if pixels[x, 0][3] == 0:
            dq.append((x, 0))
        if pixels[x, h - 1][3] == 0:
            dq.append((x, h - 1))
    for y in range(h):
        if pixels[0, y][3] == 0:
            dq.append((0, y))
        if pixels[w - 1, y][3] == 0:
            dq.append((w - 1, y))

    while dq:
        x, y = dq.popleft()
        idx = y * w + x
        if exterior[idx]:
            continue
        if pixels[x, y][3] > 0:
            continue
        exterior[idx] = 1
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not exterior[ny * w + nx]:
                dq.append((nx, ny))

    # 内部空洞の緑ピクセルのみを透過（白や明るい色は除外）
    green_min = qc.get("green_min", 200)
    green_gap = qc.get("green_gap", 120)
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if exterior[idx]:
                continue
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            # 緑が支配的なピクセルのみ除去（白い服・テキストは保護）
            if g >= green_min and (g - max(r, b)) >= green_gap:
                pixels[x, y] = (r, g, b, 0)

    return img


def _check_interior_green_cavities(img: Image.Image, qc: dict = None) -> dict:
    """キャラ内部の穴（目の間、腕の隙間等）に残る緑ピクセルを検出"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()

    # 外部透明ピクセルをエッジからフラッドフィルで特定
    exterior = bytearray(w * h)
    dq = deque()
    for x in range(w):
        if pixels[x, 0][3] == 0:
            dq.append((x, 0))
        if pixels[x, h - 1][3] == 0:
            dq.append((x, h - 1))
    for y in range(h):
        if pixels[0, y][3] == 0:
            dq.append((0, y))
        if pixels[w - 1, y][3] == 0:
            dq.append((w - 1, y))

    while dq:
        x, y = dq.popleft()
        idx = y * w + x
        if exterior[idx]:
            continue
        if pixels[x, y][3] > 0:
            continue
        exterior[idx] = 1
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and not exterior[ny * w + nx]:
                dq.append((nx, ny))

    # 内部空洞の緑ピクセルを検出
    green_min = qc.get("green_min", 200)
    green_gap = qc.get("green_gap", 120)
    interior_green = 0
    interior_total = 0
    for y in range(h):
        for x in range(w):
            idx = y * w + x
            if exterior[idx]:
                continue
            r, g, b, a = pixels[x, y]
            if a == 0:
                # 内部の透明ピクセル: 緑判定不要だがカウント
                interior_total += 1
                continue
            interior_total += 1
            if g >= green_min and (g - max(r, b)) >= green_gap:
                interior_green += 1

    max_pct = qc.get("interior_green_max_pct", 0.1)
    pct = (interior_green / interior_total * 100) if interior_total else 0.0
    return {
        "passed": pct <= max_pct,
        "interior_green_px": interior_green,
        "pct": round(pct, 3),
    }


def _check_interior_ghost(img: Image.Image, qc: dict = None) -> dict:
    """キャラ本体内部の半透明ピクセルを検出（服・肌が誤って透過）"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()

    # エッジ3px内側を「内部」とみなす
    erosion = 3
    interior_semi = 0
    interior_total = 0
    for y in range(erosion, h - erosion):
        for x in range(erosion, w - erosion):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            interior_total += 1
            if 0 < a < 255:
                interior_semi += 1

    max_pct = qc.get("interior_ghost_max_pct", 0.5)
    pct = (interior_semi / interior_total * 100) if interior_total else 0.0
    return {
        "passed": pct <= max_pct,
        "ghost_px": interior_semi,
        "pct": round(pct, 3),
    }


def _check_character_clipping(img: Image.Image, qc: dict = None) -> dict:
    """キャラが画像端で切れているかチェック"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()
    min_margin = qc.get("min_margin_px", 5)

    edge_touching = []
    # 上端
    for x in range(w):
        if pixels[x, 0][3] > 0:
            edge_touching.append("top")
            break
    # 下端
    for x in range(w):
        if pixels[x, h - 1][3] > 0:
            edge_touching.append("bottom")
            break
    # 左端
    for y in range(h):
        if pixels[0, y][3] > 0:
            edge_touching.append("left")
            break
    # 右端
    for y in range(h):
        if pixels[w - 1, y][3] > 0:
            edge_touching.append("right")
            break

    # 最小余白計算
    margins = {"top": h, "bottom": h, "left": w, "right": w}
    for y in range(h):
        for x in range(w):
            if pixels[x, y][3] > 0:
                margins["top"] = min(margins["top"], y)
                margins["bottom"] = min(margins["bottom"], h - 1 - y)
                margins["left"] = min(margins["left"], x)
                margins["right"] = min(margins["right"], w - 1 - x)

    actual_min = min(margins.values())
    return {
        "passed": actual_min >= min_margin and len(edge_touching) == 0,
        "min_margin": actual_min,
        "edge_touching": edge_touching,
    }


def _check_line_spec_compliance(img: Image.Image, qc: dict = None) -> dict:
    """LINE仕様のサイズ・ファイルサイズチェック"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    max_w = qc.get("max_width", 370)
    max_h = qc.get("max_height", 320)
    min_w = qc.get("min_width", 50)
    min_h = qc.get("min_height", 50)
    max_kb = qc.get("max_file_size_kb", 1024)

    messages = []
    if w > max_w or h > max_h:
        messages.append(f"サイズ超過: {w}x{h} (上限 {max_w}x{max_h})")
    if w < min_w or h < min_h:
        messages.append(f"サイズ不足: {w}x{h} (下限 {min_w}x{min_h})")

    # ファイルサイズ推定
    import io as _io
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    file_size_kb = buf.tell() / 1024

    if file_size_kb > max_kb:
        messages.append(f"ファイルサイズ超過: {file_size_kb:.0f}KB (上限 {max_kb}KB)")

    return {
        "passed": len(messages) == 0,
        "size": (w, h),
        "file_size_kb": round(file_size_kb, 1),
        "messages": messages,
    }


def _check_edge_white_lines(img: Image.Image, qc: dict = None) -> dict:
    """画像端の白線（グリッド境界線の残り）をチェック

    透過済み画像のエッジに、グリッド分割時の白い境界線が
    残っていないかを検出する。
    """
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()

    band = qc.get("edge_band_px", 3)
    white_min = qc.get("edge_white_min", 240)
    max_ratio = qc.get("edge_white_max_ratio", 0.3)

    edge_stats = {"top": 0, "bottom": 0, "left": 0, "right": 0}
    edge_total = {"top": 0, "bottom": 0, "left": 0, "right": 0}
    edge_white = {"top": 0, "bottom": 0, "left": 0, "right": 0}

    # 上端
    for y in range(band):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0:
                edge_total["top"] += 1
                if r >= white_min and g >= white_min and b >= white_min:
                    edge_white["top"] += 1

    # 下端
    for y in range(h - band, h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a > 0:
                edge_total["bottom"] += 1
                if r >= white_min and g >= white_min and b >= white_min:
                    edge_white["bottom"] += 1

    # 左端
    for x in range(band):
        for y in range(h):
            r, g, b, a = pixels[x, y]
            if a > 0:
                edge_total["left"] += 1
                if r >= white_min and g >= white_min and b >= white_min:
                    edge_white["left"] += 1

    # 右端
    for x in range(w - band, w):
        for y in range(h):
            r, g, b, a = pixels[x, y]
            if a > 0:
                edge_total["right"] += 1
                if r >= white_min and g >= white_min and b >= white_min:
                    edge_white["right"] += 1

    # 各エッジの白線比率を計算
    problem_edges = []
    for side in ["top", "bottom", "left", "right"]:
        if edge_total[side] > 0:
            ratio = edge_white[side] / edge_total[side]
            edge_stats[side] = round(ratio * 100, 1)
            if ratio > max_ratio:
                problem_edges.append(f"{side}({edge_stats[side]:.0f}%)")

    return {
        "passed": len(problem_edges) == 0,
        "edge_white_pct": edge_stats,
        "edge_white_px": edge_white,
        "edge_total_px": edge_total,
        "problem_edges": problem_edges,
    }


def _remove_edge_white_lines(img: Image.Image, qc: dict = None) -> Image.Image:
    """エッジの白線を透過させる

    グリッド分割時に残った白い境界線を透過処理する。
    2段階処理:
    1. 連続した白線（20%以上）を検出して透過
    2. 残った外周の孤立した白ピクセルも透過
    """
    if qc is None:
        qc = QUALITY_CONFIG_STRICT
    w, h = img.size
    pixels = img.load()

    white_min = qc.get("edge_white_min", 240)

    def is_white(r, g, b, a):
        return a > 0 and r >= white_min and g >= white_min and b >= white_min

    def is_visible(r, g, b, a):
        return a > 0

    # Phase 1: 外周2ピクセルの白線を検出して透過
    outer_layers = 2
    white_line_threshold = 0.15  # 15%以上が白なら境界線

    for layer in range(outer_layers):
        # 上端
        visible_top = sum(1 for x in range(w) if is_visible(*pixels[x, layer]))
        white_top = sum(1 for x in range(w) if is_white(*pixels[x, layer]))
        if visible_top > 0 and white_top / max(visible_top, 1) > white_line_threshold:
            for x in range(w):
                r, g, b, a = pixels[x, layer]
                if is_white(r, g, b, a):
                    pixels[x, layer] = (r, g, b, 0)

        # 下端
        visible_bottom = sum(1 for x in range(w) if is_visible(*pixels[x, h - 1 - layer]))
        white_bottom = sum(1 for x in range(w) if is_white(*pixels[x, h - 1 - layer]))
        if visible_bottom > 0 and white_bottom / max(visible_bottom, 1) > white_line_threshold:
            for x in range(w):
                r, g, b, a = pixels[x, h - 1 - layer]
                if is_white(r, g, b, a):
                    pixels[x, h - 1 - layer] = (r, g, b, 0)

        # 左端
        visible_left = sum(1 for y in range(h) if is_visible(*pixels[layer, y]))
        white_left = sum(1 for y in range(h) if is_white(*pixels[layer, y]))
        if visible_left > 0 and white_left / max(visible_left, 1) > white_line_threshold:
            for y in range(h):
                r, g, b, a = pixels[layer, y]
                if is_white(r, g, b, a):
                    pixels[layer, y] = (r, g, b, 0)

        # 右端
        visible_right = sum(1 for y in range(h) if is_visible(*pixels[w - 1 - layer, y]))
        white_right = sum(1 for y in range(h) if is_white(*pixels[w - 1 - layer, y]))
        if visible_right > 0 and white_right / max(visible_right, 1) > white_line_threshold:
            for y in range(h):
                r, g, b, a = pixels[w - 1 - layer, y]
                if is_white(r, g, b, a):
                    pixels[w - 1 - layer, y] = (r, g, b, 0)

    # Phase 2: 最外周1ピクセルの白を無条件で透過
    # （コンテンツから離れた端の白は境界線の残り）
    for x in range(w):
        r, g, b, a = pixels[x, 0]
        if is_white(r, g, b, a):
            pixels[x, 0] = (r, g, b, 0)
        r, g, b, a = pixels[x, h - 1]
        if is_white(r, g, b, a):
            pixels[x, h - 1] = (r, g, b, 0)

    for y in range(h):
        r, g, b, a = pixels[0, y]
        if is_white(r, g, b, a):
            pixels[0, y] = (r, g, b, 0)
        r, g, b, a = pixels[w - 1, y]
        if is_white(r, g, b, a):
            pixels[w - 1, y] = (r, g, b, 0)

    return img


def evaluate_stamp_quality_full(img: Image.Image, bg: tuple, qc: dict = None, text: str = "") -> dict:
    """全QCチェックを統合実行し、結果を返す"""
    if qc is None:
        qc = QUALITY_CONFIG_STRICT

    # 既存の透過品質チェック
    base = evaluate_transparency_quality(img, bg, qc)

    # 拡張チェック
    interior_green = _check_interior_green_cavities(img, qc)
    interior_ghost = _check_interior_ghost(img, qc)
    clipping = _check_character_clipping(img, qc)
    line_spec = _check_line_spec_compliance(img, qc)
    edge_white = _check_edge_white_lines(img, qc)

    # 致命的エラー（NGとする）と警告（OKだが注意）を分離
    errors = []    # 致命的: ok=False
    warnings = []  # 非致命的: ok=True のまま

    # --- 致命的チェック ---
    # 背景色が大量に残っている
    if base["bg_remain_pct"] > 1.0:
        errors.append(f"背景色残留: {base['bg_remain_pct']:.2f}%")
    elif base["bg_remain_pct"] > 0:
        warnings.append(f"背景色微残留: {base['bg_remain_pct']:.2f}%")

    # 内部空洞に緑が残っている
    if not interior_green["passed"]:
        errors.append(f"内部空洞に緑残留: {interior_green['interior_green_px']}px ({interior_green['pct']:.3f}%)")

    # 底部緑ライン
    if base["bottom_green_pct"] > 1.0:
        errors.append(f"底部緑ライン: {base['bottom_green_pct']:.2f}%")
    elif base["bottom_green_pct"] > 0:
        warnings.append(f"底部緑ライン微残: {base['bottom_green_pct']:.2f}%")

    # LINE仕様違反
    if not line_spec["passed"]:
        for msg in line_spec["messages"]:
            errors.append(msg)

    # --- 非致命的チェック（警告のみ）---
    # 半透明ピクセル（アンチエイリアス・影・グラデーション）
    if base["semi_pct"] > 0:
        warnings.append(f"半透明ピクセル: {base['semi_pct']:.2f}%")

    # キャラ内部半透明（ゴースト）
    if not interior_ghost["passed"]:
        warnings.append(f"キャラ内部半透明: {interior_ghost['ghost_px']}px ({interior_ghost['pct']:.3f}%)")

    # 浮き白ピクセル
    if base["stray_top_white_px"] > 0:
        warnings.append(f"浮き白ピクセル: {base['stray_top_white_px']}px")

    # キャラ切れ/余白
    if not clipping["passed"]:
        if clipping["edge_touching"]:
            warnings.append(f"キャラ切れ: {', '.join(clipping['edge_touching'])}端に接触")
        if clipping["min_margin"] < qc.get("min_margin_px", 5):
            warnings.append(f"余白不足: {clipping['min_margin']}px (最低{qc.get('min_margin_px', 5)}px)")

    # エッジ白線（グリッド境界線の残り）
    if not edge_white["passed"]:
        errors.append(f"エッジ白線: {', '.join(edge_white['problem_edges'])}")

    all_ok = len(errors) == 0

    return {
        "ok": all_ok,
        "base": base,
        "interior_green": interior_green,
        "interior_ghost": interior_ghost,
        "clipping": clipping,
        "line_spec": line_spec,
        "edge_white": edge_white,
        "errors": errors,
        "warnings": warnings,
    }


def split_grids_and_transparent(grid_dir: str, output_dir: str = None, run_tests: bool = True,
                                config: dict = None, qc: dict = None) -> list:
    """grid_1.png と grid_2.png を分割し、厳格透過＋品質テストを実行"""
    grid_path = Path(grid_dir)
    if output_dir is None:
        output_dir = grid_path / "grid_split_transparent_strict"
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = TRANSPARENCY_CONFIG_DEFAULT.copy()
    if qc is None:
        qc = QUALITY_CONFIG_STRICT

    results = []
    grids = [(grid_path / "grid_1.png", 1), (grid_path / "grid_2.png", 13)]

    for grid_file, start_index in grids:
        if not grid_file.exists():
            continue
        grid_img = Image.open(grid_file)
        if grid_img.mode != "RGBA":
            grid_img = grid_img.convert("RGBA")
        stamps = split_grid_image(grid_img, rows=3, cols=4, clean_edges=True)
        for i, cell in enumerate(stamps):
            idx = start_index + i
            out, bg = apply_strict_transparency(cell, config=config, qc=qc)
            out_path = output_path / f"{idx:02d}.png"
            out.save(out_path, "PNG")
            if run_tests:
                stats = evaluate_stamp_quality_full(out, bg, qc=qc, text="")
                results.append({"path": str(out_path), **stats})
            else:
                results.append({"path": str(out_path), "ok": True})

    if run_tests:
        # errors（致命的）がある場合のみNG
        fails = [r for r in results if r.get("errors")]
        warns = [r for r in results if r.get("warnings") and not r.get("errors")]

        if fails:
            print("品質テストNG（致命的エラー）:")
            for r in fails:
                print(f" - {Path(r['path']).name}:")
                for e in r.get("errors", []):
                    print(f"     [NG] {e}")

        if warns:
            print("品質テスト警告（非致命的）:")
            for r in warns:
                print(f" - {Path(r['path']).name}:")
                for w in r.get("warnings", []):
                    print(f"     [WARN] {w}")

        passed = len(results) - len(fails)
        print(f"\n品質テスト結果: {passed}/{len(results)} PASS")

        if fails:
            raise ValueError(f"品質テストに失敗しました。{len(fails)}件の致命的エラーがあります。")
    print(f"出力先: {output_path}")
    return results


def _collect_paths_for_mode(output_dir: str, mode: str) -> list:
    output_path = Path(output_dir)
    paths = []

    if mode == "package":
        for i in range(1, 25):
            p = output_path / f"{i:02d}.png"
            if p.exists():
                paths.append(p)
        for name in ["main.png", "tab.png"]:
            p = output_path / name
            if p.exists():
                paths.append(p)
        return paths

    if mode == "eco24":
        for p in output_path.glob("*.png"):
            if p.name.startswith("_") or p.name.startswith("grid_"):
                continue
            paths.append(p)
        return paths

    # mode == "all"
    return list(output_path.glob("*.png"))


def postprocess_transparency_dir(output_dir: str, mode: str = "package",
                                 update_zip: bool = False, config: dict = None) -> list:
    """出力ディレクトリ内の画像を背景透過し、必要ならZIPを更新"""
    paths = _collect_paths_for_mode(output_dir, mode)
    stats = []

    if not paths:
        return stats

    print(f"背景透過を再処理中... ({len(paths)} files)")
    if config is None:
        config = TRANSPARENCY_CONFIG_DEFAULT.copy()

        # _prompts.json に背景色がある場合は固定色で透過
        prompts_path = Path(output_dir) / "_prompts.json"
        if prompts_path.exists():
            try:
                prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
                bg = prompts.get("background_color") or ""
                hex_color = _extract_hex_color(bg)
                if hex_color:
                    config["fixed_colors"] = [hex_color]
            except Exception:
                pass
    for path in paths:
        s = transparentize_file(path, path, config)
        stats.append({"path": str(path), **s})

    if update_zip and mode == "package":
        create_submission_zip(output_dir)

    return stats


def _build_reactions_from_prompts(prompts: dict) -> list:
    """_prompts.json の内容でリアクションの詳細プロンプトを復元"""
    reactions = expand_all_pose_refs([dict(r) for r in REACTIONS])
    prompt_reactions = prompts.get("reactions", [])
    by_index = {r.get("index"): r for r in prompt_reactions}

    for i, base in enumerate(reactions, start=1):
        p = by_index.get(i)
        if not p:
            continue
        base["enhanced_prompt"] = p.get("enhanced_prompt")
    return reactions


def _extract_hex_color(text: str) -> tuple:
    """文字列から #RRGGBB を抽出して (r,g,b) を返す"""
    import re
    if not text:
        return None
    m = re.search(r"#([0-9a-fA-F]{6})", text)
    if not m:
        return None
    hex_str = m.group(1)
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return (r, g, b)


def _measure_min_margin(img: Image.Image) -> int:
    """不透明ピクセルの最小余白(px)を返す"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    px = img.load()

    minx, miny = w, h
    maxx, maxy = -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y

    if maxx < 0:
        return min(w, h) // 2

    left = minx
    top = miny
    right = w - 1 - maxx
    bottom = h - 1 - maxy
    return min(left, top, right, bottom)


def _normalize_margin(img: Image.Image, target_margin: int) -> Image.Image:
    """最小余白が target_margin 未満なら縮小して余白を確保する"""
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    w, h = img.size
    px = img.load()

    minx, miny = w, h
    maxx, maxy = -1, -1
    for y in range(h):
        for x in range(w):
            if px[x, y][3] > 0:
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y

    if maxx < 0:
        return img

    left = minx
    top = miny
    right = w - 1 - maxx
    bottom = h - 1 - maxy
    min_margin = min(left, top, right, bottom)

    if min_margin >= target_margin:
        return img

    content = img.crop((minx, miny, maxx + 1, maxy + 1))
    cw, ch = content.size

    max_w = max(1, w - 2 * target_margin)
    max_h = max(1, h - 2 * target_margin)
    scale = min(max_w / cw, max_h / ch)
    if scale >= 1.0:
        return img

    new_w = max(1, int(cw * scale))
    new_h = max(1, int(ch * scale))
    resized = content.resize((new_w, new_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    paste_x = (w - new_w) // 2
    paste_y = (h - new_h) // 2
    canvas.paste(resized, (paste_x, paste_y), resized)
    return canvas


def _compute_reference_margin(output_dir: Path, indices: list, fallback: int = 16) -> int:
    """参照画像群から平均の最小余白を算出"""
    margins = []
    for idx in indices:
        path = output_dir / f"{idx:02d}.png"
        if not path.exists():
            continue
        img = Image.open(path)
        margins.append(_measure_min_margin(img))
    if not margins:
        return fallback
    return max(8, int(sum(margins) / len(margins)))


def _resolve_output_stamp_path(output_dir: Path, idx: int, reaction_id: str) -> Path:
    """出力ファイル名を既存の形式に合わせて選択"""
    plain = output_dir / f"{idx:02d}.png"
    with_id = output_dir / f"{idx:02d}_{reaction_id}.png"

    if plain.exists() and not with_id.exists():
        return plain
    if with_id.exists() and not plain.exists():
        return with_id

    # 両方なければ、package形式を優先
    return plain


def regenerate_grid_from_prompts(client, output_dir: str, grid_num: int = 2,
                                 max_retries: int = 3, full_body: bool = True) -> dict:
    """_prompts.json を使って指定グリッド（1 or 2）を再生成"""
    output_path = Path(output_dir)
    prompts_path = output_path / "_prompts.json"
    character_path = output_path / "_character.png"

    if not prompts_path.exists():
        raise FileNotFoundError(f"_prompts.json が見つかりません: {prompts_path}")
    if not character_path.exists():
        raise FileNotFoundError(f"_character.png が見つかりません: {character_path}")

    prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
    style = prompts.get("style", "sd_25")
    background_color = prompts.get("background_color")
    modifiers = prompts.get("modifiers") or DEFAULT_MODIFIERS.copy()

    transparency_config = TRANSPARENCY_CONFIG_DEFAULT.copy()
    bg_hex = _extract_hex_color(background_color or "")
    if bg_hex:
        transparency_config["fixed_colors"] = [bg_hex]

    reactions = _build_reactions_from_prompts(prompts)

    # キャラクターYAMLを読み込み（存在すれば）
    character_yaml = None
    character_yaml_path = output_path / "_character.yaml"
    if character_yaml_path.exists():
        import yaml
        with open(character_yaml_path, 'r', encoding='utf-8') as f:
            character_yaml = yaml.safe_load(f)
        print(f"  キャラクターYAML読み込み: {character_yaml_path}")

    if grid_num == 1:
        subset = reactions[:12]
        start_index = 1
    elif grid_num == 2:
        subset = reactions[12:24]
        start_index = 13
    else:
        raise ValueError("grid_num は 1 または 2 を指定してください")

    print(f"グリッド再生成: {grid_num}/2 ({start_index:02d}〜{start_index+11:02d})")

    grid_data = None
    validation = None
    for attempt in range(max_retries):
        print(f"  生成試行 {attempt + 1}/{max_retries}...")
        grid_data = generate_grid_from_character(
            client,
            str(character_path),
            subset,
            chibi_style=style,
            background_color=background_color,
            character_yaml=character_yaml,
            modifiers=modifiers,
            force_full_body=full_body
        )

        print("  検証中...")
        validation = validate_grid(client, grid_data, expected_cells=12)
        if validation.get("valid"):
            print("  [OK] グリッド検証OK")
            break
        print(f"  [NG] {validation.get('reason', '不明な理由')}")

    if grid_data is None:
        raise ValueError("グリッド画像が生成されませんでした")

    grid_img = Image.open(io.BytesIO(grid_data))
    grid_path = output_path / f"grid_{grid_num}.png"
    grid_img.save(grid_path, "PNG")
    print(f"  グリッド画像保存: {grid_path}")

    stamps = split_grid_image(grid_img, rows=3, cols=4)
    stamps = [center_character_in_cell(s) for s in stamps]

    target_margin = None
    if grid_num == 2:
        target_margin = _compute_reference_margin(output_path, list(range(1, 13)), fallback=16)
        print(f"  余白ターゲット: {target_margin}px")

    updated_files = []
    for i, (stamp, reaction) in enumerate(zip(stamps, subset)):
        idx = start_index + i
        if target_margin:
            stamp = _normalize_margin(stamp, target_margin)
        out_path = _resolve_output_stamp_path(output_path, idx, reaction["id"])
        stamp.save(out_path, "PNG")
        updated_files.append(str(out_path))
        print(f"  保存: {out_path}")

    # 透過処理を更新（更新分のみ）
    for path_str in updated_files:
        transparentize_file(Path(path_str), Path(path_str), transparency_config)

    # ZIPを更新
    create_submission_zip(output_dir)

    return {
        "grid": grid_num,
        "updated": updated_files,
        "validation": validation
    }


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

    # リアクションをシャッフル（pose_refを展開）
    reactions = expand_all_pose_refs(REACTIONS.copy())
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

    # セッション管理オプション
    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument("--session", metavar="ID",
                               help="既存セッションを使用して生成")
    session_group.add_argument("--list", action="store_true",
                               help="セッション一覧を表示")
    session_group.add_argument("--latest", action="store_true",
                               help="最新セッションを使用して生成")

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
    mode_group.add_argument("--fix-transparency", metavar="DIR",
                            help="既存出力ディレクトリの背景透過を再処理")
    mode_group.add_argument("--split-grids", metavar="DIR",
                            help="既存の grid_1.png / grid_2.png を分割して透過（品質テスト付き）")
    mode_group.add_argument("--regenerate-grid", metavar="DIR",
                            help="既存出力ディレクトリのグリッドを再生成（_prompts.json を使用）")

    # 共通オプション
    parser.add_argument("--output", "-o", help="出力先（ファイルまたはディレクトリ）")
    # スタイルオプション（旧スタイルIDもエイリアスで対応）
    all_style_choices = list(CHIBI_STYLES.keys()) + list(STYLE_ALIASES.keys())
    parser.add_argument("--style", choices=all_style_choices,
                        default=None, help="スタイル（推奨: sd_25, sd_10, sd_30, face_only, yuru_line）")
    parser.add_argument("--type", "-t", choices=["stamp", "main", "tab"],
                        default="stamp", help="画像タイプ")
    parser.add_argument("--count", "-c", type=int, default=1,
                        help="生成枚数（--promptモード時）")
    parser.add_argument("--project", help="Google Cloud プロジェクトID")
    parser.add_argument("--no-remove-bg", action="store_true",
                        help="背景除去をスキップ")
    parser.add_argument("--no-items", action="store_true",
                        help="アイテム検出をスキップ（デフォルトは写真からアイテムを自動検出）")
    # モディファイアオプション
    parser.add_argument("--text-mode", choices=["none", "small", "deka"],
                        default=None, help="テキストモード（デフォルト: deka=でか文字）")
    parser.add_argument("--outline", choices=["none", "white", "bold"],
                        default=None, help="アウトライン（デフォルト: bold=太フチ）")
    parser.add_argument("--cpu", action="store_true",
                        help="CUDAを使用せずCPUで処理（デフォルトはCUDA優先）")
    parser.add_argument("--check-cuda", action="store_true",
                        help="CUDA環境をチェックして終了")
    parser.add_argument("--fix-mode", choices=["package", "eco24", "all"],
                        default="package", help="透過再処理の対象範囲（デフォルト: package）")
    parser.add_argument("--no-fix-zip", action="store_true",
                        help="透過再処理時にsubmission.zipを再作成しない")
    parser.add_argument("--grid-num", type=int, choices=[1, 2], default=2,
                        help="再生成するグリッド番号（1 or 2）")
    parser.add_argument("--no-full-body", action="store_true",
                        help="グリッド再生成時の全身表示強制を無効化")
    # ペルソナオプション
    parser.add_argument("--persona-age", choices=["Teen", "20s", "30s", "40s", "50s+"],
                        help="ペルソナ年代（Teen / 20s / 30s / 40s / 50s+）")
    parser.add_argument("--persona-target", choices=["Friend", "Family", "Partner", "Work"],
                        help="ペルソナ相手（Friend / Family / Partner / Work）")
    parser.add_argument("--persona-theme", choices=["共感強化", "ツッコミ強化", "褒め強化", "家族強化", "応援強化"],
                        help="ペルソナテーマ（共感強化 / ツッコミ強化 / 褒め強化 / 家族強化 / 応援強化）")
    parser.add_argument("--persona-intensity", type=int, choices=[1, 2, 3], default=2,
                        help="ペルソナ強度 1(控えめ) / 2(バランス) / 3(特化)（デフォルト: 2）")
    parser.add_argument("--persona-context",
                        help="自由テキスト（例: '関西弁×エンジニアネタ'）")
    parser.add_argument("--reactions-file",
                        help="カスタムリアクション定義ファイル（JSON/YAML）")
    parser.add_argument("--ai-reactions", action="store_true",
                        help="AIでリアクションを自動生成する（デフォルト: グローバルREACTIONSを使用）")

    args = parser.parse_args()

    # 透過再処理モード（API不要）
    if args.fix_transparency:
        target_dir = Path(args.fix_transparency)
        if not target_dir.exists():
            print(f"Error: ディレクトリが見つかりません: {args.fix_transparency}", file=sys.stderr)
            sys.exit(1)

        stats = postprocess_transparency_dir(
            str(target_dir),
            mode=args.fix_mode,
            update_zip=not args.no_fix_zip
        )

        print(f"透過再処理完了: {len(stats)} files")
        return

    # グリッド分割 + 透過 + 品質テスト（API不要）
    if args.split_grids:
        target_dir = Path(args.split_grids)
        if not target_dir.exists():
            print(f"Error: ディレクトリが見つかりません: {args.split_grids}", file=sys.stderr)
            sys.exit(1)
        output_dir = args.output or str(target_dir / "grid_split_transparent_strict")
        try:
            split_grids_and_transparent(str(target_dir), output_dir=output_dir, run_tests=True)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        return

    # セッション一覧表示モード
    if args.list:
        try:
            from session_manager import Session, print_session_list
            sessions = Session.list_all()
            print_session_list(sessions)
        except ImportError:
            print("セッション管理モジュールが見つかりません")
        return

    # セッションからの生成モード
    session = None
    if args.session or args.latest:
        try:
            from session_manager import Session, print_session_detail
            if args.latest:
                session = Session.load_latest()
                if not session:
                    print("セッションがありません。--package で新規生成してください。")
                    return
            else:
                session = Session.load(args.session)

            print_session_detail(session)

            # セッションから設定を取得
            if not args.package and not args.eco24:
                # セッションからの生成は--packageモードを使用
                args.package = session.config.get("image_path")

            if not args.style:
                args.style = session.config.get("style", "sd_25")
            if not args.output:
                args.output = session.get_output_dir()

            # モディファイアもセッションから
            if not hasattr(args, 'text_mode') or args.text_mode is None:
                args.text_mode = session.config.get("text_mode", "deka")
            if not hasattr(args, 'outline') or args.outline is None:
                args.outline = session.config.get("outline", "bold")

        except ImportError:
            print("セッション管理モジュールが見つかりません")
            return
        except ValueError as e:
            print(f"エラー: {e}")
            return

    # CUDA環境チェックモード
    if args.check_cuda:
        cuda_info = check_cuda_availability()
        print("=== CUDA 環境チェック ===")
        print(f"CUDA利用可能: {'はい' if cuda_info['cuda_available'] else 'いいえ'}")
        if cuda_info['device_name']:
            print(f"GPUデバイス: {cuda_info['device_name']}")
        print(f"利用可能プロバイダー: {', '.join(cuda_info['providers'])}")
        return

    # 生成モードの場合は --prompt, --sticker-set, --eco, --eco24, --package, --fix-transparency, --split-grids, --regenerate-grid のいずれかが必須
    if not args.prompt and not args.sticker_set and not args.eco and not args.eco24 and not args.package and not args.fix_transparency and not args.split_grids and not args.regenerate_grid:
        parser.error("--prompt, --sticker-set, --eco, --eco24, --package, --fix-transparency, --split-grids, --regenerate-grid のいずれかを指定してください")

    # クライアント作成
    client = create_client(args.project)

    # グリッド再生成モード（_prompts.json を使用）
    if args.regenerate_grid:
        target_dir = Path(args.regenerate_grid)
        if not target_dir.exists():
            print(f"Error: ディレクトリが見つかりません: {args.regenerate_grid}", file=sys.stderr)
            sys.exit(1)
        regenerate_grid_from_prompts(
            client,
            str(target_dir),
            grid_num=args.grid_num,
            full_body=not args.no_full_body
        )
        return

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
        # MVP品質プロファイル適用
        mvp = apply_mvp_quality(args)
        detect_items_flag = not getattr(args, 'no_items', False)
        modifiers = {
            "text_mode": args.text_mode,
            "outline": args.outline,
        }
        # REACTIONSの優先順位: セッション > ファイル > DB駆動 > AI生成(--ai-reactions明示時のみ) > グローバルREACTIONS
        reactions = session.get_reactions() if session else None
        if not reactions and getattr(args, 'reactions_file', None):
            reactions = load_reactions_from_file(args.reactions_file)
        if not reactions and (args.persona_age or args.persona_target):
            reactions = get_reactions_from_db(
                age=args.persona_age or "20s",
                target=args.persona_target or "Friend",
                theme=args.persona_theme,
                intensity=args.persona_intensity or 2,
            )
        if not reactions and getattr(args, 'ai_reactions', False) and (args.persona_age or args.persona_context):
            reactions = generate_reactions_with_ai(
                client,
                persona_age=args.persona_age or "20s",
                persona_target=args.persona_target or "Friend",
                persona_theme=args.persona_theme or "共感強化",
                persona_intensity=args.persona_intensity or 2,
                context=args.persona_context or "",
            )
        generate_24_stickers(client, args.eco24, output_dir, remove_bg=False,
                             chibi_style=args.style, detect_items=detect_items_flag,
                             modifiers=modifiers, reactions=reactions)
        return

    # 申請パッケージ生成モード
    if args.package:
        if not os.path.exists(args.package):
            print(f"Error: 画像が見つかりません: {args.package}", file=sys.stderr)
            sys.exit(1)

        output_dir = args.output or f"./output/linestamp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # MVP品質プロファイル適用
        mvp = apply_mvp_quality(args)
        detect_items_flag = not getattr(args, 'no_items', False)
        modifiers = {
            "text_mode": args.text_mode,
            "outline": args.outline,
        }
        # REACTIONSの優先順位: セッション > ファイル > DB駆動 > AI生成(--ai-reactions明示時のみ) > グローバルREACTIONS
        reactions = session.get_reactions() if session else None
        if not reactions and getattr(args, 'reactions_file', None):
            reactions = load_reactions_from_file(args.reactions_file)
        if not reactions and (args.persona_age or args.persona_target):
            reactions = get_reactions_from_db(
                age=args.persona_age or "20s",
                target=args.persona_target or "Friend",
                theme=args.persona_theme,
                intensity=args.persona_intensity or 2,
            )
        if not reactions and getattr(args, 'ai_reactions', False) and (args.persona_age or args.persona_context):
            reactions = generate_reactions_with_ai(
                client,
                persona_age=args.persona_age or "20s",
                persona_target=args.persona_target or "Friend",
                persona_theme=args.persona_theme or "共感強化",
                persona_intensity=args.persona_intensity or 2,
                context=args.persona_context or "",
            )
        generate_submission_package(client, args.package, output_dir,
                                    chibi_style=args.style, detect_items=detect_items_flag,
                                    modifiers=modifiers, reactions=reactions)
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
