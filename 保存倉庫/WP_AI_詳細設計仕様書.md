# WP Doctor AI / wp-ai 詳細設計仕様書（実行可能版）

最終更新: 2025-11-18
作成者: Rovo Dev AI Agent（補助: 開発者 shima）
対象リポジトリ: 本ワークスペース（WordPress プラグイン + Python クライアント）

---

## 0. 本書の目的

- 後日、本プロジェクトを「迷わず実行」できるよう、現状の実装を正確に踏まえた詳細設計（運用手順/構成/API/セキュリティ/テスト）を1つに集約する。
- 将来的な方向性（別アプリ wp-ai でのCLI駆動）も本書で提示し、移行や拡張を容易にする。

---

## 1. 背景と方針（要約）

- 現状: 
  - WordPress プラグイン「WP Doctor AI」: 管理UI + RESTユーティリティ（namespace: `wpdoctor/v1`）
  - Python クライアント/CLI: `wp_Doctor/client` から REST 経由で診断/分析/計画/一部実行を行う
  - OpenAPI（骨子）: `openapi/wpdoctor_v1.yaml`
- 推奨方針（ご提示内容の理解）:
  - 「WP Doctor（Web UI 診断）」と「wp-ai（CLI 実行）」の役割分担を明確化
  - セキュリティ、性能、保守性、コストの観点から、CLI 別アプリの優位性が高い
  - 当面は現行構成を維持しつつ、将来 `wp-ai` へ進化可能な設計を採用

---

## 2. 全体アーキテクチャ

- コンポーネント
  - WordPress プラグイン（`wpdoctorai-plugin/` または `wpdoctorai/`）
    - REST API 提供（system-info / error-logs / plugins-analysis / quick-checks / actions / repair-plan / llm-config / llm-chat / llm-chat/cancel）
    - 管理画面（設定 -> WP Doctor AI）: React(wp.element) で軽量UI、`assets/js/admin.js`, `assets/css/admin.css`
  - Python クライアント（`wp_Doctor/client/`）
    - `doctor_client.py`: 認証・HTTP・API呼び出し、LLMチャット（ストリーミング対応）
    - `cli.py`: サブコマンド `system`, `plugins`, `logs`, `aiplan`, `repair`, `aichat-stream`
  - OpenAPI: `openapi/wpdoctor_v1.yaml`（今後詳細化）
  - ローカルE2E基盤: `docker-compose.yml`（WordPress + MySQL、プラグインをバインド）

- データフロー（典型）
  1) CLI から Application Passwords による Basic 認証で REST 叩く
  2) プラグインが WordPress/サーバ情報・ログ・プラグイン一覧を収集して JSON 返却
  3) CLI が結果を表示。`aiplan` は LLM（Gemini/OpenAI互換）設定があればサーバ側で生成し、なければ規則ベースの代替

---

## 3. 実行方法（最短手順）

- 3.1 ローカル（Docker Compose）
  1) 前提: Docker/Compose v2
  2) 起動: `docker compose -f wp_Doctor/docker-compose.yml up -d --build`
  3) WordPress 初期設定: http://localhost:8080 にアクセスし、管理者作成
  4) プラグイン有効化: 管理画面 -> プラグイン -> 「WP Doctor AI」を有効
  5) デバッグログ: 既に `WORDPRESS_CONFIG_EXTRA` で有効（wp-content/debug.log）
  6) CLI テスト:
     - `python -m pip install -r wp_Doctor/requirements.txt`
     - `python -m wp_Doctor.client.cli system --env-file apikey.env`
     - `python -m wp_Doctor.client.cli plugins --env-file apikey.env`
     - `python -m wp_Doctor.client.cli logs --env-file apikey.env --level all --limit 100`

- 3.2 実サーバ
  1) プラグイン設置: `wp_Doctor/wpdoctorai-plugin` を `wp-content/plugins/wpdoctorai-plugin` に配置し有効化
  2) 認証: 管理ユーザの Application Passwords を発行
  3) HTTPS 必須
  4) CLI 設定: `apikey.env`（`WP_URL`, `WP_USERNAME`, `WP_APP_PASSWORD`）
  5) コマンド: READMEの例と同等

- 3.3 LLM設定（サーバ側）
  - 管理画面 -> 設定 -> WP Doctor AI -> AI Settings
  - Provider: Gemini / OpenAI互換
  - Base URL / Model / API Key を保存
  - 参考: `GEMINI_API_SETUP.md`, `GEMINI_API_FINAL_FIX.md`, `GEMINI_DEBUG_STEPS.md`

---

## 4. REST API 仕様（現状準拠）

エンドポイント（REST namespace: `wpdoctor/v1`）と主な挙動:

- GET `/system-info` → サイト/サーバ情報
- GET `/error-logs?lines=200&level=all&format=json|raw` → ログ末尾抽出（file tail + 解析）
- GET `/plugins-analysis` → プラグイン一覧・カテゴリ推定・単純コンフリクト検知
- GET `/quick-checks` → メモリ/実行時間/HTTPS/WordPress/DB/DEBUG の簡易健診
- GET `/mixed-content?url=&limit=` → HTTP混在リンク検出（先頭ページ）
- POST `/actions`（payload: `{action, payload}`）→ cache_flush / rewrite_flush / plugin_toggle 等
- POST `/repair-plan` → QuickChecks/Plugins/MixedContent からドライラン計画生成
- GET/POST（サーバ実装はPOST） `/llm-config` → LLM 設定取得/保存
- POST `/llm-chat` → 非ストリーミング応答（JSON `{content: string}`）
- POST `/llm-chat/cancel` → SSE ストリームキャンセル

注意:
- SSE: いまの実装では `/llm-chat` を `stream:true` で叩くと SSE ヘッダでチャンク配信（`event: message|ping|done|error|init`）。ただし内部で現時点は全文取得後に分割出力。
- 認可: `manage_options` 権限ユーザ + `wp_create_nonce('wp_rest')` を JS 側に配布（CLI は Basic 認証）。

OpenAPI 骨子: `openapi/wpdoctor_v1.yaml`（今後、`/quick-checks` 等も反映予定）

---

## 5. Python クライアント設計

- ファイル: `wp_Doctor/client/doctor_client.py`, `cli.py`
- サイト設定の解決順序: `--env-file` > `~/.wp_doctor/config.json` > OS環境変数
- タイムアウト: `WP_DOCTOR_HTTP_TIMEOUT`（未設定時 30s）
- 提供API:
  - `system_info()`, `plugins_analysis()`, `error_logs(level, limit, since)`
  - `ai_plan(prompt, use_llm=True)` → `/ai-plan` が無い環境では `/repair-plan` やローカル規則にフォールバック
  - `ai_plan_and_apply(prompt, use_llm, auto_apply_low_risk)`
  - `repair(actions, dry_run=True, auto_apply_low_risk=False)`
  - `llm_chat(messages)` / `llm_chat_stream(messages, stream=True, include_context, log_lines, log_level, cancel_token)`
- CLI コマンド:
  - `system`, `plugins`, `logs [--level fatal|warning|notice|all --limit N --since ISO8601]`
  - `aiplan [--no-llm] [--apply-low-risk]`
  - `repair '<JSON actions array>' [--dry-run] [--apply-low-risk]`
  - `aichat-stream "prompt"`

サンプル:
```
python -m wp_Doctor.client.cli aiplan "キャッシュをクリアして最適化" --apply-low-risk --env-file apikey.env
python -m wp_Doctor.client.cli logs --level fatal --limit 200 --env-file apikey.env
```

---

## 6. LLM（Gemini/OpenAI互換）設計

- サーバ側設定を `wpdoctorai_llm` option に保存（`api_key` はマスク表示）
- Gemini 呼び出し: v1 -> v1beta の順でフォールバック（モデル名の互換差異対策）
- OpenAI互換: `/v1/chat/completions` を最小実装
- 応答ポリシ: 
  - まず日本語ナチュラルテキストで説明
  - 任意で末尾に実行可能な JSON（actions）ブロックをフェンスして付与（JSONのみ禁止）
- コンテキスト注入: `include_context` が指定された場合、System/Plugins/Logs を安全に短文化（サイズ上限・行長上限）
- ストリーミング: 現状は Provider の非ストリームAPI結果を SSE で分割送出。将来: Provider 由来のネイティブストリームに対応予定。

---

## 7. データモデル/保存先

- WordPress options
  - `wpdoctorai_llm`: `{ provider, base_url, model, api_key }`
  - `wpdoctorai_last_active_plugins`: ロールバック用スナップショット
- Transient
  - `wpdoctorai_rate_*`: アクション発火や LLM 呼び出しのレート制御
  - `llm_jobs`（メモリ上プロパティ）: SSE キャンセル状態を保持
- ログ
  - `wp-content/debug.log`（WP_DEBUG_LOG）
  - PHP error_log（ini設定による）

---

## 8. 非機能要件

- セキュリティ
  - HTTPS 前提 / Basic 認証（App Passwords） / 管理権限ガード
  - レート制限（transient） / JSON入力のバリデーション / 出力のエスケープ
  - LLM には個人情報/秘匿情報を送らない運用（必要時はマスキング）
- パフォーマンス
  - ログ tail はサイズ上限（既定 2MB）/ チャンク読み / 行数上限
  - プラグインサイズ計測はファイル数上限（5,000）
  - LLM コンテキスト総量上限（16KB）
