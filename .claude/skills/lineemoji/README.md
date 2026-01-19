# LINE絵文字生成スキル

Vertex AI (gemini-3-pro-image-preview) を使用してLINE絵文字用画像を生成するスキル。

## 使い方

### スキル呼び出し（推奨）
```bash
/lineemoji
# または
/emoji
```

### 直接実行
```bash
cd .claude/skills/lineemoji
python generate_emoji.py --package ../../../input/参照画像.jpg --output ../../../output/lineemoji
```

## LINE絵文字仕様

| 種類 | サイズ |
|------|--------|
| 絵文字画像 | 180×180px |
| タブ画像 | 96×74px |
| 形式 | PNG（背景透過） |
| セット数 | 8/16/24/32/40枚 |
| 余白 | 不要 |

## スタンプとの違い

- **サイズ**: 絵文字は180×180px（スタンプは370×320px）
- **余白**: 絵文字は不要（スタンプは必要）
- **テキスト**: 絵文字はなし（スタンプはあり）
- **デザイン**: 絵文字はシンプル・太線必須

## 出力ファイル

```
output/lineemoji/
├── _character.png    # 生成されたキャラクター
├── _grid.png         # 4x4グリッド
├── _prompts.json     # 使用したプロンプト
├── tab.png           # タブ画像 (96x74)
├── 001.png ~ 016.png # 絵文字画像 (180x180)
└── submission.zip    # 申請用パッケージ
```
