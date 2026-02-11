"""
LINEスタンプ生成 - 司令塔エージェント

対話で要件を収束させ、実行計画を作り、承認後に実行する。
検証して要約を返し、セッションと品質ログを更新する。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import json

from .tools import LINESTAMP_TOOLS


class ConversationState(Enum):
    """会話の状態"""
    INIT = "init"                      # 初期状態
    PURPOSE_CONFIRM = "purpose_confirm" # 目的確認
    INPUT_COLLECT = "input_collect"    # 入力収集
    PLAN_PRESENT = "plan_present"      # 実行計画提示
    APPROVAL = "approval"              # 承認待ち
    EXECUTING = "executing"            # 実行中
    VALIDATING = "validating"          # 検証中
    SUMMARY = "summary"                # まとめ


class Purpose(Enum):
    """目的"""
    GENERATE = "generate"         # 新規生成
    REGENERATE = "regenerate"     # 再生成
    POSE_SEARCH = "pose_search"   # ポーズ辞書
    QC_STATS = "qc_stats"         # 品質統計
    VALIDATE = "validate"         # 検証


@dataclass
class DraftConfig:
    """設定ドラフト"""
    image_path: Optional[str] = None
    style: str = "sd_25"
    text_mode: str = "deka"
    outline: str = "bold"
    persona_age: Optional[str] = None
    persona_target: Optional[str] = None
    persona_theme: Optional[str] = None
    persona_intensity: int = 2
    items_mode: str = "auto"
    output_dir: Optional[str] = None
    count: int = 24
    output_format: str = "package"  # package / eco24


@dataclass
class ExecutionPlan:
    """実行計画"""
    tool_name: str
    parameters: Dict[str, Any]
    expected_api_calls: int = 2
    output_dir: Optional[str] = None
    validation_items: List[str] = field(default_factory=list)


@dataclass
class ConductorState:
    """司令塔の状態"""
    conversation_state: ConversationState = ConversationState.INIT
    purpose: Optional[Purpose] = None
    session_id: Optional[str] = None
    draft_config: DraftConfig = field(default_factory=DraftConfig)
    reactions_draft: List[Dict[str, Any]] = field(default_factory=list)
    execution_plan: Optional[ExecutionPlan] = None
    outputs: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class LinestampConductor:
    """
    LINEスタンプ生成の司令塔エージェント。

    会話フロー:
    1. 目的確認 → 2. 入力収集 → 3. 実行計画提示 → 4. 承認 → 5. 実行 → 6. 検証 → 7. まとめ
    """

    def __init__(self):
        self.state = ConductorState()
        self.tools = LINESTAMP_TOOLS

    def reset(self):
        """状態をリセット"""
        self.state = ConductorState()

    def get_state_summary(self) -> str:
        """現在の状態サマリーを返す"""
        return f"""
## 現在の状態

- 会話状態: {self.state.conversation_state.value}
- 目的: {self.state.purpose.value if self.state.purpose else '未設定'}
- セッションID: {self.state.session_id or '未設定'}
- 画像: {self.state.draft_config.image_path or '未設定'}
- スタイル: {self.state.draft_config.style}
- 出力形式: {self.state.draft_config.output_format}
"""

    def get_purpose_options(self) -> str:
        """目的選択肢を返す"""
        return """
## 何をしたいですか？

1. **新規生成** - 新しいスタンプを作成
2. **再生成** - 過去のセッションから再生成
3. **ポーズ辞書** - ポーズを検索・追加
4. **品質統計** - 成功率やテンプレートを確認
5. **検証** - 出力を検証
"""

    def set_purpose(self, purpose: str) -> str:
        """目的を設定"""
        purpose_map = {
            "1": Purpose.GENERATE,
            "generate": Purpose.GENERATE,
            "新規": Purpose.GENERATE,
            "2": Purpose.REGENERATE,
            "regenerate": Purpose.REGENERATE,
            "再生成": Purpose.REGENERATE,
            "3": Purpose.POSE_SEARCH,
            "pose": Purpose.POSE_SEARCH,
            "ポーズ": Purpose.POSE_SEARCH,
            "4": Purpose.QC_STATS,
            "qc": Purpose.QC_STATS,
            "品質": Purpose.QC_STATS,
            "5": Purpose.VALIDATE,
            "validate": Purpose.VALIDATE,
            "検証": Purpose.VALIDATE,
        }

        normalized = purpose.lower().strip()
        self.state.purpose = purpose_map.get(normalized)

        if self.state.purpose:
            self.state.conversation_state = ConversationState.INPUT_COLLECT
            return self._get_input_prompt()
        else:
            return f"目的が認識できませんでした: {purpose}\n" + self.get_purpose_options()

    def _get_input_prompt(self) -> str:
        """目的に応じた入力プロンプトを返す"""
        if self.state.purpose == Purpose.GENERATE:
            return """
## 新規生成 - 入力情報

