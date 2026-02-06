"""
マスタデータシード投入スクリプト

pose_master, text_master, reactions_master に初期データを投入する
"""

import sys
from pathlib import Path

# モジュールパスを追加
sys.path.insert(0, str(Path(__file__).parent))

from database import (
    init_database,
    upsert_pose_master,
    upsert_text_master,
    upsert_reactions_master,
    upsert_persona_config,
    list_pose_master,
    list_text_master,
    list_persona_config,
)


# ==================== ポーズマスタ シードデータ ====================

POSE_SEEDS = [
    # === 肯定系 ===
    {
        "id": "peace_sign",
        "name": "ピースサイン",
        "name_en": "peace sign",
        "category": "肯定",
        "gesture": "人差し指と中指を立ててVサイン。手のひらを正面に向ける。他の指は軽く握る。",
        "gesture_en": "Peace sign with index and middle fingers raised in V shape. Palm facing forward.",
        "expression": "明るい笑顔、元気いっぱいの表情。",
        "vibe": "元気・肯定・即レス",
        "difficulty": 1,
        "body_parts": ["手", "指"],
        "tags": ["定番", "簡単", "友達向け"],
    },
    {
        "id": "thumbs_up",
        "name": "サムズアップ",
        "name_en": "thumbs up",
        "category": "肯定",
        "gesture": "親指を立てて「いいね」のジェスチャー。他の指は握りしめる。腕は軽く曲げて体の前に。",
        "gesture_en": "Thumbs up gesture. Other fingers closed in fist. Arm slightly bent in front of body.",
        "expression": "にっこり笑顔、承認の表情。",
        "vibe": "承認・OK・いいね",
        "difficulty": 1,
        "body_parts": ["手", "指"],
        "tags": ["定番", "簡単", "汎用"],
    },
    {
        "id": "ok_sign",
        "name": "OKサイン",
        "name_en": "OK sign",
        "category": "肯定",
        "gesture": "右手で親指と人差し指で丸を作るOKサインジェスチャー。手は顔の横（頬の高さ）に位置。残り3本の指は軽く曲げる。手のひらはやや正面向き、指先の丸い部分がやや上を向く。",
        "gesture_en": "OK sign gesture with right hand. Thumb and index finger form a circle. Hand positioned near face.",
        "expression": "自信満々の笑顔、褒める表情。目はキラキラ、口角が上がる。余裕のある肯定表情。",
        "vibe": "評価・承認・余裕",
        "difficulty": 2,
        "body_parts": ["手", "指"],
        "hints": ["手の形が崩れやすいので注意", "丸の部分を明確に", "親指と人差し指の接点を強調"],
        "avoid": ["指が6本以上", "手の向きが反転", "丸が潰れている"],
        "tags": ["定番", "褒め"],
    },
    {
        "id": "nod",
        "name": "うなずき",
        "name_en": "nodding",
        "category": "共感",
        "gesture": "軽く首を前に傾けてうなずくポーズ。顔はやや下向き。",
        "gesture_en": "Light nodding with head tilted forward.",
        "expression": "やさしい笑顔、共感の目。穏やかな表情。",
        "vibe": "共感・理解・同意",
        "difficulty": 1,
        "body_parts": ["頭", "首"],
        "tags": ["共感", "簡単"],
    },
    {
        "id": "empathy_hands",
        "name": "両手を胸に当てて共感",
        "name_en": "hands on chest empathy",
        "category": "共感",
        "gesture": "両手を胸の前で重ねるように当てる。体はやや前傾。",
        "gesture_en": "Both hands pressed together against chest. Body leaning slightly forward.",
        "expression": "大きくうなずく、わかるー！の顔。目を見開いて共感を示す。",
        "vibe": "強い共感・感動",
        "difficulty": 1,
        "body_parts": ["手", "胸"],
        "tags": ["共感", "感動"],
    },
    {
        "id": "chin_hand",
        "name": "あごに手を当てる",
        "name_en": "hand on chin",
        "category": "思考",
        "gesture": "片手であごを支えるように軽く触れる。肘は曲げる。",
        "gesture_en": "One hand lightly touching chin. Elbow bent.",
        "expression": "納得の表情、ふむふむ。考え込む雰囲気。",
        "vibe": "納得・思考・理解",
        "difficulty": 1,
        "body_parts": ["手", "あご"],
        "tags": ["思考", "納得"],
    },

    # === 礼儀系 ===
    {
        "id": "light_bow",
        "name": "軽くお辞儀",
        "name_en": "light bow",
        "category": "礼儀",
        "gesture": "軽く頭を下げてお辞儀。腰から15-20度くらい前傾。手は体の横または前に揃える。",
        "gesture_en": "Light bow with head lowered. Body tilted forward 15-20 degrees from waist.",
        "expression": "感謝の笑顔、嬉しそう。",
        "vibe": "感謝・礼儀・丁寧",
        "difficulty": 1,
        "body_parts": ["頭", "腰"],
        "tags": ["礼儀", "感謝"],
    },

    # === 愛情系 ===
    {
        "id": "heart_hands",
        "name": "両手でハートマーク",
        "name_en": "heart hands",
        "category": "愛情",
        "gesture": "両手の親指と人差し指でハートマークを作る。指先を合わせてハートの形に。胸の前あたりに配置。",
        "gesture_en": "Heart shape formed with both hands' thumbs and index fingers. Positioned in front of chest.",
        "expression": "大好きの気持ち、キラキラ目。幸せそうな笑顔。",
        "vibe": "愛情・大好き・幸せ",
        "difficulty": 2,
        "body_parts": ["手", "指"],
        "tags": ["愛情", "恋人向け"],
    },

    # === 照れ系 ===
    {
        "id": "tehepero",
        "name": "てへぺろ",
        "name_en": "tehepero",
        "category": "照れ",
        "gesture": "舌を少し出して片目をつぶり、頭を軽く傾ける。片手で頭を軽く叩くジェスチャー。",
        "gesture_en": "Tongue slightly out, one eye closed, head tilted. One hand lightly tapping head.",
        "expression": "照れ笑いの表情。申し訳なさそうだけど愛嬌がある。",
        "vibe": "照れ・ごめんね・愛嬌",
        "difficulty": 2,
        "body_parts": ["顔", "舌", "手"],
        "tags": ["照れ", "謝罪"],
    },

    # === 否定系 ===
    {
        "id": "stop_hands",
        "name": "両手を前に出してストップ",
        "name_en": "stop hands",
        "category": "否定",
        "gesture": "両手を前に出して「ストップ」のジェスチャー。手のひらを相手に向ける。指は揃える。",
        "gesture_en": "Both hands extended forward in stop gesture. Palms facing outward. Fingers together.",
        "expression": "焦り顔、待って！慌てた表情。",
        "vibe": "待って・ストップ・焦り",
        "difficulty": 1,
        "body_parts": ["手", "腕"],
        "tags": ["否定", "待って"],
    },
    {
        "id": "x_sign",
        "name": "バツサイン",
        "name_en": "X sign",
        "category": "否定",
        "gesture": "両腕を胸の前で交差させてバツマーク。手のひらは外側に向ける。",
        "gesture_en": "Arms crossed in X shape in front of chest. Palms facing outward.",
        "expression": "困り顔、今は無理の表情。",
        "vibe": "無理・NG・できない",
        "difficulty": 1,
        "body_parts": ["腕"],
        "tags": ["否定", "無理"],
    },

    # === 驚き系 ===
    {
        "id": "wide_eyes",
        "name": "目を見開く",
        "name_en": "wide eyes",
        "category": "驚き",
        "gesture": "特になし。表情のみ。",
        "expression": "目まんまる、軽い驚き。口が小さく開く。",
        "vibe": "驚き・えっ",
        "difficulty": 1,
        "body_parts": ["顔"],
        "tags": ["驚き", "反応"],
    },

    # === 別れ系 ===
    {
        "id": "wave_goodbye",
        "name": "手を振る",
        "name_en": "waving goodbye",
        "category": "別れ",
        "gesture": "片手を上げて左右に振る。手のひらを相手に向ける。",
        "gesture_en": "One hand raised and waving side to side. Palm facing outward.",
        "expression": "にこやか、バイバイ。明るい別れの表情。",
        "vibe": "さよなら・また会おう",
        "difficulty": 1,
        "body_parts": ["手", "腕"],
        "tags": ["別れ", "挨拶"],
    },

    # === ツッコミ系 ===
    {
        "id": "tsukkomi",
        "name": "ツッコミの手振り",
        "name_en": "tsukkomi gesture",
        "category": "反応",
        "gesture": "片手を前に出してツッコミのジェスチャー。手のひらは相手に向け、指は揃える。",
        "gesture_en": "One hand extended forward in tsukkomi gesture. Palm facing outward, fingers together.",
        "expression": "あきれた表情、なんでやねん顔。",
        "vibe": "ツッコミ・あきれ・呆れ",
        "difficulty": 1,
        "body_parts": ["手", "腕"],
        "tags": ["ツッコミ", "関西"],
    },
    {
        "id": "deny_wave",
        "name": "両手を振って否定",
        "name_en": "deny waving",
        "category": "否定",
        "gesture": "両手を前に出して左右に振る。手のひらを相手に向ける。",
        "gesture_en": "Both hands waving side to side. Palms facing outward.",
        "expression": "否定の表情、ちがうちがう。",
        "vibe": "否定・ちがう・訂正",
        "difficulty": 1,
        "body_parts": ["手", "腕"],
        "tags": ["否定"],
    },
    {
        "id": "mouth_cover_surprise",
        "name": "口を手で覆う驚き",
        "name_en": "mouth cover surprise",
        "category": "驚き",
        "gesture": "片手または両手で口を覆うポーズ。指は揃える。",
        "gesture_en": "One or both hands covering mouth. Fingers together.",
        "expression": "信じられない顔、驚き。目を大きく見開く。",
        "vibe": "驚愕・嘘でしょ・信じられない",
        "difficulty": 1,
        "body_parts": ["手", "口"],
        "tags": ["驚き"],
    },
    {
        "id": "intense_stare",
        "name": "目をむき出しにする",
        "name_en": "intense stare",
        "category": "驚き",
        "gesture": "特になし。表情のみ。",
        "expression": "目を見開く、マジ？の顔。眉を上げる。",
        "vibe": "本当？・マジ？",
        "difficulty": 1,
        "body_parts": ["顔"],
        "tags": ["驚き", "反応"],
    },
    {
        "id": "hands_up_surprise",
        "name": "両手を上げて驚く",
        "name_en": "hands up surprise",
        "category": "驚き",
        "gesture": "両手を顔の横に上げる。手のひらは正面向き。指は開く。",
        "gesture_en": "Both hands raised beside face. Palms facing forward. Fingers spread.",
        "expression": "超驚き、えええ顔。目と口が大きく開く。",
        "vibe": "大驚き・えええ",
        "difficulty": 1,
        "body_parts": ["手", "腕"],
        "tags": ["驚き", "大げさ"],
    },
    {
        "id": "laughing_hard",
        "name": "笑い転げる",
        "name_en": "laughing hard",
        "category": "喜び",
        "gesture": "お腹を抱えて笑う。体がくの字に曲がる。",
        "gesture_en": "Holding stomach while laughing. Body bent forward.",
        "expression": "爆笑、涙出る。目が線になる。",
        "vibe": "爆笑・ウケる・最高",
        "difficulty": 2,
        "body_parts": ["体", "腕"],
        "tags": ["笑い", "リアクション"],
    },

    # === 応援系 ===
    {
        "id": "banzai",
        "name": "万歳",
        "name_en": "banzai",
        "category": "喜び",
        "gesture": "両手を高く上げて万歳のポーズ。手のひらは正面または内側に向ける。",
        "gesture_en": "Both arms raised high in banzai pose. Palms facing forward or inward.",
        "expression": "大喜び、やったー！の顔。満面の笑み。",
        "vibe": "喜び・やった・勝利",
        "difficulty": 1,
        "body_parts": ["腕"],
        "tags": ["喜び", "祝い"],
    },
    {
        "id": "fist_pump",
        "name": "ガッツポーズ",
        "name_en": "fist pump",
        "category": "応援",
        "gesture": "握りこぶしを作り、腕を曲げて力強く引く。肘を曲げ、拳を肩の高さに。",
        "gesture_en": "Clenched fist with arm bent, pulling powerfully. Elbow bent, fist at shoulder height.",
        "expression": "やる気満々の表情、がんばる顔。",
        "vibe": "やる気・頑張る・応援",
        "difficulty": 1,
        "body_parts": ["腕", "拳"],
        "tags": ["応援", "やる気"],
    },
    {
        "id": "sleepy_face",
        "name": "眠そうな顔",
        "name_en": "sleepy face",
        "category": "状態",
        "gesture": "特になし、または片手で頬杖。",
        "expression": "眠そう、おやすみ。目が半分閉じている。",
        "vibe": "眠い・おやすみ",
        "difficulty": 1,
        "body_parts": ["顔"],
        "tags": ["状態", "夜"],
    },
    {
        "id": "with_bird",
        "name": "肩にオカメインコ",
        "name_en": "with cockatiel",
        "category": "特殊",
        "gesture": "肩に小鳥（オカメインコ）が乗っている。",
        "gesture_en": "A cockatiel perched on shoulder.",
        "expression": "嬉しそう、インコと一緒。幸せな笑顔。",
        "vibe": "かわいい・ペット・癒し",
        "difficulty": 3,
        "body_parts": ["肩"],
        "tags": ["特殊", "ペット"],
    },
    {
        "id": "kimikimi",
        "name": "きみきみ",
        "name_en": "Kimikimi pointing",
        "category": "応援",
        "gesture": "右手の人差し指と親指を立てて「きみ！」と指すジェスチャー（L字型）。人差し指は上に向け、親指は横に開く。残り3本の指は握る。手は顔の横〜やや前方に位置。相手を指すように人差し指の先がやや前方を向く。",
        "gesture_en": "Right hand with index finger and thumb extended in L-shape, pointing 'you!' gesture. Index finger pointing up, thumb extended sideways. Other three fingers curled. Hand positioned beside face or slightly forward.",
        "expression": "笑顔、元気いっぱいの表情。目を大きく開いて口を開けて笑う。エネルギッシュで明るい雰囲気。",
        "vibe": "応援・激励・明るい・エネルギッシュ",
        "difficulty": 2,
        "body_parts": ["手", "指"],
        "hints": ["人差し指と親指の両方が立っていることが重要", "L字型の手の形を明確に", "勢いのある笑顔で元気な印象を出す"],
        "avoid": ["指が曖昧で何を指しているかわからない", "ピストルのような攻撃的な印象", "指が6本以上"],
        "tags": ["応援", "オリジナル"],
        "source": "custom",
    },

    # === 追加ポーズ（応援・褒め・共感・状態） ===
    {
        "id": "pointing",
        "name": "指さし",
        "name_en": "pointing",
        "category": "応援",
        "gesture": "片手の人差し指を前に向けて指す。腕を軽く伸ばす。",
        "gesture_en": "Pointing forward with index finger. Arm slightly extended.",
        "expression": "力強い笑顔、自信のある表情。",
        "vibe": "指名・応援・注目",
        "difficulty": 1,
        "body_parts": ["手", "指"],
        "tags": ["応援", "簡単"],
    },
    {
        "id": "clap",
        "name": "拍手",
        "name_en": "clapping",
        "category": "褒め",
        "gesture": "両手を合わせて拍手。手のひら同士が向き合う。胸の高さで。",
        "gesture_en": "Clapping with both hands at chest height. Palms facing each other.",
        "expression": "感心した笑顔、すごい！の表情。",
        "vibe": "称賛・すごい・拍手",
        "difficulty": 1,
        "body_parts": ["手"],
        "tags": ["褒め", "称賛"],
    },
    {
        "id": "head_pat",
        "name": "頭をなでる",
        "name_en": "head patting",
        "category": "共感",
        "gesture": "片手を自分の頭の上に置いて軽くなでるジェスチャー。",
        "gesture_en": "One hand on top of own head, lightly patting.",
        "expression": "優しい微笑み、安心させる表情。",
        "vibe": "慰め・安心・大丈夫",
        "difficulty": 1,
        "body_parts": ["手", "頭"],
        "tags": ["共感", "慰め"],
    },
    {
        "id": "megaphone",
        "name": "メガホンで応援",
        "name_en": "megaphone cheer",
        "category": "応援",
        "gesture": "両手を口の横に当ててメガホンのように叫ぶポーズ。",
        "gesture_en": "Both hands cupped around mouth like a megaphone, cheering.",
        "expression": "全力の笑顔、応援してる！の表情。",
        "vibe": "応援・声援・エール",
        "difficulty": 1,
        "body_parts": ["手", "口"],
        "tags": ["応援", "元気"],
    },
    {
        "id": "praying",
        "name": "祈るポーズ",
        "name_en": "praying hands",
        "category": "共感",
        "gesture": "両手を合わせて胸の前で祈るように組む。",
        "gesture_en": "Both hands pressed together in prayer position in front of chest.",
        "expression": "心配そうな優しい目、気遣いの表情。",
        "vibe": "祈り・お願い・気遣い",
        "difficulty": 1,
        "body_parts": ["手"],
        "tags": ["共感", "気遣い"],
    },
    {
        "id": "fist_double",
        "name": "両手ガッツポーズ",
        "name_en": "double fist pump",
        "category": "応援",
        "gesture": "両手で握りこぶしを作り、胸の前で力強く引く。両肘を曲げる。",
        "gesture_en": "Both fists clenched and pulled back powerfully at chest level. Both elbows bent.",
        "expression": "気合い満々、全力応援の表情。目が輝く。",
        "vibe": "気合い・全力応援・やるぞ",
        "difficulty": 1,
        "body_parts": ["腕", "拳"],
        "tags": ["応援", "気合い"],
    },
    {
        "id": "cheek_rest",
        "name": "頬杖",
        "name_en": "chin rest",
        "category": "状態",
        "gesture": "片手で頬を支えて頬杖をつく。やや首を傾ける。",
        "gesture_en": "Resting cheek on one hand. Head slightly tilted.",
        "expression": "穏やかな笑顔、ほのぼの。",
        "vibe": "のんびり・リラックス・穏やか",
        "difficulty": 1,
        "body_parts": ["手", "頬"],
        "tags": ["状態", "リラックス"],
    },
    {
        "id": "hand_on_chest",
        "name": "胸に手を当てる",
        "name_en": "hand on chest",
        "category": "応援",
        "gesture": "片手を胸に当てて真っすぐ前を見る。誠意のあるポーズ。",
        "gesture_en": "One hand placed on chest, looking straight ahead. Sincere pose.",
        "expression": "真っすぐな目、信頼の笑顔。",
        "vibe": "信頼・誠意・約束",
        "difficulty": 1,
        "body_parts": ["手", "胸"],
        "tags": ["応援", "信頼"],
    },
]


