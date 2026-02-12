"""
LINEスタンプ生成スキル - データベース管理モジュール

SQLiteを使用したセッション管理・品質管理・テンプレート管理
"""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# データベースファイルのデフォルトパス
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent.parent.parent / "linestamp.db"


def get_db_path() -> Path:
    """データベースファイルのパスを取得"""
    return Path(os.environ.get("LINESTAMP_DB_PATH", DEFAULT_DB_PATH))


def ensure_database():
    """DBファイルが無ければ自動で初期化＋シード投入"""
    db_path = get_db_path()
    if db_path.exists():
        return
    print(f"[DB] データベースが見つかりません。初期化します: {db_path}")
    init_database()
    try:
        from seed_master_data import seed_all
        seed_all()
    except ImportError:
        print("[DB] seed_master_data.py が見つかりません。テーブルのみ作成しました。")


def get_connection() -> sqlite3.Connection:
    """データベース接続を取得"""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能に
    return conn


def init_database():
    """データベースを初期化（テーブル作成）"""
    conn = get_connection()
    cursor = conn.cursor()

    # セッション管理テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT,
            style TEXT,
            text_mode TEXT DEFAULT 'deka',
            outline TEXT DEFAULT 'bold',
            persona_age TEXT,
            persona_target TEXT,
            persona_theme TEXT,
            persona_intensity INTEGER DEFAULT 2,
            status TEXT DEFAULT 'draft',
            output_dir TEXT,
            notes TEXT
        )
    """)

    # REACTIONSデータテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reactions (
            session_id TEXT,
            idx INTEGER,
            reaction_id TEXT,
            emotion TEXT,
            pose TEXT,
            text TEXT,
            pose_locked BOOLEAN DEFAULT 0,
            outfit TEXT,
            item TEXT,
            PRIMARY KEY (session_id, idx),
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # ポーズ辞書テーブル（ジェスチャー＋表情）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pose_dictionary (
            name TEXT PRIMARY KEY,
            name_en TEXT,
            gesture_ja TEXT,
            gesture_en TEXT,
            expression_ja TEXT,
            expression_en TEXT,
            vibe TEXT,
            prompt_ja TEXT NOT NULL,
            prompt_en TEXT,
            category TEXT,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            last_used DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT
        )
    """)

    # 既存テーブルにカラム追加（マイグレーション）
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN gesture_ja TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN gesture_en TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN expression_ja TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN expression_en TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN vibe TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN yaml_path TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN hints TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN avoid TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pose_dictionary ADD COLUMN updated_at DATETIME")
    except sqlite3.OperationalError:
        pass

    # プロンプト結果テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            prompt_type TEXT,
            prompt_hash TEXT,
            prompt_text TEXT,
            success BOOLEAN,
            retry_count INTEGER DEFAULT 0,
            failure_reason TEXT,
            execution_time_ms INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # REACTIONSテンプレートテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reaction_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            persona_age TEXT,
            persona_target TEXT,
            persona_theme TEXT,
            reactions_json TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            total_rating INTEGER DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 生成出力履歴テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS outputs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            grid_num INTEGER,
            output_path TEXT,
            success BOOLEAN,
            aspect_ratio REAL,
            validation_result TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # ==================== トレンド収集テーブル ====================

    # ランキングスナップショット
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ranking_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_type TEXT NOT NULL,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            list_hash TEXT NOT NULL,
            total_items INTEGER NOT NULL,
            UNIQUE (list_type, list_hash)
        )
    """)

    # ランキング順位
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ranking_entries (
            snapshot_id INTEGER,
            rank_position INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            PRIMARY KEY (snapshot_id, rank_position),
            FOREIGN KEY (snapshot_id) REFERENCES ranking_snapshots(id)
        )
    """)

    # 商品メタデータ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products_meta (
            product_id INTEGER PRIMARY KEY,
            store_url TEXT NOT NULL,
            title TEXT,
            creator_id INTEGER,
            creator_name TEXT,
            description TEXT,
            price_amount INTEGER,
            price_currency TEXT DEFAULT 'JPY',
            sticker_type TEXT,
            sticker_count INTEGER,
            first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # スタンプ特徴
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sticker_features (
            sticker_id TEXT PRIMARY KEY,
            product_id INTEGER NOT NULL,
            image_path TEXT,
            features_json TEXT NOT NULL,
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 商品特徴集約
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product_features (
            product_id INTEGER PRIMARY KEY,
            pack_features TEXT NOT NULL,
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # CLIP埋め込み
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sticker_embeddings (
            sticker_id INTEGER PRIMARY KEY,
            model_name TEXT NOT NULL,
            embedding TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ナレッジベース
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            description TEXT,
            source_url TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (category, key)
        )
    """)

    # ==================== v2.0 マスタテーブル ====================

    # ポーズマスタ（pose_dictionaryの拡張版）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pose_master (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            name_en TEXT,
            gesture TEXT NOT NULL,
            gesture_en TEXT,
            expression TEXT,
            expression_en TEXT,
            vibe TEXT,
            prompt_full TEXT,
            category TEXT,
            tags TEXT,
            difficulty INTEGER DEFAULT 2,
            body_parts TEXT,
            requires_full_body BOOLEAN DEFAULT 0,
            similar_poses TEXT,
            incompatible_with TEXT,
            hints TEXT,
            avoid TEXT,
            success_count INTEGER DEFAULT 0,
            failure_count INTEGER DEFAULT 0,
            avg_quality_score REAL,
            last_used DATETIME,
            source TEXT DEFAULT 'builtin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
    """)

    # セリフマスタ
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS text_master (
            id TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            text_variants TEXT,
            reading TEXT,
            meaning TEXT,
            meaning_en TEXT,
            category TEXT,
            usage TEXT,
            formality INTEGER DEFAULT 2,
            persona_age TEXT,
            persona_target TEXT,
            persona_theme TEXT,
            text_size TEXT DEFAULT 'normal',
            decoration TEXT,
            seasonal TEXT,
            usage_count INTEGER DEFAULT 0,
            source TEXT DEFAULT 'builtin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # リアクションマスタ（ポーズ×セリフの組み合わせ）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reactions_master (
            id TEXT PRIMARY KEY,
            text_id TEXT NOT NULL,
            pose_id TEXT NOT NULL,
            emotion TEXT,
            emotion_en TEXT,
            persona_age TEXT,
            persona_target TEXT,
            persona_theme TEXT,
            intensity_range TEXT,
            slot_type TEXT,
            priority INTEGER DEFAULT 50,
            is_essential BOOLEAN DEFAULT 0,
            outfit TEXT,
            item_hint TEXT,
            enhance_expression BOOLEAN DEFAULT 1,
            incompatible_reactions TEXT,
            usage_count INTEGER DEFAULT 0,
            success_rate REAL,
            avg_rating REAL,
            source TEXT DEFAULT 'builtin',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            FOREIGN KEY (text_id) REFERENCES text_master(id),
            FOREIGN KEY (pose_id) REFERENCES pose_master(id)
        )
    """)

    # ペルソナ設定
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS persona_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            age TEXT NOT NULL,
            target TEXT NOT NULL,
            theme TEXT,
            intensity INTEGER DEFAULT 2,
            core_slots INTEGER DEFAULT 12,
            theme_slots INTEGER DEFAULT 8,
            reaction_slots INTEGER DEFAULT 4,
            recommended_formality INTEGER,
            recommended_text_size TEXT,
            recommended_style TEXT,
            essential_reactions TEXT,
            excluded_reactions TEXT,
            description TEXT,
            example_texts TEXT,
            UNIQUE(age, target, theme, intensity)
        )
    """)

    # 生成ログ（学習用）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            slot_index INTEGER,
            reaction_id TEXT,
            pose_id TEXT,
            text_id TEXT,
            prompt_text TEXT,
            success BOOLEAN,
            retry_count INTEGER DEFAULT 0,
            failure_reason TEXT,
            execution_time_ms INTEGER,
            transparency_ok BOOLEAN,
            size_ok BOOLEAN,
            aspect_ok BOOLEAN,
            quality_score REAL,
            user_rating INTEGER,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id),
            FOREIGN KEY (reaction_id) REFERENCES reactions_master(id),
            FOREIGN KEY (pose_id) REFERENCES pose_master(id),
            FOREIGN KEY (text_id) REFERENCES text_master(id)
        )
    """)

    # インデックス作成
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reactions_session ON reactions(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pose_name ON pose_dictionary(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_type ON prompt_results(prompt_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_templates_persona ON reaction_templates(persona_age, persona_target, persona_theme)")

    # トレンド用インデックス
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranking_entries_product ON ranking_entries(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ranking_snapshots_type ON ranking_snapshots(list_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_meta_creator ON products_meta(creator_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sticker_features_product ON sticker_features(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_base(category)")

    # v2.0 マスタ用インデックス
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pose_master_category ON pose_master(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_master_category ON text_master(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_text_master_formality ON text_master(formality)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reactions_master_pose ON reactions_master(pose_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reactions_master_text ON reactions_master(text_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reactions_master_slot ON reactions_master(slot_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_persona_config_key ON persona_config(age, target, theme)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generation_logs_session ON generation_logs(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generation_logs_reaction ON generation_logs(reaction_id)")

    conn.commit()
    conn.close()

    print(f"データベース初期化完了: {get_db_path()}")


# ==================== セッション管理 ====================

def create_session(
    image_path: str,
    style: str = "sd_25",
    text_mode: str = "deka",
    outline: str = "bold",
    persona_age: str = None,
    persona_target: str = None,
    persona_theme: str = None,
    persona_intensity: int = 2
) -> str:
    """新規セッションを作成"""
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions (
            id, image_path, style, text_mode, outline,
            persona_age, persona_target, persona_theme, persona_intensity
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, image_path, style, text_mode, outline,
        persona_age, persona_target, persona_theme, persona_intensity
    ))

    conn.commit()
    conn.close()

    return session_id


def get_session(session_id: str) -> Optional[Dict]:
    """セッション情報を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def update_session(session_id: str, **kwargs):
    """セッション情報を更新"""
    conn = get_connection()
    cursor = conn.cursor()

    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = list(kwargs.values()) + [session_id]

    cursor.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", values)

    conn.commit()
    conn.close()


