# REACTIONS

REACTIONSは、スタンプ1枠を定義するリアクションの配列です。各リアクションは id・感情(emotion)・ポーズ(pose)・セリフ(text) で構成されます。

## 1要素の属性

| 属性 | 必須 | 説明 |
|------|------|------|
| `id` | Yes | 識別子（ローマ字、例: `ryo`, `oke`） |
| `emotion` | Yes | 表情の説明 |
| `pose` | Yes | ポーズの説明（体の動き・しぐさ） |
| `text` | Yes | スタンプ文字（テキストなしの場合は空文字） |
| `pose_locked` | No | `True` の場合、AI が pose を変更しない |
| `outfit` | No | 衣装指定（任意） |
| `item` | No | 持ち物指定（任意） |

## 例

```python
REACTIONS = [
    # 基本
    {"id": "ryo", "emotion": "軽くうなずく笑顔、即レス感", "pose": "軽く指さし", "text": "りょ"},
    {"id": "oke", "emotion": "明るい笑顔", "pose": "サムズアップ", "text": "おけ！"},

    # pose_locked（詳細ポーズ指定）
    {"id": "iijan", "emotion": "自信満々の笑顔", "pose": "右手で親指と人差し指を使った『ＯＫサイン』のジェスチャー。親指と人差し指で丸をつくり、中指・薬指・小指は軽く曲げる。手のひらはやや正面向き、手は顔の横に位置。", "text": "いいじゃん", "pose_locked": True},

    # outfit（衣装指定）
    {"id": "biju", "emotion": "キメ顔", "pose": "ポーズ", "text": "ビジュいいじゃん", "pose_locked": True, "outfit": "黒い革ジャケット"},
]
```

## 運用ルール

### 基本ルール
- 24案は重複を避ける（意味・言い回し乱立なし）
- `text_mode` が `none` の場合、`text` は空にする
- `item` は自動検出がある場合でも、衝突が起きたら手動指定を優先

### pose_locked の使い方
- ユーザーが詳細なポーズ指示を出した場合 → `pose_locked: True` を追加
- ポーズ辞書から取得したポーズ → `pose_locked: True` を追加
- AIによる変更を許可する場合 → `pose_locked` を省略または `False`

### id の命名規則
- ポーズ辞書の `name` と `id` は、検索しやすい語彙で統一
- ローマ字化（例: りょ→ryo, おけ→oke）
- 短く、ユニークに

## 24枠構成（推奨）

| 枠 | 数 | 内容 |
|----|-----|------|
| コア用途 | 12 | 必ず入れる基本用途 |
| テーマ強化 | 8 | テーマに沿って厚くする |
| 反応・遊び | 4 | テンポを作る、相手別に事故回避 |

### コア用途 12枠（用途固定）
1. OK/了解（即レス）×2
2. 同意（軽）×1
3. 共感（中）×1
4. 理解/納得 ×1
5. 感謝（軽）×1
6. 感謝（強）×1
7. 軽謝罪 ×1
8. 保留（ちょい待ち/あとで）×1
9. 軽拒否（今むり等）×1
10. 反応（軽驚き/えっ等）×1
11. 締め（終端/解散等）×1

## DBへの保存

REACTIONSはセッションに紐づけてDBに保存されます:

```python
from session_manager import Session

session = Session.create(
    image_path="input/photo.jpg",
    style="yuru_line",
    persona_age="Kid",
    persona_target="Family",
    persona_theme="ツッコミ・反応強化",
    persona_intensity=3
)

reactions = [
    {"id": "ryo", "emotion": "...", "pose": "...", "text": "りょ！"},
    # ... 24件
]
session.set_reactions(reactions)
```
