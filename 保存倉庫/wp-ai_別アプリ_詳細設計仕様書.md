# wp-ai 別アプリ 詳細設計仕様書（AI→WP-CLI 実行）

最終更新: 2025-11-18
作成: Rovo Dev AI Agent（補助: 開発者 shima）
ライセンス想定: MIT（Phase 2で確定）

---

## 0. 目的と範囲

- 目的: WordPress運用者/開発者が「自然言語で指示」→「安全・可逆に WP-CLI を実行」できるCLIアプリを提供する。
- 範囲: CLIコア、LLM統合、コマンド合成、安全実行（dry-run/承認/リスク制御/履歴/簡易ロールバック）、SSH/ローカル実行、最小のWP Doctor API連携。
- 非対象（当面）: Web UI（Electron/TkはPhase 3）、高度な自動修復（破壊的変更の完全ロールバック）、SaaSホスティング。

---

## 1. ペルソナとユースケース

- ペルソナ
  - サイト運用者（技術中級）: キャッシュクリア、プラグイン有効化/無効化、パーマリンク再生成
  - 開発者/DevOps: ステージング運用、SSH越しの一括操作、CIとの連携
- 代表ユースケース
  - 「キャッシュをクリアして」→ `wp cache flush`
  - 「パーマリンクを再設定して」→ `wp rewrite flush --hard`
  - 「プラグインXを無効化してログを確認」→ `wp plugin deactivate X` → `wp doctor log tail ...`
  - 「メンテナンスモードにして更新、終わったら解除」→複数コマンドの安全な計画・実行

---

## 2. アーキテクチャ（高レベル）

- コンポーネント
  1) CLI フロント（`wp-ai`）: 入出力、承認フロー、履歴閲覧
  2) LLM アダプタ: OpenAI/Gemini などに対する抽象化 + 関数呼び出し/JSON出力約束
  3) 意図解析/計画生成: 自然言語 → 正規化意図 → コマンド計画（複数ステップ）
  4) ポリシー/リスクエンジン: 危険度分類、ガードレール（許可リスト、危険語句拒否）
  5) コマンド合成器: `Intent → wp-cli commands` へ確定変換（テンプレート + 実引数検証）
  6) 実行ランナー: LocalRunner / SSHRunner（並列・タイムアウト・キャンセル）
  7) 状態/履歴ストア: JSONL/SQLite の実行履歴、設定、鍵管理（OS Keyring）
  8) ロールバック支援: 低リスク操作の逆操作、スナップショット連携のフック
  9) 任意連携: WP Doctor API から診断情報取得（コンテキスト強化。双方向依存は持たない）

- データフロー
  ユーザの自然言語 → 意図解析/計画 → リスク評価 → ドライラン説明 → 承認 → 実行（ローカル/SSH） → 履歴記録 → （必要時）ロールバック

---

## 3. CLI UXとコマンド仕様

- エントリポイント: `wp-ai`（Python console_script）
- グローバルオプション: `--config`, `--host <name>`, `--ssh`, `--yes`, `--dry-run`, `--json`, `--timeout`, `--parallel`
- サブコマンド（初期MVP）
  - `init`                      初期設定（設定ファイル・鍵の保管確認）
  - `say "<自然言語>"`          自然言語 → 計画 → 実行（標準フロー）
  - `plan "<自然言語>"`         計画のみ出力（JSON/表）
  - `run <cmd...>`              任意のwp-cliを実行（ポリシーと履歴つき）
  - `history [--limit N]`       実行履歴表示
  - `rollback <job_id>`         簡易ロールバック（可能な範囲）
  - `ssh add-host`              SSHホスト追加（name, host, user, port, key）
  - `config set/get/list`       設定操作（LLM, ポリシー, 既定ホスト等）
  - `context pull`              （任意）WP Doctor APIから診断情報取得

- 例
  - `wp-ai say "キャッシュをクリアして" --host prod --yes`
  - `wp-ai plan "パーマリンクを再設定し、終わったらキャッシュクリア" --json`
  - `wp-ai run wp plugin deactivate akismet --ssh --host staging`

---

## 4. 設定と保存形式

- ルート: OSごとに以下（XDGに準拠）
  - Windows: `%APPDATA%/wp-ai/`
  - macOS: `~/Library/Application Support/wp-ai/`
  - Linux: `~/.config/wp-ai/`
- ファイル
  - `config.toml`
    - `llm.provider = "openai|gemini|noop"`
    - `llm.base_url = "https://api.openai.com/v1"`
    - `llm.model = "gpt-4o-mini"`
    - `policy.allowlist = ["wp cache flush", "wp rewrite flush", "wp plugin (activate|deactivate) .*", ...]`
    - `policy.blocklist = ["wp db drop", "wp option delete siteurl", ...]`
    - `runner.default = "local|ssh"`
  - `hosts.toml`（複数ホスト定義）
    - `[[hosts]] name="prod" host="example.com" user="wp" port=22 path="/var/www/html"`
  - `secrets.keyring`（OS Keyring に格納: API Key、SSH鍵パスフレーズ等）
  - `history.sqlite` または `history.jsonl`（MVPはJSONL）