def list_sessions(status: str = None, limit: int = 20) -> List[Dict]:
    """セッション一覧を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    if status:
        cursor.execute(
            "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_latest_session() -> Optional[Dict]:
    """最新のセッションを取得"""
    sessions = list_sessions(limit=1)
    return sessions[0] if sessions else None


# ==================== REACTIONS管理 ====================

def save_reactions(session_id: str, reactions: List[Dict]):
    """セッションのREACTIONSを保存"""
    conn = get_connection()
    cursor = conn.cursor()

    # 既存のREACTIONSを削除
    cursor.execute("DELETE FROM reactions WHERE session_id = ?", (session_id,))

    # 新しいREACTIONSを挿入
    for idx, r in enumerate(reactions):
        cursor.execute("""
            INSERT INTO reactions (
                session_id, idx, reaction_id, emotion, pose, text,
                pose_locked, outfit, item
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, idx, r.get("id"), r.get("emotion"), r.get("pose"),
            r.get("text"), r.get("pose_locked", False), r.get("outfit"),
            json.dumps(r.get("item")) if r.get("item") else None
        ))

    conn.commit()
    conn.close()


def get_reactions(session_id: str) -> List[Dict]:
    """セッションのREACTIONSを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM reactions WHERE session_id = ? ORDER BY idx",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()

    reactions = []
    for row in rows:
        r = dict(row)
        # itemをJSONからパース
        if r.get("item"):
            r["item"] = json.loads(r["item"])
        # pose_lockedをboolに変換
        r["pose_locked"] = bool(r.get("pose_locked"))
        # 不要なカラムを削除
        r.pop("session_id", None)
        r.pop("idx", None)
        # reaction_id を id に変換
        r["id"] = r.pop("reaction_id", None)
        reactions.append(r)

    return reactions


# ==================== ポーズ辞書 ====================

def register_shigusa(
    name: str,
    gesture_ja: str,
    expression_ja: str,
    vibe: str = None,
    gesture_en: str = None,
    expression_en: str = None,
    name_en: str = None,
    category: str = None,
    notes: str = None
):
    """ポーズを辞書に登録（ジェスチャー＋表情→統合プロンプト自動生成）"""
    # 統合プロンプトを自動生成（句点重複を回避）
    g = gesture_ja.rstrip('。')
    e = expression_ja.rstrip('。')
    prompt_ja = f"{g}。{e}。"
    if vibe:
        prompt_ja += f"（{vibe}）"

    prompt_en = None
    if gesture_en and expression_en:
        g_en = gesture_en.rstrip('.')
        e_en = expression_en.rstrip('.')
        prompt_en = f"{g_en}. {e_en}."

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO pose_dictionary (
            name, name_en, gesture_ja, gesture_en, expression_ja, expression_en,
            vibe, prompt_ja, prompt_en, category, notes,
            success_count, failure_count, last_used, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            COALESCE((SELECT success_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT failure_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT last_used FROM pose_dictionary WHERE name = ?), NULL),
            COALESCE((SELECT created_at FROM pose_dictionary WHERE name = ?), CURRENT_TIMESTAMP)
        )
    """, (name, name_en, gesture_ja, gesture_en, expression_ja, expression_en,
          vibe, prompt_ja, prompt_en, category, notes, name, name, name, name))

    conn.commit()
    conn.close()


