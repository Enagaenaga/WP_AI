# WP Doctor AI - 引き継ぎメモ (Phase 1 完了時点)

**作成日:** 2025-11-20
**ステータス:** Phase 1 実装完了 / 検証中断 (環境要因)

## 1. 現状の進捗
「WP Doctor AI システム統合マスター詳細設計仕様書」に基づき、**Phase 1: Core CLI & SSH Runner** の実装コードを完了しました。

### 実装済み機能
- CLI基盤: `wp-ai` コマンド (Typer製)
- 設定管理: `config.toml` の読み込み、KeyringによるAPI Key管理
- LLM接続: Gemini (Google Generative AI) との接続、JSONレスポンスのパース
- SSH実行: Paramiko を使用したリモートコマンド実行
- プロンプト: システムプロンプトとコンテキスト注入ロジック（基礎）

### 成果物ディレクトリ
- `wp-ai/`: CLIのソースコード一式
- `docker-compose.yml`: 検証用環境定義

## 2. 現在のブロッカー (中断理由)
ローカル環境での動作検証を行おうとしましたが、以下の理由で中断しています。
- Docker未検出: ターミナルで `docker` コマンドが認識されません。Docker Desktopがインストールされていないか、PATHが通っていない可能性があります。

## 3. 次回の作業手順 (Next Steps)

### A. 環境の準備
1. Dockerの確認: Docker Desktop を起動するか、インストールしてください。
2. API Keyの準備: Gemini または OpenAI の API Key を用意してください。

### B. 動作検証の再開
以下のコマンドで検証を行ってください。

```powershell
# 1. 依存関係のインストール (まだの場合)
cd wp-ai
& .\.venv\Scripts\pip install -e .

# 2. 初期設定 (API Keyの登録)
& .\.venv\Scripts\wp-ai init

# 3. テスト環境の起動 (Dockerが使える場合)
cd ..
# Docker Desktop 起動後に以下を実行
# 参考: docker-compose.yml（wordpress/db/wpcli/ssh-server）
# - wordpress: http://localhost:8080
# - ssh-server: localhost:2222 (user: kusanagi / pass: password)

docker compose up -d

# 4. CLI サンプル実行
# 設定ファイル (wp-ai/config.toml) の [hosts.ssh] パスワードが "password" であることを確認
& wp-ai\wp_ai\.venv\Scripts\wp-ai say "プラグインの一覧を見せて" --host docker
```

## 4. 参考実装のWordPress環境へのデプロイと統合テスト

このリポジトリには、参考実装のREST APIプラグイン `保存倉庫/WPDoctorAI_plugin_endpoints_example.php` が含まれます。以下の手順でローカルのWordPress (docker-compose) にデプロイし、`curl` と `wp-cli` で統合テストを実施できます。

### 4.1 自動デプロイ＆テストスクリプト（推奨）
PowerShell スクリプト `tmp_rovodev_deploy_and_test.ps1` を用意しています。Docker Desktopが起動している状態で実行してください。

```powershell
# 既定引数
# - SiteURL: http://localhost:8080
# - AdminUser: admin / AdminPass: Admin!Pass123 / AdminEmail: admin@example.com

# 1) サービス起動 + WordPress初期化 + プラグイン配置/有効化 + Application Password発行 + curlテスト
powershell -ExecutionPolicy Bypass -File .\tmp_rovodev_deploy_and_test.ps1

# 2) 任意: 引数を指定
powershell -ExecutionPolicy Bypass -File .\tmp_rovodev_deploy_and_test.ps1 -SiteURL "http://localhost:8080" -AdminUser admin -AdminPass "Admin!Pass123" -AdminEmail "admin@example.com"
```

スクリプトが実施すること:
- `docker compose up -d` による `wordpress`/`db`/`wpcli`/`ssh-server` の起動
- `wp core install` によるWordPress初期化
- 参考プラグインの配置と `wp plugin activate wpdoctor-api` による有効化
- 管理者ユーザーの Application Password 発行（`wp user application-password create`）
- `curl -u <user>:<app_pass> http://localhost:8080/wp-json/wpdoctor/v1/...` によるREST疎通テスト
- `wp plugin list` の確認

### 4.2 手動手順（参考）
1) サービス起動
```powershell
docker compose up -d
```

2) WordPressインストール
```powershell
docker compose run --rm wpcli bash -lc "wp core install --path=/var/www/html --url='http://localhost:8080' --title='WP Doctor AI Test' --admin_user='admin' --admin_password='Admin!Pass123' --admin_email='admin@example.com' --skip-email"
```

