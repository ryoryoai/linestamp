---
name: linestamp-validate
description: スタンプ画像の品質チェック（サイズ・透過・視認性）を実行する
user-invocable: false
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/pipeline-guard.sh validate_pre"
---

# linestamp-validate

透過済みスタンプ画像のLINE仕様適合性を検証し、レポートを生成する。
linestamp パイプラインの Step 6。

## 使用タイミング

- linestamp オーケストレーターの Step 6 として呼び出される
- 品質問題の調査が必要な場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば、よくある品質問題の傾向を把握する
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | `transparent/*.png` | PNG画像 |
| 出力 | `work/validation-report.json` | JSON |

### チェック項目

| チェック | 判定 | FAIL条件 |
|---------|------|---------|
| size | 370×320以内 | 超過 |
| evenDimensions | 幅・高さが偶数 | 奇数（LINE登録失敗） |
| fileSize | 500KB以内 | 超過 |
| transparency | 透過率5%超 | 透過不足 |
| tabVisibility | タブ縮小時20px以上 | 視認困難 |

### validation-report.json スキーマ

```json
{
  "generated_at": "2026-02-12T...",
  "total": 24,
  "passed": 22,
  "failed": 2,
  "results": [
    {
      "file": "01.png",
      "passed": true,
      "checks": {
        "size": "OK",
        "evenDimensions": "OK",
        "fileSize": "OK",
        "transparency": "OK",
        "tabVisibility": "OK"
      }
    }
  ]
}
```

## コマンド

### 品質チェック

```bash
python .claude/skills/linestamp-validate/scripts/check.py \
  --input output/session/transparent/ \
  --output output/session/work/validation-report.json
```

### 品質統計

```bash
python .claude/skills/linestamp-validate/scripts/stats.py \
  --db linestamp.db
```

## ファイル構成

```
linestamp-validate/
├── SKILL.md
├── schemas/
│   └── validation-report.schema.json
└── scripts/
    ├── check.py
    └── stats.py
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: 合格率、失敗チェック項目、品質スコア分布を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_failure_patterns; import json
   print(json.dumps(get_failure_patterns(10), indent=2, default=str))
   "
   ```
3. **learnings.md を更新**:
   - 新しい失敗パターン → Failure Patterns に追加
   - 品質傾向 → Execution Know-How に追加
   - Statistics Snapshot → 最新値で上書き
   - Summary → 新知見を反映して書き直し
   - Change Log → エントリ追加
4. **学ぶことがなかった場合**: Statistics と Change Log の日付のみ更新

### 更新判断

| 状況 | 更新先 |
|------|-------|
| 新しい失敗パターン | Failure Patterns |
| 品質改善の傾向 | Execution Know-How |
| チェック基準の調整 | Parameter Optimization |
| 3回以上確認したルール | Best Practices に昇格 |

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| validation-report.json を手動編集して FAIL を PASS に変える | 品質チェックの意味がなくなる | 画像を修正して再検証する。fix.py で自動修正後に再度 validate を実行 |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
