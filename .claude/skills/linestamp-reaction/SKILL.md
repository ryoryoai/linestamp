---
name: linestamp-reaction
description: ペルソナ設定に基づいてLINEスタンプ用リアクション24件を選択・生成・詳細化する
user-invocable: false
---

# linestamp-reaction

ペルソナ（年代×相手×テーマ×強度）に基づいてリアクション24件を選択・AI生成し、
画像生成用に詳細化（enhance）する。linestamp パイプラインの Step 2。

## 使用タイミング

- linestamp オーケストレーターの Step 2 として呼び出される
- リアクションの再選択・カスタマイズが必要な場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば回避策を適用する
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | ペルソナ設定 (CLI引数) | - |
| 入力 | (任意) カスタムリアクションファイル | JSON/YAML |
| 入力 | (任意) `work/character.yaml` | YAML |
| 入力 | (任意) `work/charm.json` | JSON |
| 出力 | `work/reactions.json` | JSON |

### reactions.json スキーマ

```json
[
  {
    "idx": 1,
    "id": "ryo",
    "text": "りょ！",
    "emotion": "軽くうなずく笑顔",
    "pose": "ピースサイン",
    "pose_locked": false,
    "enhanced_prompt": "Facial Expression:\n- Eyes: ...",
    "item": null,
    "outfit": null
  }
]
```

## コマンド

### リアクション選択

```bash
python .claude/skills/linestamp-reaction/scripts/select_reactions.py \
  --age 20s \
  --target Friend \
  --theme 共感強化 \
  --intensity 2 \
  --output output/linestamp-20260212/work/reactions.json
```

### リアクション詳細化（enhance）

```bash
python .claude/skills/linestamp-reaction/scripts/enhance.py \
  --reactions output/linestamp-20260212/work/reactions.json \
  --character-yaml output/linestamp-20260212/work/character.yaml \
  --output output/linestamp-20260212/work/reactions.json
```

## オプション（select.py）

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--age` | 年代 (Kid/Teen/20s/30s+) | `20s` |
| `--target` | 相手 (Friend/Partner/Family/Work) | `Friend` |
| `--theme` | テーマ | `共感強化` |
| `--intensity` | 強度 (1-3) | `2` |
| `--reactions-file` | カスタムリアクションファイル | - |
| `--ai-generate` | AIで生成 | `false` |
| `--template` | DB保存済みテンプレート名（例: きみきみさん） | - |
| `--charm` | charm.json パス（emotion_shelf重み付け） | - |
| `--charm-name` | DB保存済みチャームプロファイル名 | - |
| `--output` | 出力パス | (必須) |
| `--config` | config.json パス | 自動検出 |
| `--db` | DBパス | 自動検出 |

## オプション（enhance.py）

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--reactions` | reactions.json パス | (必須) |
| `--character-yaml` | character.yaml パス | - |
| `--charm` | charm.json パス（コンテキスト補強） | - |
| `--charm-name` | DB保存済みチャームプロファイル名（`--charm` より優先） | - |
| `--output` | 出力パス | reactions入力と同じ |
| `--config` | config.json パス | 自動検出 |

## リアクション取得優先順位

1. `--template` が指定 → DB テンプレートから読み込み
2. `--reactions-file` が指定 → ファイルから読み込み
3. `--ai-generate` が指定 → Gemini で24件生成
4. DBマスタが利用可能 → ペルソナに合わせてDB選択（重複排除自動適用）
5. フォールバック → config.json の defaultReactions

## 重複排除

DB選択時、`deduplicate_reactions()` が自動で以下を排除:
- **テキスト重複**: 同じ `text` を持つリアクション
- **ポーズ重複**: 同じ `_pose_id` を持つリアクション

不足分はフォールバックリアクションから自動補完される。

## ファイル構成

```
linestamp-reaction/
├── SKILL.md
├── schemas/
│   └── reactions.schema.json
├── prompts/
│   └── enhance-reaction.md
└── scripts/
    ├── select_reactions.py
    └── enhance.py
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: リアクション選択の妥当性、AI詳細化の品質を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_prompt_stats; import json
   print(json.dumps(get_prompt_stats('reaction_selection'), indent=2, default=str))
   print(json.dumps(get_prompt_stats('reaction_enhance'), indent=2, default=str))
   "
   ```
3. **learnings.md を更新**:
   - 新発見 → 該当セクションにエントリ追加（既存は削除しない）
   - Statistics Snapshot → 最新値で上書き
   - Summary → 新知見を反映して書き直し
   - Change Log → エントリ追加
4. **学ぶことがなかった場合**: Statistics と Change Log の日付のみ更新

### 更新判断

| 状況 | 更新先 |
|------|-------|
| 成功（新パターン） | Prompt Patterns |
| リトライで成功 | Execution Know-How |
| 失敗 | Failure Patterns |
| パラメータ調整で改善 | Parameter Optimization |
| 3回以上確認したルール | Best Practices に昇格 |

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| LINE仕様外のスタンプ個数で出力する | LINE Creators Market が受理しない | 出力件数を 8/16/24/32/40 のいずれかに強制。デフォルト24件 |

## 参照

- ペルソナ設計: `../linestamp/docs/persona.md`
- リアクション定義: `../linestamp/docs/reactions.md`
- 共有ライブラリ: `../linestamp/lib/`