def register_pose(
    name: str,
    prompt_ja: str,
    prompt_en: str = None,
    name_en: str = None,
    category: str = None,
    notes: str = None
):
    """ポーズを辞書に登録（後方互換性用）"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO pose_dictionary (
            name, name_en, prompt_ja, prompt_en, category, notes,
            success_count, failure_count, last_used, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            COALESCE((SELECT success_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT failure_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT last_used FROM pose_dictionary WHERE name = ?), NULL),
            COALESCE((SELECT created_at FROM pose_dictionary WHERE name = ?), CURRENT_TIMESTAMP)
        )
    """, (name, name_en, prompt_ja, prompt_en, category, notes, name, name, name, name))

    conn.commit()
    conn.close()


def get_pose(name: str) -> Optional[Dict]:
    """ポーズを辞書から取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM pose_dictionary WHERE name = ?", (name,))
    row = cursor.fetchone()

    conn.close()

    if row:
        return dict(row)
    return None


def search_poses(keyword: str = None, category: str = None) -> List[Dict]:
    """ポーズを検索"""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if keyword:
        conditions.append("(name LIKE ? OR name_en LIKE ? OR prompt_ja LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

    if category:
        conditions.append("category = ?")
        params.append(category)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    cursor.execute(f"""
        SELECT * FROM pose_dictionary
        WHERE {where_clause}
        ORDER BY (success_count * 1.0 / NULLIF(success_count + failure_count, 0)) DESC
    """, params)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_pose_stats(name: str, success: bool):
    """ポーズの成功/失敗統計を更新"""
    conn = get_connection()
    cursor = conn.cursor()

    if success:
        cursor.execute("""
            UPDATE pose_dictionary
            SET success_count = success_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (name,))
    else:
        cursor.execute("""
            UPDATE pose_dictionary
            SET failure_count = failure_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE name = ?
        """, (name,))

    conn.commit()
    conn.close()


# ==================== プロンプト品質管理 ====================

def record_prompt_result(
    session_id: str,
    prompt_type: str,
    prompt_text: str,
    success: bool,
    retry_count: int = 0,
    failure_reason: str = None,
    execution_time_ms: int = None
):
    """プロンプト結果を記録"""
    import hashlib
    prompt_hash = hashlib.md5(prompt_text.encode()).hexdigest()[:16]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO prompt_results (
            session_id, prompt_type, prompt_hash, prompt_text,
            success, retry_count, failure_reason, execution_time_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, prompt_type, prompt_hash, prompt_text,
        success, retry_count, failure_reason, execution_time_ms
    ))

    conn.commit()
    conn.close()


def get_prompt_stats(prompt_type: str = None) -> Dict:
    """プロンプトの統計情報を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    if prompt_type:
        cursor.execute("""
            SELECT
                prompt_type,
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                AVG(retry_count) as avg_retries,
                AVG(execution_time_ms) as avg_time_ms
            FROM prompt_results
            WHERE prompt_type = ?
            GROUP BY prompt_type
        """, (prompt_type,))
    else:
        cursor.execute("""
            SELECT
                prompt_type,
                COUNT(*) as total,
                SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
                AVG(retry_count) as avg_retries,
                AVG(execution_time_ms) as avg_time_ms
            FROM prompt_results
            GROUP BY prompt_type
        """)

    rows = cursor.fetchall()
    conn.close()

    return {row["prompt_type"]: dict(row) for row in rows}


def get_failure_patterns(limit: int = 10) -> List[Dict]:
    """失敗パターンを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            failure_reason,
            COUNT(*) as count,
            prompt_type
        FROM prompt_results
        WHERE success = 0 AND failure_reason IS NOT NULL
        GROUP BY failure_reason, prompt_type
        ORDER BY count DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==================== REACTIONSテンプレート ====================

def save_template(
    name: str,
    reactions: List[Dict],
    persona_age: str = None,
    persona_target: str = None,
    persona_theme: str = None
) -> int:
    """REACTIONSテンプレートを保存"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reaction_templates (
            name, persona_age, persona_target, persona_theme, reactions_json
        ) VALUES (?, ?, ?, ?, ?)
    """, (name, persona_age, persona_target, persona_theme, json.dumps(reactions, ensure_ascii=False)))

    template_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return template_id


