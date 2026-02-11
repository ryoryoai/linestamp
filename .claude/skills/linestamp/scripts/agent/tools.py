"""
LINEスタンプ生成 - カスタムツール定義

ツール契約に基づき、既存CLIをラップするツールを定義。
v1: Bash経由でCLI呼び出し
v2: カスタムツール化（将来）
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# スキルディレクトリのパス
# __file__ = .../linestamp/.claude/skills/linestamp/scripts/agent/tools.py
SKILL_DIR = Path(__file__).parent.parent.parent  # .../linestamp/.claude/skills/linestamp
SCRIPTS_DIR = SKILL_DIR / "scripts"  # .../linestamp/.claude/skills/linestamp/scripts
PROJECT_ROOT = SKILL_DIR.parent.parent.parent  # .../linestamp


def run_command(cmd: List[str], cwd: Path = None) -> Dict[str, Any]:
    """コマンドを実行して結果を返す"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=300  # 5分タイムアウト
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": {
                "code": "TIMEOUT",
                "message": "コマンドがタイムアウトしました（5分）",
                "recoverable": True
            }
        }
    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "EXEC_ERROR",
                "message": str(e),
                "recoverable": False
            }
        }


# =============================================================================
# ツール1: linestamp_generate_package
# =============================================================================

def linestamp_generate_package(
    image_path: str,
    style: str = "sd_25",
    text_mode: str = "deka",
    outline: str = "bold",
    persona_age: Optional[str] = None,
    persona_target: Optional[str] = None,
    persona_theme: Optional[str] = None,
    persona_intensity: int = 2,
    items_mode: str = "auto",
    output_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    申請パッケージを生成する。

    Args:
        image_path: 参照画像のパス（必須）
        style: スタイルID（既定: sd_25）
        text_mode: テキストモード（既定: deka）
        outline: アウトライン（既定: bold）
        persona_age: 年代（任意）
        persona_target: 相手（任意）
        persona_theme: テーマ（任意）
        persona_intensity: 強度（既定: 2）
        items_mode: アイテム検出（auto/off、既定: auto）
        output_dir: 出力ディレクトリ（任意）

    Returns:
        session_id, output_dir, files, validation
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "generate_stamp.py"),
        "--package", image_path,
        "--style", style,
        "--text-mode", text_mode,
        "--outline", outline
    ]

    # ペルソナ（DB駆動REACTIONS選択）
    if persona_age or persona_target or persona_theme:
        if persona_age:
            cmd.extend(["--persona-age", persona_age])
        if persona_target:
            cmd.extend(["--persona-target", persona_target])
        if persona_theme:
            cmd.extend(["--persona-theme", persona_theme])
        cmd.extend(["--persona-intensity", str(persona_intensity)])

    if items_mode == "off":
        cmd.append("--no-items")

    if output_dir:
        cmd.extend(["--output", output_dir])

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", {
                "code": "GENERATE_FAILED",
                "message": result.get("stderr", "生成に失敗しました"),
                "recoverable": True
            })
        }

    # TODO: 出力からsession_id等をパース
    # 現状はstdoutをそのまま返す
    return {
        "success": True,
        "stdout": result["stdout"],
        "message": "パッケージ生成が完了しました"
    }


# =============================================================================
# ツール2: linestamp_regenerate_session
# =============================================================================

def linestamp_regenerate_session(
    session_id: str,
    overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    既存セッションから再生成する。

    Args:
        session_id: セッションID（必須）
        overrides: 上書き設定（任意）

    Returns:
        session_id, output_dir, files, validation
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "generate_stamp.py"),
        "--session", session_id
    ]

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": {
                "code": "REGENERATE_FAILED",
                "message": result.get("stderr", "再生成に失敗しました"),
                "recoverable": True
            }
        }

    return {
        "success": True,
        "stdout": result["stdout"],
        "message": f"セッション {session_id} から再生成が完了しました"
    }


# =============================================================================
# ツール3: linestamp_list_sessions
# =============================================================================

