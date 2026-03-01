---
name: linestamp
description: >
  LINEスタンプ制作のオーケストレーター。ヒアリングを行い、各工程スキルを順番に呼び出す。
  自身では画像生成を行わず、サブスキルに委譲する。
  LINEスタンプ、スタンプ生成、/linestamp に反応する。
argument-hint: [generate|pose|session|qc|trend]
---

# /linestamp - LINEスタンプ制作

## 使い方

`/linestamp` を起動したら、目的を確認して適切なワークフローを実行します。

| 目的 | セクション |
|------|-----------|
| 申請パッケージを作りたい | [生成ワークフロー](#生成ワークフロー) |
| 過去セッションから再生成 | [セッション](#セッション) |
| 保存済みプロファイルで生成 | [プロファイル再利用](#プロファイル再利用) |
| ポーズ辞書を管理したい | `/linestamp-pose` |
| 品質統計を見たい | `/linestamp-validate` |
| 透過背景を修正したい | `/linestamp-transparent` |
| トレンドを分析したい | `/linestamp-trend` |
| 仕様を確認したい | [docs/](./docs/) を参照 |

---

## スキル依存グラフ

```
linestamp (Orchestrator)
  │
  ├─ [Step 1a]  linestamp-character   → variations/ (マトリックス12候補) [推奨]
  ├─ [Step 1b]  linestamp-character   → character.png + character.yaml
  ├─ [Step 1.5] linestamp-charm       → charm.json (optional)
  ├─ [Step 2]   linestamp-reaction    → reactions.json (charm-aware)
  ├─ [Step 3]   linestamp-item        → items.json (optional)
  ├─ [Step 4]   linestamp-grid        → grids/ + stamps/01-24.png
  ├─ [Step 5]   linestamp-transparent → transparent/01-24.png
  ├─ [Step 6]   linestamp-validate    → validation-report.json
  ├─ [Step 7]   linestamp-package     → main.png + tab.png + submission.zip
  └─ [Step 8]   linestamp-submit      → submission-metadata.json + browser提出 (optional)
```

独立ユーティリティ:
- `linestamp-pose` - ポーズ辞書管理
- `linestamp-trend` - LINE STOREトレンド分析

---

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、パイプライン全体の運用に反映する
- Pipeline Interaction Patterns を確認し、スキル間の既知の相互作用に注意する
- 該当する Failure Patterns があれば回避策を適用する
- 存在しない場合はスキップ（初回実行後に自動生成）

> **学習サイクル**: 各ステップのスキルは実行前に learnings.md を参照し、
> 実行後に学びを記録する。パイプライン全体完了後、オーケストレーターの
> learnings.md にスキル間の相互作用パターンを記録する。

---

## 生成ワークフロー

### Step 0: ヒアリング

**デフォルト値があっても、ユーザーの意図を確認せずに生成を開始してはならない。**

以下の順番でユーザーにヒアリングすること:

| # | 確認項目 | 確認内容 | 参照 |
|---|---------|---------|------|
| 1 | 参照画像 | どの画像を使うか（input/内の一覧を提示） | - |
| 1.5a | デフォルメ選択 | **マトリックス表示**（12候補: 3 SD比率 × 4 絵柄から選択） / **直接指定**（スタイル確定済み） | config.json `deformation_levels`, `art_styles` |
| 1.5b | 画風スタイル | 直接指定の場合: **reference** / **sd_25** / 他スタイル | config.json `styles` |
| 2 | ペルソナ（年代） | **Kid** / **Teen** / **20s** / **30s+** | [persona.md](./docs/persona.md) |
| 3 | ペルソナ（相手） | **Friend** / **Partner** / **Family** / **Work** | [persona.md](./docs/persona.md) |
| 4 | ペルソナ（テーマ） | 共感強化 / ツッコミ・反応強化 / 褒め強化 / 家族強化 | [persona.md](./docs/persona.md) |
| 5 | ペルソナ（強度） | 1（控えめ）〜 3（特化） | [persona.md](./docs/persona.md) |
| 6 | セリフ確認 | 年代×相手で語彙が変わる（カスタム希望があれば） | [reactions.md](./docs/reactions.md) |
| 7 | チャームモード | **Light**（質問5つ）/ **Deep**（SNS + 質問10問）/ **スキップ** | [linestamp-charm](../linestamp-charm/SKILL.md) |
| 8 | チャーム質問 | 5〜10問の対話（モードに応じて） | charm質問テンプレート |
| 9 | SNSテキスト | Deepモード時: テキストファイルパス（任意） | - |

> **MVP品質ロック中** - style=sd_25, text_mode=deka, outline=bold, 透過=ON, アイテム検出=ON は固定。
> 解除するには `config.json` の `mvpQuality` を編集。

**省略可能な場合:**
- ユーザーが「デフォルトでいい」「おまかせ」と明示した場合のみ
- 過去セッションからの再生成

### Step 0.5: セッション作成と設定の永続化

**ヒアリング完了後、Step 1 の前に必ずセッションを作成し `work/session-config.json` を書き出すこと。**

#### 1. DBセッション作成 & 対話履歴の記録

```bash
# セッション作成 + ヒアリング結果をDBに記録
python3 -c "
import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
from session_manager import Session

s = Session.create(
    image_path='input/photo.jpg',
    style='reference',
    persona_age='Kid',
    persona_target='Friend',
    persona_theme='共感強化',
    persona_intensity=3
)

# ヒアリングで得た回答をDBに記録（実際の回答に合わせて変更）
s.record_qa('hearing', '参照画像', 'input/photo.jpg')
s.record_qa('hearing', 'スタイル', 'reference')
s.record_qa('hearing', 'ペルソナ年代', 'Kid')
s.record_qa('hearing', 'ペルソナ相手', 'Friend')
s.record_qa('hearing', 'ペルソナテーマ', '共感強化')
s.record_qa('hearing', 'ペルソナ強度', '3')
s.record_qa('hearing', 'チャームモード', 'Light')

print(s.session_id)
"
```

> **注意**: `record_qa(step, question_text, answer_text)` の引数はヒアリングの実際の回答に合わせること。
> ユーザーの自由記述もそのまま `answer_text` に記録する。

#### 2. session-config.json の書き出し

これにより、下流スクリプト（generate.py 等）が `--style` フラグなしでも正しいスタイルを自動適用する。

```bash
# work ディレクトリを作成し、session-config.json を書き出す
mkdir -p output/linestamp-XXXXXXXX/work
cat > output/linestamp-XXXXXXXX/work/session-config.json << 'EOF'
{
  "session_id": "20260301_152252",
  "style": "reference",
  "persona": { "age": "Kid", "target": "Friend", "theme": "共感強化", "intensity": 3 },
  "created_at": "2026-02-27T..."
}
EOF
```

> **session_id を必ず含めること。** 下流スキルがDBへの記録（ログ、QA等）に使用する。
> `config_loader.get_session_id(work_dir)` で取得可能。

**スタイル解決の優先順位**: CLI `--style` > `session-config.json` > `sd_25`（フォールバック）

> **重要**: CLIフラグの渡し忘れによる画風消失を防ぐ安全ネット。
> ヒアリングで決定したスタイルを永続化することで、パイプライン中のどのスクリプトからも参照可能になる。

### Step 1a: バリエーション生成 (`linestamp-character`) [推奨]

ユーザーが「見比べたい」「候補を見せて」と言った場合、マトリックスバリエーションを生成する。
3 SD比率 × 4 絵柄 = 12パターンを1回のAPI呼び出しで生成。

```bash
python .claude/skills/linestamp-character/scripts/variations.py \
  --reference input/photo.jpg \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-XXXXXXXX/
```

1. `preview.png` を Read ツールでプレビュー表示
2. ユーザーに番号を選んでもらう
3. 選択した画像を採用:
   ```bash
   cp output/linestamp-XXXXXXXX/character/variations/cells/06.png \
      output/linestamp-XXXXXXXX/character/character.png
   ```
4. `extract.py` でキャラクター特徴抽出（下記 Step 1b と同じ）

### Step 1b: キャラクター生成 (`linestamp-character`) [直接指定]

スタイルが確定済み（「sd_25でいい」「前回と同じ」）の場合、1枚だけ生成する。

```bash
# キャラクター生成
python .claude/skills/linestamp-character/scripts/generate.py \
  --reference input/photo.jpg \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-XXXXXXXX/

# 特徴抽出
python .claude/skills/linestamp-character/scripts/extract.py \
  --character output/linestamp-XXXXXXXX/character/character.png \
  --output output/linestamp-XXXXXXXX/work/character.yaml

# 特徴抽出（ユーザーが外見を指定した場合 → --overrides で上書き）
# ヒアリングで髪型・服装等の指摘があった場合、必ず --overrides を付ける
python .claude/skills/linestamp-character/scripts/extract.py \
  --character output/linestamp-XXXXXXXX/character/character.png \
  --overrides '{"hair": {"style": "long straight flowing back"}}' \
  --output output/linestamp-XXXXXXXX/work/character.yaml
```

> **重要**: ヒアリングでユーザーが外見（髪型、服装等）を明示的に補正した場合、
> 必ず `--overrides` で character.yaml に反映すること。
> AI抽出は画像から推定するため、ユーザーの意図と異なる場合がある。

**出力**: `character/character.png`, `work/character.yaml`

### Step 1.5: チャームポイント抽出 (`linestamp-charm`) [optional]

三層入力（外見 + SNS + 対話）からチャームポイントを抽出し、人格プロファイルを生成する。
スキップした場合、Step 2 以降は従来通りの動作。

```bash
# チャーム質問の実施（オーケストレーターが対話で回答を収集）
# 回答を answers.json として保存

# チャーム分析（Light モード、人物名でDB保存）
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers output/linestamp-XXXXXXXX/work/answers.json \
  --character-yaml output/linestamp-XXXXXXXX/work/character.yaml \
  --person-name "田中太郎" \
  --session-id XXXXXXXX \
  --output output/linestamp-XXXXXXXX/work/charm.json

# チャーム分析（Deep モード - SNSテキスト付き）
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers output/linestamp-XXXXXXXX/work/answers.json \
  --character-yaml output/linestamp-XXXXXXXX/work/character.yaml \
  --sns-text input/sns_posts.txt \
  --mode deep \
  --person-name "田中太郎" \
  --session-id XXXXXXXX \
  --output output/linestamp-XXXXXXXX/work/charm.json

# 既存チャーム読み込み（同じ人物の再生成時、分析スキップ）
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers /dev/null \
  --load-charm "田中太郎" \
  --output output/linestamp-XXXXXXXX/work/charm.json

# 既存チャーム更新（追加情報で洗練）
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers output/linestamp-XXXXXXXX/work/new_answers.json \
  --update-charm "田中太郎" \
  --update-note "共感をもっと強めに" \
  --output output/linestamp-XXXXXXXX/work/charm.json
```

**出力**: `work/charm.json`（チャームプロファイル）

### Step 2: リアクション選択・詳細化 (`linestamp-reaction`)

ペルソナ設定に基づいて24件のリアクションを選択し、AI詳細化する。

```bash
# リアクション選択（charm.jsonがある場合は--charmを追加）
python .claude/skills/linestamp-reaction/scripts/select_reactions.py \
  --age 20s --target Friend --theme 共感強化 \
  --db linestamp.db \
  --charm output/linestamp-XXXXXXXX/work/charm.json \
  --output output/linestamp-XXXXXXXX/work/reactions.json

# AI詳細化（charm.jsonがある場合は--charmを追加）
python .claude/skills/linestamp-reaction/scripts/enhance.py \
  --reactions output/linestamp-XXXXXXXX/work/reactions.json \
  --character-yaml output/linestamp-XXXXXXXX/work/character.yaml \
  --charm output/linestamp-XXXXXXXX/work/charm.json \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-XXXXXXXX/work/reactions.json
```

**出力**: `work/reactions.json`

### Step 3: アイテム検出・マッチング (`linestamp-item`) [optional]

参照画像から持ち物や小物を検出し、リアクションに割り当てる。

```bash
# アイテム検出
python .claude/skills/linestamp-item/scripts/detect.py \
  --reference input/photo.jpg \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-XXXXXXXX/work/items.json

# リアクションへのマッチング
python .claude/skills/linestamp-item/scripts/match.py \
  --items output/linestamp-XXXXXXXX/work/items.json \
  --reactions output/linestamp-XXXXXXXX/work/reactions.json \
  --output output/linestamp-XXXXXXXX/work/reactions.json
```

**出力**: `work/items.json`, 更新された `work/reactions.json`

### Step 4: グリッド画像生成・分割 (`linestamp-grid`)

キャラクターとリアクションからグリッド画像を生成し、個別スタンプに分割する。

```bash
# グリッド生成 (12枚×2回 = 24枚)
python .claude/skills/linestamp-grid/scripts/generate.py \
  --character output/linestamp-XXXXXXXX/character/character.png \
  --reactions output/linestamp-XXXXXXXX/work/reactions.json \
  --character-yaml output/linestamp-XXXXXXXX/work/character.yaml \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-XXXXXXXX/

# グリッド分割
python .claude/skills/linestamp-grid/scripts/split.py \
  --grid output/linestamp-XXXXXXXX/grids/grid_1.png \
  --output output/linestamp-XXXXXXXX/stamps/ --start-index 1

python .claude/skills/linestamp-grid/scripts/split.py \
  --grid output/linestamp-XXXXXXXX/grids/grid_2.png \
  --output output/linestamp-XXXXXXXX/stamps/ --start-index 13
```

**出力**: `grids/grid_1.png`, `grids/grid_2.png`, `stamps/01.png`〜`stamps/24.png`

### Step 5: 背景透過 (`linestamp-transparent`)

スタンプ画像の背景を透過処理する。

```bash
python .claude/skills/linestamp-transparent/scripts/process.py \
  --input output/linestamp-XXXXXXXX/stamps/ \
  --output output/linestamp-XXXXXXXX/transparent/
```

**出力**: `transparent/01.png`〜`transparent/24.png`

### Step 6: 品質チェック (`linestamp-validate`)

透過済みスタンプの品質を検証する。

```bash
python .claude/skills/linestamp-validate/scripts/check.py \
  --input output/linestamp-XXXXXXXX/transparent/ \
  --output output/linestamp-XXXXXXXX/work/validation-report.json
```

**出力**: `work/validation-report.json`

**失敗時のリカバリ:**
- 透過問題 → Step 5 に戻って `linestamp-transparent` で再処理
- グリッド品質問題 → Step 4 に戻って `linestamp-grid` で再生成
  ```bash
  python .claude/skills/linestamp-grid/scripts/regenerate.py \
    --output output/linestamp-XXXXXXXX/ --grid-num 2
  ```

### Step 7: パッケージ生成 (`linestamp-package`)

main画像、tab画像、submission.zipを生成する。

```bash
python .claude/skills/linestamp-package/scripts/package.py \
  --input output/linestamp-XXXXXXXX/transparent/ \
  --output output/linestamp-XXXXXXXX/
```

**出力**: `main.png`, `tab.png`, `submission.zip`

### Step 8: LINE提出 (`linestamp-submit`) [optional]

LINE Creators Market へのスタンプ申請を Playwright CLI で自動化する。
ユーザーが「申請」「提出」を希望した場合のみ実行。

```bash
# メタデータ生成
python .claude/skills/linestamp-submit/scripts/generate_metadata.py \
  --session-dir output/linestamp-XXXXXXXX/
```

**出力**: `work/submission-metadata.json`

この後はブラウザ自動化フローに移行。詳細は `linestamp-submit/SKILL.md` を参照。

**フロー概要**:
1. Playwright セッション (`line_creators`) で creator.line.me を開く
2. 未ログインならユーザーに手動ログインを依頼
3. メタデータをユーザーに確認 → フォーム入力
4. main.png, tab.png, 01-24.png を順次アップロード
5. 審査リクエストボタンは **手動** で押してもらう

### 実行後確認

1. 生成された画像の一覧を表示
2. grid画像をReadツールでプレビュー
3. ファイルサイズと仕様適合確認
4. `submission.zip` の完全性確認（24枚 + main + tab）

### 実行後学習（パイプライン完了後）

**パイプライン全体完了後、以下の手順で `./learnings.md` を更新すること。**

1. **パイプライン全体の結果評価**:
   - 各ステップの成功/失敗、リトライ回数
   - エンドツーエンドの所要時間
   - 最終成果物の品質
2. **スキル間の相互作用を確認**:
   - 上流の出力が下流にどう影響したか
   - ステップ間の手戻り（リカバリ）が発生したか
   - ヒアリング内容が最終品質にどう反映されたか
3. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_generation_stats, get_prompt_stats; import json
   print('=== Generation Stats ===')
   print(json.dumps(get_generation_stats(), indent=2, default=str))
   print('=== Pipeline Stats ===')
   for step in ['character_generation','reaction_selection','item_detection','grid_generation','transparency','package']:
       stats = get_prompt_stats(step)
       if stats: print(f'{step}: {json.dumps(stats, default=str)}')
   "
   ```
4. **learnings.md を更新**:
   - スキル間の相互作用 → Pipeline Interaction Patterns に追加
   - パイプライン運用の知見 → Execution Know-How に追加
   - 新発見 → 該当セクションにエントリ追加（既存は削除しない）
   - Statistics Snapshot → 最新値で上書き
   - Summary → 新知見を反映して書き直し
   - Change Log → エントリ追加
5. **学ぶことがなかった場合**: Statistics と Change Log の日付のみ更新

#### 更新判断

| 状況 | 更新先 |
|------|-------|
| スキル間の影響パターン | Pipeline Interaction Patterns |
| 成功（新パターン） | Prompt Patterns |
| リトライ・手戻りで成功 | Execution Know-How |
| パイプライン失敗 | Failure Patterns |
| ヒアリング調整で改善 | Parameter Optimization |
| 3回以上確認したルール | Best Practices に昇格 |

---

## 作業ディレクトリ構造

```
output/linestamp-{YYYYMMDD_HHMMSS}/
├── work/                          # 中間ファイル (JSON契約)
│   ├── session-config.json        # Step 0.5 → 全スキル (session_id, style, persona)
│   ├── character.yaml             # Step 1 → Step 1.5, 4
│   ├── answers.json               # Step 1.5 (対話回答)
│   ├── charm.json                 # Step 1.5 → Step 2 (optional)
│   ├── reactions.json             # Step 2,3 → Step 4
│   ├── items.json                 # Step 3
│   ├── prompts.json               # 全スキルが追記 (再現性担保)
│   └── validation-report.json     # Step 6
├── character/
│   ├── character.png              # Step 1 (採用画像)
│   └── variations/                # Step 1a (マトリックスバリエーション)
│       ├── grid.png               # API生成の4x3グリッド原画
│       ├── preview.png            # 番号+軸ラベル付きプレビュー
│       ├── plan.json              # セル割り当て計画
│       └── cells/
│           ├── 01.png ... 12.png  # 個別セル画像
├── grids/
│   ├── grid_1.png                 # Step 4
│   └── grid_2.png                 # Step 4
├── stamps/
│   ├── 01.png ... 24.png          # Step 4 (raw, with bg)
├── transparent/
│   ├── 01.png ... 24.png          # Step 5
├── main.png                       # Step 7
├── tab.png                        # Step 7
└── submission.zip                 # Step 7
```

---

## セッション

### セッション管理（レガシー）

既存セッションの参照にはDBを直接使用:

```bash
sqlite3 linestamp.db "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10"
sqlite3 linestamp.db "SELECT * FROM reactions WHERE session_id = '<セッションID>'"
```

### グリッド部分再生成

```bash
python .claude/skills/linestamp-grid/scripts/regenerate.py \
  --output output/linestamp-XXXXXXXX/ --grid-num 2
```

---

## プロファイル再利用

保存済みのチャームプロファイル・リアクションテンプレートを使って、ヒアリングなしで高速に生成できる。

### 保存済みプロファイル一覧

```bash
sqlite3 linestamp.db "SELECT id, person_name, created_at FROM charm_profiles ORDER BY created_at DESC"
sqlite3 linestamp.db "SELECT id, name, age, target, theme, created_at FROM reaction_templates ORDER BY created_at DESC"
```

### プロファイル再利用で生成

Step 2 のリアクション選択・詳細化で `--charm-name` と `--template` を使う:

```bash
# テンプレートから24件ロード（選択スキップ）
python .claude/skills/linestamp-reaction/scripts/select_reactions.py \
  --template きみきみさん \
  --output output/linestamp-XXXXXXXX/work/reactions.json

# チャームプロファイルで詳細化（成熟度コンテキスト自動適用）
python .claude/skills/linestamp-reaction/scripts/enhance.py \
  --reactions output/linestamp-XXXXXXXX/work/reactions.json \
  --character-yaml output/linestamp-XXXXXXXX/work/character.yaml \
  --charm-name きみきみさん \
  --output output/linestamp-XXXXXXXX/work/reactions.json
```

### 優先順位

1. `--template` 指定 → DB テンプレートをそのまま使用
2. `--reactions-file` 指定 → ファイルから読み込み
3. `--ai-generate` → Gemini で生成
4. DBマスタ → ペルソナに合わせて選択

### プロファイル保存

リアクションを手動キュレーションした後に保存する:

```python
import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
from database import save_charm_profile, save_template
import json

# チャーム保存
with open('work/charm.json') as f:
    charm = json.load(f)
save_charm_profile("名前", charm)

# テンプレート保存
with open('work/reactions.json') as f:
    reactions = json.load(f)
save_template("名前", reactions, age="30s+", target="Friend", theme="共感強化", intensity=2)
```

---

## 外部スキル参照テーブル

| スキル | 役割 | 入力 | 出力 |
|--------|------|------|------|
| `linestamp-character` | キャラクター生成・特徴抽出 | 参照画像 | character.png, character.yaml |
| `linestamp-charm` | チャームポイント抽出 | 対話回答, character.yaml, SNSテキスト | charm.json |
| `linestamp-reaction` | リアクション選択・詳細化 | ペルソナ設定, charm.json | reactions.json |
| `linestamp-item` | アイテム検出・マッチング | 参照画像, reactions.json | items.json, reactions.json更新 |
| `linestamp-grid` | グリッド生成・分割 | character.png, reactions.json | grids/, stamps/ |
| `linestamp-transparent` | 背景透過 | stamps/ | transparent/ |
| `linestamp-validate` | 品質チェック | transparent/ | validation-report.json |
| `linestamp-package` | パッケージ生成 | transparent/ | main.png, tab.png, submission.zip |
| `linestamp-submit` | LINE提出 (optional) | submission.zip, charm.json | submission-metadata.json |
| `linestamp-pose` | ポーズ辞書管理 | CLI | YAML, DB |
| `linestamp-trend` | トレンド分析 | CLI | DB, 統計 |

---

## 共有リソース

| リソース | パス | 説明 |
|----------|------|------|
| config.json | `.claude/skills/linestamp/config.json` | スタイル、モディファイア、MVP品質設定 |
| database.py | `.claude/skills/linestamp/lib/database.py` | DB操作共有モジュール |
| session_manager.py | `.claude/skills/linestamp/lib/session_manager.py` | セッション管理 |
| config_loader.py | `.claude/skills/linestamp/lib/config_loader.py` | config.json読み込み |
| image_utils.py | `.claude/skills/linestamp/lib/image_utils.py` | Vertex AIクライアント、画像ユーティリティ |

---

## 参照ドキュメント

| ファイル | 内容 |
|---------|------|
| [persona.md](./docs/persona.md) | 年代×相手×テーマの設計、語彙マトリクス |
| [styles.md](./docs/styles.md) | スタイル一覧とモディファイア |
| [reactions.md](./docs/reactions.md) | REACTIONS属性定義 |
| [db-schema.md](./docs/db-schema.md) | SQLite スキーマ |

---

## エージェント

| エージェント | 用途 |
|-------------|------|
| `linestamp-generator` | フルパイプライン実行 (Step 1-7) |
| `linestamp-qc` | 品質チェック + 透過修正のループ |

---

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| パイプラインのステップをスキップする | 特に validate, transparent を飛ばすと品質未達のまま提出される | 各ステップの結果をユーザーに見せてから次に進む。QC は省略不可 |
| 他セッションの output/ を削除・上書きする | 他のスタンプセットの成果物が失われる | 出力は常に `output/linestamp-XXXXXXXX/` 配下。他セッションのディレクトリには触れない |
| input/ 内のファイルを削除・移動・上書きする | ユーザー提供の原本を保護 | input/ は read-only 扱い。加工結果は全て output/ 配下に書き出す |

## 事前確認事項

- **ADC認証**: `gcloud auth application-default login` が必要
- **外部API呼び出し**: grid生成で2回 (12枚×2)、character生成で1回
- **rembg**: 透過処理に必要 (`pip install rembg`)