def get_template(template_id: int) -> Optional[Dict]:
    """テンプレートを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reaction_templates WHERE id = ?", (template_id,))
    row = cursor.fetchone()

    conn.close()

    if row:
        result = dict(row)
        result["reactions"] = json.loads(result["reactions_json"])
        return result
    return None


def search_templates(
    persona_age: str = None,
    persona_target: str = None,
    persona_theme: str = None
) -> List[Dict]:
    """テンプレートを検索"""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if persona_age:
        conditions.append("persona_age = ?")
        params.append(persona_age)
    if persona_target:
        conditions.append("persona_target = ?")
        params.append(persona_target)
    if persona_theme:
        conditions.append("persona_theme = ?")
        params.append(persona_theme)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    cursor.execute(f"""
        SELECT * FROM reaction_templates
        WHERE {where_clause}
        ORDER BY
            (total_rating * 1.0 / NULLIF(rating_count, 0)) DESC,
            usage_count DESC
    """, params)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        result = dict(row)
        result["reactions"] = json.loads(result["reactions_json"])
        result["avg_rating"] = result["total_rating"] / result["rating_count"] if result["rating_count"] > 0 else 0
        results.append(result)

    return results


def update_template_usage(template_id: int):
    """テンプレート使用回数を更新"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE reaction_templates
        SET usage_count = usage_count + 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (template_id,))

    conn.commit()
    conn.close()


def rate_template(template_id: int, rating: int):
    """テンプレートを評価（1-5）"""
    if rating < 1 or rating > 5:
        raise ValueError("Rating must be between 1 and 5")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE reaction_templates
        SET total_rating = total_rating + ?, rating_count = rating_count + 1, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (rating, template_id))

    conn.commit()
    conn.close()


# ==================== 出力履歴 ====================

def record_output(
    session_id: str,
    grid_num: int,
    output_path: str,
    success: bool,
    aspect_ratio: float = None,
    validation_result: str = None
):
    """出力結果を記録"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO outputs (
            session_id, grid_num, output_path, success, aspect_ratio, validation_result
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (session_id, grid_num, output_path, success, aspect_ratio, validation_result))

    conn.commit()
    conn.close()


# ==================== 初期データ投入 ====================

def seed_pose_dictionary():
    """ポーズ辞書に初期データを投入"""
    initial_poses = [
        {
            "name": "OKサイン",
            "name_en": "OK sign",
            "prompt_ja": "右手で親指と人差し指を使った『ＯＫサイン』のジェスチャー。親指と人差し指で丸をつくり、中指・薬指・小指は軽く曲げる。手のひらはやや正面向き、指先の丸い部分がやや上を向く。手は顔の横（頬高さ）〜肩より少し上に位置。",
            "prompt_en": "OK sign gesture with right hand. Thumb and index finger form a circle, middle/ring/pinky fingers slightly curled. Palm faces slightly forward, the circle pointing slightly upward. Hand positioned near face (cheek height) to slightly above shoulder.",
            "category": "肯定"
        },
        {
            "name": "ピース",
            "name_en": "peace sign",
            "prompt_ja": "人差し指と中指を立ててVサイン。手のひらを正面に向ける。他の指は軽く握る。",
            "prompt_en": "Peace sign with index and middle fingers raised in V shape. Palm facing forward. Other fingers loosely curled.",
            "category": "肯定"
        },
        {
            "name": "サムズアップ",
            "name_en": "thumbs up",
            "prompt_ja": "親指を立てて「いいね」のジェスチャー。他の指は握りしめる。腕は軽く曲げて体の前に。",
            "prompt_en": "Thumbs up gesture. Other fingers closed in fist. Arm slightly bent in front of body.",
            "category": "肯定"
        },
        {
            "name": "ハート",
            "name_en": "heart",
            "prompt_ja": "両手の親指と人差し指でハートマークを作る。指先を合わせてハートの形に。胸の前あたりに配置。",
            "prompt_en": "Heart shape formed with both hands' thumbs and index fingers. Fingertips touching to form heart. Positioned in front of chest.",
            "category": "愛情"
        },
        {
            "name": "バツ",
            "name_en": "X sign",
            "prompt_ja": "両腕を胸の前で交差させてバツマーク。手のひらは外側に向ける。",
            "prompt_en": "Arms crossed in X shape in front of chest. Palms facing outward.",
            "category": "否定"
        },
        {
            "name": "ガッツポーズ",
            "name_en": "fist pump",
            "prompt_ja": "握りこぶしを作り、腕を曲げて力強く引く。肘を曲げ、拳を肩の高さに。やる気満々の表情と一緒に。",
            "prompt_en": "Clenched fist with arm bent, pulling powerfully. Elbow bent, fist at shoulder height. With a determined expression.",
            "category": "応援"
        },
        {
            "name": "万歳",
            "name_en": "banzai",
            "prompt_ja": "両手を高く上げて万歳のポーズ。手のひらは正面または内側に向ける。",
            "prompt_en": "Both arms raised high in banzai pose. Palms facing forward or inward.",
            "category": "喜び"
        },
        {
            "name": "お辞儀",
            "name_en": "bow",
            "prompt_ja": "軽く頭を下げてお辞儀。腰から15-30度くらい前傾。手は体の横または前に揃える。",
            "prompt_en": "Light bow with head lowered. Body tilted forward 15-30 degrees from waist. Hands at sides or together in front.",
            "category": "礼儀"
        },
        {
            "name": "てへぺろ",
            "name_en": "tehepero",
            "prompt_ja": "舌を少し出して片目をつぶり、頭を軽く傾ける。片手で頭を軽く叩くジェスチャー。照れ笑いの表情。",
            "prompt_en": "Tongue slightly out, one eye closed, head tilted. One hand lightly tapping head. Embarrassed smile expression.",
            "category": "照れ"
        },
        {
            "name": "ツッコミ",
            "name_en": "tsukkomi",
            "prompt_ja": "片手を前に出してツッコミのジェスチャー。手のひらは相手に向け、指は揃える。あきれた表情と一緒に。",
            "prompt_en": "One hand extended forward in tsukkomi gesture. Palm facing outward, fingers together. With exasperated expression.",
            "category": "反応"
        }
    ]

    for pose in initial_poses:
        register_pose(**pose)

    print(f"ポーズ辞書に{len(initial_poses)}件の初期データを投入しました")


# ==================== トレンド収集 ====================

def save_ranking_snapshot(
    list_type: str,
    product_ids: List[int],
    list_hash: str
) -> tuple:
    """ランキングスナップショットを保存（変化時のみ）"""
    conn = get_connection()
    cursor = conn.cursor()

    # ハッシュで重複チェック
    cursor.execute(
        "SELECT id FROM ranking_snapshots WHERE list_type = ? AND list_hash = ?",
        (list_type, list_hash)
    )
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return existing["id"], False  # 既存のスナップショット

    # 新規スナップショット作成
    cursor.execute(
        """
        INSERT INTO ranking_snapshots (list_type, list_hash, total_items)
        VALUES (?, ?, ?)
        """,
        (list_type, list_hash, len(product_ids))
    )
    snapshot_id = cursor.lastrowid

    # ランキング順位を保存
    for rank, product_id in enumerate(product_ids, start=1):
        cursor.execute(
            """
            INSERT INTO ranking_entries (snapshot_id, rank_position, product_id)
            VALUES (?, ?, ?)
            """,
            (snapshot_id, rank, product_id)
        )
        # productsテーブルにも追加（存在しなければ）
        cursor.execute(
            """
            INSERT OR IGNORE INTO products_meta (product_id, store_url)
            VALUES (?, ?)
            """,
            (product_id, f"https://store.line.me/stickershop/product/{product_id}/ja")
        )

    conn.commit()
    conn.close()
    return snapshot_id, True  # 新規スナップショット


def get_products_without_meta(limit: int = 50) -> List[int]:
    """メタデータ未取得の商品IDリストを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT product_id FROM products_meta
        WHERE title IS NULL
        ORDER BY first_seen_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [row["product_id"] for row in rows]


