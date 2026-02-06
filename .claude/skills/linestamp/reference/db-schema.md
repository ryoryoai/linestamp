# DB_SCHEMA（SQLite）

linestamp.db のテーブル定義。
詳細は `.claude/skills/linestamp/scripts/database.py` を参照。

## テーブル一覧

| テーブル | 用途 |
|---------|------|
| sessions | セッション管理（画像・スタイル・ペルソナ設定） |
| reactions | セッションごとのREACTIONS |
| pose_dictionary | ポーズ辞書（ジェスチャー＋表情） |
| prompt_results | プロンプト実行結果（品質管理） |
| reaction_templates | REACTIONSテンプレート |
| outputs | 生成出力履歴 |

---

## sessions

セッション管理テーブル。

| カラム | 型 | 説明 |
|--------|-----|------|
| id | TEXT PRIMARY KEY | セッションID（例: 20240127_143052） |
| created_at | DATETIME | 作成日時 |
| image_path | TEXT | 参照画像パス |
| style | TEXT | スタイルID |
| text_mode | TEXT | テキストモード（deka/small/none） |
| outline | TEXT | アウトライン（bold/white/none） |
| persona_age | TEXT | 年代（Kid/Teen/20s/30s+） |
| persona_target | TEXT | 相手（Friend/Partner/Family/Work） |
| persona_theme | TEXT | テーマ |
| persona_intensity | INTEGER | 強度（0-3） |
| status | TEXT | ステータス（draft/completed/failed） |
| output_dir | TEXT | 出力ディレクトリ |
| notes | TEXT | メモ |

---

## reactions

セッションごとのREACTIONS。

| カラム | 型 | 説明 |
|--------|-----|------|
| session_id | TEXT | セッションID（FK） |
| idx | INTEGER | インデックス（0-23） |
| reaction_id | TEXT | REACTIONS ID |
| emotion | TEXT | 表情の説明 |
| pose | TEXT | ポーズの説明 |
| text | TEXT | スタンプ文字 |
| pose_locked | BOOLEAN | ポーズ固定フラグ |
| outfit | TEXT | 衣装指定 |
| item | TEXT | 持ち物（JSON） |

PRIMARY KEY: (session_id, idx)

---

## pose_dictionary

ポーズ辞書（ジェスチャー＋表情）。

| カラム | 型 | 説明 |
|--------|-----|------|
| name | TEXT PRIMARY KEY | ポーズ名（日本語） |
| name_en | TEXT | ポーズ名（英語） |
| gesture_ja | TEXT | ジェスチャー（日本語） |
| gesture_en | TEXT | ジェスチャー（英語） |
| expression_ja | TEXT | 表情（日本語） |
| expression_en | TEXT | 表情（英語） |
| vibe | TEXT | 雰囲気キーワード |
| prompt_ja | TEXT NOT NULL | 統合プロンプト（日本語） |
| prompt_en | TEXT | 統合プロンプト（英語） |
| category | TEXT | カテゴリ（肯定/否定/愛情/応援/喜び/礼儀/照れ/反応/その他） |
| success_count | INTEGER | 成功回数 |
| failure_count | INTEGER | 失敗回数 |
| last_used | DATETIME | 最終使用日時 |
| created_at | DATETIME | 作成日時 |
| notes | TEXT | メモ |

---

## prompt_results

プロンプト実行結果（品質管理）。

| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PRIMARY KEY | 自動採番 |
| session_id | TEXT | セッションID（FK） |
| prompt_type | TEXT | プロンプト種別 |
| prompt_hash | TEXT | プロンプトハッシュ |
| prompt_text | TEXT | プロンプト全文 |
| success | BOOLEAN | 成功フラグ |
| retry_count | INTEGER | リトライ回数 |
| failure_reason | TEXT | 失敗理由 |
| execution_time_ms | INTEGER | 実行時間（ミリ秒） |
| created_at | DATETIME | 作成日時 |

---

## reaction_templates

REACTIONSテンプレート。

| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PRIMARY KEY | 自動採番 |
| name | TEXT | テンプレート名 |
| persona_age | TEXT | 年代 |
| persona_target | TEXT | 相手 |
| persona_theme | TEXT | テーマ |
| reactions_json | TEXT NOT NULL | REACTIONS（JSON） |
| usage_count | INTEGER | 使用回数 |
| total_rating | INTEGER | 累計評価 |
| rating_count | INTEGER | 評価回数 |
| created_at | DATETIME | 作成日時 |
| updated_at | DATETIME | 更新日時 |

---

## outputs

生成出力履歴。

| カラム | 型 | 説明 |
|--------|-----|------|
| id | INTEGER PRIMARY KEY | 自動採番 |
| session_id | TEXT | セッションID（FK） |
| grid_num | INTEGER | グリッド番号 |
| output_path | TEXT | 出力パス |
| success | BOOLEAN | 成功フラグ |
| aspect_ratio | REAL | アスペクト比 |
| validation_result | TEXT | バリデーション結果 |
| created_at | DATETIME | 作成日時 |
