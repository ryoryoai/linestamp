"""
LINEスタンプ生成スキル - ポーズ辞書管理ツール

ポーズの登録・検索・一覧表示・YAML import/exportを行うCLIツール
"""

import sys
import json
from pathlib import Path
from datetime import datetime

import yaml

from database import (
    init_database,
    get_connection,
    register_pose,
    register_shigusa,
    get_pose,
    search_poses,
    update_pose_stats,
)

# YAMLポーズ定義のディレクトリ
POSES_DIR = Path(__file__).parent / "poses"


def list_poses(category: str = None):
    """ポーズ一覧を表示"""
    poses = search_poses(category=category)

    if not poses:
        print("ポーズが登録されていません")
        return

    print("\n" + "=" * 70)
    print("ポーズ辞書一覧")
    if category:
        print(f"カテゴリ: {category}")
    print("=" * 70)
    print(f"{'名前':<20} {'カテゴリ':<10} {'成功率':<8} {'使用回数'}")
    print("-" * 70)

    for p in poses:
        total = p['success_count'] + p['failure_count']
        rate = p['success_count'] / total if total > 0 else 0
        rate_str = f"{rate:.0%}" if total > 0 else "-"
        print(f"{p['name']:<20} {p['category'] or '-':<10} {rate_str:<8} {total}回")

    print("=" * 70 + "\n")


def show_pose(name: str):
    """ポーズ詳細を表示"""
    pose = get_pose(name)

    if not pose:
        print(f"ポーズが見つかりません: {name}")
        return

    print("\n" + "=" * 70)
    print(f"ポーズ: {pose['name']}")
    print("=" * 70)
    print(f"英語名: {pose['name_en'] or '-'}")
    print(f"カテゴリ: {pose['category'] or '-'}")
    print(f"メモ: {pose['notes'] or '-'}")
    print()

    # 新形式（ジェスチャー＋表情）があれば表示
    if pose.get('gesture_ja'):
        print("【ジェスチャー】")
        print(pose['gesture_ja'])
        print()
        print("【表情】")
        print(pose.get('expression_ja') or '-')
        print()
        if pose.get('vibe'):
            print(f"【雰囲気】{pose['vibe']}")
            print()

    print("【統合プロンプト（AI出力用）】")
    print(pose['prompt_ja'])
    print()

    if pose.get('prompt_en'):
        print("【英語プロンプト】")
        print(pose['prompt_en'])
        print()

    total = pose['success_count'] + pose['failure_count']
    rate = pose['success_count'] / total if total > 0 else 0
    print(f"成功率: {rate:.0%} ({pose['success_count']}/{total})")
    print(f"最終使用: {pose['last_used'] or '-'}")
    print("=" * 70 + "\n")