def upsert_product_meta(
    product_id: int,
    store_url: str,
    title: str = None,
    creator_id: int = None,
    creator_name: str = None,
    description: str = None,
    price_amount: int = None,
    price_currency: str = "JPY",
    sticker_type: str = None,
    sticker_count: int = None
):
    """商品メタデータをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO products_meta (
            product_id, store_url, title, creator_id, creator_name,
            description, price_amount, price_currency, sticker_type, sticker_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (product_id) DO UPDATE SET
            title = excluded.title,
            creator_id = excluded.creator_id,
            creator_name = excluded.creator_name,
            description = excluded.description,
            price_amount = excluded.price_amount,
            price_currency = excluded.price_currency,
            sticker_type = excluded.sticker_type,
            sticker_count = excluded.sticker_count,
            updated_at = CURRENT_TIMESTAMP
        """,
        (product_id, store_url, title, creator_id, creator_name,
         description, price_amount, price_currency, sticker_type, sticker_count)
    )

    conn.commit()
    conn.close()


def get_products_without_features(limit: int = 10) -> List[int]:
    """特徴未抽出の商品IDリストを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT pm.product_id FROM products_meta pm
        LEFT JOIN product_features pf ON pm.product_id = pf.product_id
        WHERE pf.product_id IS NULL AND pm.title IS NOT NULL
        ORDER BY pm.updated_at DESC
        LIMIT ?
        """,
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()

    return [row["product_id"] for row in rows]


def upsert_sticker_features(
    sticker_id: str,
    product_id: int,
    image_path: str = None,
    features_json: dict = None
):
    """スタンプ特徴をアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    features_str = json.dumps(features_json, ensure_ascii=False) if features_json else "{}"

    cursor.execute(
        """
        INSERT INTO sticker_features (sticker_id, product_id, image_path, features_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (sticker_id) DO UPDATE SET
            image_path = excluded.image_path,
            features_json = excluded.features_json,
            analyzed_at = CURRENT_TIMESTAMP
        """,
        (sticker_id, product_id, image_path, features_str)
    )

    conn.commit()
    conn.close()


def upsert_product_features(product_id: int, pack_features: dict):
    """商品特徴集約をアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    features_str = json.dumps(pack_features, ensure_ascii=False)

    cursor.execute(
        """
        INSERT INTO product_features (product_id, pack_features)
        VALUES (?, ?)
        ON CONFLICT (product_id) DO UPDATE SET
            pack_features = excluded.pack_features,
            analyzed_at = CURRENT_TIMESTAMP
        """,
        (product_id, features_str)
    )

    conn.commit()
    conn.close()


def upsert_embedding(sticker_id: int, model_name: str, embedding: List[float]):
    """CLIP埋め込みをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    embedding_str = json.dumps(embedding)

    cursor.execute(
        """
        INSERT INTO sticker_embeddings (sticker_id, model_name, embedding)
        VALUES (?, ?, ?)
        ON CONFLICT (sticker_id) DO UPDATE SET
            model_name = excluded.model_name,
            embedding = excluded.embedding,
            created_at = CURRENT_TIMESTAMP
        """,
        (sticker_id, model_name, embedding_str)
    )

    conn.commit()
    conn.close()


def upsert_knowledge(
    category: str,
    key: str,
    value: Any,
    description: str = None,
    source_url: str = None
):
    """ナレッジベースをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    value_str = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)

    cursor.execute(
        """
        INSERT INTO knowledge_base (category, key, value, description, source_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (category, key) DO UPDATE SET
            value = excluded.value,
            description = excluded.description,
            source_url = excluded.source_url,
            updated_at = CURRENT_TIMESTAMP
        """,
        (category, key, value_str, description, source_url)
    )

    conn.commit()
    conn.close()


