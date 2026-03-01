---
name: linestamp-submit
description: >
  LINE Creators Market にスタンプセットを提出する。
  メタデータ生成（Gemini）→ ブラウザ自動化（Playwright CLI）→ 画像アップロード → 審査リクエスト。
user-invocable: false
---

# linestamp-submit

LINE Creators Market へのスタンプ申請を自動化する。
linestamp パイプラインの Step 8（optional）。

## 使用タイミング

- linestamp オーケストレーターの Step 8 として呼び出される（任意）
- linestamp-package (Step 7) が完了し、submission.zip が存在する場合のみ実行可能
- ユーザーが「申請」「提出」「submit」を希望した場合

## 事前学習確認

**実行前に必ず `./learnings.md` を Read ツールで読み込むこと。**

## 入出力

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | `submission.zip` | ZIP（main.png + tab.png + 01-24.png） |
| 入力 | `work/submission-metadata.json` | JSON |
| 出力 | ステータス「審査待ち」 | LINE Creators Market 上 |

## 前提条件

- Playwright CLI: `$HOME/.claude/skills/playwright/scripts/playwright_cli.sh`
- LINE Creators Market アカウント
- 認証情報: macOS Keychain に保存済み（初回のみ `scripts/line_creators.sh setup` で登録）

## Step A: メタデータ生成

```bash
python .claude/skills/linestamp-submit/scripts/generate_metadata.py \
  --session-dir output/linestamp-XXXXXXXX/
```

## Step B: 自動申請（Phase 1〜5 一括）

```bash
python .claude/skills/linestamp-submit/scripts/submit.py \
  --session-dir output/linestamp-XXXXXXXX/
```

| フラグ | 必須 | デフォルト | 説明 |
|--------|------|----------|------|
| `--session-dir` | Yes | - | セッション出力ディレクトリ |
| `--sticker-count` | No | 24 | スタンプ個数 (8/16/24/32/40) |
| `--dry-run` | No | false | ブラウザ起動せず検証のみ |
| `--skip-auth` | No | false | 認証スキップ（既にログイン済み前提） |

スクリプトは以下を自動処理する:
1. **認証**: `line_creators.sh open` でブラウザ起動 + ログイン確認（PIN認証はユーザー操作）
2. **新規スタンプ作成**: マイページ → フォーム入力（タイトル/説明文/コピーライト/AI使用/カテゴリ）→ 保存
3. **画像アップロード**: スタンプ個数変更 → eval+upload の2段階で ZIP 一括アップロード
4. **審査リクエスト**: 同意チェック → リクエスト送信 → ステータス「審査待ち」確認

**出力:**
- stdout: 進捗ログ + 最終結果
- `work/submit-result.json`: `{sticker_id, status, submitted_at}`
- `work/submit-screenshot.png`: 最終確認スクリーンショット

### ドライラン

事前に検証だけ行いたい場合:

```bash
python .claude/skills/linestamp-submit/scripts/submit.py \
  --session-dir output/linestamp-XXXXXXXX/ --dry-run
```

## 手動フォールバック

`submit.py` が失敗した場合は、以下を参考にブラウザで手動入力する。
`work/submission-metadata.json` から値を読み取って入力する。

### Playwright CLI セットアップ

```bash
export PWCLI="$HOME/.claude/skills/playwright/scripts/playwright_cli.sh"
export PLAYWRIGHT_CLI_SESSION=line_creators
```

### Phase 1: 認証

```bash
# ラッパースクリプト使用（推奨）
scripts/line_creators.sh open

# または手動
"$PWCLI" open https://creator.line.me/my/ --headed --profile .playwright-cli/profiles/line_creators
```

**重要**: `open` は初回のみ。以降のナビゲーションは `goto` を使う。

### Phase 2-3: 新規スタンプ作成 + フォーム入力

```bash
# マイページ → 新規登録 → スタンプ → フォーム入力 → 保存
# 各要素は snapshot で ref を確認してから操作
"$PWCLI" snapshot
"$PWCLI" click eXX   # 新規登録 → スタンプ選択
"$PWCLI" fill eXX "{title_en}"     # textbox "タイトル English"
"$PWCLI" fill eXX "{description_en}" # textbox "スタンプ説明文 English"
"$PWCLI" select eXX "Japanese"     # 言語追加
"$PWCLI" fill eXX "{title_ja}"     # textbox "タイトル Japanese"
"$PWCLI" fill eXX "{description_ja}" # textbox "スタンプ説明文 Japanese"
"$PWCLI" fill eXX "{copyright}"    # textbox "コピーライト"
"$PWCLI" check eXX                 # radio "AIを使用しています"
"$PWCLI" click eXX                 # 保存 → OK
```

### Phase 4: 画像アップロード（ZIP 2段階操作）

```bash
"$PWCLI" select eXX "24個"         # スタンプ個数変更
"$PWCLI" eval '() => { document.querySelector("input[type=file].mdBtn").click(); return "clicked"; }'
"$PWCLI" upload "/absolute/path/to/submission.zip"
```

### Phase 5: 審査リクエスト

```bash
"$PWCLI" click eXX                 # リクエストボタン
"$PWCLI" check eXX                 # 同意します
"$PWCLI" click eXX                 # OK
```

### 手動入力ガイド

```
=== 手動入力ガイド ===
タイトル(日): {title_ja}
タイトル(英): {title_en}
説明(日): {description_ja}
説明(英): {description_en}
Copyright: {copyright}
AI使用: はい
画像: submission.zip をZIPファイルアップロードで一括登録
```

### キャンペーンポップアップ対策

```bash
"$PWCLI" eval '() => { document.querySelectorAll("dialog, .MdPOP01Modal").forEach(el => el.remove()); return "removed"; }'
```

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| ログイン情報をコード・ログ・ファイルに書き出す | 認証情報漏洩リスク | macOS Keychain 経由のみ使用。`line_creators.sh` が Keychain から取得する |
| パスワード・PIN・トークンを stdout/ファイルに出力する | ログに残ると漏洩する | 認証関連の値はマスク表示（`****`）または非表示 |
| 画像アップロードをユーザー確認なしで実行する | 誤ったファイルを LINE に送信するリスク | アップロード直前にファイル一覧とサイズを表示し、ユーザーの明示的な承認を得る |
| `--dry-run` なしでいきなり本番実行する | 操作の取り消しが困難 | 初回は必ず `--dry-run` で検証し、問題なければ本番実行 |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
- Playwright CLI: `$HOME/.claude/skills/playwright/SKILL.md`
- 実行知見: `./learnings.md`
