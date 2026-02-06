#!/usr/bin/env python3
"""
LINEスタンプ生成 - Agent SDK 実行スクリプト

使用方法:
    # REPL モード（対話）
    python run.py

    # 単発実行
    python run.py --prompt "スタンプを作って"

    # Agent SDK 経由
    python run.py --sdk --prompt "input/photo.jpg からスタンプを生成して"

    # セッション継続
    python run.py --sdk --resume <session_id> --prompt "続きを実行して"

    # Pythonから直接
    from run import run_agent_sdk
    import asyncio
    asyncio.run(run_agent_sdk("スタンプを作って"))
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# パスを追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.conductor import LinestampConductor

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent


def run_repl():
    """REPLモードで実行"""
    conductor = LinestampConductor()

    print("=" * 60)
    print("LINEスタンプ生成 - 司令塔エージェント")
    print("=" * 60)
    print("コマンド: reset（リセット）, quit（終了）, status（状態）")
    print("=" * 60)
    print()

    # 初期プロンプト
    response = conductor.process_input("")
    print(response)
    print()

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("終了します。")
                break

            if user_input.lower() == "reset":
                conductor.reset()
                response = conductor.process_input("")
                print(response)
                print()
                continue

            if user_input.lower() == "status":
                print(conductor.get_state_summary())
                continue

            response = conductor.process_input(user_input)
            print()
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n終了します。")
            break
        except EOFError:
            print("\n終了します。")
            break


def run_single(prompt: str):
    """単発実行"""
    conductor = LinestampConductor()

    # 初期化
    conductor.process_input("")

    # プロンプト処理
    response = conductor.process_input(prompt)
    print(response)


async def run_agent_sdk(
    prompt: str,
    resume: Optional[str] = None,
    verbose: bool = False,
    use_cli_auth: bool = False
) -> Optional[str]:
    """
    Agent SDK 経由で実行

    Args:
        prompt: 実行するプロンプト
        resume: 継続するセッションID（任意）
        verbose: 詳細出力
        use_cli_auth: CLI認証を使用（ANTHROPIC_API_KEYを無視）

    Returns:
        セッションID（継続用）
    """
    import os

    # CLI認証を強制する場合、環境変数を一時的に削除
    original_api_key = None
    if use_cli_auth and 'ANTHROPIC_API_KEY' in os.environ:
        original_api_key = os.environ.pop('ANTHROPIC_API_KEY')
        if verbose:
            print("[CLI認証モード] ANTHROPIC_API_KEY を一時的に無効化")

    try:
        from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition
    except ImportError:
        print("claude-agent-sdk がインストールされていません。")
        print("pip install claude-agent-sdk でインストールしてください。")
        print()
        print("代わりに組み込みの司令塔を使用します...")
        # 環境変数を復元
        if original_api_key:
            os.environ['ANTHROPIC_API_KEY'] = original_api_key
        run_single(prompt)
        return None

    # オプション設定
    options_kwargs = {
        "cwd": str(PROJECT_ROOT),
        "setting_sources": ["project"],  # CLAUDE.md と skills を読み込む
        "allowed_tools": [
            "Read", "Write", "Edit", "Bash",
            "Glob", "Grep", "Skill", "Task",
            "AskUserQuestion"
        ],
        "permission_mode": "acceptEdits",  # 編集は自動承認
        "agents": {
            # LINEスタンプ生成専用サブエージェント
            "linestamp-generator": AgentDefinition(
                description="LINEスタンプ画像を生成するエージェント。Vertex AI (Gemini) を使用。",
                prompt="""あなたはLINEスタンプ生成の専門家です。

以下のツールを使って申請パッケージを生成します:
- generate_stamp.py: スタンプ画像生成
- pose_manager.py: ポーズ辞書管理
- session_manager.py: セッション管理

生成時は必ず:
1. 参照画像の存在確認
2. スタイル選択の確認
3. 出力形式の確認
を行ってから実行してください。""",
                tools=["Read", "Bash", "Glob", "Grep"]
            ),
            # 品質チェック専用サブエージェント
            "linestamp-qc": AgentDefinition(
                description="LINEスタンプの品質チェックを行うエージェント。",
                prompt="""生成されたスタンプの品質をチェックします:
- 画像サイズ（370x320px以下）
- ファイルサイズ（1MB以下）
- 透過PNG確認
- タブサイズ視認性（96x74px）
- main.png（240x240px）
- ZIP構成""",
                tools=["Read", "Bash", "Glob"]
            )
        }
    }

    # セッション継続
    if resume:
        options_kwargs["resume"] = resume

    options = ClaudeAgentOptions(**options_kwargs)

    session_id = None
    result_text = None

    try:
        async for message in query(prompt=prompt, options=options):
            # メッセージタイプに応じた処理
            msg_type = getattr(message, 'type', None)
            msg_subtype = getattr(message, 'subtype', None)

            # セッションID取得
            if msg_subtype == 'init':
                session_id = getattr(message, 'session_id', None)
                if verbose:
                    print(f"[Session] {session_id}")

            # 結果出力
            if hasattr(message, 'result'):
                result_text = message.result
                print(message.result)

            # アシスタントメッセージ
            elif msg_type == 'assistant':
                content = getattr(message, 'content', None)
                if content and verbose:
                    print(f"[Assistant] {content[:100]}...")

            # ツール使用
            elif msg_type == 'tool_use':
                tool_name = getattr(message, 'name', 'unknown')
                if verbose:
                    print(f"[Tool] {tool_name}")

            # ツール結果
            elif msg_type == 'tool_result':
                if verbose:
                    content = getattr(message, 'content', '')
                    print(f"[Result] {str(content)[:100]}...")

            # その他（デバッグ用）
            elif verbose:
                print(f"[{msg_type}] {message}")

    except Exception as e:
        print(f"エラー: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
    finally:
        # 環境変数を復元
        if original_api_key:
            os.environ['ANTHROPIC_API_KEY'] = original_api_key

    if session_id:
        print(f"\n[セッションID: {session_id}]")
        print("継続するには: python run.py --sdk --resume {session_id} --prompt '...'")

    return session_id


async def run_interactive_sdk():
    """Agent SDK を使った対話モード"""
    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError:
        print("claude-agent-sdk がインストールされていません。")
        print("REPLモードにフォールバックします...")
        run_repl()
        return

    print("=" * 60)
    print("LINEスタンプ生成 - Agent SDK モード")
    print("=" * 60)
    print("コマンド: quit（終了）, verbose（詳細表示切替）")
    print("=" * 60)
    print()

    session_id = None
    verbose = False

    while True:
        try:
            user_input = input("> ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("終了します。")
                break

            if user_input.lower() == "verbose":
                verbose = not verbose
                print(f"詳細表示: {'ON' if verbose else 'OFF'}")
                continue

            # Agent SDK で実行（セッション継続）
            session_id = await run_agent_sdk(
                prompt=user_input,
                resume=session_id,
                verbose=verbose
            )
            print()

        except KeyboardInterrupt:
            print("\n終了します。")
            break
        except EOFError:
            print("\n終了します。")
            break


def main():
    parser = argparse.ArgumentParser(
        description="LINEスタンプ生成 - 司令塔エージェント",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # REPLモード（組み込み司令塔）
  python run.py

  # Agent SDK で単発実行
  python run.py --sdk --prompt "input/photo.jpg からスタンプを生成"

  # Agent SDK で対話モード
  python run.py --sdk

  # セッション継続
  python run.py --sdk --resume abc123 --prompt "続きを実行"
"""
    )
    parser.add_argument(
        "--prompt", "-p",
        help="単発実行するプロンプト"
    )
    parser.add_argument(
        "--sdk",
        action="store_true",
        help="Agent SDK 経由で実行"
    )
    parser.add_argument(
        "--resume", "-r",
        help="継続するセッションID"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="詳細出力"
    )
    parser.add_argument(
        "--cli-auth",
        action="store_true",
        help="CLI認証を使用（ANTHROPIC_API_KEYを無視してサブスクリプション課金）"
    )

    args = parser.parse_args()

    if args.sdk:
        if args.prompt:
            # Agent SDK で単発実行
            asyncio.run(run_agent_sdk(
                prompt=args.prompt,
                resume=args.resume,
                verbose=args.verbose,
                use_cli_auth=args.cli_auth
            ))
        else:
            # Agent SDK で対話モード
            asyncio.run(run_interactive_sdk())
    else:
        if args.prompt:
            # 組み込み司令塔で単発実行
            run_single(args.prompt)
        else:
            # 組み込み司令塔でREPL
            run_repl()


if __name__ == "__main__":
    main()