def get_trend_stats() -> Dict:
    """トレンドデータの統計を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) as count FROM ranking_snapshots")
    stats["snapshots"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM products_meta")
    stats["products"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM products_meta WHERE title IS NOT NULL")
    stats["products_with_meta"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM product_features")
    stats["products_with_features"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM sticker_features")
    stats["stickers_analyzed"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM sticker_embeddings")
    stats["stickers_with_embeddings"] = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM knowledge_base")
    stats["knowledge_entries"] = cursor.fetchone()["count"]

    conn.close()
    return stats


def list_products_for_analysis(
    analyzed: bool = None,
    has_meta: bool = True,
    limit: int = 50
) -> List[Dict]:
    """分析対象の商品リストを取得（インタラクティブ選択用）"""
    conn = get_connection()
    cursor = conn.cursor()

    if analyzed is None:
        # 全商品（メタデータあり）
        cursor.execute(
            """
            SELECT pm.*, pf.analyzed_at as feature_analyzed_at
            FROM products_meta pm
            LEFT JOIN product_features pf ON pm.product_id = pf.product_id
            WHERE pm.title IS NOT NULL
            ORDER BY pm.updated_at DESC
            LIMIT ?
            """,
            (limit,)
        )
    elif analyzed:
        # 分析済み商品
        cursor.execute(
            """
            SELECT pm.*, pf.analyzed_at as feature_analyzed_at
            FROM products_meta pm
            INNER JOIN product_features pf ON pm.product_id = pf.product_id
            WHERE pm.title IS NOT NULL
            ORDER BY pf.analyzed_at DESC
            LIMIT ?
            """,
            (limit,)
        )
    else:
        # 未分析商品
        cursor.execute(
            """
            SELECT pm.*, NULL as feature_analyzed_at
            FROM products_meta pm
            LEFT JOIN product_features pf ON pm.product_id = pf.product_id
            WHERE pm.title IS NOT NULL AND pf.product_id IS NULL
            ORDER BY pm.updated_at DESC
            LIMIT ?
            """,
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_latest_rankings(list_type: str = "top_creators", limit: int = 100) -> List[Dict]:
    """最新のランキングを取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT re.rank_position, re.product_id, pm.title, pm.creator_name
        FROM ranking_entries re
        INNER JOIN ranking_snapshots rs ON re.snapshot_id = rs.id
        LEFT JOIN products_meta pm ON re.product_id = pm.product_id
        WHERE rs.list_type = ?
        AND rs.id = (
            SELECT MAX(id) FROM ranking_snapshots WHERE list_type = ?
        )
        ORDER BY re.rank_position
        LIMIT ?
        """,
        (list_type, list_type, limit)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==================== v2.0 マスタ管理 ====================

def upsert_pose_master(
    id: str,
    name: str,
    gesture: str,
    name_en: str = None,
    gesture_en: str = None,
    expression: str = None,
    expression_en: str = None,
    vibe: str = None,
    category: str = None,
    tags: list = None,
    difficulty: int = 2,
    body_parts: list = None,
    requires_full_body: bool = False,
    similar_poses: list = None,
    incompatible_with: list = None,
    hints: list = None,
    avoid: list = None,
    source: str = "builtin"
):
    """ポーズマスタをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    # プロンプトを自動生成
    prompt_parts = [gesture]
    if expression:
        prompt_parts.append(expression)
    if vibe:
        prompt_parts.append(f"（{vibe}）")
    prompt_full = "\n".join(prompt_parts)

    cursor.execute("""
        INSERT INTO pose_master (
            id, name, name_en, gesture, gesture_en, expression, expression_en,
            vibe, prompt_full, category, tags, difficulty, body_parts,
            requires_full_body, similar_poses, incompatible_with, hints, avoid, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            name = excluded.name,
            name_en = excluded.name_en,
            gesture = excluded.gesture,
            gesture_en = excluded.gesture_en,
            expression = excluded.expression,
            expression_en = excluded.expression_en,
            vibe = excluded.vibe,
            prompt_full = excluded.prompt_full,
            category = excluded.category,
            tags = excluded.tags,
            difficulty = excluded.difficulty,
            body_parts = excluded.body_parts,
            requires_full_body = excluded.requires_full_body,
            similar_poses = excluded.similar_poses,
            incompatible_with = excluded.incompatible_with,
            hints = excluded.hints,
            avoid = excluded.avoid,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
    """, (
        id, name, name_en, gesture, gesture_en, expression, expression_en,
        vibe, prompt_full, category,
        json.dumps(tags, ensure_ascii=False) if tags else None,
        difficulty,
        json.dumps(body_parts, ensure_ascii=False) if body_parts else None,
        requires_full_body,
        json.dumps(similar_poses, ensure_ascii=False) if similar_poses else None,
        json.dumps(incompatible_with, ensure_ascii=False) if incompatible_with else None,
        json.dumps(hints, ensure_ascii=False) if hints else None,
        json.dumps(avoid, ensure_ascii=False) if avoid else None,
        source
    ))

    conn.commit()
    conn.close()


def upsert_text_master(
    id: str,
    text: str,
    text_variants: list = None,
    reading: str = None,
    meaning: str = None,
    meaning_en: str = None,
    category: str = None,
    usage: list = None,
    formality: int = 2,
    persona_age: list = None,
    persona_target: list = None,
    persona_theme: list = None,
    text_size: str = "normal",
    decoration: dict = None,
    seasonal: list = None,
    source: str = "builtin"
):
    """セリフマスタをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO text_master (
            id, text, text_variants, reading, meaning, meaning_en,
            category, usage, formality, persona_age, persona_target, persona_theme,
            text_size, decoration, seasonal, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            text = excluded.text,
            text_variants = excluded.text_variants,
            reading = excluded.reading,
            meaning = excluded.meaning,
            meaning_en = excluded.meaning_en,
            category = excluded.category,
            usage = excluded.usage,
            formality = excluded.formality,
            persona_age = excluded.persona_age,
            persona_target = excluded.persona_target,
            persona_theme = excluded.persona_theme,
            text_size = excluded.text_size,
            decoration = excluded.decoration,
            seasonal = excluded.seasonal,
            source = excluded.source
    """, (
        id, text,
        json.dumps(text_variants, ensure_ascii=False) if text_variants else None,
        reading, meaning, meaning_en, category,
        json.dumps(usage, ensure_ascii=False) if usage else None,
        formality,
        json.dumps(persona_age, ensure_ascii=False) if persona_age else None,
        json.dumps(persona_target, ensure_ascii=False) if persona_target else None,
        json.dumps(persona_theme, ensure_ascii=False) if persona_theme else None,
        text_size,
        json.dumps(decoration, ensure_ascii=False) if decoration else None,
        json.dumps(seasonal, ensure_ascii=False) if seasonal else None,
        source
    ))

    conn.commit()
    conn.close()


