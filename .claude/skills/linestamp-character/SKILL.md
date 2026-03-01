---
name: linestamp-character
description: 参照画像からLINEスタンプ用キャラクターを生成し、特徴をYAMLで抽出する
user-invocable: false
---

# linestamp-character

参照写真からちびキャラスタイルのキャラクター画像を生成し、特徴をYAML形式で抽出する。
linestamp パイプラインの最初のステップ。

## 使用タイミング

- linestamp オーケストレーターの Step 1 として呼び出される
- 参照画像からキャラクター画像を新規生成する場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば回避策を適用する
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | 参照画像 (jpg/png) | 画像ファイル |
| 出力 | `character/character.png` | PNG画像 |
| 出力 | `work/character.yaml` | YAMLファイル |

### character.yaml スキーマ

```yaml
version: "1.0"
extracted_at: "2026-02-12T..."
source_image: "input/photo.jpg"
face:
  shape: "oval"
  skin_tone: "fair"
hair:
  color: "black"
  style: "short spiky"
  bangs: "none"
eyes:
  color: "dark brown"
  shape: "large round"
  style: "anime sparkle"
outfit:
  type: "casual"
  primary_color: "blue"
  secondary_color: "white"
  details: "T-shirt with logo"
body:
  build: "average"
  age_impression: "child"
accessories: []
distinctive_features: []
```

## コマンド

### バリエーション生成 (推奨)

12パターン（3 SD比率 × 4 絵柄）のマトリックスを生成し、ユーザーに選んでもらう。

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
4. `extract.py` でキャラクター特徴抽出

**出力構造:**
```
character/
├── character.png              ← 最終採用画像（選択後にコピー）
└── variations/
    ├── grid.png               ← API生成の4x3グリッド原画
    ├── preview.png            ← 番号+軸ラベル付きマトリックスプレビュー
    ├── plan.json              ← セル割り当て計画（再現性用）
    └── cells/
        ├── 01.png ... 12.png  ← 個別セル画像
```

### キャラクター生成 (直接指定)

スタイルが確定している場合は1枚だけ生成する。

```bash
python .claude/skills/linestamp-character/scripts/generate.py \
  --reference input/photo.jpg \
  --style sd_25 \
  --config .claude/skills/linestamp/config.json \
  --output output/linestamp-20260212/
```

### 特徴抽出（既存キャラクター画像から）

```bash
python .claude/skills/linestamp-character/scripts/extract.py \
  --character output/linestamp-20260212/character/character.png \
  --output output/linestamp-20260212/work/character.yaml
```

### 特徴抽出 + ユーザー指定の上書き

ヒアリングで得た情報がAI判定と異なる場合、`--overrides` で上書きする。
**オーケストレーターはヒアリングで外見に関する指摘を受けた場合、必ずこのオプションを使うこと。**

```bash
# 例: 髪型をユーザー指定で上書き
python .claude/skills/linestamp-character/scripts/extract.py \
  --character output/linestamp-20260212/character/character.png \
  --overrides '{"hair": {"style": "long straight flowing back"}}' \
  --output output/linestamp-20260212/work/character.yaml
```

## オプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--reference` | 参照画像パス | (必須) |
| `--style` | スタイルID | `sd_25` |
| `--config` | config.json パス | 自動検出 |
| `--output` | 出力ベースディレクトリ | `./output/` |
| `--project` | GCPプロジェクトID | 環境変数 or config |

## ファイル構成

```
linestamp-character/
├── SKILL.md
├── prompts/
│   ├── generate-character.md
│   └── extract-features.md
└── scripts/
    ├── generate.py       # 1枚生成（スタイル直接指定）
    ├── variations.py     # マトリックスバリエーション生成
    └── extract.py        # 特徴抽出
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: キャラクター生成の成功/失敗、類似度、スタイル適合性を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_prompt_stats; import json
   print(json.dumps(get_prompt_stats('character_generation'), indent=2, default=str))
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
| 参照画像をキャラクター生成以外の目的で使用・外部送信する | プライバシー保護 | Vertex AI への送信のみ許可。ログやDBに画像データを保存しない |
| 生成画像が写実的すぎる状態でパイプラインを進める | 肖像権リスク | SD比率が適用されていることをユーザーに確認。写実的な場合はスタイル変更を提案 |
| input/ 内の参照画像を削除・移動・上書きする | ユーザーの原本を保護 | input/ は read-only 扱い。出力は全て output/ 配下に書き出す |

## 参照

- スタイル定義: `../linestamp/docs/styles.md`
- 共有ライブラリ: `../linestamp/lib/`
