---
name: linestamp
description: >
  Vertex AIを使用してLINEスタンプ画像パッケージを生成する。
  セッション管理、ポーズ辞書、品質管理、透過修正、トレンド分析も行う。
  LINEスタンプ、スタンプ生成、/linestamp に反応する。
argument-hint: [generate|pose|session|qc|trend|透過修正]
---

# /linestamp - LINEスタンプ制作

## 使い方

`/linestamp` を起動したら、目的を確認して適切なコマンドを実行します。

| 目的 | セクション |
|------|-----------|
| 申請パッケージを作りたい | [生成](#生成-generate) |
| 過去セッションから再生成 | [セッション](#セッション-sessions) |
| ポーズ辞書を管理したい | [ポーズ辞書](#ポーズ辞書-pose) |
| ポーズを対話調整したい | [ポーズ調整](#ポーズ調整-pose-tune) |
| 品質統計を見たい | [品質管理](#品質管理-qc) |
| 透過背景を修正したい | [透過修正](#透過修正-transparentize) |
| トレンドを分析したい | [トレンド](#トレンド-trend) |
| 仕様を確認したい | [reference](./reference/) を参照 |

---

## 生成 (generate)

### 申請パッケージ生成（推奨）
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --package <画像パス> --style <スタイルID>
```
24枚のスタンプ画像 + main.png + tab.png + ZIP を生成します。

### 24枚スタンプのみ
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --eco24 <画像パス> --style <スタイルID>
```

### 既存セッションから再生成
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --session <セッションID>
python .claude/skills/linestamp/scripts/generate_stamp.py --latest
```

### グリッド部分再生成（13〜24など）
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --regenerate-grid <output_dir> --grid-num 2
python .claude/skills/linestamp/scripts/generate_stamp.py --regenerate-grid <output_dir> --grid-num 2 --no-full-body
```

### オプション一覧

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--package` | 申請パッケージ生成 | - |
| `--eco24` | 24枚スタンプのみ | - |
| `--session` | 既存セッションから再生成 | - |
| `--latest` | 最新セッションから再生成 | - |
| `--reactions-file` | カスタムリアクション定義ファイル（JSON/YAML） | - |
| `--output` | 出力ディレクトリ | `./output/linestamp` |

> **MVP品質ロック中** — 以下はMVP_QUALITYで固定されユーザー選択不要:
> style=sd_25, text_mode=deka, outline=bold, 透過=ON, アイテム検出=ON
> 解除するには `generate_stamp.py` の `apply_mvp_quality()` を編集

### 必須確認フロー（生成前に必ず実行）

**デフォルト値があっても、ユーザーの意図を確認せずに生成を開始してはならない。**

以下の順番でユーザーにヒアリングすること：

| # | 確認項目 | 確認内容 | 参照 |
|---|---------|---------|------|
| 1 | 参照画像 | どの画像を使うか（input/内の一覧を提示） | - |
| 2 | ペルソナ（年代） | **Teen** / **20s** / **30s** / **40s+** | [persona.md](./reference/persona.md) |
| 3 | ペルソナ（相手） | **Friend** / **Family** / **Partner** / **Work** | [persona.md](./reference/persona.md) |
| 4 | ペルソナ（テーマ） | 共感強化 / ツッコミ強化 / 褒め強化 / 家族強化 / 応援強化 | [persona.md](./reference/persona.md) |
| 5 | ペルソナ（強度） | 1（控えめ）〜 3（特化） | [persona.md](./reference/persona.md) |
| 6 | セリフ確認 | 年代×相手で語彙が変わる（カスタム希望があれば） | [reactions.md](./reference/reactions.md) |

<!-- MVP品質ロック中: 以下の選択肢は非表示。解除時にコメントを外す
| 7 | スタイル | 頭身・タッチ（sd_25/sd_10/yuru_line等） | [styles.md](./reference/styles.md) |
| 8 | テキストモード | でか文字(deka) / 小さめ(small) / なし(none) | [persona.md](./reference/persona.md) |
| 9 | アウトライン | 太フチ(bold) / 白フチ(white) / なし(none) | - |
-->

**年代×相手の組み合わせで、推奨テーマ・語彙・文字量が自動提案される。**
ペルソナ選択肢の詳細（年代別語彙、テーマ別枠配分、強度設定）は [persona.md](./reference/persona.md) を参照。

**省略可能な場合:**
- ユーザーが「デフォルトでいい」「おまかせ」と明示した場合のみ
- 過去セッションからの再生成（`--session` / `--latest`）

### 事前確認事項

1. **外部API呼び出し回数**: 8枚=1回, 16枚=2回, 24枚=2回, 32枚=3回, 40枚=4回
2. **ADC認証**: `gcloud auth application-default login` が必要

### 実行後確認

1. 生成された画像の一覧を表示
2. grid画像をReadツールでプレビュー
3. ファイルサイズと仕様適合確認

---

## セッション (sessions)

### セッション一覧
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --list
```

### 最新セッションの詳細
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --latest
```

### 特定セッションの詳細
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --session <セッションID>
```

### DB直接参照
```bash
sqlite3 linestamp.db "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 10"
sqlite3 linestamp.db "SELECT * FROM reactions WHERE session_id = '<セッションID>'"
```

---

## ポーズ辞書 (pose)

ポーズ = ジェスチャー（手・体の動き） + 表情（顔の表情・雰囲気） + 雰囲気キーワード

### ポーズ一覧
```bash
python .claude/skills/linestamp/scripts/pose_manager.py list
python .claude/skills/linestamp/scripts/pose_manager.py list 肯定  # カテゴリでフィルタ
```

### ポーズ詳細
```bash
python .claude/skills/linestamp/scripts/pose_manager.py show "いいじゃん（M!LK）"
```

### ポーズ追加（対話形式）
```bash
python .claude/skills/linestamp/scripts/pose_manager.py add
```

### ポーズ検索
```bash
python .claude/skills/linestamp/scripts/pose_manager.py search "顎"
```

### REACTIONS向けエクスポート
```bash
python .claude/skills/linestamp/scripts/pose_manager.py export "いいじゃん（M!LK）"
```

### YAML操作
```bash
python .claude/skills/linestamp/scripts/pose_manager.py yaml-list          # YAMLファイル一覧
python .claude/skills/linestamp/scripts/pose_manager.py yaml-export "OKサイン"  # YAMLにエクスポート
python .claude/skills/linestamp/scripts/pose_manager.py yaml-import poses/new.yaml  # インポート
python .claude/skills/linestamp/scripts/pose_manager.py yaml-sync-to-db    # YAML → DB 同期
python .claude/skills/linestamp/scripts/pose_manager.py yaml-sync-to-yaml  # DB → YAML 同期
```

---

## ポーズ調整 (pose-tune)

対話形式でポーズ定義を調整し、生成プロンプトを最適化します。

### 対話調整を開始
```bash
python .claude/skills/linestamp/scripts/pose_tuner.py
```

### ポーズ一覧
```bash
python .claude/skills/linestamp/scripts/pose_tuner.py list
```

### ポーズ詳細を表示
```bash
python .claude/skills/linestamp/scripts/pose_tuner.py show "OKサイン"
```

### 生成用プロンプトをプレビュー
```bash
python .claude/skills/linestamp/scripts/pose_tuner.py prompt "OKサイン"
```

### 1枚テスト生成（pose_locked用）
```bash
python .claude/skills/linestamp/scripts/pose_tuner.py test "OKサイン" input/ref.jpg
python .claude/skills/linestamp/scripts/pose_tuner.py test "OKサイン" input/ref.jpg \
  --emotion "得意げ" --text "いいね！" --style sd_25 --output output/test.png
```

出力先: `output/pose_test/` （自動生成時）

### 対話調整フロー

1. `python pose_tuner.py` で起動
2. 既存ポーズを選択、新規作成、またはYAMLインポート
3. ジェスチャー・表情・雰囲気・ヒントを編集
4. `s` で保存（YAML + DB 双方向同期）

### YAMLスキーマ

必須フィールド: `name`, `gesture`, `expression`
オプション: `name_en`, `category`, `vibe`, `hints`, `avoid`

テンプレートは `scripts/poses/_template.yaml` を参照。

---

## 品質管理 (qc)

DBの `prompt_results` テーブルと `pose_dictionary` テーブルから統計を取得する。

主な分析観点：
- **プロンプト統計**: `prompt_type` 別の成功率・平均リトライ数
- **失敗パターン**: `failure_reason` 別の頻度
- **ポーズ成功率**: ポーズごとの成功/失敗率

スキーマ詳細は [db-schema.md](./reference/db-schema.md) を参照。

### 品質チェック基準

| チェック項目 | 基準 |
|-------------|------|
| タブサイズ視認性 | 30%以上（96×74px表示面積） |
| 余白 | 10px以上 |
| ファイルサイズ | 1MB以下 |
| 透過PNG | アルファチャンネルあり |

---

## 透過修正 (transparentize)

生成済みスタンプの透過背景を修正します（API呼び出しなし）。

### パッケージ出力の修正
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --fix-transparency <output_dir> --fix-mode package
```

### eco24出力の修正
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --fix-transparency <output_dir> --fix-mode eco24
```

### ZIP再生成をスキップ
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --fix-transparency <output_dir> --fix-mode package --no-fix-zip
```

### モード

| モード | 対象 |
|--------|------|
| `package` | 01.png〜24.png + main.png + tab.png |
| `eco24` | 全 .png（`_` や `grid_` 開始を除く） |
| `all` | フォルダ内の全 .png |

---

## トレンド (trend)

LINE STORE のランキング・メタデータ・特徴を収集して分析します。

### ランキング収集
```bash
python .claude/skills/linestamp/scripts/trend_collector.py collect --max-items 100
```

### URL指定でデータ取得
```bash
python .claude/skills/linestamp/scripts/trend_collector.py fetch <URL> --analyze
python .claude/skills/linestamp/scripts/trend_collector.py fetch <URL> --analyze --analyzer claude
python .claude/skills/linestamp/scripts/trend_collector.py fetch <URL> --analyze --analyzer gemini
```

### 特徴分析
```bash
python .claude/skills/linestamp/scripts/trend_collector.py analyze --product-ids 12345 --analyzer gemini --ai-limit 5
python .claude/skills/linestamp/scripts/trend_collector.py analyze --interactive
```

### 統計表示
```bash
python .claude/skills/linestamp/scripts/trend_collector.py stats
```

### AI分析オプション

| オプション | 説明 |
|-----------|------|
| `--analyzer claude` | Claude Code CLI で画像分析 |
| `--analyzer gemini` | Gemini (Vertex AI) で画像分析 |
| `--ai-limit N` | 商品あたりの分析枚数 |

---

## 参照ドキュメント

| ファイル | 内容 |
|---------|------|
| [persona.md](./reference/persona.md) | **年代×相手×テーマの設計、語彙マトリクス** |
| [styles.md](./reference/styles.md) | スタイル一覧とモディファイア |
| [reactions.md](./reference/reactions.md) | REACTIONS属性定義 |
| [db-schema.md](./reference/db-schema.md) | SQLite スキーマ |
