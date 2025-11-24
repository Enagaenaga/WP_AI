WP Doctor AI システム統合マスター詳細設計仕様書
バージョン: 1.0.0 (Determined)
ステータス: APPROVED (GO)
対象: WP Doctor AI (Plugin) / wp-ai (CLI Client)
作成日: 2025-11-21

プロジェクトの実行（GOサイン）に向け、これまでの2つの設計書（Doc A: 現行Plugin, Doc B: 新規CLI）を統合し、アーキテクチャの決定事項と実装詳細を確定させた**「統合マスター詳細設計仕様書」**を作成しました。

開発チームはこのドキュメントを「正（SSOT: Single Source of Truth）」として実装を進めてください。

---

# WP Doctor AI システム統合マスター詳細設計仕様書

**バージョン:** 1.0.0 (Determined)
**ステータス:** **APPROVED (GO)**
**対象:** WP Doctor AI (Plugin) / wp-ai (CLI Client)
**作成日:** 2025-11-21

---

## 1. プロジェクト概要と基本方針

### 1.1 目的
WordPress の運用・保守を自律化・効率化するための AI エージェントシステムを構築する。
従来の「プラグイン内で完結する自動化」のセキュリティリスクとPHPの実行制約を解消するため、**「診断（Read）」と「操作（Write）」の責務を分離したハイブリッド構成**を採用する。

### 1.2 アーキテクチャ決定事項
- **診断・情報収集 (Telemetry):** WordPress プラグイン (`WP Doctor AI`) が担当。
  - 役割: ログ収集、構成情報の提供、簡易ヘルスチェック。
  - 通信: REST API (`wpdoctor/v1`)。
- **判断・実行 (Operation):** Python CLI アプリケーション (`wp-ai`) が担当。
  - 役割: 自然言語の解釈、リスク評価、コマンド合成、SSH/ローカル経由での WP-CLI 実行。
  - 通信: SSH (操作用) / HTTPS (LLMおよび診断取得用)。

### 1.3 システム構成図
```
[ Operator / Developer ]
       |
       v (CLI Command)
+-----------------------+          +-------------------------+
|   wp-ai (Python CLI)  | <------> |      LLM Provider       |
|-----------------------|   HTTPS  | (OpenAI / Gemini)       |
| - Intent Parser       |          +-------------------------+
| - Policy Engine       |
| - SSH Runner          |
+-----------------------+
       |      ^
       | SSH  | HTTPS (REST /system-info)
       v      |
+-----------------------+
|   Target Server       |
|-----------------------|
| [ WordPress Core ]    |
|      + WP-CLI         | <--- (Executed via SSH)
|      + Plugin         |
|        (WP Doctor AI) | ---> (Provides Diagnostic JSON)
+-----------------------+
```

---

## 2. コンポーネント詳細設計: wp-ai (CLI)

本システムの「頭脳」兼「執刀医」。Python パッケージとして実装。

### 2.1 技術スタック
- **言語:** Python 3.10+
- **CLI FW:** `typer` or `click`
- **SSH:** `paramiko`
- **Validation:** `pydantic`
- **Config/Secret:** `tomli`, `keyring` (OSネイティブな鍵管理)

### 2.2 コマンドインターフェース
MVP（Phase 1）で実装すべき必須コマンド。

| コマンド | 引数/オプション | 挙動 |
| :--- | :--- | :--- |
| `init` | なし | 設定ファイル (`config.toml`) 生成、APIキー登録フロー |
| `say` | `"<instruction>"` `--host <name>` `--yes` | **メイン機能**。指示→計画→(承認)→実行→ログ保存 |
| `plan` | `"<instruction>"` `--host <name>` | 実行せず、AIが生成したコマンド計画とリスクを表示 |
| `run` | `<wp-command...>` `--host <name>` | WP-CLIコマンドを直接ラップ実行（履歴・SSH管理のみ利用） |
| `history`| `--limit <n>` | 過去の実行ログ（JSONL）を閲覧 |
| `config` | `list`, `set` | 設定確認・変更 |

### 2.3 処理フロー (The "Say" Loop)
1.  **Context Loading:**
    - 指定 `host` の設定から接続情報をロード。
    - (Optional) プラグインの REST API (`/system-info`) を叩き、WPバージョン・有効プラグイン・直近エラーを取得。
2.  **LLM Planning:**
    - System Prompt + Context + User Instruction を送信。
    - 出力要件: JSON Schema（意図、コマンドリスト、リスク、理由）。
3.  **Policy Check:**
    - 生成されたコマンド (`wp ...`) をローカルの `Allowlist / Blocklist` 正規表現で検証。
    - 禁止コマンド（`db drop` 等）が含まれる場合、エラーとして中断。
4.  **Dry Run & Approval:**
    - ユーザーに「実行しようとしているコマンド」「リスク」「理由」を提示。
    - `--yes` オプションが無い限り `[Y/n]` で承認を求める。
5.  **Execution (SSH/Local):**
    - SSH接続を確立し、コマンドを順次実行。
    - `stdout`, `stderr` をリアルタイムに近い形で取得・表示。
6.  **Logging:**
    - 実行結果（成否、出力）を `history.jsonl` に追記。