3) プラグイン配置と有効化
```powershell
# 配置
$cid = $(docker compose ps -q wordpress)
docker cp 保存倉庫/WPDoctorAI_plugin_endpoints_example.php $cid:/var/www/html/wp-content/plugins/wpdoctor-api/wpdoctor-api.php
# 有効化
docker compose run --rm wpcli bash -lc "wp plugin activate wpdoctor-api --path=/var/www/html"
```

4) Application Password の発行
```powershell
$APP_PWD = $(docker compose run --rm wpcli bash -lc "wp user application-password create admin 'WP Doctor AI Tests' --porcelain --path=/var/www/html").Trim()
```

5) curlでエンドポイント検証
```powershell
$AUTH = "admin:$APP_PWD"
curl -u $AUTH http://localhost:8080/wp-json/wpdoctor/v1/system-info
curl -u $AUTH http://localhost:8080/wp-json/wpdoctor/v1/plugins-analysis
curl -u $AUTH http://localhost:8080/wp-json/wpdoctor/v1/error-logs?lines=5
curl -u $AUTH http://localhost:8080/wp-json/wpdoctor/v1/db-check
```

## 5. Application Passwordの発行手順（本番/ステージング）

- 要件: WordPress 5.6+、ユーザーは最低でも必要な権限（本プラグインは `manage_options` を要求）
- 方法: Web管理画面 または `wp-cli` で発行

### 5.1 管理画面から（HTTPS推奨）
1. 管理画面 > ユーザー > プロファイル > アプリケーションパスワード
2. 「新しいアプリケーションパスワード名」を入力（例: "WP Doctor AI"）
3. 「新しいアプリケーションパスワードを追加」をクリックし、発行された値を安全に保管

### 5.2 WP-CLIから
```bash
wp user application-password create <username> "WP Doctor AI" --porcelain
```
出力されたパスワードはサーバー側に平文保存されないため、初回表示時に安全に控えてください。

## 6. HTTPS設定ガイド（要点）

- 本番ではHTTPS必須。Basic認証やApplication Password利用時は特に平文漏洩防止が重要。
- 代表的な構成:
  - 1) 既存CDN/ALB/プロキシでTLS終端し、オリジンへはHTTP/HTTPSでフォワード
  - 2) サーバーにLet’s Encrypt (certbot) を導入し、Nginx/ApacheでTLS終端
- Let’s Encrypt自動更新設定を必ず実施（cron等）。
- WordPressの一般設定で、サイトURL/ホームURLを `https://` に更新。
- `wp doctor ai` クライアントの `api_url` も `https://` で設定（中間者攻撃対策）。

## 7. 最小権限（Least Privilege）ガイド

- 参考プラグインの権限チェックは `current_user_can('manage_options')`。本番では、必要な操作に応じて権限を細分化し、専用のカスタムケイパビリティを導入することを検討。
- APIアクセストークン（Application Password）は「用途ごと」「環境ごと」に発行し、不要になったら即時失効。
- アクセス元IP制限、WAF、レート制限を導入。
- 監査ログ: RESTアクセスログ、WP-CLI実行履歴（`wp-ai` の history.jsonl など）を保全。
- 秘密情報はキーチェーン（Windows Credential Manager / macOS Keychain / GNOME Keyring）やVaultに格納。

## 8. `wp-ai` クライアントの設定例（API連携）

`wp-ai/config.toml` に `hosts` の `api_url` と Basic認証（Application Password）を登録してください。

```toml
[[hosts]]
name = "docker"
api_url = "http://localhost:8080/wp-json"
[hosts.ssh]
host = "localhost"
port = 2222
user = "kusanagi"
password = "password"
```

APIユーザー名/パスワードは Keyring に保存します。

```bash
wp-ai creds set --host docker  # 実装予定: 現状は keyring 直書き関数を利用
```

暫定: `wp-ai/wp_ai/auth.py` の `set_api_basic_auth_keys(host_name, username, password)` をPython REPL等から利用可能。

## 9. トラブルシューティング

- `docker compose` が見つからない: Docker Desktopのインストール、PATH設定を確認
- `wp-cli` の `wp core install` が止まる: DB初期化待ち時間を延ばす、`depends_on` の再確認
- Application Passwordで401/403: ユーザー権限、HTTPS、Basic Authヘッダーを確認
- RESTエンドポイント404: プラグインの有効化、パーマリンクの再生成（`wp rewrite flush --hard`）を実施

## 10. 関連ファイル
- `task.md`: タスクのチェックリスト
- `implementation_plan.md`: 実装計画書
- `保存倉庫/WPDoctorAI_plugin_endpoints_example.php`: 参考実装プラグイン（RESTエンドポイント）
- `docker-compose.yml`: ローカル検証環境（wordpress/db/wpcli/ssh-server）