def add_pose_interactive():
    """対話形式でポーズを追加（ジェスチャー＋表情）"""
    print("\n=== ポーズ登録（ジェスチャー＋表情）===\n")

    name = input("ポーズ名（日本語）: ").strip()
    if not name:
        print("キャンセルしました")
        return

    name_en = input("ポーズ名（英語、省略可）: ").strip() or None

    print("\n【ジェスチャー】手・体の動きを入力（複数行可、空行で終了）:")
    print("例: 片手を顎に添える。親指と人差し指を軽く曲げ、指の関節部分を顎に当てる...")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    gesture_ja = "\n".join(lines)

    if not gesture_ja:
        print("ジェスチャーが空のためキャンセルしました")
        return

    print("\n【表情】顔の表情・雰囲気を入力（複数行可、空行で終了）:")
    print("例: 余裕のある肯定表情、少し得意げで決めポーズだが力まない")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    expression_ja = "\n".join(lines)

    if not expression_ja:
        print("表情が空のためキャンセルしました")
        return

    vibe = input("\n【雰囲気キーワード】（省略可、例: 評価・承認・余裕）: ").strip() or None

    print("\n--- 英語版（省略可）---")
    print("ジェスチャー（英語、空行で終了）:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    gesture_en = "\n".join(lines) or None

    print("表情（英語、空行で終了）:")
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    expression_en = "\n".join(lines) or None

    print("\nカテゴリを選択:")
    categories = ["肯定", "否定", "愛情", "応援", "喜び", "礼儀", "照れ", "反応", "その他"]
    for i, cat in enumerate(categories, 1):
        print(f"  {i}. {cat}")
    cat_input = input("番号を入力（省略可）: ").strip()
    category = categories[int(cat_input) - 1] if cat_input.isdigit() and 1 <= int(cat_input) <= len(categories) else None

    notes = input("\nメモ（省略可）: ").strip() or None

    # 登録
    register_shigusa(
        name=name,
        name_en=name_en,
        gesture_ja=gesture_ja,
        gesture_en=gesture_en,
        expression_ja=expression_ja,
        expression_en=expression_en,
        vibe=vibe,
        category=category,
        notes=notes,
    )

    print(f"\n* ポーズを登録しました: {name}")
    show_pose(name)


def search_pose_interactive():
    """対話形式でポーズを検索"""
    keyword = input("検索キーワード: ").strip()
    if not keyword:
        list_poses()
        return

    poses = search_poses(keyword=keyword)

    if not poses:
        print(f"「{keyword}」に一致するポーズが見つかりません")
        return

    print(f"\n「{keyword}」の検索結果: {len(poses)}件\n")
    for p in poses:
        print(f"  - {p['name']} ({p['category'] or '-'})")

    if len(poses) == 1:
        show_pose(poses[0]['name'])


def export_pose_for_reaction(name: str):
    """REACTIONSに使える形式でポーズを出力"""
    pose = get_pose(name)

    if not pose:
        print(f"ポーズが見つかりません: {name}")
        return None

    print("\n【REACTIONSに追加する形式】")
    print("```python")
    print(f'{{"id": "xxx", "emotion": "xxx", "pose": "{pose["prompt_ja"]}", "text": "xxx", "pose_locked": True}},')
    print("```")
    print()

    return pose['prompt_ja']


# ==================== YAML Import/Export ====================

def export_pose_to_yaml(name: str, output_path: str = None) -> str:
    """ポーズをYAML形式でエクスポート"""
    pose = get_pose(name)

    if not pose:
        print(f"ポーズが見つかりません: {name}")
        return None

    # YAMLデータ構築
    yaml_data = {
        "name": pose["name"],
    }

    # オプションフィールド
    if pose.get("name_en"):
        yaml_data["name_en"] = pose["name_en"]

    if pose.get("category"):
        yaml_data["category"] = pose["category"]

    # gesture/expression があれば使用、なければ prompt_ja から
    if pose.get("gesture_ja"):
        yaml_data["gesture"] = pose["gesture_ja"]
    else:
        yaml_data["gesture"] = pose.get("prompt_ja", "")

    if pose.get("expression_ja"):
        yaml_data["expression"] = pose["expression_ja"]
    else:
        yaml_data["expression"] = ""

    if pose.get("vibe"):
        yaml_data["vibe"] = pose["vibe"]

    # hints/avoid（JSON文字列からパース）
    if pose.get("hints"):
        try:
            yaml_data["hints"] = json.loads(pose["hints"])
        except (json.JSONDecodeError, TypeError):
            yaml_data["hints"] = [pose["hints"]]

    if pose.get("avoid"):
        try:
            yaml_data["avoid"] = json.loads(pose["avoid"])
        except (json.JSONDecodeError, TypeError):
            yaml_data["avoid"] = [pose["avoid"]]

    # 出力パス決定
    if output_path is None:
        # 名前をファイル名に変換（スペースをアンダースコアに）
        safe_name = name.replace(" ", "_").replace("/", "_").replace("（", "_").replace("）", "")
        output_path = POSES_DIR / f"{safe_name}.yaml"
    else:
        output_path = Path(output_path)

    # YAML出力
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"エクスポート完了: {output_path}")
    return str(output_path)


