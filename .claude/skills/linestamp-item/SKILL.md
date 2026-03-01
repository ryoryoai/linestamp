---
name: linestamp-item
description: 参照画像からアイテムを検出し、リアクションにマッチングする
user-invocable: false
---

# linestamp-item

参照画像から持ち物・アクセサリーなどのアイテムを検出し、
各リアクションに最適にマッチングする。linestamp パイプラインの Step 3（任意）。

## 使用タイミング

- linestamp オーケストレーターの Step 3 として呼び出される（任意ステップ）
- 参照画像にアイテムが含まれる場合に自動実行

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば回避策を適用する
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | 参照画像 (jpg/png) | 画像ファイル |
| 入力 | `work/reactions.json` | JSON |
| 出力 | `work/items.json` | JSON |
| 出力 | `work/reactions.json` (更新) | JSON |

### items.json スキーマ

```json
[
  {
    "name": "花束",
    "name_en": "flower bouquet",
    "description": "ピンクと白のバラの花束、リボン付き",
    "description_en": "pink and white rose bouquet with ribbon",
    "category": "gift",
    "hold_style": "両手で抱える"
  }
]
```

## コマンド

### アイテム検出

```bash
python .claude/skills/linestamp-item/scripts/detect.py \
  --reference input/photo.jpg \
  --output output/linestamp-20260212/work/items.json
```

### アイテムマッチング

```bash
python .claude/skills/linestamp-item/scripts/match.py \
  --items output/linestamp-20260212/work/items.json \
  --reactions output/linestamp-20260212/work/reactions.json \
  --output output/linestamp-20260212/work/reactions.json
```

## オプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--reference` | 参照画像パス | (必須 for detect) |
| `--items` | items.json パス | (必須 for match) |
| `--reactions` | reactions.json パス | (必須 for match) |
| `--output` | 出力パス | (必須) |
| `--config` | config.json パス | 自動検出 |

## ファイル構成

```
linestamp-item/
├── SKILL.md
├── prompts/
│   ├── detect-items.md
│   └── match-items.md
└── scripts/
    ├── detect.py
    └── match.py
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: アイテム検出精度、マッチングの妥当性を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_prompt_stats; import json
   print(json.dumps(get_prompt_stats('item_detection'), indent=2, default=str))
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
| 検出アイテム数を無制限に出力する | アイテムが多すぎるとスタンプが雑多になる | 検出アイテムは最大10個に制限。超過分は関連度スコア順に切り捨てる |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
