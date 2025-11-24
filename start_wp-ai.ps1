# WP-AI 起動スクリプト
# このスクリプトは wp-ai アプリケーションを起動します

Write-Host "=== WP-AI 起動スクリプト ===" -ForegroundColor Cyan
Write-Host ""

# プロジェクトディレクトリに移動
$projectDir = Join-Path $PSScriptRoot "wp-ai"
Set-Location $projectDir

# 仮想環境のパスを確認
$venvPath = Join-Path $projectDir ".venv"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

# 仮想環境が存在しない場合は作成
if (-not (Test-Path $venvPath)) {
    Write-Host "仮想環境が見つかりません。新しい仮想環境を作成します..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "エラー: 仮想環境の作成に失敗しました" -ForegroundColor Red
        exit 1
    }
    Write-Host "仮想環境を作成しました" -ForegroundColor Green
}

# 仮想環境を有効化
Write-Host "仮想環境を有効化しています..." -ForegroundColor Yellow
& $venvActivate

# 依存関係をインストール（初回または更新時）
$requirementsCheck = Join-Path $venvPath "installed.txt"
if (-not (Test-Path $requirementsCheck)) {
    Write-Host "依存関係をインストールしています..." -ForegroundColor Yellow
    pip install -e .
    if ($LASTEXITCODE -eq 0) {
        "installed" | Out-File -FilePath $requirementsCheck
        Write-Host "依存関係のインストールが完了しました" -ForegroundColor Green
    } else {
        Write-Host "警告: 依存関係のインストールに問題がある可能性があります" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== WP-AI の起動準備が完了しました ===" -ForegroundColor Green
Write-Host ""
Write-Host "使用方法:" -ForegroundColor Cyan
Write-Host "  wp-ai --help                    # ヘルプを表示"
Write-Host "  wp-ai diagnose                  # WordPressを診断"
Write-Host "  wp-ai ssh test                  # SSH接続をテスト"
Write-Host "  wp-ai config show               # 設定を表示"
Write-Host ""
Write-Host "対話モードで起動する場合:" -ForegroundColor Cyan
Write-Host "  wp-ai" -ForegroundColor White
Write-Host ""

# APIキーの設定確認
Write-Host "APIキーの設定を確認しています..." -ForegroundColor Yellow
$apiKeyCheck = python -c "import keyring; key = keyring.get_password('wp-ai', 'gemini_api_key'); print('set' if key else 'not_set')" 2>$null
if ($apiKeyCheck -eq "not_set") {
    Write-Host "警告: Gemini APIキーが設定されていません" -ForegroundColor Yellow
    Write-Host "APIキーを設定するには以下を実行してください:" -ForegroundColor Yellow
    Write-Host "  python set_api_key.py" -ForegroundColor White
    Write-Host ""
}

# 起動モードの選択
Write-Host "起動モードを選択してください:" -ForegroundColor Cyan
Write-Host "  1) 対話モードで起動"
Write-Host "  2) コマンド実行モード（コマンドを入力）"
Write-Host "  3) ヘルプを表示"
Write-Host "  4) 終了"
Write-Host ""
$choice = Read-Host "選択 (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "対話モードで起動します..." -ForegroundColor Green
        wp-ai
    }
    "2" {
        Write-Host ""
        $command = Read-Host "実行するコマンドを入力してください (例: diagnose, ssh test)"
        if ($command) {
            Write-Host ""
            Write-Host "コマンドを実行します: wp-ai $command" -ForegroundColor Green
            Invoke-Expression "wp-ai $command"
        }
    }
    "3" {
        Write-Host ""
        wp-ai --help
    }
    "4" {
        Write-Host "終了します" -ForegroundColor Yellow
        exit 0
    }
    default {
        Write-Host "無効な選択です。ヘルプを表示します。" -ForegroundColor Yellow
        wp-ai --help
    }
}

Write-Host ""
Write-Host "スクリプトが終了しました" -ForegroundColor Cyan