def linestamp_list_sessions(limit: int = 20) -> Dict[str, Any]:
    """
    セッション一覧を取得する。

    Args:
        limit: 取得件数（既定: 20）

    Returns:
        sessions: セッション一覧
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "generate_stamp.py"),
        "--list"
    ]

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": {
                "code": "LIST_FAILED",
                "message": result.get("stderr", "一覧取得に失敗しました"),
                "recoverable": True
            }
        }

    return {
        "success": True,
        "stdout": result["stdout"]
    }


# =============================================================================
# ツール4: linestamp_pose_search
# =============================================================================

def linestamp_pose_search(
    keyword: str,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    ポーズ辞書を検索する。

    Args:
        keyword: 検索キーワード（必須）
        category: カテゴリ（任意）

    Returns:
        poses: ポーズ一覧
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "pose_manager.py"),
        "search", keyword
    ]

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": {
                "code": "SEARCH_FAILED",
                "message": result.get("stderr", "検索に失敗しました"),
                "recoverable": True
            }
        }

    return {
        "success": True,
        "stdout": result["stdout"]
    }


# =============================================================================
# ツール5: linestamp_qc_pose_stats
# =============================================================================

def linestamp_qc_pose_stats(min_uses: int = 3) -> Dict[str, Any]:
    """
    ポーズの成功率統計を取得する。

    Args:
        min_uses: 最小使用回数（既定: 3）

    Returns:
        stats: 統計情報
    """
    # SQLiteを直接クエリ
    import sqlite3
    db_path = PROJECT_ROOT / "linestamp.db"

    if not db_path.exists():
        return {
            "success": False,
            "error": {
                "code": "DB_NOT_FOUND",
                "message": "データベースが見つかりません",
                "recoverable": False
            }
        }

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                name as pose_name,
                (success_count * 1.0 / NULLIF(success_count + failure_count, 0)) as success_rate,
                (success_count + failure_count) as uses,
                last_used
            FROM pose_dictionary
            WHERE (success_count + failure_count) >= ?
            ORDER BY success_rate DESC
        """, (min_uses,))

        rows = cursor.fetchall()
        conn.close()

        stats = [dict(row) for row in rows]

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "DB_ERROR",
                "message": str(e),
                "recoverable": False
            }
        }


# =============================================================================
# ツール6: linestamp_validate_output
# =============================================================================

def linestamp_validate_output(
    output_dir: str,
    mode: str = "package"
) -> Dict[str, Any]:
    """
    出力を検証する。

    Args:
        output_dir: 出力ディレクトリ（必須）
        mode: package / eco24（既定: package）

    Returns:
        ok: 検証結果
        issues: 問題一覧
    """
    output_path = Path(output_dir)

    if not output_path.exists():
        return {
            "success": False,
            "error": {
                "code": "DIR_NOT_FOUND",
                "message": f"ディレクトリが見つかりません: {output_dir}",
                "recoverable": False
            }
        }

    issues = []

    # スタンプ画像のチェック
    stamp_files = list(output_path.glob("stamp_*.png"))
    if len(stamp_files) < 8:
        issues.append(f"スタンプ画像が少なすぎます: {len(stamp_files)}枚")

    if mode == "package":
        # main.png のチェック
        main_path = output_path / "main.png"
        if not main_path.exists():
            issues.append("main.png が見つかりません")

        # tab.png のチェック
        tab_path = output_path / "tab.png"
        if not tab_path.exists():
            issues.append("tab.png が見つかりません")

        # ZIP のチェック
        zip_files = list(output_path.glob("*.zip"))
        if not zip_files:
            issues.append("ZIPファイルが見つかりません")

    return {
        "success": True,
        "ok": len(issues) == 0,
        "issues": issues,
        "stamp_count": len(stamp_files)
    }


# =============================================================================
# ツール一覧（Agent SDK 用）
# =============================================================================

# =============================================================================
# ツール7: linestamp_trend_collect
# =============================================================================