# ==================== セリフマスタ シードデータ ====================

TEXT_SEEDS = [
    # === コアセリフ（汎用） ===
    {
        "id": "ryo",
        "text": "りょ！",
        "text_variants": ["りょ", "りょー！", "了解！"],
        "reading": "りょ",
        "meaning": "了解の略、軽い同意",
        "category": "返事",
        "usage": ["即レス", "軽い同意"],
        "formality": 1,
        "persona_age": ["Teen", "20s"],
        "persona_target": ["Friend"],
        "text_size": "large",
    },
    {
        "id": "okke",
        "text": "おっけー！",
        "text_variants": ["おっけ！", "オッケー！", "OK！"],
        "reading": "おっけー",
        "meaning": "OK、了承",
        "category": "返事",
        "usage": ["了承", "同意"],
        "formality": 1,
        "persona_age": ["Teen", "20s", "30s"],
        "persona_target": ["Friend", "Family"],
        "text_size": "large",
    },
    {
        "id": "unun",
        "text": "うんうん",
        "text_variants": ["うん", "うんうん！"],
        "reading": "うんうん",
        "meaning": "うなずき、共感",
        "category": "共感",
        "usage": ["相槌", "共感"],
        "formality": 1,
        "persona_target": ["Friend", "Family"],
        "text_size": "normal",
    },
    {
        "id": "wakaru",
        "text": "わかるー！",
        "text_variants": ["わかる！", "わっかるー！", "それなー！"],
        "reading": "わかる",
        "meaning": "強い共感",
        "category": "共感",
        "usage": ["強い共感", "同意"],
        "formality": 1,
        "persona_age": ["Teen", "20s", "30s"],
        "persona_target": ["Friend"],
        "text_size": "large",
    },
    {
        "id": "naruhodo",
        "text": "なるほどね！",
        "text_variants": ["なるほど！", "なるほどー"],
        "reading": "なるほど",
        "meaning": "納得、理解",
        "category": "理解",
        "usage": ["納得", "理解を示す"],
        "formality": 2,
        "text_size": "normal",
    },
    {
        "id": "arigato",
        "text": "ありがとー！",
        "text_variants": ["ありがとう！", "ありがと！", "サンキュー！"],
        "reading": "ありがとう",
        "meaning": "感謝",
        "category": "感謝",
        "usage": ["お礼", "感謝"],
        "formality": 2,
        "text_size": "large",
    },
    {
        "id": "daisuki",
        "text": "だいすき！",
        "text_variants": ["大好き！", "だいすきー！"],
        "reading": "だいすき",
        "meaning": "愛情表現",
        "category": "愛情",
        "usage": ["愛情", "褒め"],
        "formality": 1,
        "persona_target": ["Friend", "Partner", "Family"],
        "text_size": "large",
    },
    {
        "id": "gomenne",
        "text": "ごめんね〜",
        "text_variants": ["ごめん！", "ごめんねー", "すまん！"],
        "reading": "ごめんね",
        "meaning": "軽い謝罪",
        "category": "謝罪",
        "usage": ["軽い謝罪", "お詫び"],
        "formality": 1,
        "text_size": "normal",
    },
    {
        "id": "chottomatte",
        "text": "ちょっとまって！",
        "text_variants": ["待って！", "ちょいまち！", "まって！"],
        "reading": "ちょっとまって",
        "meaning": "待ってほしい",
        "category": "要求",
        "usage": ["一時停止", "待って"],
        "formality": 1,
        "text_size": "large",
    },
    {
        "id": "imamuri",
        "text": "いまむり〜",
        "text_variants": ["むり〜", "無理！", "今ムリ"],
        "reading": "いまむり",
        "meaning": "今は無理",
        "category": "断り",
        "usage": ["断り", "できない"],
        "formality": 1,
        "persona_age": ["Teen", "20s"],
        "persona_target": ["Friend"],
        "text_size": "normal",
    },
    {
        "id": "eh",
        "text": "えっ！？",
        "text_variants": ["え！？", "えっ？", "え？"],
        "reading": "え",
        "meaning": "軽い驚き",
        "category": "驚き",
        "usage": ["驚き", "反応"],
        "formality": 1,
        "text_size": "large",
    },
    {
        "id": "baibai",
        "text": "ばいばーい！",
        "text_variants": ["ばいばい！", "バイバイ！", "またね！"],
        "reading": "ばいばい",
        "meaning": "さようなら",
        "category": "別れ",
        "usage": ["別れ", "挨拶"],
        "formality": 1,
        "text_size": "large",
    },

    # === ツッコミ系 ===
    {
        "id": "nandeyanen",
        "text": "なんでやねん！",
        "text_variants": ["なんでやねん", "なんでよ！"],
        "reading": "なんでやねん",
        "meaning": "関西風ツッコミ",
        "category": "ツッコミ",
        "usage": ["ツッコミ", "反応"],
        "formality": 1,
        "persona_theme": ["ツッコミ強化"],
        "text_size": "large",
    },
    {
        "id": "chigauchigau",
        "text": "ちがうちがう！",
        "text_variants": ["ちがう！", "違う違う！"],
        "reading": "ちがう",
        "meaning": "否定",
        "category": "否定",
        "usage": ["否定", "訂正"],
        "formality": 1,
        "text_size": "normal",
    },
    {
        "id": "usodesho",
        "text": "うそでしょ！？",
        "text_variants": ["嘘でしょ！", "うそ！？", "マジで！？"],
        "reading": "うそでしょ",
        "meaning": "信じられない",
        "category": "驚き",
        "usage": ["驚き", "不信"],
        "formality": 2,
        "text_size": "large",
    },
    {
        "id": "maji",
        "text": "まじ！？",
        "text_variants": ["マジ！？", "まじで！？", "本当！？"],
        "reading": "まじ",
        "meaning": "本当？",
        "category": "驚き",
        "usage": ["確認", "驚き"],
        "formality": 1,
        "persona_age": ["Teen", "20s", "30s"],
        "text_size": "large",
    },
    {
        "id": "eeee",
        "text": "えええ〜！",
        "text_variants": ["えー！", "ええ！？"],
        "reading": "ええ",
        "meaning": "大きな驚き",
        "category": "驚き",
        "usage": ["大驚き"],
        "formality": 1,
        "text_size": "large",
    },
    {
        "id": "waratta",
        "text": "わらった！",
        "text_variants": ["笑った！", "ウケる！", "草"],
        "reading": "わらった",
        "meaning": "面白い",
        "category": "笑い",
        "usage": ["笑い", "面白い"],
        "formality": 1,
        "persona_age": ["Teen", "20s", "30s"],
        "text_size": "large",
    },

    # === 褒め系 ===
    {
        "id": "iijan",
        "text": "いいじゃん",
        "text_variants": ["いいじゃん！", "いいね！", "ええやん"],
        "reading": "いいじゃん",
        "meaning": "肯定的評価",
        "category": "褒め",
        "usage": ["褒め", "肯定"],
        "formality": 1,
        "persona_theme": ["褒め強化"],
        "text_size": "large",
    },
    {
        "id": "kyoubijuiijan",
        "text": "今日ビジュいいじゃん",
        "text_variants": ["ビジュいいね！", "今日かわいい！"],
        "reading": "きょうびじゅいいじゃん",
        "meaning": "見た目を褒める",
        "category": "褒め",
        "usage": ["褒め", "ビジュアル"],
        "formality": 1,
        "persona_age": ["Teen", "20s"],
        "persona_target": ["Friend", "Partner"],
        "persona_theme": ["褒め強化"],
        "text_size": "normal",
    },

    # === 特殊 ===
    {
        "id": "piyo",
        "text": "ぴよ！",
        "text_variants": ["ぴよぴよ", "ピヨ！"],
        "reading": "ぴよ",
        "meaning": "鳥の鳴き声、かわいい",
        "category": "特殊",
        "usage": ["かわいい", "ペット"],
        "formality": 1,
        "text_size": "large",
    },
    {
        "id": "yatta",
        "text": "やったー！",
        "text_variants": ["やった！", "イェーイ！"],
        "reading": "やった",
        "meaning": "喜び、成功",
        "category": "喜び",
        "usage": ["喜び", "成功"],
        "formality": 1,
        "text_size": "large",
    },
    {
        "id": "ganbaru",
        "text": "がんばる！",
        "text_variants": ["頑張る！", "がんばります！", "ファイト！"],
        "reading": "がんばる",
        "meaning": "やる気、意気込み",
        "category": "応援",
        "usage": ["自己励まし", "決意"],
        "formality": 2,
        "text_size": "large",
    },
    {
        "id": "oyasumi",
        "text": "おやすみ〜",
        "text_variants": ["おやすみ！", "おやすみなさい", "ねる〜"],
        "reading": "おやすみ",
        "meaning": "就寝の挨拶",
        "category": "挨拶",
        "usage": ["夜の挨拶", "就寝"],
        "formality": 2,
        "text_size": "normal",
    },
    {
        "id": "kimikimi",
        "text": "きみきみ！",
        "text_variants": ["きみ！", "君きみ！"],
        "reading": "きみきみ",
        "meaning": "相手を指して呼びかける、応援",
        "category": "応援",
        "usage": ["応援", "呼びかけ"],
        "formality": 1,
        "persona_theme": ["応援強化"],
        "text_size": "large",
        "source": "custom",
    },

    # === 共感テーマ追加 ===
    {"id": "sorena", "text": "それな！", "text_variants": ["それな", "それなー！"], "reading": "それな", "meaning": "強い同意", "category": "共感", "usage": ["同意", "共感"], "formality": 1, "persona_age": ["Teen", "20s", "30s"], "persona_target": ["Friend"], "persona_theme": ["共感強化"], "text_size": "large"},
    {"id": "hontosore", "text": "ほんとそれ", "text_variants": ["ほんとそれ！", "ホントそれ"], "reading": "ほんとそれ", "meaning": "完全同意", "category": "共感", "usage": ["完全同意"], "formality": 1, "persona_theme": ["共感強化"], "text_size": "normal"},
    {"id": "donmai", "text": "どんまい！", "text_variants": ["どんまい", "ドンマイ！"], "reading": "どんまい", "meaning": "気にしないで", "category": "共感", "usage": ["慰め", "励まし"], "formality": 1, "persona_theme": ["共感強化"], "text_size": "large"},
    {"id": "daijoubu", "text": "大丈夫だよ", "text_variants": ["大丈夫！", "だいじょうぶ！"], "reading": "だいじょうぶ", "meaning": "安心させる", "category": "共感", "usage": ["慰め", "安心"], "formality": 2, "persona_theme": ["共感強化"], "text_size": "large"},
    {"id": "ganbattane", "text": "がんばったね", "text_variants": ["がんばったね！", "頑張ったね"], "reading": "がんばったね", "meaning": "努力を認める", "category": "共感", "usage": ["慰め", "称賛"], "formality": 2, "persona_theme": ["共感強化"], "text_size": "normal"},
    {"id": "tsuraiyone", "text": "つらいよね", "text_variants": ["つらいね", "大変だったね"], "reading": "つらいよね", "meaning": "共感", "category": "共感", "usage": ["共感", "寄り添い"], "formality": 2, "persona_theme": ["共感強化"], "text_size": "normal"},
    {"id": "yokattane", "text": "よかったね！", "text_variants": ["よかった！", "良かったー！"], "reading": "よかったね", "meaning": "安堵・喜び", "category": "共感", "usage": ["喜び", "安堵"], "formality": 2, "persona_theme": ["共感強化"], "text_size": "large"},

    # === 家族テーマ追加 ===
    {"id": "gohandekita", "text": "ごはんできたよ", "text_variants": ["ごはんだよ！", "ご飯できた"], "reading": "ごはんできた", "meaning": "食事の準備完了", "category": "生活", "usage": ["連絡", "食事"], "formality": 2, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "normal"},
    {"id": "kaeruyo", "text": "帰るよ！", "text_variants": ["帰ります！", "今帰る！"], "reading": "かえるよ", "meaning": "帰宅連絡", "category": "生活", "usage": ["連絡", "帰宅"], "formality": 2, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "large"},
    {"id": "kaimono", "text": "買い物行く！", "text_variants": ["買い物行ってくる", "お買い物！"], "reading": "かいものいく", "meaning": "外出連絡", "category": "生活", "usage": ["連絡", "外出"], "formality": 2, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "normal"},
    {"id": "kiwotsukete", "text": "気をつけてね", "text_variants": ["気をつけて！", "気をつけてー"], "reading": "きをつけて", "meaning": "注意を促す", "category": "気遣い", "usage": ["気遣い", "注意"], "formality": 2, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "normal"},
    {"id": "imadoko", "text": "いまどこ？", "text_variants": ["今どこ？", "どこにいる？"], "reading": "いまどこ", "meaning": "居場所確認", "category": "生活", "usage": ["連絡", "確認"], "formality": 2, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "large"},
    {"id": "samui", "text": "寒いね〜", "text_variants": ["さむい！", "寒っ！"], "reading": "さむい", "meaning": "天候の共有", "category": "気遣い", "usage": ["気遣い", "天候"], "formality": 1, "persona_target": ["Family"], "persona_theme": ["家族強化"], "text_size": "normal"},

    # === 応援テーマ追加 ===
    {"id": "ganbare", "text": "がんばれ！", "text_variants": ["頑張れ！", "がんばれー！"], "reading": "がんばれ", "meaning": "応援", "category": "応援", "usage": ["応援", "激励"], "formality": 2, "persona_theme": ["応援強化"], "text_size": "large"},
    {"id": "fight", "text": "ファイト！", "text_variants": ["ファイト", "ファイトー！"], "reading": "ふぁいと", "meaning": "頑張れ", "category": "応援", "usage": ["応援"], "formality": 1, "persona_theme": ["応援強化"], "text_size": "large"},
    {"id": "ouenshiteru", "text": "応援してる！", "text_variants": ["応援してるよ！", "おうえんしてる"], "reading": "おうえんしてる", "meaning": "応援の気持ち", "category": "応援", "usage": ["応援", "支持"], "formality": 2, "persona_theme": ["応援強化"], "text_size": "large"},
    {"id": "shinjiteru", "text": "信じてる！", "text_variants": ["信じてるよ！", "信じてる"], "reading": "しんじてる", "meaning": "信頼", "category": "応援", "usage": ["信頼", "応援"], "formality": 2, "persona_theme": ["応援強化"], "text_size": "large"},
    {"id": "sasuga", "text": "さすが！", "text_variants": ["さすが〜！", "流石！"], "reading": "さすが", "meaning": "称賛", "category": "褒め", "usage": ["褒め", "称賛"], "formality": 2, "persona_theme": ["応援強化", "褒め強化"], "text_size": "large"},
    {"id": "sugoi", "text": "すごい！", "text_variants": ["すごいじゃん！", "すごーい！"], "reading": "すごい", "meaning": "称賛・驚き", "category": "褒め", "usage": ["褒め", "驚き"], "formality": 2, "persona_theme": ["応援強化", "褒め強化"], "text_size": "large"},
    {"id": "isshoni", "text": "一緒にがんばろ！", "text_variants": ["一緒にがんばろう！", "一緒に頑張ろう"], "reading": "いっしょにがんばろう", "meaning": "共に頑張る", "category": "応援", "usage": ["応援", "仲間意識"], "formality": 2, "persona_theme": ["応援強化"], "text_size": "normal"},
]


