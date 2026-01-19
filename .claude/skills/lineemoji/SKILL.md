---
name: lineemoji
description: LINE絵文字用画像をVertex AIで生成。「絵文字作成」「絵文字生成」「LINE絵文字」時に使用。/lineemoji または /emoji でも起動可能。
---

# /lineemoji - LINE絵文字画像生成

## 概要
Vertex AI の gemini-3-pro-image-preview を使用してLINE絵文字用の画像を生成します。
対話形式でステップバイステップに進行します。

## トリガー
- `/lineemoji`
- `/emoji`
- 「絵文字を作って」「LINE絵文字生成」

---

## LINE絵文字仕様

| 種類 | サイズ | 必須 |
|------|--------|------|
| 絵文字画像 | 180×180px | 8/16/24/32/40枚 |
| タブ画像 | 96×74px | 1枚 |
| 形式 | PNG（背景透過） | - |
| 余白 | **不要** | - |
| ファイル名 | 001～040（3桁） | - |

---

## ステップバイステップ実行フロー

### Step 1: 参照画像の指定

AskUserQuestion で参照画像のパスを確認：

```
質問: 参照画像（キャラクターの写真やイラスト）のパスを教えてください
例: input/my_character.jpg
```

---

### Step 2: ちびキャラスタイルの選択

| スタイルID | 名前 | 説明 |
|-----------|------|------|
| `face_only` | **顔だけタイプ（推奨）** | 顔だけ。絵文字に最適 |
| `mini_face` | **ミニ顔** | 顔メインで小さなボディ付き |
| `ultra_sd` | **超SD** | 約1頭身。丸み重視 |
| `standard_sd` | **基本SD** | 約2〜2.5頭身 |
| `puni` | **ぷにキャラ型** | 丸み強調 |

---

### Step 3: 絵文字枚数の選択

| 枚数 | グリッド | API呼び出し |
|------|----------|-------------|
| 8枚 | 2×4 | 1回 |
| 16枚 | 4×4 | 1回 |
| 24枚 | 12×2回 | 2回 |
| 32枚 | 16×2回 | 2回 |
| **40枚（推奨）** | 20×2回 | 2回 |

---

### Step 4: 表情バリエーション確認

#### 40種類の絵文字表情（テキストなし）

**基本表情（1-8）**
| ID | 説明 |
|----|------|
| smile | 満面の笑み |
| laugh | 大笑い |
| wink | ウインク |
| love | ハート目 |
| happy | 幸せそう |
| grin | ニカッと笑う |
| blush | 照れ笑い |
| relieved | ほっとした顔 |

**ポジティブ感情（9-16）**
| ID | 説明 |
|----|------|
| excited | 大興奮 |
| sparkle | キラキラ目 |
| proud | ドヤ顔 |
| celebrate | お祝い |
| starstruck | 感動 |
| yay | やったー |
| thumbsup | いいね |
| peace | ピース |

**ネガティブ感情（17-24）**
| ID | 説明 |
|----|------|
| sad | 悲しい |
| cry | 泣き顔 |
| sob | 号泣 |
| angry | 怒り顔 |
| pout | ふくれっ面 |
| frustrated | イライラ |
| disappointed | がっかり |
| worried | 心配 |

**驚き・困惑（25-32）**
| ID | 説明 |
|----|------|
| shocked | 驚き |
| surprised | びっくり |
| scared | 怖い |
| confused | 混乱 |
| thinking | 考え中 |
| suspicious | 疑い |
| nervous | 緊張 |
| dizzy | 目が回る |

**特殊表情（33-40）**
| ID | 説明 |
|----|------|
| sleepy | 眠そう |
| sick | 体調不良 |
| cool | クール |
| nerd | メガネ・知的 |
| hungry | お腹すいた |
| stuffed | お腹いっぱい |
| kiss | 投げキス |
| hug | ハグ |

---

### Step 5: 生成実行

#### コマンドラインオプション

```bash
# 40枚の申請パッケージ生成（推奨）
python {SKILL_DIR}/generate_emoji.py --package <画像パス> --count 40 --style face_only --output ./output/lineemoji

# 絵文字のみ生成
python {SKILL_DIR}/generate_emoji.py --generate <画像パス> --count 40 --style face_only --output ./output/lineemoji
```

| オプション | 説明 | 例 |
|-----------|------|-----|
| `--package` | 申請パッケージ生成 | `--package input/photo.jpg` |
| `--generate`, `-g` | 絵文字のみ生成 | `-g input/photo.jpg` |
| `--count`, `-c` | 枚数（8/16/24/32/40） | `--count 40` |
| `--style` | ちびキャラスタイル | `--style face_only` |
| `--output`, `-o` | 出力ディレクトリ | `-o ./output/myemoji` |
| `--project` | GCPプロジェクトID | `--project my-project` |

---

### Step 6: 結果確認

生成完了後、以下を報告：

1. **生成された画像の一覧**
2. **プレビュー表示**（grid画像をReadツールで表示）
3. **次のアクション提案**

---

## 出力ファイル構成

```
output/lineemoji/
├── _character.png      # 生成されたキャラクター
├── _grid_1.png         # グリッド画像1
├── _grid_2.png         # グリッド画像2（40枚の場合）
├── _prompts.json       # 使用したプロンプト
├── tab.png             # タブ画像 (96×74px)
├── 001.png ~ 040.png   # 絵文字画像 (180×180px)
└── submission.zip      # 申請用パッケージ
```

---

## 注意事項
- ADC認証が必要: `gcloud auth application-default login`
- 絵文字は180pxと小さいため、**太線・シンプル**なデザインが重要
- **テキストなし**（スタンプとの違い）

## トラブルシューティング

| エラー | 解決方法 |
|--------|----------|
| 認証エラー | `gcloud auth application-default login` を実行 |
| 絵文字が見づらい | `--style face_only` で顔だけタイプを使用 |
