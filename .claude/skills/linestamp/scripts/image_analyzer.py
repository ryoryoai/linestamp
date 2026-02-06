"""
マルチAI画像分析モジュール

スタンプ画像の内容を複数のAIモデルで分析して特徴を抽出
対応モデル: Claude Code CLI, Gemini CLI
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

# 利用可能なモデルタイプ
AnalyzerType = Literal["claude", "gemini"]

# モデル設定
GEMINI_MODEL = "gemini-2.0-flash"
CLAUDE_MODEL = "claude-sonnet-4-20250514"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# 共通の分析プロンプト
ANALYSIS_PROMPT = """このLINEスタンプ画像を分析してください。以下のJSON形式で回答してください：

```json
{
  "has_text": true/false,
  "text_content": "画像内のテキスト（あれば）",
  "text_language": "ja/en/etc",
  "text_intent": "greeting/thanks/apology/confirmation/rejection/love/encouragement/humor/other",
  "character_type": "human/animal/creature/object/text_only",
  "character_style": "cute/cool/realistic/simple/chibi/pixel",
  "expression": "happy/sad/angry/surprised/neutral/embarrassed/tired/excited",
  "pose": "standing/sitting/waving/bowing/pointing/thumbs_up/peace/heart/crying/sleeping/running/other",
  "mood": "cheerful/calm/energetic/romantic/funny/serious",
  "use_case": "daily_chat/work/love/family/friends/apology/thanks",
  "colors": ["主要な色1", "主要な色2"],
  "tags": ["特徴を表すタグ1", "タグ2", "タグ3"]
}
```

