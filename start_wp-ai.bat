@echo off
setlocal disabledelayedexpansion
REM WP-AI Startup Script

REM プロジェクトディレクトリに移動
cd /d "%~dp0wp-ai"
if errorlevel 1 (
    echo エラー: wp-ai ディレクトリが見つかりません
    pause
    exit /b 1
)

REM Pythonのインストール確認
python --version > nul 2>&1
if errorlevel 1 (
    echo エラー: Python がインストールされていません
    pause
    exit /b 1
)

REM 仮想環境の確認と作成
if not exist "..\.venv" (
    echo 仮想環境を作成しています...
    python -m venv ..\.venv
)

REM 仮想環境の有効化
if not exist "..\.venv\Scripts\activate.bat" (
    echo エラー: 仮想環境の起動スクリプトが見つかりません
    pause
    exit /b 1
)
call ..\.venv\Scripts\activate.bat

REM 依存関係のインストール確認
if not exist "..\.venv\installed.txt" (
    echo 依存関係をインストールしています...
    pip install -e .
    if errorlevel 1 (
        echo エラー: 依存関係のインストールに失敗しました
        pause
        exit /b 1
    )
    echo installed > "..\.venv\installed.txt"
    echo インストールが完了しました
)

:menu
cls
echo ===================================
echo    WP-AI 起動メニュー
echo ===================================
echo.
echo   1. ヘルプを表示
echo   2. カスタムコマンドを実行
echo   3. システム情報
echo   4. プラグイン分析
echo   5. ログを表示
echo   6. AIチャットモード
echo   7. LLM設定
echo   8. 終了
echo.

set /p mychoice="選択 (1-8): "

if "%mychoice%"=="1" goto opt1
if "%mychoice%"=="2" goto opt2
if "%mychoice%"=="3" goto opt3
if "%mychoice%"=="4" goto opt4
if "%mychoice%"=="5" goto opt5
if "%mychoice%"=="6" goto opt6
if "%mychoice%"=="7" goto opt7
if "%mychoice%"=="8" goto opt8
if "%mychoice%"=="１" goto opt1
if "%mychoice%"=="２" goto opt2
if "%mychoice%"=="３" goto opt3
if "%mychoice%"=="４" goto opt4
if "%mychoice%"=="５" goto opt5
if "%mychoice%"=="６" goto opt6
if "%mychoice%"=="７" goto opt7
if "%mychoice%"=="８" goto opt8

echo 無効な選択です。
pause
goto menu

:opt1
echo.
wp-ai --help
echo.
pause
goto menu

:opt2
echo.
set /p cmd="コマンドを入力してください: "
if not "%cmd%"=="" wp-ai %cmd%
echo.
pause
goto menu

:opt3
echo.
set /p host="ホスト名を入力してください [docker]: "
if "%host%"=="" set host=docker
wp-ai system info --host %host%
echo.
pause
goto menu

:opt4
echo.
set /p host="ホスト名を入力してください [docker]: "
if "%host%"=="" set host=docker
wp-ai plugins analysis --host %host%
echo.
pause
goto menu

:opt5
echo.
set /p host="ホスト名を入力してください [docker]: "
if "%host%"=="" set host=docker
set /p lines="行数 [50]: "
if "%lines%"=="" set lines=50
wp-ai logs tail --host %host% --lines %lines%
echo.
pause
goto menu

:opt6
echo.
set /p msg="AIへのメッセージを入力してください: "
if not "%msg%"=="" wp-ai aichat ask "%msg%"
echo.
pause
goto menu

:opt7
echo.
echo 現在のLLM設定:
wp-ai llm-config show
echo.
pause
goto menu

:opt8
echo 終了します...
exit /b 0