---

## 5. LLM 統合詳細

- プロバイダ: OpenAI/互換, Gemini（将来: Azure OpenAI, Local LLM）
- 出力制約: JSON関数呼び出し/ツール呼び出し形式での出力を強制。スキーマ例:
```json
{
  "intent": "cache_flush|rewrite_flush|plugin_toggle|composite",
  "steps": [
    { "cmd": "wp cache flush", "risk": "low", "explain": "キャッシュをクリア" },
    { "cmd": "wp rewrite flush --hard", "risk": "low", "explain": "パーマリンク更新" }
  ],
  "requires_confirmation": true
}
```
- プロンプト戦略
  - System: 役割、禁止事項（破壊的操作禁止）、出力を上記スキーマに限定
  - Context: （任意）WP Doctor診断サマリ（バイト/トークン上限）
  - Guard: 正規表現検証やスキーマバリデーションに失敗したら自動再プロンプト
- フォールバック
  - LLM失敗時はテンプレートベースのルール（簡易パーサ）で既知の自然言語をマッピング

---

## 6. ポリシー/リスクモデル

- リスク分類: `low|medium|high|unknown`
- 既定ポリシー
  - 許可（low）: cache flush, rewrite flush, plugin activate/deactivate, transient delete, cron event run
  - 要承認（medium）: コア/プラグイン更新、検索置換（dry-run必須）
  - 禁止（high）: DB drop, コア再インストール、ユーザ削除 等
- 検証
  - 生成コマンドを `allowlist` 正規表現でマッチング
  - `blocklist` 命中は即拒否
  - 未分類は `unknown` として要承認 or 再プロンプト

---

## 7. コマンド合成と検証

- 合成テンプレート
  - `cache_flush` → `wp cache flush`
  - `rewrite_flush` → `wp rewrite flush --hard`
  - `plugin_toggle` → `wp plugin <activate|deactivate> <slug>`
  - `mixed_content_scan` → 任意ツール/grep, 将来拡張
- 引数検証
  - スラッグの存在/形式チェック
  - 追加フラグは安全なサブセットのみ許可（`--allow-root` は封印）
- マルチサイト
  - `--url=<site>` または `--network` をホスト設定で既定化

---

## 8. 実行ランナー

- LocalRunner
  - 実行: `subprocess` で `wp` コマンド、`cwd=hosts.path`
  - タイムアウト/キャンセル: `Popen` + セッション/グループ kill
  - 出力: `stdout/stderr` ストリーム、実行ログに保存
- SSHRunner
  - ライブラリ: `paramiko`（Windows含むクロスプラットフォーム）
  - 鍵: OpenSSH鍵、エージェント利用、known_hosts 検証
  - コマンド: `cd <path> && wp ...`
  - 転送: 必要時のみ（将来のバックアップフック等）
- 並列実行
  - 将来: 複数ホストに対し `--parallel` でファンアウト（MVPは単一）

---

## 9. 履歴・監査・ロールバック

- 履歴レコード（JSONL）
```json
{
  "id": "2025-11-18T09:31:22Z-abcdef",
  "ts": "2025-11-18T09:31:22Z",
  "user": "local-user",
  "host": "prod",
  "intent": "cache_flush",
  "steps": ["wp cache flush"],
  "risk": "low",
  "approved": true,
  "dry_run": false,
  "result": { "exit": 0, "stdout": "...", "stderr": "" }
}
```
- ロールバック方針
  - 低リスク操作は逆操作で対応（activate ⇄ deactivate）
  - 破壊的操作は原則禁止。バックアップ/スナップショットの外部連携フックを提供（実装は環境側で）
- 監査
  - すべての入力と出力、承認の有無を記録。`--json` で外部SIEM連携を想定

---

## 10. セキュリティ設計

- 秘密情報
  - APIキー/SSH鍵パスフレーズは OS Keyring に保存
  - 設定ファイルには平文秘密を保存しない
- 権限境界
  - SSHユーザは最小権限（`wp` 実行に必要十分）
  - `sudo` が必要な操作は対象外 or 明示承認+専用ポリシー
- ガードレール
  - allowlist/blacklist/正規表現検証/危険語句検出
  - LLM出力は必ずスキーマ検証 + コマンド再構築（生文字列をそのまま実行しない）
- 通信
  - LLMはHTTPS/TLS必須。SSHは強暗号スイート、known_hosts厳格

---

## 11. エラー処理

