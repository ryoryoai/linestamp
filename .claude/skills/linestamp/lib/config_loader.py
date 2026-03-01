#!/usr/bin/env python3
"""
config.json 読み込みユーティリティ

全スキルが共有する設定ファイル (.claude/skills/linestamp/config.json) を読み込み、
スタイル・モディファイア・MVP品質プロファイル等へのアクセスを提供する。

Usage:
    from config_loader import load_config, get_style, resolve_style_id, build_modifier_prompt
"""

import json
from pathlib import Path
from typing import Optional


# デフォルトの config.json パス
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# モジュールレベルキャッシュ
_config_cache: dict = {}


def load_config(config_path: str = None) -> dict:
    """config.json を読み込み（キャッシュ付き）

    Args:
        config_path: config.json のパス。省略時はデフォルトパスを使用。

    Returns:
        設定辞書
    """
    global _config_cache

    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    path_key = str(path.resolve())

    if path_key not in _config_cache:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            _config_cache[path_key] = json.load(f)

    return _config_cache[path_key]


def clear_cache():
    """設定キャッシュをクリア"""
    global _config_cache
    _config_cache = {}


# ============================================================
# スタイル関連
# ============================================================

def resolve_style_id(style_id: str, config: dict = None) -> str:
    """スタイルIDを解決（エイリアス対応）

    Args:
        style_id: スタイルID（エイリアス含む）
        config: 設定辞書。省略時は自動読み込み。

    Returns:
        解決済みスタイルID
    """
    if config is None:
        config = load_config()

    aliases = config.get("styleAliases", {})
    if style_id in aliases:
        resolved = aliases[style_id]
        print(f"スタイル '{style_id}' → '{resolved}' にエイリアス解決")
        return resolved
    return style_id


def get_style(style_id: str, config: dict = None) -> dict:
    """スタイル情報を取得（エイリアス対応、フォールバック付き）

    Args:
        style_id: スタイルID
        config: 設定辞書

    Returns:
        スタイル情報辞書 (name, description, category, prompt)
    """
    if config is None:
        config = load_config()

    resolved_id = resolve_style_id(style_id, config)
    styles = config.get("styles", {})

    if resolved_id in styles:
        return styles[resolved_id]

    # フォールバック: sd_25
    default_style = config.get("defaults", {}).get("style", "sd_25")
    print(f"警告: スタイル '{style_id}' が見つかりません。{default_style}を使用します。")
    return styles.get(default_style, styles.get("sd_25", {}))


def list_styles(category: str = None, config: dict = None) -> list:
    """スタイル一覧を取得（カテゴリでフィルタ可能）

    Args:
        category: "core" or "advanced"。省略時は全て。
        config: 設定辞書

    Returns:
        スタイル情報のリスト
    """
    if config is None:
        config = load_config()

    styles = []
    for style_id, info in config.get("styles", {}).items():
        if category is None or info.get("category") == category:
            styles.append({
                "id": style_id,
                "name": info["name"],
                "description": info["description"],
                "category": info.get("category", "core"),
            })
    return styles


# ============================================================
# モディファイア関連
# ============================================================

def get_defaults(config: dict = None) -> dict:
    """デフォルトモディファイア設定を取得"""
    if config is None:
        config = load_config()
    return config.get("defaults", {
        "style": "sd_25",
        "textMode": "deka",
        "outline": "bold",
        "politeness": "casual",
    })


def get_modifier_info(modifier_type: str, value: str, config: dict = None) -> Optional[dict]:
    """モディファイア情報を取得

    Args:
        modifier_type: "textMode", "outline", "politeness"
        value: モディファイア値
        config: 設定辞書

    Returns:
        モディファイア情報辞書 or None
    """
    if config is None:
        config = load_config()

    modifiers = config.get("modifiers", {})
    if modifier_type in modifiers and value in modifiers[modifier_type]:
        return modifiers[modifier_type][value]
    return None


def build_modifier_prompt(modifiers: dict = None, config: dict = None) -> str:
    """モディファイア設定からプロンプト文字列を構築

    Args:
        modifiers: {"textMode": "deka", "outline": "bold"} 形式。省略時はデフォルト。
        config: 設定辞書

    Returns:
        結合されたプロンプト文字列
    """
    if config is None:
        config = load_config()

    defaults = get_defaults(config)
    if modifiers is None:
        modifiers = defaults.copy()

    all_modifiers = config.get("modifiers", {})
    prompt_parts = []

    # テキストモード
    text_mode = modifiers.get("textMode", modifiers.get("text_mode", defaults.get("textMode", "deka")))
    text_modes = all_modifiers.get("textMode", {})
    if text_mode in text_modes:
        prompt_parts.append(text_modes[text_mode]["prompt"])

    # アウトライン
    outline = modifiers.get("outline", defaults.get("outline", "bold"))
    outlines = all_modifiers.get("outline", {})
    if outline in outlines:
        prompt_parts.append(outlines[outline]["prompt"])

    return "\n\n".join(prompt_parts)