# ==================== リアクションマスタ シードデータ ====================

REACTION_SEEDS = [
    # === コア12枠 ===
    {"id": "ryo", "text_id": "ryo", "pose_id": "peace_sign", "emotion": "元気にうなずく、即レス感", "slot_type": "core", "priority": 100, "is_essential": True, "persona_age": ["Teen", "20s"], "persona_target": ["Friend"]},
    {"id": "okke", "text_id": "okke", "pose_id": "thumbs_up", "emotion": "明るく返事、にっこり笑顔", "slot_type": "core", "priority": 99, "is_essential": True, "persona_age": ["Teen", "20s", "30s"], "persona_target": ["Friend", "Family"]},
    {"id": "unun", "text_id": "unun", "pose_id": "nod", "emotion": "やさしくうなずく、共感の目", "slot_type": "core", "priority": 98, "is_essential": True, "persona_target": ["Friend", "Family"]},
    {"id": "wakaru", "text_id": "wakaru", "pose_id": "empathy_hands", "emotion": "大きくうなずく、わかるー！の顔", "slot_type": "core", "priority": 97, "is_essential": True, "persona_age": ["Teen", "20s", "30s"], "persona_target": ["Friend"]},
    {"id": "naruhodo", "text_id": "naruhodo", "pose_id": "chin_hand", "emotion": "納得の表情、ふむふむ", "slot_type": "core", "priority": 96, "is_essential": True},
    {"id": "arigato", "text_id": "arigato", "pose_id": "light_bow", "emotion": "感謝の笑顔、嬉しそう", "slot_type": "core", "priority": 95, "is_essential": True},
    {"id": "daisuki", "text_id": "daisuki", "pose_id": "heart_hands", "emotion": "大好きの気持ち、キラキラ目", "slot_type": "core", "priority": 94, "persona_target": ["Friend", "Partner", "Family"]},
    {"id": "gomenne", "text_id": "gomenne", "pose_id": "tehepero", "emotion": "申し訳なさそう、てへぺろ", "slot_type": "core", "priority": 93},
    {"id": "chottomatte", "text_id": "chottomatte", "pose_id": "stop_hands", "emotion": "焦り顔、待って！", "slot_type": "core", "priority": 92},
    {"id": "imamuri", "text_id": "imamuri", "pose_id": "x_sign", "emotion": "困り顔、今は無理", "slot_type": "core", "priority": 91, "persona_age": ["Teen", "20s"], "persona_target": ["Friend"]},
    {"id": "eh", "text_id": "eh", "pose_id": "wide_eyes", "emotion": "目まんまる、軽い驚き", "slot_type": "core", "priority": 90},
    {"id": "baibai", "text_id": "baibai", "pose_id": "wave_goodbye", "emotion": "にこやか、バイバイ", "slot_type": "core", "priority": 89, "is_essential": True},

    # === テーマ強化（ツッコミ）6枠 ===
    {"id": "nandeyanen", "text_id": "nandeyanen", "pose_id": "tsukkomi", "emotion": "あきれ顔、ツッコミ", "slot_type": "theme", "priority": 80, "persona_theme": ["ツッコミ強化"], "persona_age": ["Teen", "20s", "30s"], "persona_target": ["Friend"]},
    {"id": "chigauchigau", "text_id": "chigauchigau", "pose_id": "deny_wave", "emotion": "否定の表情、ちがうちがう", "slot_type": "theme", "priority": 79, "persona_target": ["Friend"]},
    {"id": "usodesho", "text_id": "usodesho", "pose_id": "mouth_cover_surprise", "emotion": "信じられない顔、驚き", "slot_type": "theme", "priority": 78},
    {"id": "maji", "text_id": "maji", "pose_id": "intense_stare", "emotion": "目を見開く、マジ？", "slot_type": "theme", "priority": 77, "persona_age": ["Teen", "20s", "30s"]},
    {"id": "eeee", "text_id": "eeee", "pose_id": "hands_up_surprise", "emotion": "超驚き、両手上げ", "slot_type": "theme", "priority": 76},
    {"id": "waratta", "text_id": "waratta", "pose_id": "laughing_hard", "emotion": "爆笑、涙出る", "slot_type": "theme", "priority": 75, "persona_age": ["Teen", "20s", "30s"]},

    # === 褒め2枠 ===
    {"id": "iijan", "text_id": "iijan", "pose_id": "ok_sign", "emotion": "自信満々の笑顔、軽く肯定", "slot_type": "theme", "priority": 85, "persona_theme": ["褒め強化"]},
    {"id": "kyoubijuiijan", "text_id": "kyoubijuiijan", "pose_id": "ok_sign", "emotion": "自信満々の笑顔、褒める表情", "slot_type": "theme", "priority": 84, "outfit": "黒い革ジャケット", "persona_theme": ["褒め強化"]},

    # === 反応・遊び4枠 ===
    {"id": "piyo", "text_id": "piyo", "pose_id": "with_bird", "emotion": "嬉しそう、インコと一緒", "slot_type": "reaction", "priority": 70},
    {"id": "yatta", "text_id": "yatta", "pose_id": "banzai", "emotion": "大喜び、やったー！", "slot_type": "reaction", "priority": 69},
    {"id": "ganbaru", "text_id": "ganbaru", "pose_id": "fist_pump", "emotion": "やる気満々、頑張る", "slot_type": "reaction", "priority": 68},
    {"id": "oyasumi", "text_id": "oyasumi", "pose_id": "sleepy_face", "emotion": "眠そう、おやすみ", "slot_type": "reaction", "priority": 67},

    # === オリジナル ===
    {"id": "kimikimi", "text_id": "kimikimi", "pose_id": "kimikimi", "emotion": "元気いっぱい、応援", "slot_type": "theme", "priority": 86, "persona_theme": ["応援強化"], "source": "custom"},

    # === 共感強化テーマ（8枠） ===
    {"id": "sorena", "text_id": "sorena", "pose_id": "pointing", "emotion": "大きくうなずく、共感の表情", "slot_type": "theme", "priority": 80, "persona_theme": ["共感強化"], "persona_age": ["Teen", "20s", "30s"], "persona_target": ["Friend"]},
    {"id": "hontosore", "text_id": "hontosore", "pose_id": "empathy_hands", "emotion": "深くうなずく、完全同意", "slot_type": "theme", "priority": 79, "persona_theme": ["共感強化"]},
    {"id": "donmai", "text_id": "donmai", "pose_id": "head_pat", "emotion": "優しい笑顔、慰め", "slot_type": "theme", "priority": 78, "persona_theme": ["共感強化"]},
    {"id": "daijoubu", "text_id": "daijoubu", "pose_id": "praying", "emotion": "安心させる微笑み", "slot_type": "theme", "priority": 77, "persona_theme": ["共感強化"]},
    {"id": "ganbattane", "text_id": "ganbattane", "pose_id": "clap", "emotion": "温かい笑顔、頑張りを認める", "slot_type": "theme", "priority": 76, "persona_theme": ["共感強化"]},
    {"id": "tsuraiyone", "text_id": "tsuraiyone", "pose_id": "hand_on_chest", "emotion": "心配そうな優しい目、寄り添い", "slot_type": "theme", "priority": 75, "persona_theme": ["共感強化"]},
    {"id": "yokattane", "text_id": "yokattane", "pose_id": "banzai", "emotion": "一緒に喜ぶ笑顔、安堵", "slot_type": "theme", "priority": 74, "persona_theme": ["共感強化"]},
    {"id": "unun_kyoukan", "text_id": "unun", "pose_id": "nod", "emotion": "何度もうなずく、深い共感", "slot_type": "theme", "priority": 73, "persona_theme": ["共感強化"]},

    # === 家族強化テーマ（8枠） ===
    {"id": "gohandekita", "text_id": "gohandekita", "pose_id": "megaphone", "emotion": "元気に呼びかける", "slot_type": "theme", "priority": 80, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "kaeruyo", "text_id": "kaeruyo", "pose_id": "wave_goodbye", "emotion": "にこやかに手を振る", "slot_type": "theme", "priority": 79, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "kaimono", "text_id": "kaimono", "pose_id": "fist_pump", "emotion": "やる気の笑顔", "slot_type": "theme", "priority": 78, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "kiwotsukete", "text_id": "kiwotsukete", "pose_id": "praying", "emotion": "心配そうな優しい目", "slot_type": "theme", "priority": 77, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "imadoko", "text_id": "imadoko", "pose_id": "chin_hand", "emotion": "ちょっと心配、疑問の表情", "slot_type": "theme", "priority": 76, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "samui", "text_id": "samui", "pose_id": "cheek_rest", "emotion": "ぶるぶる、寒そうな顔", "slot_type": "theme", "priority": 75, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "otsukare_kazoku", "text_id": "oyasumi", "pose_id": "sleepy_face", "emotion": "穏やかな笑顔、おつかれ", "slot_type": "theme", "priority": 74, "persona_theme": ["家族強化"], "persona_target": ["Family"]},
    {"id": "arigato_kazoku", "text_id": "arigato", "pose_id": "light_bow", "emotion": "感謝の気持ち、丁寧なお辞儀", "slot_type": "theme", "priority": 73, "persona_theme": ["家族強化"], "persona_target": ["Family"]},

    # === 応援強化テーマ（8枠） ===
    {"id": "ganbare", "text_id": "ganbare", "pose_id": "fist_pump", "emotion": "力強い笑顔、応援", "slot_type": "theme", "priority": 85, "persona_theme": ["応援強化"]},
    {"id": "fight", "text_id": "fight", "pose_id": "fist_double", "emotion": "元気いっぱい、拳を掲げる", "slot_type": "theme", "priority": 84, "persona_theme": ["応援強化"]},
    {"id": "ouenshiteru", "text_id": "ouenshiteru", "pose_id": "megaphone", "emotion": "温かい笑顔、全力応援", "slot_type": "theme", "priority": 83, "persona_theme": ["応援強化"]},
    {"id": "shinjiteru", "text_id": "shinjiteru", "pose_id": "hand_on_chest", "emotion": "真っすぐな目、信頼の笑顔", "slot_type": "theme", "priority": 82, "persona_theme": ["応援強化"]},
    {"id": "sasuga", "text_id": "sasuga", "pose_id": "clap", "emotion": "感心した顔、称賛", "slot_type": "theme", "priority": 81, "persona_theme": ["応援強化", "褒め強化"]},
    {"id": "sugoi", "text_id": "sugoi", "pose_id": "hands_up_surprise", "emotion": "目をキラキラ、称賛と驚き", "slot_type": "theme", "priority": 80, "persona_theme": ["応援強化", "褒め強化"]},
    {"id": "isshoni", "text_id": "isshoni", "pose_id": "pointing", "emotion": "仲間意識、温かい笑顔", "slot_type": "theme", "priority": 79, "persona_theme": ["応援強化"]},
    {"id": "daijoubu_ouen", "text_id": "daijoubu", "pose_id": "head_pat", "emotion": "安心させる微笑み、大丈夫", "slot_type": "theme", "priority": 78, "persona_theme": ["応援強化"]},

    # === 褒め強化テーマ追加（3枠） ===
    {"id": "sasuga_home", "text_id": "sasuga", "pose_id": "thumbs_up", "emotion": "感心した顔、さすがの表情", "slot_type": "theme", "priority": 83, "persona_theme": ["褒め強化"]},
    {"id": "sugoi_home", "text_id": "sugoi", "pose_id": "clap", "emotion": "キラキラ目、すごい！", "slot_type": "theme", "priority": 82, "persona_theme": ["褒め強化"]},
    {"id": "ganbattane_home", "text_id": "ganbattane", "pose_id": "head_pat", "emotion": "温かい笑顔、努力を認める", "slot_type": "theme", "priority": 81, "persona_theme": ["褒め強化"]},

    # === ツッコミ強化テーマ追加（2枠） ===
    {"id": "maji_tsukko", "text_id": "maji", "pose_id": "tsukkomi", "emotion": "あきれ顔、マジで？", "slot_type": "theme", "priority": 74, "persona_theme": ["ツッコミ強化"]},
    {"id": "eh_tsukko", "text_id": "eh", "pose_id": "hands_up_surprise", "emotion": "超驚き、えっ！？", "slot_type": "theme", "priority": 73, "persona_theme": ["ツッコミ強化"]},

    # === 汎用追加（全テーマで使える） ===
    {"id": "otsukare", "text_id": "oyasumi", "pose_id": "wave_goodbye", "emotion": "にこやか、お疲れ様", "slot_type": "core", "priority": 88, "is_essential": True},
]