- 分類: 入力エラー / LLM失敗 / ポリシー拒否 / 実行失敗 / SSH失敗 / タイムアウト
- リトライ: LLM（指数的バックオフ最大2回）、SSH接続（1回）
- メッセージ: 人間可読 + `--json`で機械可読
- 失敗時アクション: 差し止め・部分完了の記録・ロールバック提案

---

## 12. 実装言語/依存/パッケージング

- 言語: Python 3.10+
- 主要依存
  - `click` or `typer`（CLI）
  - `pydantic`（スキーマ）
  - `httpx`（LLM HTTP）
  - `paramiko`（SSH）
  - `tomli-w`（設定書き込み）
  - `keyring`（秘密管理）
  - `rich`（表示/プログレス/SSE風）
- 配布
  - Poetry で `wp-ai` エントリポイントを作成
  - PyPI 公開（パッケージ名: `wp-ai`）

---

## 13. ディレクトリ構成（MVP）

```
wp-ai/
  pyproject.toml
  src/wp_ai/__init__.py
  src/wp_ai/cli.py
  src/wp_ai/config.py
  src/wp_ai/llm.py
  src/wp_ai/policy.py
  src/wp_ai/intent.py
  src/wp_ai/planner.py
  src/wp_ai/synthesizer.py
  src/wp_ai/runner_local.py
  src/wp_ai/runner_ssh.py
  src/wp_ai/history.py
  tests/
```

---

## 14. 実行フロー詳細（`say` コマンド）

1) 入力: 自然言語 + 実行対象ホスト
2) コンテキスト（任意）: WP Doctor APIから診断（要URL/アプリパスワード）をpullし短文化
3) LLMへプロンプト → JSON計画を取得
4) ポリシー検証（allowlist/blacklist/スキーマ）
5) ドライラン説明を表示（リスク/影響範囲/見積時間）
6) 承認（`--yes` でスキップ）
7) ランナー（local/ssh）で順次実行、逐次表示
8) 履歴保存、失敗時はロールバック提案

---

## 15. WP Doctor との連携（任意）

- 取得可能: `/system-info`, `/error-logs`, `/plugins-analysis`, `/quick-checks`
- 目的: LLMへの補助文脈（過剰送信しない。サイズ上限16KB）
- 注意: 双方向依存を避ける（wp-ai 単体で完結可能）

---

## 16. テスト戦略

- 単体: 意図解析・ポリシー・スキーマ検証・コマンド合成
- 結合: LocalRunner/SSHRunner（DockerでWPコンテナ用意）
- E2E: `say` → `plan` → `run` シナリオ、dry-runと承認フロー
- 逆行テスト: 危険コマンド生成を意図的に試み、拒否・再プロンプトを確認
- CI: Github Actions（pytest、ruff/flake8、mypy）

---

## 17. リリース計画（ロードマップ）

- Phase 1（2週間）MVP
  - LLM（OpenAI/Geminiのどちらか）/ allowlist / LocalRunner / SSHRunner / 履歴 / `say|plan|run|history`
- Phase 2（1週間）公開
  - MIT/README/ドキュメント/サンプル設定/ PyPI
- Phase 3（2–3週間）拡張
  - GUI（任意）、並列実行、WP Doctor診断の自動コンテキスト化、ロールバックの厚み（バックアップフック）

---

## 18. セキュリティ/コンプライアンスチェックリスト

- [ ] LLMキーをKeyring保管・マスク表示
- [ ] SSH known_hosts 検証を強制
- [ ] `--allow-root` を禁止、sudo要件は明示ポリシー外
- [ ] 生成コマンドは必ず再構築/検証（生実行禁止）
- [ ] 履歴に機微情報を残さない（マスク）

---

## 19. サンプル設定/実行

- `config.toml`
```
[llm]
provider = "gemini"
base_url = "https://generativelanguage.googleapis.com"
model = "gemini-2.5-flash"

[policy]
allowlist = [
  "^wp cache flush$",
  "^wp rewrite flush( --hard)?$",
  "^wp plugin (activate|deactivate) [a-z0-9_-]+$"
]
blocklist = [
  "^wp db drop",
  "^wp .* --allow-root"
]

[runner]
default = "ssh"
```

- `hosts.toml`
```
[[hosts]]
name = "prod"
host = "prod.example.com"
user = "wp"
port = 22
path = "/var/www/html"
```

- 実行例
```
wp-ai say "キャッシュをクリアして" --host prod --yes
```

---

## 20. 既知の課題 / 今後のTODO

- LLMの関数呼び出し整備（OpenAI/Gemini差分の吸収）
- ロールバックの強化（事前スナップショット連携）
- 並列実行・分散（複数ホスト）
- WP-CLIが存在しない環境向けの自動セットアップガイド

---

以上。wp-aiは「診断はWP Doctor、実行はCLI」という責務分離に基づき、安全・効率・保守性を重視して設計した。MVPから段階的に拡張し、既存運用（SSH、IaC、CI）に親和的な形で導入できる。