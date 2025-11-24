#!/bin/bash
# WP-AI 起動スクリプト (Linux/Mac用)
# このスクリプトは wp-ai アプリケーションを起動します

echo "=== WP-AI 起動スクリプト ==="
echo ""

# プロジェクトディレクトリに移動
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$SCRIPT_DIR/wp-ai"
cd "$PROJECT_DIR"

# 仮想環境のパスを確認
VENV_PATH="$PROJECT_DIR/.venv"
VENV_ACTIVATE="$VENV_PATH/bin/activate"

# 仮想環境が存在しない場合は作成
if [ ! -d "$VENV_PATH" ]; then
    echo "仮想環境が見つかりません。新しい仮想環境を作成します..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "エラー: 仮想環境の作成に失敗しました"
        exit 1
    fi
    echo "仮想環境を作成しました"
fi

# 仮想環境を有効化
echo "仮想環境を有効化しています..."
source "$VENV_ACTIVATE"

# 依存関係をインストール（初回または更新時）
REQUIREMENTS_CHECK="$VENV_PATH/installed.txt"
if [ ! -f "$REQUIREMENTS_CHECK" ]; then
    echo "依存関係をインストールしています..."
    pip install -e .
    if [ $? -eq 0 ]; then
        echo "installed" > "$REQUIREMENTS_CHECK"
        echo "依存関係のインストールが完了しました"
    else
        echo "警告: 依存関係のインストールに問題がある可能性があります"
    fi
fi

echo ""
echo "=== WP-AI の起動準備が完了しました ==="
echo ""
echo "使用方法:"
echo "  wp-ai --help                    # ヘルプを表示"
echo "  wp-ai diagnose                  # WordPressを診断"
echo "  wp-ai ssh test                  # SSH接続をテスト"
echo "  wp-ai config show               # 設定を表示"
echo ""
echo "対話モードで起動する場合:"
echo "  wp-ai"
echo ""

# APIキーの設定確認
echo "APIキーの設定を確認しています..."
API_KEY_CHECK=$(python -c "import keyring; key = keyring.get_password('wp-ai', 'gemini_api_key'); print('set' if key else 'not_set')" 2>/dev/null)
if [ "$API_KEY_CHECK" = "not_set" ]; then
    echo "警告: Gemini APIキーが設定されていません"
    echo "APIキーを設定するには以下を実行してください:"
    echo "  python set_api_key.py"
    echo ""
fi

# 起動モードの選択
echo "起動モードを選択してください:"
echo "  1) 対話モードで起動"
echo "  2) コマンド実行モード（コマンドを入力）"
echo "  3) ヘルプを表示"
echo "  4) 終了"
echo ""
read -p "選択 (1-4): " choice

case $choice in
    1)
        echo ""
        echo "対話モードで起動します..."
        wp-ai
        ;;
    2)
        echo ""
        read -p "実行するコマンドを入力してください (例: diagnose, ssh test): " command
        if [ -n "$command" ]; then
            echo ""
            echo "コマンドを実行します: wp-ai $command"
            wp-ai $command
        fi
        ;;
    3)
        echo ""
        wp-ai --help
        ;;
    4)
        echo "終了します"
        exit 0
        ;;
    *)
        echo "無効な選択です。ヘルプを表示します。"
        wp-ai --help
        ;;
esac

echo ""
echo "スクリプトが終了しました"