def upsert_reactions_master(
    id: str,
    text_id: str,
    pose_id: str,
    emotion: str = None,
    emotion_en: str = None,
    persona_age: list = None,
    persona_target: list = None,
    persona_theme: list = None,
    intensity_range: list = None,
    slot_type: str = "core",
    priority: int = 50,
    is_essential: bool = False,
    outfit: str = None,
    item_hint: str = None,
    enhance_expression: bool = True,
    incompatible_reactions: list = None,
    source: str = "builtin"
):
    """リアクションマスタをアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO reactions_master (
            id, text_id, pose_id, emotion, emotion_en,
            persona_age, persona_target, persona_theme, intensity_range,
            slot_type, priority, is_essential, outfit, item_hint,
            enhance_expression, incompatible_reactions, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (id) DO UPDATE SET
            text_id = excluded.text_id,
            pose_id = excluded.pose_id,
            emotion = excluded.emotion,
            emotion_en = excluded.emotion_en,
            persona_age = excluded.persona_age,
            persona_target = excluded.persona_target,
            persona_theme = excluded.persona_theme,
            intensity_range = excluded.intensity_range,
            slot_type = excluded.slot_type,
            priority = excluded.priority,
            is_essential = excluded.is_essential,
            outfit = excluded.outfit,
            item_hint = excluded.item_hint,
            enhance_expression = excluded.enhance_expression,
            incompatible_reactions = excluded.incompatible_reactions,
            source = excluded.source,
            updated_at = CURRENT_TIMESTAMP
    """, (
        id, text_id, pose_id, emotion, emotion_en,
        json.dumps(persona_age, ensure_ascii=False) if persona_age else None,
        json.dumps(persona_target, ensure_ascii=False) if persona_target else None,
        json.dumps(persona_theme, ensure_ascii=False) if persona_theme else None,
        json.dumps(intensity_range, ensure_ascii=False) if intensity_range else None,
        slot_type, priority, is_essential, outfit, item_hint,
        enhance_expression,
        json.dumps(incompatible_reactions, ensure_ascii=False) if incompatible_reactions else None,
        source
    ))

    conn.commit()
    conn.close()


def get_pose_master(id: str) -> Optional[Dict]:
    """ポーズマスタを取得"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pose_master WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        for key in ['tags', 'body_parts', 'similar_poses', 'incompatible_with', 'hints', 'avoid']:
            if data.get(key):
                data[key] = json.loads(data[key])
        return data
    return None


def get_text_master(id: str) -> Optional[Dict]:
    """セリフマスタを取得"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM text_master WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        for key in ['text_variants', 'usage', 'persona_age', 'persona_target', 'persona_theme', 'decoration', 'seasonal']:
            if data.get(key):
                data[key] = json.loads(data[key])
        return data
    return None


def get_reactions_master(id: str) -> Optional[Dict]:
    """リアクションマスタを取得"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reactions_master WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        for key in ['persona_age', 'persona_target', 'persona_theme', 'intensity_range', 'incompatible_reactions']:
            if data.get(key):
                data[key] = json.loads(data[key])
        return data
    return None


def select_reactions_for_persona(
    age: str,
    target: str,
    theme: str = None,
    intensity: int = 2,
    limit: int = 24
) -> List[Dict]:
    """ペルソナに合ったリアクションを選択（ポーズ・セリフ詳細付き）"""
    conn = get_connection()
    cursor = conn.cursor()

    # ペルソナ設定を取得
    cursor.execute("""
        SELECT * FROM persona_config
        WHERE age = ? AND target = ? AND (theme = ? OR theme IS NULL) AND intensity = ?
        ORDER BY theme DESC NULLS LAST
        LIMIT 1
    """, (age, target, theme, intensity))
    config = cursor.fetchone()

    # リアクションを選択
    cursor.execute("""
        SELECT
            rm.*,
            pm.name as pose_name, pm.gesture, pm.expression, pm.vibe, pm.prompt_full,
            tm.text, tm.text_variants, tm.formality
        FROM reactions_master rm
        JOIN pose_master pm ON rm.pose_id = pm.id
        JOIN text_master tm ON rm.text_id = tm.id
        WHERE (rm.persona_age LIKE ? OR rm.persona_age IS NULL)
          AND (rm.persona_target LIKE ? OR rm.persona_target IS NULL)
          AND (rm.persona_theme LIKE ? OR rm.persona_theme IS NULL OR ? IS NULL)
          AND (rm.intensity_range LIKE ? OR rm.intensity_range IS NULL)
        ORDER BY rm.is_essential DESC, rm.priority DESC
        LIMIT ?
    """, (
        f'%{age}%', f'%{target}%', f'%{theme}%' if theme else '%', theme,
        f'%{intensity}%', limit
    ))

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        data = dict(row)
        # JSONフィールドをパース
        for key in ['persona_age', 'persona_target', 'persona_theme', 'intensity_range',
                    'incompatible_reactions', 'text_variants']:
            if data.get(key):
                try:
                    data[key] = json.loads(data[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        results.append(data)

    return results


def list_pose_master(category: str = None) -> List[Dict]:
    """ポーズマスタ一覧を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    if category:
        cursor.execute("SELECT * FROM pose_master WHERE category = ? ORDER BY name", (category,))
    else:
        cursor.execute("SELECT * FROM pose_master ORDER BY category, name")

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_text_master(category: str = None, formality: int = None) -> List[Dict]:
    """セリフマスタ一覧を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if formality:
        conditions.append("formality = ?")
        params.append(formality)

    where = " AND ".join(conditions) if conditions else "1=1"
    cursor.execute(f"SELECT * FROM text_master WHERE {where} ORDER BY category, text", params)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def upsert_persona_config(
    age: str,
    target: str,
    theme: str = None,
    intensity: int = 2,
    core_slots: int = 12,
    theme_slots: int = 8,
    reaction_slots: int = 4,
    recommended_formality: int = None,
    recommended_text_size: str = None,
    recommended_style: str = None,
    essential_reactions: list = None,
    excluded_reactions: list = None,
    description: str = None,
    example_texts: list = None
):
    """ペルソナ設定をアップサート"""
    conn = get_connection()
    cursor = conn.cursor()

    # 既存レコードを削除してから挿入（UNIQUE制約対応）
    cursor.execute("""
        DELETE FROM persona_config
        WHERE age = ? AND target = ? AND (theme = ? OR (theme IS NULL AND ? IS NULL)) AND intensity = ?
    """, (age, target, theme, theme, intensity))

    cursor.execute("""
        INSERT INTO persona_config (
            age, target, theme, intensity,
            core_slots, theme_slots, reaction_slots,
            recommended_formality, recommended_text_size, recommended_style,
            essential_reactions, excluded_reactions, description, example_texts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        age, target, theme, intensity,
        core_slots, theme_slots, reaction_slots,
        recommended_formality, recommended_text_size, recommended_style,
        json.dumps(essential_reactions, ensure_ascii=False) if essential_reactions else None,
        json.dumps(excluded_reactions, ensure_ascii=False) if excluded_reactions else None,
        description,
        json.dumps(example_texts, ensure_ascii=False) if example_texts else None
    ))

    conn.commit()
    conn.close()


