---
name: linestamp-charm
description: >
  三層入力（写真 + SNS + 対話）からチャームポイントを抽出し、
  人格プロファイル（charm.json）を生成する。linestamp パイプラインの Step 1.5。
user-invocable: false
---

# linestamp-charm

三層入力モデル（外見・行動・対話）からチャームポイントを抽出し、
「人格のOS」となるプロファイルJSON（charm.json）を生成する。

## 設計思想

### 三層入力モデル

| 層 | ソース | 抽出物 | 役割 |
|----|--------|--------|------|
| 第一層: 外見 | 写真 (character.yaml) | 年齢感、雰囲気、笑顔の質、姿勢 | ビジュアルの軸 |
| 第二層: 行動 | SNSテキスト (任意) | 反応パターン、語尾、感情表出、価値観 | 性格の軸 |
| 第三層: 対話 | 質問への回答 | 自覚していない魅力、価値観の核 | チャームの芯 |

### 単一チャーム原則

> チャームは一つに絞る。欲張って三つも四つも入れると、人格がぼやける。
> 24枚は一つの重心を中心に回すほうが強い。

例: 「理屈っぽいけど実は面倒見がいい人」 -> 理屈を軸に、時々やさしさがにじむ構成

## 使用タイミング

- linestamp オーケストレーターの Step 1.5 として呼び出される
- character.yaml 生成後、リアクション選択前に実行
- charm.json はオプション（スキップ可）

## 二つのモード

| モード | 入力 | 用途 |
|--------|------|------|
| **Light** | 写真 + 質問5つ | 手軽にチャーム抽出 |
| **Deep** | 写真 + SNSテキスト + 質問10問 | 精密なプロファイリング |

## 入出力（JSON契約）

| 種類 | ファイル | 形式 |
|------|---------|------|
| 入力 | `work/character.yaml` (任意) | YAML |
| 入力 | 対話回答 (CLI / answers.json) | JSON |
| 入力 | SNSテキスト (Deepモード時) | テキスト |
| 出力 | `work/charm.json` | JSON |

### charm.json スキーマ

```json
{
  "version": "1.0",
  "mode": "light",
  "core_charm": "理屈っぽいけど実は面倒見がいい",
  "personality_type": {
    "primary": "理屈型",
    "shadow": "面倒見型"
  },
  "reaction_style": {
    "trouble": "冷静に原因を分析しようとする",
    "success": "控えめに喜ぶが、相手の成功は大げさに褒める",
    "praise": "具体的な行動を指摘して褒める",
    "anger": "論理で詰めるが、すぐ冷める",
    "failure": "反省より改善策を考える"
  },
  "emotional_range": {
    "default_temperature": 0.6,
    "high": ["褒め", "驚き"],
    "standard": ["共感", "喜び", "応援"],
    "low": ["照れ", "愛情", "謝罪"]
  },
  "speech_tone": {
    "formality": 1,
    "exclamation_tendency": 0.5,
    "preferred_endings": ["〜だよ", "〜じゃん", "〜でしょ"],
    "vocabulary_hints": ["整理しよ", "つまり", "なるほど"]
  },
  "shadow_trait": {
    "trait": "照れ屋",
    "expression_pattern": "褒められると話をそらす、感謝をストレートに言えない",
    "slots": 2
  },
  "social_context": {
    "age_feel": "20s",
    "atmosphere": "知的だが親しみやすい"
  },
  "scores": {
    "positivity": 0.65,
    "empathy": 0.70,
    "assertiveness": 0.75,
    "logic_structure": 0.85,
    "question_tendency": 0.60,
    "exclamation_tendency": 0.50
  },
  "emotion_shelf": {
    "共感": 1.1,
    "ツッコミ": 0.8,
    "喜び": 0.9,
    "驚き": 1.2,
    "褒め": 1.4,
    "照れ": 0.7,
    "応援": 0.9,
    "謝罪": 0.4,
    "否定": 0.6,
    "別れ": 0.5,
    "愛情": 0.5,
    "状態": 0.6
  },
  "raw_observations": [
    "褒めるとき具体的（共感度高い）",
    "トラブル時に冷静（論理構造率高い）",
    "自分の感情は間接表現（照れ屋の影）"
  ]
}
```

## コマンド

### Light モード

```bash
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers work/answers.json \
  --character-yaml work/character.yaml \
  --output work/charm.json
```

### Deep モード

```bash
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers work/answers.json \
  --sns-text input/sns_posts.txt \
  --character-yaml work/character.yaml \
  --mode deep \
  --person-name "田中太郎" \
  --session-id 20260216_123456 \
  --output work/charm.json
```

