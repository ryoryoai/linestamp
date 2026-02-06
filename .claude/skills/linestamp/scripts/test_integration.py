"""統合テスト - generate_stamp.py の新機能が正しく動作するか確認"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 50)
print("Integration Test: generate_stamp.py")
print("=" * 50)

# 1. インポートテスト
print("\n[1] Import test...")
try:
    from generate_stamp import (
        MASTER_DB_AVAILABLE,
        POSE_DB_AVAILABLE,
        get_reactions_from_db,
        log_generation_result,
        expand_pose_ref,
        expand_all_pose_refs,
        REACTIONS,
    )
    print("  OK: All imports successful")
    print(f"  MASTER_DB_AVAILABLE: {MASTER_DB_AVAILABLE}")
    print(f"  POSE_DB_AVAILABLE: {POSE_DB_AVAILABLE}")
except Exception as e:
    print(f"  FAIL: {e}")
    sys.exit(1)

# 2. get_reactions_from_db テスト
print("\n[2] get_reactions_from_db test...")
try:
    reactions = get_reactions_from_db(
        age="20s",
        target="Friend",
        theme=None,
        intensity=2,
        limit=5
    )
    print(f"  OK: Got {len(reactions)} reactions")
    if reactions:
        r = reactions[0]
        print(f"  Sample: id={r.get('id')}, text={r.get('text')}")
        print(f"  Has _pose_id: {'_pose_id' in r}")
        print(f"  Has _text_id: {'_text_id' in r}")
        print(f"  pose_locked: {r.get('pose_locked')}")
except Exception as e:
    print(f"  FAIL: {e}")

# 3. expand_pose_ref テスト
print("\n[3] expand_pose_ref test...")
try:
    # pose_ref を含むリアクション
    test_reaction = {"id": "test", "pose_ref": "kimikimi", "text": "test", "emotion": "test"}
    expanded = expand_pose_ref(test_reaction)

    if "pose" in expanded and "pose_ref" not in expanded:
        print(f"  OK: pose_ref expanded successfully")
        print(f"  pose length: {len(expanded.get('pose', ''))} chars")
        print(f"  pose_locked: {expanded.get('pose_locked')}")
    else:
        print(f"  WARN: pose_ref may not have expanded properly")
except Exception as e:
    print(f"  FAIL: {e}")

# 4. log_generation_result テスト (dry run)
print("\n[4] log_generation_result test...")
try:
    # 実際にはログしない（セッションIDがないため）
    # 関数が呼べるかだけ確認
    if MASTER_DB_AVAILABLE:
        print("  OK: log_generation_result function available")
        print("  (Skipping actual logging - no active session)")
    else:
        print("  SKIP: MASTER_DB not available")
except Exception as e:
    print(f"  FAIL: {e}")

# 5. ハードコードREACTIONSとの比較
print("\n[5] REACTIONS comparison...")
print(f"  Hardcoded REACTIONS: {len(REACTIONS)} items")
try:
    db_reactions = get_reactions_from_db(age="20s", target="Friend", limit=24)
    print(f"  DB reactions (20s/Friend): {len(db_reactions)} items")

    # DBからの取得がハードコードより少ない場合は警告
    if len(db_reactions) < len(REACTIONS):
        print(f"  INFO: DB has fewer reactions - fallback to hardcoded may occur")
except Exception as e:
    print(f"  FAIL: {e}")

# 6. ペルソナ別テスト
print("\n[6] Persona variations test...")
test_personas = [
    ("Teen", "Friend", None),
    ("20s", "Friend", None),
    ("30s", "Work", None),
    ("20s", "Partner", None),
]
for age, target, theme in test_personas:
    try:
        reactions = get_reactions_from_db(age=age, target=target, theme=theme, limit=5)
        print(f"  {age}/{target}: {len(reactions)} reactions")
    except Exception as e:
        print(f"  {age}/{target}: FAIL - {e}")

print("\n" + "=" * 50)
print("Test completed!")
print("=" * 50)