def list_persona_config(age: str = None, target: str = None) -> List[Dict]:
    """ペルソナ設定一覧を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []
    if age:
        conditions.append("age = ?")
        params.append(age)
    if target:
        conditions.append("target = ?")
        params.append(target)

    where = " AND ".join(conditions) if conditions else "1=1"
    cursor.execute(f"SELECT * FROM persona_config WHERE {where} ORDER BY age, target, theme, intensity", params)

    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        data = dict(row)
        for key in ['essential_reactions', 'excluded_reactions', 'example_texts']:
            if data.get(key):
                try:
                    data[key] = json.loads(data[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        results.append(data)

    return results


def get_persona_config(age: str, target: str, theme: str = None, intensity: int = 2) -> Optional[Dict]:
    """特定のペルソナ設定を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM persona_config
        WHERE age = ? AND target = ? AND (theme = ? OR theme IS NULL) AND intensity = ?
        ORDER BY theme DESC NULLS LAST
        LIMIT 1
    """, (age, target, theme, intensity))

    row = cursor.fetchone()
    conn.close()

    if row:
        data = dict(row)
        for key in ['essential_reactions', 'excluded_reactions', 'example_texts']:
            if data.get(key):
                try:
                    data[key] = json.loads(data[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return data
    return None


# ==================== 生成ログ ====================

def record_generation_log(
    session_id: str,
    slot_index: int = None,
    reaction_id: str = None,
    pose_id: str = None,
    text_id: str = None,
    prompt_text: str = None,
    success: bool = True,
    retry_count: int = 0,
    failure_reason: str = None,
    execution_time_ms: int = None,
    transparency_ok: bool = None,
    size_ok: bool = None,
    aspect_ok: bool = None,
    quality_score: float = None,
    user_rating: int = None,
    notes: str = None
) -> int:
    """生成ログを記録"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO generation_logs (
            session_id, slot_index, reaction_id, pose_id, text_id,
            prompt_text, success, retry_count, failure_reason, execution_time_ms,
            transparency_ok, size_ok, aspect_ok, quality_score, user_rating, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, slot_index, reaction_id, pose_id, text_id,
        prompt_text, success, retry_count, failure_reason, execution_time_ms,
        transparency_ok, size_ok, aspect_ok, quality_score, user_rating, notes
    ))

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return log_id


def get_generation_stats(session_id: str = None, reaction_id: str = None) -> Dict:
    """生成統計を取得"""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []
    if session_id:
        conditions.append("session_id = ?")
        params.append(session_id)
    if reaction_id:
        conditions.append("reaction_id = ?")
        params.append(reaction_id)

    where = " AND ".join(conditions) if conditions else "1=1"

    cursor.execute(f"""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) as success_count,
            AVG(retry_count) as avg_retries,
            AVG(execution_time_ms) as avg_time_ms,
            AVG(quality_score) as avg_quality,
            SUM(CASE WHEN transparency_ok THEN 1 ELSE 0 END) as transparency_ok_count,
            SUM(CASE WHEN size_ok THEN 1 ELSE 0 END) as size_ok_count
        FROM generation_logs
        WHERE {where}
    """, params)

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else {}


def update_pose_master_stats(pose_id: str, success: bool, quality_score: float = None):
    """ポーズマスタの統計を更新"""
    conn = get_connection()
    cursor = conn.cursor()

    if success:
        if quality_score is not None:
            cursor.execute("""
                UPDATE pose_master
                SET success_count = success_count + 1,
                    last_used = CURRENT_TIMESTAMP,
                    avg_quality_score = COALESCE(
                        (avg_quality_score * success_count + ?) / (success_count + 1),
                        ?
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (quality_score, quality_score, pose_id))
        else:
            cursor.execute("""
                UPDATE pose_master
                SET success_count = success_count + 1,
                    last_used = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (pose_id,))
    else:
        cursor.execute("""
            UPDATE pose_master
            SET failure_count = failure_count + 1,
                last_used = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (pose_id,))

    conn.commit()
    conn.close()


if __name__ == "__main__":
    # スクリプトとして実行された場合、データベースを初期化
    init_database()
    seed_pose_dictionary()
