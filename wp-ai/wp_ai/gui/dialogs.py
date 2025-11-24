import tkinter as tk
from tkinter import ttk, messagebox
import re
import threading
from typing import List, Optional
from pathlib import Path
from ..config import load_config, CONFIG_FILE, ensure_config_dir, write_default_config, set_api_key, get_api_key


def fetch_available_models(provider: str, api_key: Optional[str] = None) -> List[str]:
    """利用可能なモデルのリストを取得
    
    Args:
        provider: 'gemini' or 'openai'
        api_key: APIキー（Noneの場合は設定から取得）
        
    Returns:
        モデル名のリスト
    """
    if api_key is None:
        api_key = get_api_key(provider)
        
    if not api_key:
        return []
        
    try:
        if provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            
            # モデルリストを取得
            models = genai.list_models()
            
            # generateContentをサポートするモデルのみをフィルタ
            model_names = []
            for model in models:
                # サポートするメソッドをチェック
                if 'generateContent' in model.supported_generation_methods:
                    # モデル名から「models/」プレフィックスを削除
                    name = model.name
                    if name.startswith('models/'):
                        name = name[7:]  # 'models/'を削除
                    model_names.append(name)
            
            # モデル名でソート（新しいバージョンが後ろに来るように）
            model_names.sort()
            return model_names
            
        elif provider == "openai":
            # OpenAI APIを使用してモデルリストを取得
            # TODO: OpenAI実装
            return [
                "gpt-4",
                "gpt-4-turbo-preview",
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k"
            ]
        else:
            return []
            
    except Exception as e:
        print(f"モデル取得エラー: {e}")
        return []


class LLMSettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("LLM Settings")
        self.geometry("450x350")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.config = load_config()
        self.available_models = []
        self.saved_model = None  # 保存されたモデルを記憶
        self.initial_load = True  # 初回読み込みフラグ
        self._refresh_in_progress = False  # リフレッシュ中フラグ
        
        self.setup_ui()
        self.load_settings()
        
        # プロバイダー変更時にモデルリストを更新
        # 注: 初回読み込み完了後にバインドを設定
        self.after(500, lambda: self.provider_combo.bind("<<ComboboxSelected>>", self.on_provider_change))
        
    def setup_ui(self):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Provider
        ttk.Label(main_frame, text="Provider:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.provider_var = tk.StringVar()
        self.provider_combo = ttk.Combobox(main_frame, textvariable=self.provider_var, state="readonly")
        self.provider_combo['values'] = ('gemini', 'openai')
        self.provider_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, columnspan=2)
        
        # Model（コンボボックスに変更）
        ttk.Label(main_frame, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(main_frame, textvariable=self.model_var)
        self.model_combo.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # モデル更新ボタン
        self.refresh_btn = ttk.Button(main_frame, text="🔄", command=self.refresh_models, width=3)
        self.refresh_btn.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        # ステータスラベル
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="#666666", font=("Arial", 8))
        self.status_label.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(0, 5))
        
        # API Key
        ttk.Label(main_frame, text="API Key:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(main_frame, textvariable=self.api_key_var, show="*")
        self.api_key_entry.grid(row=3, column=1, sticky=tk.EW, pady=5, columnspan=2)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=3, pady=20)
        
        ttk.Button(btn_frame, text="Save", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
        
    def load_settings(self):
        llm_config = self.config.llm
        self.provider_var.set(llm_config.provider)
        self.model_var.set(llm_config.model)
        self.saved_model = llm_config.model  # 保存されたモデルを記憶
        # API key is in keyring, not config.toml
        # We leave it empty by default for security, or could try to load it?
        # Usually better to leave empty and only update if user enters something.
        
        # 初期モデルリストを読み込み（遅延実行で二重読み込みを防ぐ）
        self.after(200, self.refresh_models)
        
    def save_settings(self):
        provider = self.provider_var.get().strip()
        model = self.model_var.get().strip()
        api_key = self.api_key_var.get().strip()
        
        if not provider or not model:
            messagebox.showerror("Error", "Provider and Model are required.")
            return
            
        try:
            # 1. Save API Key if provided
            if api_key:
                set_api_key(provider, api_key)
                
            # 2. Determine which config file to use (same logic as load_config)
            local_config = Path.cwd() / "config.toml"
            if local_config.exists():
                config_path = local_config
            else:
                ensure_config_dir()
                config_path = CONFIG_FILE
            
            # 3. Load existing config
            try:
                text = config_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                if config_path == CONFIG_FILE:
                    write_default_config()
                    text = CONFIG_FILE.read_text(encoding="utf-8")
                else:
                    # Local config doesn't exist, create default
                    write_default_config(config_path)
                    text = config_path.read_text(encoding="utf-8")
                
            # Simple regex replacement to preserve comments/structure
            # This assumes the structure generated by write_default_config
            
            # Update provider
            provider_pattern = r'provider\s*=\s*".*"'
            if re.search(provider_pattern, text):
                text = re.sub(provider_pattern, f'provider = "{provider}"', text)
            
            # Update model
            model_pattern = r'model\s*=\s*".*"'
            if re.search(model_pattern, text):
                text = re.sub(model_pattern, f'model = "{model}"', text)
                
            config_path.write_text(text, encoding="utf-8")
            
            messagebox.showinfo("Success", "Settings saved successfully.\nPlease reload config in the main window.")
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {str(e)}")
    
    def on_provider_change(self, event=None):
        """プロバイダー変更時にモデルリストを更新"""
        self.refresh_models()
    
    def refresh_models(self):
        """モデルリストを更新"""
        # 既にリフレッシュ中の場合はスキップ
        if self._refresh_in_progress:
            return
            
        provider = self.provider_var.get()
        if not provider:
            return
        
        self._refresh_in_progress = True
        
        self.status_var.set("モデルリストを取得中...")
        self.refresh_btn.config(state="disabled")
        
        # バックグラウンドスレッドでモデルリストを取得
        thread = threading.Thread(
            target=self._fetch_models_background,
            args=(provider,),
            daemon=True
        )
        thread.start()
    
    def _fetch_models_background(self, provider: str):
        """バックグラウンドでモデルリストを取得"""
        try:
            # APIキーを取得（入力されている場合はそれを使用）
            api_key = self.api_key_var.get().strip()
            if not api_key:
                api_key = get_api_key(provider)
            
            models = fetch_available_models(provider, api_key)
            
            # メインスレッドでUIを更新
            self.after(0, self._update_model_list, models)
            
        except Exception as e:
            self.after(0, self._on_fetch_error, str(e))
    
    def _update_model_list(self, models: List[str]):
        """モデルリストを更新（メインスレッド）"""
        self.available_models = models
        
        if models:
            self.model_combo['values'] = models
            self.status_var.set(f"{len(models)}個のモデルが利用可能")
            
            # 現在のモデル値を保存
            current_model = self.model_var.get()
            
            # 初回読み込み時のみ、保存されたモデルを設定
            if self.initial_load:
                if self.saved_model and self.saved_model in models:
                    # 保存されたモデルがリストにあればそれを選択
                    self.model_var.set(self.saved_model)
                elif models:
                    # ない場合は最新のモデルを選択
                    self.model_var.set(models[-1])
                self.initial_load = False
            else:
                # 2回目以降は現在の値を保持
                if current_model and current_model in models:
                    # 現在の値がリストにあればそのまま
                    self.model_var.set(current_model)
                elif models:
                    # ない場合のみ最新を選択
                    self.model_var.set(models[-1])
        else:
            self.model_combo['values'] = []
            self.status_var.set("モデルが見つかりません（APIキーを確認してください）")
        
        self.refresh_btn.config(state="normal")
        self._refresh_in_progress = False  # リフレッシュ完了
    
    def _on_fetch_error(self, error_msg: str):
        """モデル取得エラー時の処理"""
        self.status_var.set(f"エラー: {error_msg}")
        self.refresh_btn.config(state="normal")


class HostManagerDialog(tk.Toplevel):
    """ホスト管理ダイアログ
    
    ホストの追加、編集、削除、接続テスト機能を提供
    """
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("ホスト管理")
        self.geometry("700x500")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        
        self.config = load_config()
        self.selected_host_index = None
        
        self.setup_ui()
        self.load_hosts()
        
    def setup_ui(self):
        """UI構築"""
        # 左側: ホストリスト
        left_frame = ttk.Frame(self, padding="10")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        
        ttk.Label(left_frame, text="ホスト一覧:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        # ホストリスト
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        self.host_listbox = tk.Listbox(list_frame, width=20)
        self.host_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.host_listbox.bind("<<ListboxSelect>>", self.on_host_select)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.host_listbox.yview)
        self.host_listbox.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ボタン
        ttk.Button(left_frame, text="新規追加", command=self.add_host).pack(fill=tk.X, pady=2)
        ttk.Button(left_frame, text="削除", command=self.delete_host).pack(fill=tk.X, pady=2)
        
        # 右側: ホスト詳細
        right_frame = ttk.Frame(self, padding="10")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        ttk.Label(right_frame, text="ホスト詳細:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        detail_frame = ttk.Frame(right_frame)
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        
        # ホスト名
        ttk.Label(detail_frame, text="ホスト名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.name_var).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        # API URL
        ttk.Label(detail_frame, text="API URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.api_url_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.api_url_var).grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        # API認証情報
        ttk.Label(detail_frame, text="API Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.api_user_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.api_user_var).grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(detail_frame, text="API Password:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.api_pass_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.api_pass_var, show="*").grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # SSH設定
        ttk.Separator(detail_frame, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Label(detail_frame, text="SSH Host:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.ssh_host_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.ssh_host_var).grid(row=5, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(detail_frame, text="SSH Port:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.ssh_port_var = tk.StringVar(value="22")
        ttk.Entry(detail_frame, textvariable=self.ssh_port_var).grid(row=6, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(detail_frame, text="SSH User:").grid(row=7, column=0, sticky=tk.W, pady=5)
        self.ssh_user_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.ssh_user_var).grid(row=7, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(detail_frame, text="SSH Password:").grid(row=8, column=0, sticky=tk.W, pady=5)
        self.ssh_password_var = tk.StringVar()
        ttk.Entry(detail_frame, textvariable=self.ssh_password_var, show="*").grid(row=8, column=1, sticky=tk.EW, pady=5)
        
        detail_frame.columnconfigure(1, weight=1)
        
        # 下部ボタン
        button_frame = ttk.Frame(right_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="保存", command=self.save_host).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="接続テスト", command=self.test_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="閉じる", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
    def load_hosts(self):
        """ホストリストを読み込み"""
        self.host_listbox.delete(0, tk.END)
        for host in self.config.hosts:
            self.host_listbox.insert(tk.END, host.name)
            
    def on_host_select(self, event=None):
        """ホスト選択時"""
        selection = self.host_listbox.curselection()
        if not selection:
            return
            
        self.selected_host_index = selection[0]
        host = self.config.hosts[self.selected_host_index]
        
        # フォームに値を設定
        self.name_var.set(host.name)
        self.api_url_var.set(host.api_url or "")
        self.ssh_host_var.set(host.ssh.host)
        self.ssh_port_var.set(str(host.ssh.port))
        self.ssh_user_var.set(host.ssh.user)
        self.ssh_password_var.set(host.ssh.password or "")
        
        # API認証情報を読み込み
        try:
            from ..auth import get_api_basic_auth_keys
            user, password = get_api_basic_auth_keys(host.name)
            if user:
                self.api_user_var.set(user)
            if password:
                self.api_pass_var.set(password)
        except:
            pass
            
    def add_host(self):
        """新規ホスト追加"""
        # フォームをクリア
        self.selected_host_index = None
        self.name_var.set("")
        self.api_url_var.set("")
        self.api_user_var.set("")
        self.api_pass_var.set("")
        self.ssh_host_var.set("")
        self.ssh_port_var.set("22")
        self.ssh_user_var.set("")
        self.ssh_password_var.set("")
        
    def save_host(self):
        """ホストを保存"""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("エラー", "ホスト名を入力してください。")
            return
            
        api_url = self.api_url_var.get().strip() or None
        ssh_host = self.ssh_host_var.get().strip()
        ssh_user = self.ssh_user_var.get().strip()
        
        if not ssh_host or not ssh_user:
            messagebox.showerror("エラー", "SSH HostとSSH Userは必須です。")
            return
            
        try:
            ssh_port = int(self.ssh_port_var.get())
        except ValueError:
            messagebox.showerror("エラー", "SSH Portは数値で入力してください。")
            return
            
        # 新しいホスト設定を作成
        from ..config import SSHConfig, HostConfig
        
        ssh_config = SSHConfig(
            host=ssh_host,
            port=ssh_port,
            user=ssh_user,
            password=self.ssh_password_var.get().strip() or None,
            strict_host_key_checking=False
        )
        
        new_host = HostConfig(
            name=name,
            ssh=ssh_config,
            api_url=api_url
        )
        
        # 既存ホストの更新 or 新規追加
        if self.selected_host_index is not None:
            self.config.hosts[self.selected_host_index] = new_host
        else:
            self.config.hosts.append(new_host)
            
        # config.tomlに保存
        self._save_config_to_file()
        
        # API認証情報を保存
        api_user = self.api_user_var.get().strip()
        api_pass = self.api_pass_var.get().strip()
        if api_user and api_pass:
            from ..auth import set_api_basic_auth_keys
            set_api_basic_auth_keys(name, api_user, api_pass)
            
        messagebox.showinfo("成功", "ホストを保存しました。")
        self.load_hosts()
        
    def delete_host(self):
        """ホストを削除"""
        if self.selected_host_index is None:
            messagebox.showwarning("警告", "削除するホストを選択してください。")
            return
            
        host = self.config.hosts[self.selected_host_index]
        if messagebox.askyesno("確認", f"ホスト '{host.name}' を削除しますか？"):
            del self.config.hosts[self.selected_host_index]
            self._save_config_to_file()
            self.selected_host_index = None
            self.load_hosts()
            self.add_host()  # フォームをクリア
            
    def test_connection(self):
        """接続テスト"""
        api_url = self.api_url_var.get().strip()
        if not api_url:
            messagebox.showwarning("警告", "API URLを入力してください。")
            return
            
        api_user = self.api_user_var.get().strip()
        api_pass = self.api_pass_var.get().strip()
        
        if not api_user or not api_pass:
            messagebox.showwarning("警告", "API UsernameとPasswordを入力してください。")
            return
            
        try:
            from ..api import WPDoctorClient
            client = WPDoctorClient(api_url, username=api_user, password=api_pass)
            info = client.system_info()
            
            messagebox.showinfo("成功", f"接続成功！\nWordPress Version: {info.get('wordpress_version', 'N/A')}")
        except Exception as e:
            messagebox.showerror("エラー", f"接続失敗:\n{str(e)}")
            
    def _save_config_to_file(self):
        """config.tomlにホスト情報を保存"""
        ensure_config_dir()
        
        # 現在のconfigパスを取得
        local_config = Path.cwd() / "config.toml"
        if local_config.exists():
            config_path = local_config
        else:
            config_path = CONFIG_FILE
            
        # TOMLファイルを再構築
        lines = []
        lines.append("[llm]")
        lines.append(f'provider = "{self.config.llm.provider}"')
        lines.append(f'model = "{self.config.llm.model}"')
        lines.append("")
        
        lines.append("[policy]")
        lines.append(f'allow_risk = "{self.config.policy.allow_risk}"')
        blocklist_str = ", ".join([f'"{pattern}"' for pattern in self.config.policy.blocklist])
        lines.append(f"blocklist = [ {blocklist_str} ]")
        lines.append("")
        
        lines.append("[runner]")
        lines.append(f'default = "{self.config.runner.default}"')
        lines.append("")
        
        # ホストを追加
        for host in self.config.hosts:
            lines.append("[[hosts]]")
            lines.append(f'name = "{host.name}"')
            if host.api_url:
                lines.append(f'api_url = "{host.api_url}"')
            lines.append("[hosts.ssh]")
            lines.append(f'host = "{host.ssh.host}"')
            lines.append(f'port = {host.ssh.port}')
            lines.append(f'user = "{host.ssh.user}"')
            if host.ssh.password:
                lines.append(f'password = "{host.ssh.password}"')
            if host.ssh.key_path:
                lines.append(f'key_path = "{host.ssh.key_path}"')
            lines.append(f'strict_host_key_checking = {str(host.ssh.strict_host_key_checking).lower()}')
            lines.append("")
            
        config_path.write_text("\n".join(lines), encoding="utf-8")