# ==================== ペルソナ設定 シードデータ ====================

PERSONA_CONFIG_SEEDS = [
    # === 友達向け (Friend) ===
    # Teen x Friend
    {
        "age": "Teen", "target": "Friend", "theme": None, "intensity": 1,
        "core_slots": 14, "theme_slots": 6, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "10代友達向け・控えめ",
        "example_texts": ["りょ！", "おっけ！", "わかる"],
    },
    {
        "age": "Teen", "target": "Friend", "theme": None, "intensity": 2,
        "core_slots": 12, "theme_slots": 8, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "10代友達向け・バランス",
        "example_texts": ["りょ！", "おっけー！", "わかるー！", "なんでやねん！"],
    },
    {
        "age": "Teen", "target": "Friend", "theme": None, "intensity": 3,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "10代友達向け・特化",
        "example_texts": ["りょ！", "草", "ウケる！", "まじ！？"],
    },
    # 20s x Friend
    {
        "age": "20s", "target": "Friend", "theme": None, "intensity": 1,
        "core_slots": 14, "theme_slots": 6, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・控えめ",
    },
    {
        "age": "20s", "target": "Friend", "theme": None, "intensity": 2,
        "core_slots": 12, "theme_slots": 8, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・バランス（デフォルト）",
        "essential_reactions": ["ryo", "okke", "arigato", "baibai"],
    },
    {
        "age": "20s", "target": "Friend", "theme": None, "intensity": 3,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・特化",
    },
    # 20s x Friend x ツッコミ強化
    {
        "age": "20s", "target": "Friend", "theme": "ツッコミ強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・ツッコミ特化",
        "essential_reactions": ["nandeyanen", "maji", "usodesho"],
    },
    # 20s x Friend x 褒め強化
    {
        "age": "20s", "target": "Friend", "theme": "褒め強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・褒め特化",
        "essential_reactions": ["iijan", "kyoubijuiijan"],
    },
    # 30s x Friend
    {
        "age": "30s", "target": "Friend", "theme": None, "intensity": 2,
        "core_slots": 12, "theme_slots": 8, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "30代友達向け・バランス",
    },

    # === 家族向け (Family) ===
    {
        "age": "20s", "target": "Family", "theme": None, "intensity": 2,
        "core_slots": 14, "theme_slots": 6, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "20代家族向け・バランス",
        "essential_reactions": ["arigato", "gomenne", "oyasumi"],
    },
    {
        "age": "30s", "target": "Family", "theme": None, "intensity": 2,
        "core_slots": 14, "theme_slots": 6, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "30代家族向け・バランス",
        "essential_reactions": ["arigato", "gomenne", "oyasumi", "ganbaru"],
    },
    {
        "age": "40s", "target": "Family", "theme": None, "intensity": 2,
        "core_slots": 16, "theme_slots": 4, "reaction_slots": 4,
        "recommended_formality": 3, "recommended_text_size": "normal",
        "description": "40代家族向け・バランス",
        "excluded_reactions": ["nandeyanen", "maji"],
    },

    # === パートナー向け (Partner) ===
    {
        "age": "20s", "target": "Partner", "theme": None, "intensity": 2,
        "core_slots": 12, "theme_slots": 8, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代恋人向け・バランス",
        "essential_reactions": ["daisuki", "arigato"],
    },
    {
        "age": "30s", "target": "Partner", "theme": None, "intensity": 2,
        "core_slots": 12, "theme_slots": 8, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "30代恋人向け・バランス",
        "essential_reactions": ["daisuki", "arigato", "oyasumi"],
    },

    # === 仕事向け (Work) ===
    {
        "age": "20s", "target": "Work", "theme": None, "intensity": 2,
        "core_slots": 16, "theme_slots": 4, "reaction_slots": 4,
        "recommended_formality": 3, "recommended_text_size": "normal",
        "description": "20代仕事向け・バランス",
        "essential_reactions": ["okke", "arigato", "naruhodo"],
        "excluded_reactions": ["nandeyanen", "maji", "waratta", "piyo"],
    },
    {
        "age": "30s", "target": "Work", "theme": None, "intensity": 2,
        "core_slots": 16, "theme_slots": 4, "reaction_slots": 4,
        "recommended_formality": 3, "recommended_text_size": "normal",
        "description": "30代仕事向け・バランス",
        "essential_reactions": ["okke", "arigato", "naruhodo", "ganbaru"],
        "excluded_reactions": ["nandeyanen", "maji", "waratta", "piyo", "daisuki"],
    },

    # === テーマ特化追加 ===
    # 30s x Friend x 共感強化
    {
        "age": "30s", "target": "Friend", "theme": "共感強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "30代友達向け・共感特化",
        "essential_reactions": ["sorena", "donmai", "daijoubu", "yokattane"],
    },
    # 20s x Friend x 共感強化
    {
        "age": "20s", "target": "Friend", "theme": "共感強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・共感特化",
        "essential_reactions": ["sorena", "donmai", "daijoubu"],
    },
    # 30s x Friend x 応援強化
    {
        "age": "30s", "target": "Friend", "theme": "応援強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "large",
        "description": "30代友達向け・応援特化",
        "essential_reactions": ["ganbare", "fight", "ouenshiteru", "shinjiteru"],
    },
    # 20s x Friend x 応援強化
    {
        "age": "20s", "target": "Friend", "theme": "応援強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 1, "recommended_text_size": "large",
        "description": "20代友達向け・応援特化",
        "essential_reactions": ["ganbare", "fight", "ouenshiteru"],
    },
    # 30s x Family x 家族強化
    {
        "age": "30s", "target": "Family", "theme": "家族強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 2, "recommended_text_size": "normal",
        "description": "30代家族向け・家族特化",
        "essential_reactions": ["gohandekita", "kiwotsukete", "kaeruyo"],
    },
    # 40s x Family x 家族強化
    {
        "age": "40s", "target": "Family", "theme": "家族強化", "intensity": 2,
        "core_slots": 10, "theme_slots": 10, "reaction_slots": 4,
        "recommended_formality": 3, "recommended_text_size": "normal",
        "description": "40代家族向け・家族特化",
        "essential_reactions": ["gohandekita", "kiwotsukete", "kaeruyo", "imadoko"],
    },
]