def import_pose_from_yaml(yaml_path: str, update_db: bool = True) -> dict:
    """YAMLファイルからポーズをインポート"""
    yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        print(f"ファイルが見つかりません: {yaml_path}")
        return None

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        print(f"YAMLが空です: {yaml_path}")
        return None

    # 必須フィールドチェック
    if "name" not in data:
        print("エラー: 'name' フィールドが必須です")
        return None

    if "gesture" not in data:
        print("エラー: 'gesture' フィールドが必須です")
        return None

    # データベースに登録
    if update_db:
        _save_pose_to_db(data, str(yaml_path))
        print(f"インポート完了: {data['name']}")

    return data


def _save_pose_to_db(pose_data: dict, yaml_path: str = None):
    """ポーズデータをDBに保存（内部用）"""
    conn = get_connection()
    cursor = conn.cursor()

    name = pose_data["name"]
    name_en = pose_data.get("name_en")
    gesture_ja = pose_data.get("gesture", "")
    expression_ja = pose_data.get("expression", "")
    vibe = pose_data.get("vibe")
    category = pose_data.get("category")
    hints = json.dumps(pose_data.get("hints", []), ensure_ascii=False) if pose_data.get("hints") else None
    avoid = json.dumps(pose_data.get("avoid", []), ensure_ascii=False) if pose_data.get("avoid") else None

    # 統合プロンプトを生成
    g = gesture_ja.strip().rstrip('。')
    e = expression_ja.strip().rstrip('。') if expression_ja else ""
    prompt_ja = f"{g}。{e}。" if e else f"{g}。"
    if vibe:
        prompt_ja += f"（{vibe}）"

    cursor.execute("""
        INSERT OR REPLACE INTO pose_dictionary (
            name, name_en, gesture_ja, expression_ja, vibe,
            prompt_ja, category, hints, avoid, yaml_path, updated_at,
            success_count, failure_count, last_used, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
            COALESCE((SELECT success_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT failure_count FROM pose_dictionary WHERE name = ?), 0),
            COALESCE((SELECT last_used FROM pose_dictionary WHERE name = ?), NULL),
            COALESCE((SELECT created_at FROM pose_dictionary WHERE name = ?), CURRENT_TIMESTAMP)
        )
    """, (name, name_en, gesture_ja, expression_ja, vibe,
          prompt_ja, category, hints, avoid, yaml_path, name, name, name, name))

    conn.commit()
    conn.close()


def sync_yaml_to_db():
    """poses/ ディレクトリ内のYAMLをDBに同期"""
    if not POSES_DIR.exists():
        print(f"ディレクトリが見つかりません: {POSES_DIR}")
        return

    yaml_files = list(POSES_DIR.glob("*.yaml")) + list(POSES_DIR.glob("*.yml"))
    # テンプレートファイルを除外
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    imported = 0
    for yaml_file in yaml_files:
        try:
            result = import_pose_from_yaml(yaml_file, update_db=True)
            if result:
                imported += 1
        except Exception as e:
            print(f"エラー ({yaml_file.name}): {e}")

    print(f"\n同期完了: {imported}件のポーズをインポートしました")


def sync_db_to_yaml():
    """DBのポーズをYAMLファイルにエクスポート"""
    poses = search_poses()

    if not poses:
        print("エクスポートするポーズがありません")
        return

    exported = 0
    for pose in poses:
        try:
            result = export_pose_to_yaml(pose["name"])
            if result:
                exported += 1
        except Exception as e:
            print(f"エラー ({pose['name']}): {e}")

    print(f"\n同期完了: {exported}件のポーズをエクスポートしました")