JSONのみを出力してください。説明は不要です。"""


@dataclass
class ImageAnalysisResult:
    """画像分析結果"""
    # テキスト関連
    has_text: bool = False
    text_content: str | None = None
    text_language: str | None = None
    text_intent: str | None = None

    # キャラクター関連
    character_type: str | None = None
    character_style: str | None = None
    expression: str | None = None
    pose: str | None = None

    # 全体的な特徴
    mood: str | None = None
    use_case: str | None = None
    colors: list[str] | None = None
    tags: list[str] | None = None

    # メタ情報
    analyzer: str | None = None
    raw_response: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_text": self.has_text,
            "text_content": self.text_content,
            "text_language": self.text_language,
            "text_intent": self.text_intent,
            "character_type": self.character_type,
            "character_style": self.character_style,
            "expression": self.expression,
            "pose": self.pose,
            "mood": self.mood,
            "use_case": self.use_case,
            "colors": self.colors,
            "tags": self.tags,
            "analyzer": self.analyzer,
        }


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """レスポンスからJSONを抽出してパース"""
    json_text = raw_text
    if "```json" in raw_text:
        json_text = raw_text.split("```json")[1].split("```")[0].strip()
    elif "```" in raw_text:
        parts = raw_text.split("```")
        if len(parts) >= 2:
            json_text = parts[1].split("```")[0].strip()

    return json.loads(json_text)


def result_from_dict(data: dict[str, Any], analyzer: str, raw: str) -> ImageAnalysisResult:
    """辞書から結果オブジェクトを生成"""
    return ImageAnalysisResult(
        has_text=data.get("has_text", False),
        text_content=data.get("text_content"),
        text_language=data.get("text_language"),
        text_intent=data.get("text_intent"),
        character_type=data.get("character_type"),
        character_style=data.get("character_style"),
        expression=data.get("expression"),
        pose=data.get("pose"),
        mood=data.get("mood"),
        use_case=data.get("use_case"),
        colors=data.get("colors"),
        tags=data.get("tags"),
        analyzer=analyzer,
        raw_response=raw,
    )


class BaseAnalyzer(ABC):
    """画像分析の基底クラス"""

    @property
    @abstractmethod
    def name(self) -> str:
        """分析器の名前"""
        pass

    @abstractmethod
    def analyze_image(
        self,
        image_path: Path | str,
        timeout_sec: float = 60.0,
    ) -> ImageAnalysisResult:
        """画像ファイルを分析"""
        pass

    def analyze_image_from_url(
        self,
        image_url: str,
        client: httpx.Client,
        timeout_sec: float = 60.0,
    ) -> ImageAnalysisResult:
        """URLから画像を取得して分析"""
        try:
            r = client.get(image_url, timeout=timeout_sec)
            r.raise_for_status()

            suffix = ".png"
            if ".gif" in image_url.lower():
                suffix = ".gif"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(r.content)
                temp_path = Path(f.name)

            try:
                return self.analyze_image(temp_path, timeout_sec)
            finally:
                temp_path.unlink(missing_ok=True)

        except Exception as e:
            log(f"  [error] Failed to fetch image: {e}")
            return ImageAnalysisResult(analyzer=self.name)


class ClaudeAnalyzer(BaseAnalyzer):
    """Claude Code CLI を使った画像分析"""

    @property
    def name(self) -> str:
        return "claude"

    def analyze_image(
        self,
        image_path: Path | str,
        timeout_sec: float = 60.0,
    ) -> ImageAnalysisResult:
        """Claude CLI で画像を分析"""
        image_path = Path(image_path)

        if not image_path.exists():
            log(f"  [error] Image not found: {image_path}")
            return ImageAnalysisResult(analyzer=self.name)

        try:
            # Claude CLI を呼び出し
            # claude -p "プロンプト" --model MODEL --output-format text 画像パス
            cmd = [
                "claude",
                "-p", ANALYSIS_PROMPT,
                "--model", CLAUDE_MODEL,
                "--output-format", "text",
                "--allowedTools", "",  # ツール無効化
                str(image_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                encoding="utf-8",
            )

            if result.returncode != 0:
                log(f"  [error] Claude CLI failed: {result.stderr}")
                return ImageAnalysisResult(analyzer=self.name, raw_response=result.stderr)

            raw_text = result.stdout.strip()
            data = parse_json_response(raw_text)
            return result_from_dict(data, self.name, raw_text)

        except subprocess.TimeoutExpired:
            log(f"  [error] Claude CLI timeout")
            return ImageAnalysisResult(analyzer=self.name)
        except json.JSONDecodeError as e:
            log(f"  [warn] JSON parse error: {e}")
            return ImageAnalysisResult(analyzer=self.name, raw_response=raw_text if 'raw_text' in dir() else None)
        except FileNotFoundError:
            log("  [error] Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
            return ImageAnalysisResult(analyzer=self.name)
        except Exception as e:
            log(f"  [error] Claude analysis failed: {e}")
            return ImageAnalysisResult(analyzer=self.name)


class GeminiAnalyzer(BaseAnalyzer):
    """Gemini CLI を使った画像分析"""

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "gemini"

    def _get_client(self):
        """Gemini クライアントを取得（遅延初期化）"""
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(
                    vertexai=True,
                    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "and-and-and-and-and"),
                    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                )
            except ImportError:
                raise RuntimeError("google-genai パッケージが必要です: pip install google-genai")
        return self._client

    def analyze_image(
        self,
        image_path: Path | str,
        timeout_sec: float = 60.0,
    ) -> ImageAnalysisResult:
        """Gemini で画像を分析"""
        from google.genai import types

        client = self._get_client()
        image_path = Path(image_path)

        with open(image_path, "rb") as f:
            image_data = f.read()

        suffix = image_path.suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")

        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_data, mime_type=mime_type),
                            types.Part.from_text(text=ANALYSIS_PROMPT),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=1024,
                ),
            )

            raw_text = response.text.strip()
            data = parse_json_response(raw_text)
            return result_from_dict(data, self.name, raw_text)

        except json.JSONDecodeError as e:
            log(f"  [warn] JSON parse error: {e}")
            return ImageAnalysisResult(analyzer=self.name, raw_response=raw_text if 'raw_text' in dir() else None)
        except Exception as e:
            log(f"  [error] Gemini analysis failed: {e}")
            return ImageAnalysisResult(analyzer=self.name)


# ==================== ファクトリ関数 ====================

def get_analyzer(analyzer_type: AnalyzerType) -> BaseAnalyzer:
    """指定されたタイプのアナライザを取得"""
    analyzers = {
        "claude": ClaudeAnalyzer,
        "gemini": GeminiAnalyzer,
    }
    if analyzer_type not in analyzers:
        raise ValueError(f"Unknown analyzer type: {analyzer_type}. Available: {list(analyzers.keys())}")
    return analyzers[analyzer_type]()


def get_available_analyzers() -> list[str]:
    """利用可能なアナライザ一覧"""
    return ["claude", "gemini"]


def analyze_sticker(
    image_url: str,
    client: httpx.Client,
    analyzer_type: AnalyzerType = "gemini",
    timeout_sec: float = 60.0,
) -> dict[str, Any]:
    """スタンプ画像を指定したモデルで分析"""
    analyzer = get_analyzer(analyzer_type)
    result = analyzer.analyze_image_from_url(image_url, client, timeout_sec)
    return result.to_dict()


# 後方互換性のためのエイリアス
def analyze_sticker_with_gemini(
    image_url: str,
    client: httpx.Client,
    analyzer: GeminiAnalyzer | None = None,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """後方互換: Geminiで分析"""
    if analyzer is None:
        analyzer = GeminiAnalyzer()
    result = analyzer.analyze_image_from_url(image_url, client, timeout_sec)
    return result.to_dict()


# ==================== CLI ====================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Image Analyzer CLI")
    parser.add_argument("target", help="Image path or URL")
    parser.add_argument(
        "--analyzer", "-a",
        choices=get_available_analyzers(),
        default="gemini",
        help="Analyzer to use (default: gemini)"
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="Timeout in seconds")

    args = parser.parse_args()

    analyzer = get_analyzer(args.analyzer)
    log(f"Using analyzer: {analyzer.name}")

    if args.target.startswith("http"):
        with httpx.Client() as client:
            result = analyzer.analyze_image_from_url(args.target, client, args.timeout)
    else:
        result = analyzer.analyze_image(args.target, args.timeout)

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
