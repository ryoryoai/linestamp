# LINEスタンプ生成プロジェクト

## 概要
Vertex AI (gemini-3-pro-image-preview) を使用してLINEスタンプ用画像を生成するプロジェクト。

## 環境要件
- Python 3.10+
- Google Cloud SDK (gcloud)
- ADC認証済み (`gcloud auth application-default login`)

## LINEスタンプ仕様
| 種類 | サイズ |
|------|--------|
| スタンプ画像 | 最大 370×320px |
| メイン画像 | 240×240px |
| タブ画像 | 96×74px |
| 形式 | PNG（背景透過） |

## 使い方

### スキル呼び出し（推奨）
```bash
/linestamp
```

### 直接実行
```bash
python .claude/skills/linestamp/scripts/generate_stamp.py --package input/参照画像.jpg --output output/submission
```

## ディレクトリ構成
```
linestamp/
├── CLAUDE.md
├── .claude/
│   └── skills/
│       └── linestamp/
│           ├── SKILL.md
│           ├── scripts/
│           │   ├── generate_stamp.py
│           │   ├── database.py
│           │   ├── session_manager.py
│           │   ├── pose_manager.py
│           │   ├── pose_tuner.py
│           │   ├── trend_collector.py
│           │   ├── image_analyzer.py
│           │   └── agent/
│           ├── poses/
│           ├── reference/
│           └── requirements.txt
├── input/
├── output/
└── requirements.txt
```