def linestamp_trend_collect(
    max_items: int = 100,
    meta_limit: int = 50,
    min_interval_sec: float = 1.0
) -> Dict[str, Any]:
    """
    LINE STOREからトレンドデータを収集する。

    Args:
        max_items: ランキング取得件数（既定: 100）
        meta_limit: メタデータ取得件数（既定: 50）
        min_interval_sec: リクエスト間隔（既定: 1.0）

    Returns:
        snapshots: 作成されたスナップショット数
        products: 発見された商品数
        meta_collected: メタデータ収集数
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "trend_collector.py"),
        "collect",
        "--max-items", str(max_items),
        "--meta-limit", str(meta_limit),
        "--min-interval-sec", str(min_interval_sec)
    ]

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", {
                "code": "COLLECT_FAILED",
                "message": result.get("stderr", "収集に失敗しました"),
                "recoverable": True
            })
        }

    return {
        "success": True,
        "stdout": result["stdout"],
        "message": "トレンドデータの収集が完了しました"
    }


# =============================================================================
# ツール8: linestamp_trend_analyze
# =============================================================================

def linestamp_trend_analyze(
    product_ids: Optional[List[int]] = None,
    limit: int = 10,
    min_interval_sec: float = 1.0
) -> Dict[str, Any]:
    """
    商品の特徴を分析する。

    Args:
        product_ids: 分析対象の商品IDリスト（任意）
        limit: 自動選択時の件数（既定: 10）
        min_interval_sec: リクエスト間隔（既定: 1.0）

    Returns:
        analyzed: 分析した商品数
        stickers: 分析したスタンプ数
    """
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "trend_collector.py"),
        "analyze",
        "--min-interval-sec", str(min_interval_sec)
    ]

    if product_ids:
        cmd.extend(["--product-ids", ",".join(str(pid) for pid in product_ids)])
    else:
        cmd.extend(["--limit", str(limit)])

    result = run_command(cmd)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", {
                "code": "ANALYZE_FAILED",
                "message": result.get("stderr", "分析に失敗しました"),
                "recoverable": True
            })
        }

    return {
        "success": True,
        "stdout": result["stdout"],
        "message": "特徴分析が完了しました"
    }


# =============================================================================
# ツール9: linestamp_trend_stats
# =============================================================================

def linestamp_trend_stats() -> Dict[str, Any]:
    """
    トレンドデータの統計を取得する。

    Returns:
        stats: 統計情報
    """
    import sqlite3
    db_path = PROJECT_ROOT / "linestamp.db"

    if not db_path.exists():
        return {
            "success": False,
            "error": {
                "code": "DB_NOT_FOUND",
                "message": "データベースが見つかりません",
                "recoverable": False
            }
        }

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        stats = {}

        queries = {
            "snapshots": "SELECT COUNT(*) FROM ranking_snapshots",
            "products": "SELECT COUNT(*) FROM products_meta",
            "products_with_meta": "SELECT COUNT(*) FROM products_meta WHERE title IS NOT NULL",
            "products_with_features": "SELECT COUNT(*) FROM product_features",
            "stickers_analyzed": "SELECT COUNT(*) FROM sticker_features",
            "stickers_with_embeddings": "SELECT COUNT(*) FROM sticker_embeddings",
            "knowledge_entries": "SELECT COUNT(*) FROM knowledge_base",
        }

        for key, query in queries.items():
            try:
                cursor.execute(query)
                stats[key] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats[key] = 0

        conn.close()

        return {
            "success": True,
            "stats": stats
        }

    except Exception as e:
        return {
            "success": False,
            "error": {
                "code": "DB_ERROR",
                "message": str(e),
                "recoverable": False
            }
        }


LINESTAMP_TOOLS = {
    "linestamp_generate_package": {
        "function": linestamp_generate_package,
        "description": "申請パッケージ（24枚+main+tab+ZIP）を生成する",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "参照画像のパス"},
                "style": {"type": "string", "default": "sd_25", "description": "スタイルID"},
                "text_mode": {"type": "string", "default": "deka", "description": "テキストモード"},
                "outline": {"type": "string", "default": "bold", "description": "アウトライン"},
                "persona_age": {"type": "string", "description": "年代"},
                "persona_target": {"type": "string", "description": "相手"},
                "persona_theme": {"type": "string", "description": "テーマ"},
                "persona_intensity": {"type": "integer", "default": 2, "description": "強度"},
                "items_mode": {"type": "string", "default": "auto", "description": "アイテム検出"},
                "output_dir": {"type": "string", "description": "出力ディレクトリ"}
            },
            "required": ["image_path"]
        }
    },
    "linestamp_regenerate_session": {
        "function": linestamp_regenerate_session,
        "description": "既存セッションから再生成する",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "セッションID"},
                "overrides": {"type": "object", "description": "上書き設定"}
            },
            "required": ["session_id"]
        }
    },
    "linestamp_list_sessions": {
        "function": linestamp_list_sessions,
        "description": "セッション一覧を取得する",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 20, "description": "取得件数"}
            }
        }
    },
    "linestamp_pose_search": {
        "function": linestamp_pose_search,
        "description": "ポーズ辞書を検索する",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "検索キーワード"},
                "category": {"type": "string", "description": "カテゴリ"}
            },
            "required": ["keyword"]
        }
    },
    "linestamp_qc_pose_stats": {
        "function": linestamp_qc_pose_stats,
        "description": "ポーズの成功率統計を取得する",
        "parameters": {
            "type": "object",
            "properties": {
                "min_uses": {"type": "integer", "default": 3, "description": "最小使用回数"}
            }
        }
    },
    "linestamp_validate_output": {
        "function": linestamp_validate_output,
        "description": "出力を検証する",
        "parameters": {
            "type": "object",
            "properties": {
                "output_dir": {"type": "string", "description": "出力ディレクトリ"},
                "mode": {"type": "string", "default": "package", "description": "package / eco24"}
            },
            "required": ["output_dir"]
        }
    },
    "linestamp_trend_collect": {
        "function": linestamp_trend_collect,
        "description": "LINE STOREからトレンドデータ（ランキング＋メタデータ）を収集する",
        "parameters": {
            "type": "object",
            "properties": {
                "max_items": {"type": "integer", "default": 100, "description": "ランキング取得件数"},
                "meta_limit": {"type": "integer", "default": 50, "description": "メタデータ取得件数"},
                "min_interval_sec": {"type": "number", "default": 1.0, "description": "リクエスト間隔（秒）"}
            }
        }
    },
    "linestamp_trend_analyze": {
        "function": linestamp_trend_analyze,
        "description": "商品の特徴を分析する",
        "parameters": {
            "type": "object",
            "properties": {
                "product_ids": {"type": "array", "items": {"type": "integer"}, "description": "分析対象の商品IDリスト"},
                "limit": {"type": "integer", "default": 10, "description": "自動選択時の件数"},
                "min_interval_sec": {"type": "number", "default": 1.0, "description": "リクエスト間隔（秒）"}
            }
        }
    },
    "linestamp_trend_stats": {
        "function": linestamp_trend_stats,
        "description": "トレンドデータの統計を取得する",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}