以下を教えてください:

1. **参照画像のパス** (必須)
   例: input/photo.jpg

2. **スタイル** (任意、デフォルト: sd_25)
   - sd_25: 標準ちびキャラ（推奨）
   - sd_10: 超デフォルメ（1頭身）
   - sd_30: ジェスチャー重視（3頭身）
   - face_only: 顔だけ
   - yuru_line: ゆる線画

3. **ペルソナ** (任意)
   - 年代: Teen / 20s / 30s / 40s / 50s+
   - 相手: Friend / Family / Partner / Work
   - テーマ: 共感強化 / ツッコミ強化 / 褒め強化 / 家族強化 / 応援強化

4. **出力形式** (任意、デフォルト: package)
   - package: 申請パッケージ（24枚+main+tab+ZIP）
   - eco24: 24枚のみ
"""

        elif self.state.purpose == Purpose.REGENERATE:
            return """
## 再生成 - セッションID

再生成するセッションIDを指定してください。

セッション一覧を見るには `list` と入力してください。
"""

        elif self.state.purpose == Purpose.POSE_SEARCH:
            return """
## ポーズ辞書 - 検索

検索キーワードを入力してください。

例: 肯定、顎、評価
"""

        elif self.state.purpose == Purpose.QC_STATS:
            return """
## 品質統計

統計を表示します。最小使用回数を指定できます（デフォルト: 3）。
"""

        elif self.state.purpose == Purpose.VALIDATE:
            return """
## 検証

検証する出力ディレクトリを指定してください。

例: output/linestamp/20260127_195145
"""

        return "入力を待っています..."

    def set_input(self, key: str, value: Any) -> str:
        """入力を設定"""
        config = self.state.draft_config

        if key == "image_path":
            config.image_path = value
        elif key == "style":
            config.style = value
        elif key == "text_mode":
            config.text_mode = value
        elif key == "outline":
            config.outline = value
        elif key == "persona_age":
            config.persona_age = value
        elif key == "persona_target":
            config.persona_target = value
        elif key == "persona_theme":
            config.persona_theme = value
        elif key == "persona_intensity":
            config.persona_intensity = int(value)
        elif key == "items_mode":
            config.items_mode = value
        elif key == "output_format":
            config.output_format = value
        elif key == "output_dir":
            config.output_dir = value
        else:
            return f"不明な入力キー: {key}"

        return f"設定しました: {key} = {value}"

    def create_execution_plan(self) -> str:
        """実行計画を作成"""
        config = self.state.draft_config

        if self.state.purpose == Purpose.GENERATE:
            if not config.image_path:
                return "エラー: 参照画像が指定されていません"

            tool_name = "linestamp_generate_package"
            parameters = {
                "image_path": config.image_path,
                "style": config.style,
                "text_mode": config.text_mode,
                "outline": config.outline,
                "items_mode": config.items_mode,
            }

            if config.persona_age:
                parameters["persona_age"] = config.persona_age
            if config.persona_target:
                parameters["persona_target"] = config.persona_target
            if config.persona_theme:
                parameters["persona_theme"] = config.persona_theme
            if config.persona_age or config.persona_target or config.persona_theme:
                parameters["persona_intensity"] = config.persona_intensity
            if config.output_dir:
                parameters["output_dir"] = config.output_dir

            self.state.execution_plan = ExecutionPlan(
                tool_name=tool_name,
                parameters=parameters,
                expected_api_calls=2,
                validation_items=[
                    "スタンプ画像24枚",
                    "main.png (240x240)",
                    "tab.png (96x74)",
                    "submission.zip"
                ]
            )

        elif self.state.purpose == Purpose.REGENERATE:
            if not self.state.session_id:
                return "エラー: セッションIDが指定されていません"

            self.state.execution_plan = ExecutionPlan(
                tool_name="linestamp_regenerate_session",
                parameters={"session_id": self.state.session_id},
                expected_api_calls=2,
                validation_items=["スタンプ画像", "main.png", "tab.png", "ZIP"]
            )

        self.state.conversation_state = ConversationState.PLAN_PRESENT
        return self._format_execution_plan()

    def _format_execution_plan(self) -> str:
        """実行計画をフォーマット"""
        plan = self.state.execution_plan
        if not plan:
            return "実行計画がありません"

        params_str = json.dumps(plan.parameters, ensure_ascii=False, indent=2)

        return f"""
## 実行計画

**ツール**: {plan.tool_name}

**パラメータ**:
```json
{params_str}
```

**予想API呼び出し**: {plan.expected_api_calls}回

**検証項目**:
{chr(10).join(f'- {item}' for item in plan.validation_items)}

---

