# WP-AI 起動ガイド

## 概要
このドキュメントでは、WP-AI アプリケーションの起動方法について説明します。

## 前提条件

### 必須要件
- Python 3.10 以上
- Docker Desktop（WordPressとwpdoctor-apiプラグインの実行環境）
- Gemini API キー（Google AI Studioから取得）

### 確認コマンド
```powershell
# Python のバージョン確認
python --version

# Docker の動作確認
docker ps
```

## 起動方法

### Windows (PowerShell)

1. **起動スクリプトを実行**
   ```powershell
   .\start_wp-ai.ps1
   ```

2. **起動モードを選択**
   - オプション1: 対話モードで起動
   - オプション2: コマンド実行モード
   - オプション3: ヘルプを表示
   - オプション4: 終了

### Linux / Mac (Bash)

1. **実行権限を付与（初回のみ）**
   ```bash
   chmod +x start_wp-ai.sh
   ```

2. **起動スクリプトを実行**
   ```bash
   ./start_wp-ai.sh
   ```

## 初回セットアップ

### 1. Docker環境の起動
```powershell
docker-compose up -d
```

### 2. wpdoctor-api プラグインのインストール
プラグインがまだインストールされていない場合：
```powershell
# WordPressコンテナにプラグインをコピー
docker cp plugins/wpdoctor-api wordpress:/var/www/html/wp-content/plugins/

# プラグインを有効化
docker-compose exec wpcli wp plugin activate wpdoctor-api
```

### 3. Gemini API キーの設定
```powershell
cd wp-ai
python set_api_key.py
```

プロンプトに従ってAPIキーを入力してください。

## 主要コマンド

### 診断機能
```bash
wp-ai diagnose
```
WordPressサイトを診断し、問題を検出します。

### SSH接続テスト
```bash
wp-ai ssh test
```
SSH接続が正常に機能するか確認します。

### 設定の表示
```bash
wp-ai config show
```
現在の設定を表示します。

### ヘルプの表示
```bash
wp-ai --help
```
利用可能なコマンドとオプションを表示します。

## 設定ファイル

### config.toml の場所
`wp-ai/config.toml`

### 設定例
```toml
[llm]
provider = "gemini"
model = "gemini-1.5-flash"

[[hosts]]
name = "docker"
api_url = "http://localhost:8080/wp-json"
[hosts.ssh]
host = "localhost"
port = 2222
user = "kusanagi"
password = "password"
```

## トラブルシューティング

### 問題1: APIキーが設定されていない
**症状**: "Gemini APIキーが設定されていません" というメッセージが表示される

**解決策**:
```powershell
cd wp-ai
python set_api_key.py
```

### 問題2: 仮想環境の作成に失敗
**症状**: "仮想環境の作成に失敗しました" というエラー

**解決策**:
```powershell
# Python がインストールされているか確認
python --version

# venv モジュールがインストールされているか確認
python -m venv --help
```

### 問題3: 依存関係のインストールに失敗
**症状**: pip install でエラーが発生する

**解決策**:
```powershell
# pip をアップグレード
python -m pip install --upgrade pip

# 手動でインストール
cd wp-ai
pip install -e .
```

### 問題4: WordPress に接続できない
**症状**: API リクエストがタイムアウトまたは失敗する

**解決策**:
```powershell
# Docker コンテナの状態を確認
docker ps

# WordPress が起動していない場合
docker-compose up -d

# プラグインが有効化されているか確認
docker-compose exec wpcli wp plugin list
```

### 問題5: SSH接続に失敗
**症状**: SSH テストが失敗する

**解決策**:
```powershell
# SSH サーバーコンテナの状態を確認
docker ps | grep wp_ssh_server

# コンテナが起動していない場合
docker-compose up -d ssh-server

# 接続テスト
ssh -p 2222 kusanagi@localhost
# パスワード: password
```

## 環境構成

### Docker コンテナ
- **wordpress**: WordPressサーバー (ポート: 8080)
- **db**: MySQLデータベース
- **ssh-server**: SSH接続用サーバー (ポート: 2222)
- **wpcli**: WP-CLIツール
- **caddy**: リバースプロキシ (ポート: 8443)

### WordPress管理画面
- URL: http://localhost:8080/wp-admin
- デフォルト認証情報は初回セットアップ時に設定

### API エンドポイント
- ベースURL: http://localhost:8080/wp-json
- wpdoctor-api: http://localhost:8080/wp-json/wpdoctor/v1

## 開発者向け情報

### プロジェクト構造
```
wp-ai/
├── wp_ai/           # メインアプリケーション
│   ├── main.py      # エントリーポイント
│   ├── api.py       # API通信
│   ├── ssh.py       # SSH接続
│   ├── llm.py       # LLM統合
│   └── ...
├── config.toml      # 設定ファイル
├── pyproject.toml   # プロジェクト定義
└── set_api_key.py   # APIキー設定ツール
```

### 仮想環境の手動管理
```powershell
# 仮想環境の作成
cd wp-ai
python -m venv .venv

# 有効化 (Windows)
.\.venv\Scripts\Activate.ps1

# 有効化 (Linux/Mac)
source .venv/bin/activate

# 依存関係のインストール
pip install -e .

# 無効化
deactivate
```

## 次のステップ

1. ✅ Docker環境の起動
2. ✅ wpdoctor-api プラグインのインストール
3. ✅ wp-ai の起動
4. 📝 診断機能のテスト
5. 📝 SSH接続のテスト
6. 📝 実際のWordPressサイトへの接続設定

---

**最終更新**: 2025年1月
**メンテナー**: WP Doctor AI Team