def list_yaml_poses():
    """poses/ ディレクトリ内のYAMLファイル一覧を表示"""
    if not POSES_DIR.exists():
        print(f"ディレクトリが見つかりません: {POSES_DIR}")
        return

    yaml_files = list(POSES_DIR.glob("*.yaml")) + list(POSES_DIR.glob("*.yml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    if not yaml_files:
        print("YAMLファイルがありません")
        return

    print("\n" + "=" * 60)
    print("YAMLポーズ定義一覧")
    print("=" * 60)

    for yaml_file in sorted(yaml_files):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            name = data.get("name", "不明")
            category = data.get("category", "-")
            print(f"  {yaml_file.name:<30} {name:<20} [{category}]")
        except Exception as e:
            print(f"  {yaml_file.name:<30} (読み込みエラー: {e})")

    print("=" * 60 + "\n")


def print_usage():
    """使い方を表示"""
    print("""
ポーズ辞書管理ツール

使い方:
  python pose_manager.py list [カテゴリ]    - ポーズ一覧を表示
  python pose_manager.py show <名前>        - ポーズ詳細を表示
  python pose_manager.py add                - 対話形式でポーズを追加
  python pose_manager.py search [キーワード] - ポーズを検索
  python pose_manager.py export <名前>      - REACTIONSに使える形式で出力

YAML操作:
  python pose_manager.py yaml-list          - YAMLファイル一覧
  python pose_manager.py yaml-export <名前> [出力パス] - YAMLにエクスポート
  python pose_manager.py yaml-import <パス> - YAMLからインポート
  python pose_manager.py yaml-sync-to-db    - YAML → DB 同期
  python pose_manager.py yaml-sync-to-yaml  - DB → YAML 同期

カテゴリ:
  肯定, 否定, 愛情, 応援, 喜び, 礼儀, 照れ, 反応, その他

例:
  python pose_manager.py list
  python pose_manager.py list 肯定
  python pose_manager.py show "OKサイン"
  python pose_manager.py add
  python pose_manager.py export "いいじゃん（OKサイン）"
  python pose_manager.py yaml-export "OKサイン"
  python pose_manager.py yaml-import poses/new_pose.yaml
""")


if __name__ == "__main__":
    init_database()

    if len(sys.argv) < 2:
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        category = sys.argv[2] if len(sys.argv) > 2 else None
        list_poses(category)

    elif cmd == "show":
        if len(sys.argv) < 3:
            print("ポーズ名を指定してください")
            sys.exit(1)
        show_pose(sys.argv[2])

    elif cmd == "add":
        add_pose_interactive()

    elif cmd == "search":
        if len(sys.argv) > 2:
            poses = search_poses(keyword=sys.argv[2])
            if poses:
                print(f"\n「{sys.argv[2]}」の検索結果: {len(poses)}件\n")
                for p in poses:
                    print(f"  - {p['name']} ({p['category'] or '-'})")
            else:
                print(f"「{sys.argv[2]}」に一致するポーズが見つかりません")
        else:
            search_pose_interactive()

    elif cmd == "export":
        if len(sys.argv) < 3:
            print("ポーズ名を指定してください")
            sys.exit(1)
        export_pose_for_reaction(sys.argv[2])

    # YAML操作コマンド
    elif cmd == "yaml-list":
        list_yaml_poses()

    elif cmd == "yaml-export":
        if len(sys.argv) < 3:
            print("ポーズ名を指定してください")
            sys.exit(1)
        output_path = sys.argv[3] if len(sys.argv) > 3 else None
        export_pose_to_yaml(sys.argv[2], output_path)

    elif cmd == "yaml-import":
        if len(sys.argv) < 3:
            print("YAMLファイルパスを指定してください")
            sys.exit(1)
        import_pose_from_yaml(sys.argv[2])

    elif cmd == "yaml-sync-to-db":
        sync_yaml_to_db()

    elif cmd == "yaml-sync-to-yaml":
        sync_db_to_yaml()

    else:
        print(f"不明なコマンド: {cmd}")
        print_usage()