# ============================================================
# MVP品質プロファイル
# ============================================================

def get_mvp_quality(config: dict = None) -> dict:
    """MVP品質プロファイルを取得"""
    if config is None:
        config = load_config()
    return config.get("mvpQuality", {})


def apply_mvp_quality(args, config: dict = None) -> dict:
    """MVP品質プロファイルを適用し、上書きがあれば警告する

    Args:
        args: argparse.Namespace オブジェクト
        config: 設定辞書

    Returns:
        適用された設定のdict
    """
    if config is None:
        config = load_config()

    mvp = get_mvp_quality(config)
    if not mvp.get("enabled", True):
        return {}

    locked = mvp.get("locked", {})
    overrides = []

    # スタイル固定
    resolved_style = resolve_style_id(
        getattr(args, "style", None) or locked.get("style", "sd_25"),
        config
    )
    if resolved_style != locked.get("style", "sd_25"):
        overrides.append(f"style: {resolved_style} → {locked['style']}")
    args.style = locked.get("style", "sd_25")

    # テキストモード固定
    current_text_mode = getattr(args, "text_mode", locked.get("textMode", "deka"))
    if current_text_mode != locked.get("textMode", "deka"):
        overrides.append(f"text_mode: {current_text_mode} → {locked['textMode']}")
    args.text_mode = locked.get("textMode", "deka")

    # アウトライン固定
    current_outline = getattr(args, "outline", locked.get("outline", "bold"))
    if current_outline != locked.get("outline", "bold"):
        overrides.append(f"outline: {current_outline} → {locked['outline']}")
    args.outline = locked.get("outline", "bold")

    # 背景透過は常にON
    if getattr(args, "no_remove_bg", False):
        overrides.append("no_remove_bg: True → False (透過は必須)")
    args.no_remove_bg = False

    # アイテム検出は常にON
    if getattr(args, "no_items", False):
        overrides.append("no_items: True → False (アイテム検出は必須)")
    args.no_items = False

    if overrides:
        print("[MVP品質] 以下の設定をMVPプロファイルで上書きしました:")
        for o in overrides:
            print(f"  - {o}")

    applied = {
        "style": args.style,
        "text_mode": args.text_mode,
        "outline": args.outline,
        "remove_bg": True,
        "detect_items": True,
        "stamps": locked.get("stamps", 24),
    }
    print(f"[MVP品質] style={applied['style']}, text={applied['text_mode']}, "
          f"outline={applied['outline']}, 透過=ON, アイテム検出=ON")
    return applied


# ============================================================
# LINE仕様
# ============================================================

def get_line_spec(config: dict = None) -> dict:
    """LINE仕様サイズ情報を取得

    Returns:
        {"stamp": (370, 320), "main": (240, 240), "tab": (96, 74)}
    """
    if config is None:
        config = load_config()

    spec = config.get("lineSpec", {})
    return {
        "stamp": (spec.get("stamp", {}).get("width", 370), spec.get("stamp", {}).get("height", 320)),
        "main": (spec.get("main", {}).get("width", 240), spec.get("main", {}).get("height", 240)),
        "tab": (spec.get("tab", {}).get("width", 96), spec.get("tab", {}).get("height", 74)),
    }


# ============================================================
# ペルソナ設定
# ============================================================

def get_persona_options(config: dict = None) -> dict:
    """ペルソナ設定オプションを取得"""
    if config is None:
        config = load_config()
    return config.get("persona", {})


def load_session_config(work_dir) -> dict:
    """work/session-config.json を読み込む"""
    path = Path(work_dir) / "session-config.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def get_session_id(work_dir) -> Optional[str]:
    """session-config.json からセッションIDを取得"""
    config = load_session_config(work_dir)
    return config.get("session_id")


def resolve_effective_style(cli_style, session_config=None, fallback="sd_25") -> str:
    """スタイル解決: CLI > session-config > fallback"""
    if cli_style is not None:
        return cli_style
    if session_config and session_config.get("style"):
        return session_config["style"]
    return fallback


def get_default_reactions(config: dict = None) -> list:
    """[非推奨] DB版 select_fallback_reactions() に移行済み"""
    import warnings
    warnings.warn(
        "get_default_reactions() is deprecated. Use database.select_fallback_reactions().",
        DeprecationWarning, stacklevel=2
    )
    try:
        from database import select_fallback_reactions, ensure_database
        ensure_database()
        return [
            {"id": r["id"], "emotion": r.get("emotion", ""),
             "text": r.get("text", ""), "pose_locked": True,
             "pose": r.get("prompt_full") or r.get("gesture", "")}
            for r in select_fallback_reactions(limit=24)
        ]
    except Exception:
        return []