### チャーム更新（既存プロファイルを新情報で洗練）

```bash
# 追加回答で更新
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers work/new_answers.json \
  --update-charm "田中太郎" \
  --output work/charm.json

# SNS追加 + 指示付きで更新（Light → Deep へアップグレード）
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers work/answers_deep.json \
  --sns-text input/sns_posts.txt \
  --mode deep \
  --update-charm "田中太郎" \
  --update-note "共感をもっと強めに、ツッコミ要素を追加して" \
  --output work/charm.json
```

### 既存チャーム読み込み（分析スキップ）

```bash
python .claude/skills/linestamp-charm/scripts/analyze_charm.py \
  --answers /dev/null \
  --load-charm "田中太郎" \
  --output work/charm.json
```

### answers.json 形式

オーケストレーターが対話結果を構造化したもの:

```json
{
  "q1_others_say": "真面目だねって言われる",
  "q2_trouble": "まず状況を整理する",
  "q3_praise": "具体的にここが良かったって言う",
  "q4_weakness": "気を遣いすぎて疲れること",
  "q5_happiest_word": "あなたがいて助かった"
}
```

Deep モード追加分:

```json
{
  "q6_anger": "黙って距離を置く",
  "q7_success": "控えめに喜ぶ",
  "q8_consulted": "まず話を聞く",
  "q9_worst_word": "お前は必要ない",
  "q10_one_word": "まじめ"
}
```

## 対話質問テンプレート

質問テンプレートは `scripts/questions.py` に定義。
オーケストレーターがヒアリング時に参照する。

### Light モード（5問）

| # | 質問 | 抽出対象 |
|---|------|----------|
| 1 | 人からよく言われることは何ですか？ | personality_type |
| 2 | 困ったとき、あなたはどう動きますか？ | reaction_style |
| 3 | 人を褒めるとき、どんな言い方をしますか？ | speech_tone |
| 4 | 自分の弱点だと思っていることは何ですか？ | shadow_trait |
| 5 | 一番うれしかった言葉は何ですか？ | core_charm |

### Deep モード（追加5問）

| # | 質問 | 抽出対象 |
|---|------|----------|
| 6 | 怒るとき、どうなりますか？ | reaction_style |
| 7 | 成功したとき、どんな反応をしますか？ | emotional_range |
| 8 | 友人に相談されたら、まず何をしますか？ | personality_type |
| 9 | 一番言われたくない言葉は何ですか？ | shadow_trait |
| 10 | あなたを一言で表すと？ | core_charm 検証 |

## オプション

| オプション | 説明 | デフォルト |
|-----------|------|----------|
| `--answers` | answers.json パス | (必須) |
| `--character-yaml` | character.yaml パス | - |
| `--sns-text` | SNSテキストファイルパス | - |
| `--mode` | `light` / `deep` | `light` |
| `--output` | 出力パス | (必須) |
| `--config` | config.json パス | 自動検出 |
| `--session-id` | セッションID（DB保存用） | - |
| `--person-name` | 人物名（DB保存・再利用用） | - |
| `--load-charm` | 既存チャームを人物名で読み込み（分析スキップ） | - |
| `--update-charm` | 既存チャームを人物名で読み込み、新情報で更新 | - |
| `--update-note` | 更新時の自由テキスト指示（例: 「共感をもっと強めに」） | - |

## ファイル構成

```
linestamp-charm/
├── SKILL.md
└── scripts/
    ├── analyze_charm.py    # メイン分析スクリプト
    └── questions.py        # 質問テンプレート・フォーマットユーティリティ
```

## 後方互換性

charm.json が存在しない場合、下流スキル（linestamp-reaction）は従来通り動作する。
charm は完全にオプションの拡張レイヤー。

## ガードレール

| 禁止 | 理由 | 正しい対応 |
|------|------|-----------|
| SNSテキストをチャーム分析以外の目的で使用・外部送信する | 個人情報保護 | Claude CLI への送信のみ許可。分析後は work/ 内に charm.json のみ残す |
| 対話回答（answers.json）の内容をログや stdout にそのまま出力する | プライバシー保護 | 回答内容はマスク表示。charm.json の抽出結果のみ出力 |
| 既存 charm.json を確認なしで上書きする | 以前のプロファイリング結果の喪失 | `--update-charm` 時は差分を表示してユーザー承認を得る |

## 参照

- 共有ライブラリ: `../linestamp/lib/`
- リアクション選択: `../linestamp-reaction/`（charm.json を消費）