def seed_all():
    """全シードデータを投入"""
    print("=" * 50)
    print("Master Data Seed")
    print("=" * 50)

    # データベース初期化
    init_database()

    # ポーズマスタ投入
    print(f"\n[1/4] pose_master: {len(POSE_SEEDS)} items")
    for pose in POSE_SEEDS:
        upsert_pose_master(**pose)
        print(f"  + {pose['id']}: {pose['name']}")

    # セリフマスタ投入
    print(f"\n[2/4] text_master: {len(TEXT_SEEDS)} items")
    for text in TEXT_SEEDS:
        upsert_text_master(**text)
        print(f"  + {text['id']}: {text['text']}")

    # リアクションマスタ投入
    print(f"\n[3/4] reactions_master: {len(REACTION_SEEDS)} items")
    for reaction in REACTION_SEEDS:
        upsert_reactions_master(**reaction)
        print(f"  + {reaction['id']}: {reaction['text_id']} x {reaction['pose_id']}")

    # ペルソナ設定投入
    print(f"\n[4/4] persona_config: {len(PERSONA_CONFIG_SEEDS)} items")
    for config in PERSONA_CONFIG_SEEDS:
        upsert_persona_config(**config)
        theme_str = config.get('theme') or 'default'
        print(f"  + {config['age']}/{config['target']}/{theme_str}/intensity{config['intensity']}")

    # 結果確認
    print("\n" + "=" * 50)
    print("Seed completed")
    print("=" * 50)

    poses = list_pose_master()
    texts = list_text_master()
    personas = list_persona_config()
    print(f"\nResults:")
    print(f"  pose_master: {len(poses)}")
    print(f"  text_master: {len(texts)}")
    print(f"  persona_config: {len(personas)}")


if __name__ == "__main__":
    seed_all()