### 2.4 設定ファイル (`config.toml`)
```toml
[llm]
provider = "gemini" # or "openai"
model = "gemini-1.5-flash" # 高速応答重視
# api_key はここには書かず keyring を使用

[policy]
allow_risk = "low" # lowリスクは確認なしなどの設定（将来）
blocklist = [ "^wp db drop", "^wp user delete" ]

[runner]
default = "ssh"
```

---

## 3. コンポーネント詳細設計: WP Doctor AI (Plugin)

本システムの「検査技師」。WordPress プラグインとして実装。
**方針変更:** 従来の「実行機能（Actions）」は将来的に廃止または Legacy 扱いとし、**「診断情報の提供」に特化**する。

### 3.1 REST API 仕様 (Namespace: `wpdoctor/v1`)
認証: Basic Auth (Application Passwords) を必須とする。

| Endpoint | Method | パラメータ | レスポンス概要 |
| :--- | :--- | :--- | :--- |
| `/system-info` | GET | なし | WP Ver, PHP Ver, Server OS, DB Size |
| `/plugins-analysis` | GET | `status=active` | プラグイン一覧、更新の有無 |
| `/error-logs` | GET | `lines=50`, `level=all` | `debug.log` または `error_log` の末尾抽出 |
| `/db-check` | GET | なし | (新規) オートロードサイズ、オーバーヘッド情報 |

### 3.2 既存機能の扱い
- **LLM Chat (Plugin UI):** 残す。ただし、「相談」用途に限定し、コマンド実行は提案のみ（「これをCLIで実行してください」と表示）とする。
- **Repair Actions:** `wp-ai` CLI への移行を促すメッセージを表示。API自体は後方互換のために残すが、推奨しない。

---

## 4. 統合連携ロジック

CLI (`wp-ai`) が Plugin (`WP Doctor AI`) をどう利用するか。

### 4.1 ホスト設定 (`hosts.toml`)
SSH情報と REST API 情報を紐付ける。

```toml
[[hosts]]
name = "production"
# SSH接続情報（実行用）
ssh_host = "203.0.113.1"
ssh_user = "kusanagi"
ssh_key_path = "~/.ssh/id_rsa"
app_path = "/home/kusanagi/website/DocumentRoot"

# REST API情報（診断取得用: Optional）
api_url = "https://example.com/wp-json"
# API User/Pass は keyring に "wp-ai:production:api" として保存
```

### 4.2 コンテキスト注入戦略
LLM のトークン節約と精度向上のため、以下のロジックでプロンプトを作成する。
1. CLI が REST API から JSON を取得。
2. Python 側で重要な情報のみ抽出・要約（例: ログは直近のエラーのみ、プラグインはActiveなもののみ）。
3. システムプロンプト末尾に `[Current System Context]` として注入。
4. これにより、ユーザーが「エラーの原因を直して」と言っただけで、ログに基づいた修正案（例: プラグイン無効化）が可能になる。

---

## 5. セキュリティ要件

1.  **秘密情報の管理:**
    - `wp-ai` は API Key および SSH パスフレーズ、WP Application Password を平文で保存してはならない（OS Keyring 利用）。
2.  **SSH 接続:**
    - `StrictHostKeyChecking` をデフォルトで有効化。
    - 可能な限り SSH Agent Forwarding は避け、必要な鍵のみを使用。
3.  **コマンドインジェクション対策:**
    - LLM が生成した引数は必ずサニタイズする。
    - シェルエスケープ処理（`shlex.quote` 等）を介してコマンドを構築する。
4.  **Plugin API 保護:**
    - HTTPS 必須。管理者権限を持つ Application Password のみを許可。

---

## 6. 開発・リリースロードマップ

以下の順序で開発を実行する。

### Phase 1: Core CLI & SSH Runner (期間: 1週間)
- **目標:** `wp-ai run` および `wp-ai say` (コンテキスト無し) が動く。
- **タスク:**
  - プロジェクト初期化 (Poetry)。
  - LLM 接続部分 (OpenAI/Gemini 互換レイヤー)。
  - SSH Runner 実装 (Paramiko)。
  - コマンド生成プロンプトの調整。

### Phase 2: Plugin Refactor & Integration (期間: 1週間)
- **目標:** Plugin が正確な診断 JSON を返し、CLI がそれを読んで賢く振る舞う。
- **タスク:**
  - Plugin 側の不要な書き込み機能の整理・API最適化。
  - CLI 側の REST API Client 実装。
  - コンテキスト注入ロジックの実装。
  - 結合テスト（Docker 環境）。

### Phase 3: Packaging & Distribution (期間: 1週間)
- **目標:** 一般ユーザーが `pip install wp-ai` で使える。
- **タスク:**
  - ドキュメント整備 (README, Setup Guide)。
  - PyPI 公開準備。
  - エラーハンドリング強化（ネットワーク切断時の再接続など）。

---

## 7. 実行前チェックリスト（GOサイン条件）

開発者は以下を確認し、直ちに着手すること。

- [ ] **リポジトリ構成:** `wp-ai` (CLI) 用の新規ディレクトリまたはリポジトリを作成したか。
- [ ] **Docker環境:** テスト用の WordPress + SSH コンテナ (`docker-compose.yml`) は手元にあるか。
- [ ] **API Key:** Gemini または OpenAI の API Key を開発用に確保したか。
- [ ] **方針理解:** 「プラグインで直そうとせず、CLI経由で直す」という方針を理解したか。

以上。本仕様書に基づき開発を開始する。