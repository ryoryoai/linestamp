---
name: linestamp-grid
description: キャラクター画像とリアクションからLINEスタンプ用グリッド画像を生成・分割する
user-invocable: false
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/pipeline-guard.sh grid_pre"
  PostToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/pipeline-guard.sh grid_post"
---

# linestamp-grid

キャラクター画像（character.png）とリアクション定義（reactions.json）から
4x3の12枠グリッド画像を生成し、個別のスタンプ画像に分割する。
linestamp パイプラインの Step 4。

## 使用タイミング

- linestamp オーケストレーターの Step 4 として呼び出される
- グリッド画像の再生成が必要な場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば回避策を適用する
- 特に背景色選択、プロンプト構成、リトライ戦略を確認
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | `character/character.png` | PNG画像 |
| 入力 | `work/character.yaml` | YAML（任意） |
| 入力 | `work/reactions.json` | JSON |
| 出力 | `grids/grid_1.png`, `grid_2.png` | PNG画像 |
| 出力 | `stamps/01-24.png` | PNG画像（raw） |
| 出力 | `work/prompts.json` に追記 | JSON |

## コマンド

### グリッド生成

```bash
python .claude/skills/linestamp-grid/scripts/generate.py \
  --character output/session/character/character.png \
  --reactions output/session/work/reactions.json \
  --config .claude/skills/linestamp/config.json \
  --output output/session/
```

### グリッド分割

```bash
python .claude/skills/linestamp-grid/scripts/split.py \
  --grid output/session/grids/grid_1.png \
  --output output/session/stamps/ \
  --start-index 1
```

### グリッド再生成

```bash
python .claude/skills/linestamp-grid/scripts/regenerate.py \
  --prompts output/session/work/prompts.json \
  --grid-num 2 \
  --output output/session/
```

## ファイル構成

```
linestamp-grid/
├── SKILL.md
├── prompts/
│   └── grid-generation.md
└── scripts/
    ├── generate.py
    ├── split.py
    └── regenerate.py
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: グリッド生成結果（成功/失敗、分割品質、リトライ回数）を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_prompt_stats, get_generation_stats; import json
   print(json.dumps(get_prompt_stats('grid_generation'), indent=2, default=str))
   print(json.dumps(get_generation_stats(), indent=2, default=str))
   "
   ```
3. **learnings.md を更新**:
   - 背景色選択の結果、プロンプトパターン、リトライ戦略 → 該当セクションに追加
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
| LINE仕様外のサイズで分割画像を出力する | 登録時にリジェクトされる | 分割後に 370×320px 以内 + 幅・高さ偶数を検証。違反があれば自動リサイズ |
| 無制限リトライでAPI呼び出しを繰り返す | APIコストが跳ね上がる | リトライ上限を3回に設定。超過時はエラー報告してユーザー判断を仰ぐ |
| 既存 stamps/ ディレクトリを確認なしで上書きする | 前回の生成結果が失われる | stamps/ にファイルが存在する場合、上書き前にユーザー確認を取る |

## 参照

- スタイル定義: `../linestamp/docs/styles.md`
- 共有ライブラリ: `../linestamp/lib/`
