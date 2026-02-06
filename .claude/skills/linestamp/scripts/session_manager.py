"""
LINEスタンプ生成スキル - セッション管理モジュール

セッションの作成・管理・読み込みを担当
DBとファイルシステムの両方を管理
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from database import (
    init_database,
    create_session as db_create_session,
    get_session as db_get_session,
    update_session as db_update_session,
    list_sessions as db_list_sessions,
    get_latest_session as db_get_latest_session,
    save_reactions as db_save_reactions,
    get_reactions as db_get_reactions,
    get_pose,
    search_templates,
    update_template_usage,
    save_template,
)

# セッションディレクトリのルート
SESSIONS_ROOT = Path(__file__).parent.parent.parent.parent.parent / "sessions"


def ensure_sessions_dir():
    """sessionsディレクトリが存在することを確認"""
    SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)


def get_session_dir(session_id: str) -> Path:
    """セッションディレクトリのパスを取得"""
    return SESSIONS_ROOT / session_id


class Session:
    """セッションを表すクラス"""

    def __init__(self, session_id: str = None):
        """
        Args:
            session_id: 既存セッションのID。Noneの場合は新規作成
        """
        self.session_id = session_id
        self.config = {}
        self.reactions = []
        self._loaded = False

        if session_id:
            self._load()

    def _load(self):
        """DBからセッション情報を読み込む"""
        session_data = db_get_session(self.session_id)
        if not session_data:
            raise ValueError(f"Session not found: {self.session_id}")

        self.config = {
            "image_path": session_data.get("image_path"),
            "style": session_data.get("style"),
            "text_mode": session_data.get("text_mode"),
            "outline": session_data.get("outline"),
            "persona": {
                "age": session_data.get("persona_age"),
                "target": session_data.get("persona_target"),
                "theme": session_data.get("persona_theme"),
                "intensity": session_data.get("persona_intensity"),
            },
            "status": session_data.get("status"),
            "output_dir": session_data.get("output_dir"),
            "created_at": session_data.get("created_at"),
        }

        self.reactions = db_get_reactions(self.session_id)
        self._loaded = True

    @classmethod
    def create(
        cls,
        image_path: str,
        style: str = "sd_25",
        text_mode: str = "deka",
        outline: str = "bold",
        persona_age: str = None,
        persona_target: str = None,
        persona_theme: str = None,
        persona_intensity: int = 2,
    ) -> "Session":
        """新規セッションを作成"""
        # DB初期化を確認
        init_database()

        # DBにセッションを作成
        session_id = db_create_session(
            image_path=image_path,
            style=style,
            text_mode=text_mode,
            outline=outline,
            persona_age=persona_age,
            persona_target=persona_target,
            persona_theme=persona_theme,
            persona_intensity=persona_intensity,
        )

        # セッションディレクトリを作成
        ensure_sessions_dir()
        session_dir = get_session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "output").mkdir(exist_ok=True)

        # 出力ディレクトリをDBに記録
        db_update_session(session_id, output_dir=str(session_dir / "output"))

        # インスタンスを作成して返す
        session = cls(session_id)
        return session

    @classmethod
    def load(cls, session_id: str) -> "Session":
        """既存セッションを読み込む"""
        return cls(session_id)

    @classmethod
    def load_latest(cls) -> Optional["Session"]:
        """最新のセッションを読み込む"""
        latest = db_get_latest_session()
        if latest:
            return cls(latest["id"])
        return None

    @classmethod
    def list_all(cls, status: str = None, limit: int = 20) -> List[Dict]:
        """セッション一覧を取得"""
        return db_list_sessions(status=status, limit=limit)

    def set_reactions(self, reactions: List[Dict]):
        """REACTIONSを設定"""
        self.reactions = reactions
        db_save_reactions(self.session_id, reactions)

        # JSONファイルにも保存（バックアップ）
        session_dir = get_session_dir(self.session_id)
        reactions_path = session_dir / "reactions.json"
        with open(reactions_path, "w", encoding="utf-8") as f:
            json.dump(reactions, f, ensure_ascii=False, indent=2)

    def get_reactions(self) -> List[Dict]:
        """REACTIONSを取得"""
        if not self.reactions:
            self.reactions = db_get_reactions(self.session_id)
        return self.reactions

    def update_config(self, **kwargs):
        """設定を更新"""
        for key, value in kwargs.items():
            if key == "persona":
                # ペルソナは個別のカラムに分解
                if isinstance(value, dict):
                    db_update_session(
                        self.session_id,
                        persona_age=value.get("age"),
                        persona_target=value.get("target"),
                        persona_theme=value.get("theme"),
                        persona_intensity=value.get("intensity"),
                    )
                    self.config["persona"] = value
            else:
                db_update_session(self.session_id, **{key: value})
                self.config[key] = value

        # configファイルも更新
        self._save_config_file()

    def _save_config_file(self):
        """config.jsonを保存"""
        session_dir = get_session_dir(self.session_id)
        config_path = session_dir / "config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def set_status(self, status: str):
        """ステータスを設定"""
        valid_statuses = ["draft", "generating", "completed", "failed", "archived"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")

        db_update_session(self.session_id, status=status)
        self.config["status"] = status

    def get_output_dir(self) -> Path:
        """出力ディレクトリを取得"""
        return get_session_dir(self.session_id) / "output"

    def to_dict(self) -> Dict:
        """辞書形式でセッション情報を取得"""
        return {
            "session_id": self.session_id,
            "config": self.config,
            "reactions": self.reactions,
        }

    def __repr__(self):
        return f"Session(id={self.session_id}, status={self.config.get('status')})"


def expand_pose(pose_name: str) -> Optional[str]:
    """ポーズ名を詳細なプロンプトに展開"""
    pose = get_pose(pose_name)
    if pose:
        return pose.get("prompt_ja") or pose.get("prompt_en")
    return None


def get_template_suggestions(
    persona_age: str = None,
    persona_target: str = None,
    persona_theme: str = None,
    limit: int = 5
) -> List[Dict]:
    """ペルソナに基づいてテンプレートを提案"""
    templates = search_templates(
        persona_age=persona_age,
        persona_target=persona_target,
        persona_theme=persona_theme,
    )
    return templates[:limit]


def use_template(template_id: int, session: Session):
    """テンプレートをセッションに適用"""
    from database import get_template
    template = get_template(template_id)
    if template:
        session.set_reactions(template["reactions"])
        update_template_usage(template_id)
        return True
    return False


def save_as_template(
    session: Session,
    name: str,
) -> int:
    """現在のセッションをテンプレートとして保存"""
    persona = session.config.get("persona", {})
    return save_template(
        name=name,
        reactions=session.reactions,
        persona_age=persona.get("age"),
        persona_target=persona.get("target"),
        persona_theme=persona.get("theme"),
    )


# ==================== CLI サポート ====================

def print_session_list(sessions: List[Dict]):
    """セッション一覧を表示"""
    if not sessions:
        print("セッションがありません")
        return

    print("\n" + "=" * 60)
    print("セッション一覧")
    print("=" * 60)
    print(f"{'ID':<20} {'ステータス':<12} {'スタイル':<12} {'作成日時'}")
    print("-" * 60)
    for s in sessions:
        print(f"{s['id']:<20} {s.get('status', '-'):<12} {s.get('style', '-'):<12} {s.get('created_at', '-')}")
    print("=" * 60 + "\n")


def print_session_detail(session: Session):
    """セッション詳細を表示"""
    print("\n" + "=" * 60)
    print(f"セッション: {session.session_id}")
    print("=" * 60)
    print(f"ステータス: {session.config.get('status')}")
    print(f"画像: {session.config.get('image_path')}")
    print(f"スタイル: {session.config.get('style')}")
    print(f"テキストモード: {session.config.get('text_mode')}")
    print(f"アウトライン: {session.config.get('outline')}")

    persona = session.config.get("persona", {})
    print(f"ペルソナ: {persona.get('age')} / {persona.get('target')} / {persona.get('theme')} / 強度{persona.get('intensity')}")

    print(f"出力先: {session.config.get('output_dir')}")
    print(f"REACTIONS: {len(session.reactions)}件")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # テスト実行
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "list":
            sessions = Session.list_all()
            print_session_list(sessions)

        elif cmd == "show" and len(sys.argv) > 2:
            session = Session.load(sys.argv[2])
            print_session_detail(session)

        elif cmd == "latest":
            session = Session.load_latest()
            if session:
                print_session_detail(session)
            else:
                print("セッションがありません")

        elif cmd == "test":
            # テスト用セッション作成
            session = Session.create(
                image_path="input/test.jpg",
                style="yuru_line",
                persona_age="Kid",
                persona_target="Family",
                persona_theme="ツッコミ・反応強化",
            )
            print(f"テストセッション作成: {session.session_id}")
            print_session_detail(session)

    else:
        print("Usage:")
        print("  python session_manager.py list          - セッション一覧")
        print("  python session_manager.py show <id>     - セッション詳細")
        print("  python session_manager.py latest        - 最新セッション")
        print("  python session_manager.py test          - テストセッション作成")
