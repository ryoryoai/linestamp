---
name: linestamp-pose
description: ポーズ辞書の管理・チューニングを行うユーティリティスキル
user-invocable: false
---

# linestamp-pose

ポーズYAML辞書の管理とチューニング。
linestamp-reaction のポーズ指定で参照される。

## 使用タイミング

- ポーズ辞書の追加・編集が必要な場合
- ポーズのチューニング（微調整）が必要な場合

## 入出力

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力/出力 | `poses/*.yaml` | YAML |
| 出力 | DB更新 | SQLite |

## コマンド

### ポーズ管理

```bash
python .claude/skills/linestamp-pose/scripts/manager.py \
  --db linestamp.db --list
```

```bash
python .claude/skills/linestamp-pose/scripts/manager.py \
  --db linestamp.db --add poses/new_pose.yaml
```

### ポーズチューニング

```bash
python .claude/skills/linestamp-pose/scripts/tuner.py \
  --db linestamp.db --pose ok_sign --adjust
```

## ファイル構成

```
linestamp-pose/
├── SKILL.md
├── poses/
│   ├── _template.yaml
│   ├── ok_sign.yaml
│   └── kimikimi.yaml
└── scripts/
    ├── manager.py
    └── tuner.py
```

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| poses_master テーブルのレコードを物理削除（DELETE）する | 他セッションで参照されているポーズが消えると整合性が壊れる | `is_active = 0` で論理削除する。物理削除は seed_master_data.py のリセット時のみ |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
- ポーズは linestamp-reaction の `pose_ref` フィールドで参照される