この計画で実行しますか？ (yes/no)
"""

    def approve(self) -> str:
        """承認して実行"""
        if not self.state.execution_plan:
            return "実行計画がありません"

        self.state.conversation_state = ConversationState.EXECUTING
        return self._execute()

    def _execute(self) -> str:
        """ツールを実行"""
        plan = self.state.execution_plan
        tool_info = self.tools.get(plan.tool_name)

        if not tool_info:
            return f"ツールが見つかりません: {plan.tool_name}"

        tool_func = tool_info["function"]

        try:
            result = tool_func(**plan.parameters)
            self.state.outputs["result"] = result

            if result.get("success"):
                self.state.conversation_state = ConversationState.VALIDATING
                return self._validate()
            else:
                error = result.get("error", {})
                self.state.errors.append(error.get("message", "不明なエラー"))
                return f"""
## 実行エラー

**コード**: {error.get('code', 'UNKNOWN')}
**メッセージ**: {error.get('message', '不明なエラー')}
**回復可能**: {error.get('recoverable', False)}

再試行しますか？ (yes/no)
"""

        except Exception as e:
            self.state.errors.append(str(e))
            return f"実行中にエラーが発生しました: {e}"

    def _validate(self) -> str:
        """出力を検証"""
        result = self.state.outputs.get("result", {})

        # TODO: linestamp_validate_output を呼び出して詳細検証

        self.state.conversation_state = ConversationState.SUMMARY
        return self._summarize()

    def _summarize(self) -> str:
        """まとめを生成"""
        result = self.state.outputs.get("result", {})

        return f"""
## 完了

{result.get('message', '処理が完了しました')}

**出力**:
```
{result.get('stdout', '')}
```

---

**次にできること**:
- 再生成: `regenerate`
- ポーズ辞書に登録: `pose add`
- テンプレートとして保存: `template save`
"""

    def process_input(self, user_input: str) -> str:
        """
        ユーザー入力を処理して応答を返す。

        これがAgent SDKから呼び出されるメインエントリポイント。
        """
        user_input = user_input.strip()

        # 状態に応じた処理
        if self.state.conversation_state == ConversationState.INIT:
            self.state.conversation_state = ConversationState.PURPOSE_CONFIRM
            return self.get_purpose_options()

        elif self.state.conversation_state == ConversationState.PURPOSE_CONFIRM:
            return self.set_purpose(user_input)

        elif self.state.conversation_state == ConversationState.INPUT_COLLECT:
            # 簡易パーサー: key=value 形式または自然言語
            if "=" in user_input:
                key, value = user_input.split("=", 1)
                return self.set_input(key.strip(), value.strip())

            # 特殊コマンド
            if user_input.lower() in ["done", "完了", "ok"]:
                return self.create_execution_plan()

            if user_input.lower() == "list":
                result = self.tools["linestamp_list_sessions"]["function"]()
                return result.get("stdout", "セッションがありません")

            # 目的に応じた入力解釈
            if self.state.purpose == Purpose.GENERATE:
                # 最初の入力は画像パスと仮定
                if not self.state.draft_config.image_path:
                    self.state.draft_config.image_path = user_input
                    return f"画像パスを設定しました: {user_input}\n\n他の設定を変更しますか？ (done で実行計画へ)"

            elif self.state.purpose == Purpose.REGENERATE:
                self.state.session_id = user_input
                return self.create_execution_plan()

            elif self.state.purpose == Purpose.POSE_SEARCH:
                result = self.tools["linestamp_pose_search"]["function"](keyword=user_input)
                return result.get("stdout", "結果がありません")

            elif self.state.purpose == Purpose.QC_STATS:
                result = self.tools["linestamp_qc_pose_stats"]["function"]()
                stats = result.get("stats", [])
                if stats:
                    lines = ["## ポーズ統計\n"]
                    for s in stats:
                        lines.append(f"- {s['pose_name']}: {s['success_rate']:.1%} ({s['uses']}回)")
                    return "\n".join(lines)
                return "統計データがありません"

            elif self.state.purpose == Purpose.VALIDATE:
                result = self.tools["linestamp_validate_output"]["function"](output_dir=user_input)
                if result.get("ok"):
                    return f"検証OK: {result.get('stamp_count')}枚のスタンプ"
                else:
                    issues = result.get("issues", [])
                    return "検証NG:\n" + "\n".join(f"- {i}" for i in issues)

            return f"入力を受け付けました: {user_input}"

        elif self.state.conversation_state == ConversationState.PLAN_PRESENT:
            if user_input.lower() in ["yes", "y", "はい", "ok"]:
                return self.approve()
            elif user_input.lower() in ["no", "n", "いいえ"]:
                self.state.conversation_state = ConversationState.INPUT_COLLECT
                return "キャンセルしました。設定を変更してください。\n" + self._get_input_prompt()
            else:
                return "yes または no で答えてください。"

        elif self.state.conversation_state == ConversationState.SUMMARY:
            # まとめ後は新しいセッション開始
            self.reset()
            return self.process_input(user_input)

        return "不明な状態です。reset で最初からやり直してください。"
