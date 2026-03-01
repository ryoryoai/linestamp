---
name: linestamp-package
description: 透過済みスタンプからmain画像・tab画像・submission.zipを生成する
user-invocable: false
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "$CLAUDE_PROJECT_DIR/.claude/hooks/pipeline-guard.sh package_pre"
---

# linestamp-package

透過済みスタンプ画像からLINE Creators Market 提出用の
main画像(240x240)、tab画像(96x74)、submission.zipを生成する。
linestamp パイプラインの Step 7（最終）。

## 使用タイミング

- linestamp オーケストレーターの Step 7 として呼び出される
- パッケージの再生成が必要な場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

- Summary と Best Practices を確認し、実行に反映する
- 該当する Failure Patterns があれば回避策を適用する
- 存在しない場合はスキップ（初回実行後に自動生成）

## 入出力

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | `transparent/*.png` | PNG画像 |
| 出力 | `main.png` | 240x240 PNG |
| 出力 | `tab.png` | 96x74 PNG |
| 出力 | `submission.zip` | ZIP |

## コマンド

```bash
python .claude/skills/linestamp-package/scripts/package.py \
  --input output/session/transparent/ \
  --output output/session/
```

## ファイル構成

```
linestamp-package/
├── SKILL.md
└── scripts/
    └── package.py
```

## 実行後学習

**実行完了後、以下の手順で `./learnings.md` を更新すること。**

1. **結果評価**: main/tab画像の品質、ZIP完全性を確認
2. **DB統計を取得**（任意）:
   ```bash
   python -c "
   import sys; sys.path.insert(0, '.claude/skills/linestamp/lib')
   from database import get_prompt_stats; import json
   print(json.dumps(get_prompt_stats('package'), indent=2, default=str))
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
| main/tab画像選択の知見 | Execution Know-How |
| 失敗 | Failure Patterns |
| 3回以上確認したルール | Best Practices に昇格 |

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| validation-report.json が PASS でない状態で submission.zip を生成する | 品質未達のスタンプが提出される | validation-report.json の存在と全項目 PASS を確認してからパッケージ生成を開始する |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
