# linestamp - LINEスタンプ生成スキル

Vertex AI (Gemini) を使用してLINEスタンプ用画像を生成するClaude Codeスキル。

## インストール

### 1. スキルフォルダをコピー

```bash
# グローバルスキルとしてインストール
cp -r linestamp ~/.claude/skills/

# または、プロジェクト固有スキルとしてインストール
cp -r linestamp .claude/skills/
```

### 2. 依存関係をインストール

```bash
pip install -r ~/.claude/skills/linestamp/requirements.txt
```

### 3. Google Cloud認証

```bash
gcloud auth application-default login
```

## 使い方

Claude Codeで以下のコマンドを実行:

```
/linestamp
```

対話形式で以下を選択:
1. 参照画像のパス
2. ちびキャラスタイル（10種類）
3. スタンプ枚数（8/16/24/32/40枚）
4. リアクションセット
5. 出力形式

## 出力ファイル

```
./output/linestamp_YYYYMMDD_HHMMSS/
├── 01.png〜24.png  # スタンプ画像
├── main.png        # メイン画像 (240×240px)
├── tab.png         # タブ画像 (96×74px)
├── grid_1.png      # グリッド画像（参考用）
├── grid_2.png
└── submission.zip  # 申請用パッケージ
```

## LINEスタンプ仕様

| 種類 | サイズ |
|------|--------|
| スタンプ画像 | 最大 370×320px |
| メイン画像 | 240×240px |
| タブ画像 | 96×74px |
| 形式 | PNG |

## 必要条件

- Python 3.10+
- Google Cloud SDK
- Vertex AI API有効化済み

## ライセンス

MIT