- 可用性
  - SSE ストリーム中断/キャンセル API / クライアント側の session reset 実装

---

## 9. エラーハンドリング/トラブルシュート

- 500 系: `debug.log` 確認
- LLM 404/400: v1/v1beta 切替、Bodyの `error` 抽出してメッセージ補足
- ログ未検出: `wp-content/debug.log` と `ini_get('error_log')` の両方を探索
- CLI 側: `/ai-plan` 404 → `/repair-plan`（POST/GET）→ ローカル規則に自動フォールバック
- 参照: `GEMINI_API_SETUP.md`, `GEMINI_API_FINAL_FIX.md`, `GEMINI_DEBUG_STEPS.md`, `UPDATE_INSTRUCTIONS.md`

---

## 10. デプロイ/運用

- プラグイン更新手順: `UPDATE_INSTRUCTIONS.md` 参照
- 代理設定（wp-config.php）: `define('GEMINI_API_KEY', '...')` でのキー供給も可
- 監視/運用
  - アクション実行履歴の保存は現状 `wp_options` で直近分のみ（TODO: 永続ジョブ履歴の導入）
  - 重要操作前のバックアップ推奨（DB/ファイル）

---

## 11. テスト戦略

- CI: `.github/workflows/wp_doctor_ci.yml`（flake8/mypy/pytest）
- ユニット（最小）: `wp_Doctor/tests/test_smoke.py`, `wp_doctor_tests/test_smoke_unique.py`
- 手動/E2E:
  - Docker 環境で `/system-info`, `/plugins-analysis`, `/error-logs` の確認
  - LLM 設定保存/取得、`/llm-chat` の非ストリーム応答
  - CLI の `aiplan --no-llm` ローカル規則確認、`--apply-low-risk` 経路

---

## 12. 将来計画（wp-ai 別アプリ）

- 推奨判断（抜粋）
  - セキュリティ/性能/機能完全性/コスト/保守性の面で別アプリが優位
  - WP Doctor（Web UI 診断）と wp-ai（CLI 実行）の棲み分けでクロスセル
- ロードマップ（例）
  - Phase 1: MVP（2週間）: AI Engine（Gemini統合）、コマンド変換、WP-CLI実行、対話型CLI、SSH遠隔
  - Phase 2: 公開（1週間）: GitHub/MIT、PyPI、ドキュメント、FB収集
  - Phase 3: 拡張（2-3週間）: GUI、プラグインAPI連携、エコシステム
- API 連携戦略
  - 当面は現プラグインの REST を参照可能にしつつ、wp-ai はサーバに入らずに SSH + WP-CLI 中心
  - 「診断はプラグイン」「実行はCLI」を原則にし、双方向連携は最小限

---

## 13. 実装 TODO 一覧（抜粋）

- OpenAPI の詳細化（`/quick-checks`, `/actions`, `/llm-*` を反映）
- `/llm-chat` のプロバイダ・ネイティブストリーム対応
- 実行履歴（/repair-jobs）の永続化/ページング
- 管理UI: 進行状況/トースト/履歴ビューの整備
- CLI: `--env-file` のデフォルト探索ルールの明文化とサンプル `.env` 配布
- セキュリティハードニング（Nonce/Capability/RateLimit の継続評価）

---

## 14. 付録: API 使用例

- error-logs（RAW）
```
curl -u USER:APP_PASSWORD \
  "https://example.com/wp-json/wpdoctor/v1/error-logs?lines=100&level=all&format=raw"
```
- actions（rewrite flush）
```
curl -u USER:APP_PASSWORD -X POST \
  -H "Content-Type: application/json" \
  -d '{"action":"rewrite_flush"}' \
  "https://example.com/wp-json/wpdoctor/v1/actions"
```
- llm-config（set）
```
curl -u USER:APP_PASSWORD -X POST \
  -H "Content-Type: application/json" \
  -d '{"provider":"gemini","base_url":"https://generativelanguage.googleapis.com","model":"gemini-2.5-flash","api_key":"AIza..."}' \
  "https://example.com/wp-json/wpdoctor/v1/llm-config"
```

---

## 15. 実行チェックリスト

- [ ] Docker で WordPress が起動し、プラグインが有効化されている
- [ ] Application Passwords が発行され、HTTPS で到達できる
- [ ] `apikey.env` を用意し、CLI `system/plugins/logs` が通る
- [ ] LLM 設定が保存でき、`/llm-chat` が自然言語応答を返す
- [ ] `aiplan --no-llm` が動作し、`--apply-low-risk` で修正計画が適用される（低リスク）

---

以上。現状の実装資産で直ちに動かすための要点と、今後の発展（wp-ai 別アプリ）に向けた設計を統合しました。