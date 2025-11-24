"""
WP-AI Launcher Window

メインランチャー画面
各機能へのアクセスを提供
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import queue
import json
from typing import Optional

from .utils import setup_encoding
from .dialogs import LLMSettingsDialog

from ..config import load_config, Config
from ..api import WPDoctorClient
from ..auth import get_api_basic_auth_keys


class LauncherWindow(tk.Tk):
    """メインランチャーウィンドウ
    
    各機能へのアクセスを提供するメニュー画面
    """
    
    def __init__(self):
        super().__init__()
        
        # UTF-8設定
        setup_encoding()
        
        self.title("WP-AI Launcher")
        self.geometry("500x400")
        
        # 設定読み込み
        self.config = load_config()
        self.hosts = []
        self.current_host = None
        
        # UI構築
        self._build_ui()
        self._load_hosts()
        
    def _build_ui(self):
        """UI構築"""
        # ヘッダー: ホスト選択
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="Host:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.host_var = tk.StringVar()
        self.host_combo = ttk.Combobox(
            header_frame,
            textvariable=self.host_var,
            state="readonly",
            width=20
        )
        self.host_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.host_combo.bind("<<ComboboxSelected>>", self.on_host_change)
        
        ttk.Button(header_frame, text="Reload", command=self.reload_hosts).pack(side=tk.LEFT, padx=5)
        ttk.Button(header_frame, text="Manage", command=self.open_host_manager).pack(side=tk.LEFT, padx=5)
        
        # メインコンテンツエリア
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # タイトル
        title_label = tk.Label(
            main_frame,
            text="WP-AI",
            font=("Arial", 24, "bold"),
            fg="#1976D2"
        )
        title_label.pack(pady=(10, 20))
        
        # ボタングリッド
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(expand=True)
        
        # ボタンスタイル設定
        style = ttk.Style()
        style.configure("Menu.TButton", padding=10, font=("Arial", 10))
        
        # 行1: AIチャット、システム情報
        row1 = ttk.Frame(button_frame)
        row1.pack(pady=5)
        
        self.chat_btn = ttk.Button(
            row1,
            text="💬 AIチャット",
            command=self.launch_chat,
            style="Menu.TButton",
            width=20
        )
        self.chat_btn.pack(side=tk.LEFT, padx=5)
        
        self.sysinfo_btn = ttk.Button(
            row1,
            text="ℹ️ システム情報",
            command=self.show_system_info,
            style="Menu.TButton",
            width=20
        )
        self.sysinfo_btn.pack(side=tk.LEFT, padx=5)
        
        # 行2: プラグイン分析、ログ表示
        row2 = ttk.Frame(button_frame)
        row2.pack(pady=5)
        
        self.plugins_btn = ttk.Button(
            row2,
            text="🔌 プラグイン分析",
            command=self.show_plugin_analysis,
            style="Menu.TButton",
            width=20
        )
        self.plugins_btn.pack(side=tk.LEFT, padx=5)
        
        self.logs_btn = ttk.Button(
            row2,
            text="📋 ログ表示",
            command=self.show_logs,
            style="Menu.TButton",
            width=20
        )
        self.logs_btn.pack(side=tk.LEFT, padx=5)
        
        # 行3: AIプランナー、実行履歴
        row3 = ttk.Frame(button_frame)
        row3.pack(pady=5)
        
        self.planner_btn = ttk.Button(
            row3,
            text="🤖 AIプランナー",
            command=self.launch_planner,
            style="Menu.TButton",
            width=20
        )
        self.planner_btn.pack(side=tk.LEFT, padx=5)
        
        self.history_btn = ttk.Button(
            row3,
            text="📜 実行履歴",
            command=self.show_history,
            style="Menu.TButton",
            width=20
        )
        self.history_btn.pack(side=tk.LEFT, padx=5)
        
        # 行4: 設定
        row4 = ttk.Frame(button_frame)
        row4.pack(pady=5)
        
        self.settings_btn = ttk.Button(
            row4,
            text="⚙️ LLM設定",
            command=self.open_llm_settings,
            style="Menu.TButton",
            width=20
        )
        self.settings_btn.pack(side=tk.LEFT, padx=5)
        
        # フッター
        footer_frame = ttk.Frame(self)
        footer_frame.pack(fill=tk.X, padx=10, pady=10)
        
        footer_label = tk.Label(
            footer_frame,
            text="WP-AI GUI v3.0 - Phase 3 AI Planner",
            font=("Arial", 8),
            fg="#666666"
        )
        footer_label.pack()
        
    def _load_hosts(self):
        """ホスト一覧を読み込み"""
        try:
            self.config = load_config()
            self.hosts = self.config.hosts
            
            if self.hosts:
                host_names = [h.name for h in self.hosts]
                self.host_combo['values'] = host_names
                self.host_combo.current(0)
                self.current_host = self.hosts[0]
            else:
                self.host_combo['values'] = []
                self.current_host = None
                messagebox.showwarning("警告", "ホストが設定されていません。")
        except Exception as e:
            messagebox.showerror("エラー", f"ホスト読み込みエラー: {str(e)}")
            
    def reload_hosts(self):
        """ホストをリロード"""
        self._load_hosts()
        
    def on_host_change(self, event=None):
        """ホスト変更時の処理"""
        selected_name = self.host_var.get()
        for host in self.hosts:
            if host.name == selected_name:
                self.current_host = host
                break
                
    def open_llm_settings(self):
        """LLM設定ダイアログを開く"""
        dialog = LLMSettingsDialog(self)
        self.wait_window(dialog)
        # 設定が変更された可能性があるので再読み込み
        self.config = load_config()
        
    def open_host_manager(self):
        """ホスト管理ダイアログを開く"""
        from .dialogs import HostManagerDialog
        dialog = HostManagerDialog(self)
        self.wait_window(dialog)
        # ホストが変更された可能性があるので再読み込み
        self.reload_hosts()
        
    def launch_chat(self):
        """AIチャットウィンドウを起動"""
        try:
            from .chat_window import ChatWindow
            
            # 新しいウィンドウとして起動
            chat = ChatWindow(parent=self)
            
        except Exception as e:
            messagebox.showerror("エラー", f"チャットウィンドウ起動エラー: {str(e)}")
            
    def show_system_info(self):
        """システム情報ウィンドウを表示"""
        if not self.current_host:
            messagebox.showwarning("警告", "ホストを選択してください。")
            return
            
        window = SystemInfoWindow(self, self.current_host)
        
    def show_plugin_analysis(self):
        """プラグイン分析ウィンドウを表示"""
        if not self.current_host:
            messagebox.showwarning("警告", "ホストを選択してください。")
            return
            
        window = PluginAnalysisWindow(self, self.current_host)
        
    def show_logs(self):
        """ログビューアウィンドウを表示"""
        if not self.current_host:
            messagebox.showwarning("警告", "ホストを選択してください。")
            return
            
        window = LogViewerWindow(self, self.current_host)
        
    def launch_planner(self):
        """AIプランナーウィンドウを起動"""
        if not self.current_host:
            messagebox.showwarning("警告", "ホストを選択してください。")
            return
            
        try:
            from .planner_window import PlannerWindow
            window = PlannerWindow(self, self.current_host)
        except Exception as e:
            messagebox.showerror("エラー", f"プランナー起動エラー: {str(e)}")
            
    def show_history(self):
        """実行履歴ウィンドウを表示"""
        try:
            from .history_window import HistoryWindow
            window = HistoryWindow(self)
        except Exception as e:
            messagebox.showerror("エラー", f"履歴ウィンドウ起動エラー: {str(e)}")


class SystemInfoWindow(tk.Toplevel):
    """システム情報表示ウィンドウ"""
    
    def __init__(self, parent, host_config):
        super().__init__(parent)
        
        self.title(f"システム情報 - {host_config.name}")
        self.geometry("600x500")
        self.transient(parent)
        
        self.host_config = host_config
        self.data_queue = queue.Queue()
        
        self._build_ui()
        self._load_data()
        
    def _build_ui(self):
        """UI構築"""
        # ツールバー
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(toolbar, text="更新", command=self._load_data).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="準備中...")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        
        # プログレスバー
        self.progress = ttk.Progressbar(toolbar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=5)
        
        # テキスト表示エリア
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.text_display = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.text_display.pack(fill=tk.BOTH, expand=True)
        
        # 閉じるボタン
        ttk.Button(self, text="閉じる", command=self.destroy).pack(pady=10)
        
    def _load_data(self):
        """データ読み込み"""
        self.status_var.set("読み込み中...")
        self.progress.start()
        
        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()
        
        self.after(100, self._check_queue)
        
    def _fetch_data(self):
        """バックグラウンドでデータ取得"""
        try:
            username, password = get_api_basic_auth_keys(self.host_config.name)
            client = WPDoctorClient(
                self.host_config.api_url,
                username=username,
                password=password
            )
            
            data = client.system_info()
            self.data_queue.put({"type": "success", "data": data})
            
        except Exception as e:
            self.data_queue.put({"type": "error", "message": str(e)})
            
    def _check_queue(self):
        """キューチェック"""
        try:
            while not self.data_queue.empty():
                msg = self.data_queue.get_nowait()
                
                if msg["type"] == "success":
                    self._display_data(msg["data"])
                    self.status_var.set("完了")
                    self.progress.stop()
                    
                elif msg["type"] == "error":
                    self.text_display.delete(1.0, tk.END)
                    self.text_display.insert(tk.END, f"エラー: {msg['message']}")
                    self.status_var.set("エラー")
                    self.progress.stop()
                    
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_queue)
                
    def _display_data(self, data):
        """データを表示"""
        self.text_display.delete(1.0, tk.END)
        
        # JSONを見やすく整形
        formatted = json.dumps(data, indent=2, ensure_ascii=False)
        self.text_display.insert(tk.END, formatted)


class PluginAnalysisWindow(tk.Toplevel):
    """プラグイン分析ウィンドウ"""
    
    def __init__(self, parent, host_config):
        super().__init__(parent)
        
        self.title(f"プラグイン分析 - {host_config.name}")
        self.geometry("800x500")
        self.transient(parent)
        
        self.host_config = host_config
        self.data_queue = queue.Queue()
        
        self._build_ui()
        self._load_data()
        
    def _build_ui(self):
        """UI構築"""
        # ツールバー
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(toolbar, text="更新", command=self._load_data).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="準備中...")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        
        # プログレスバー
        self.progress = ttk.Progressbar(toolbar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=5)
        
        # テーブル表示エリア
        table_frame = ttk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview
        columns = ("name", "version", "status", "update")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        
        self.tree.heading("name", text="プラグイン名")
        self.tree.heading("version", text="バージョン")
        self.tree.heading("status", text="状態")
        self.tree.heading("update", text="更新")
        
        self.tree.column("name", width=300)
        self.tree.column("version", width=100)
        self.tree.column("status", width=100)
        self.tree.column("update", width=100)
        
        # スクロールバー
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 閉じるボタン
        ttk.Button(self, text="閉じる", command=self.destroy).pack(pady=10)
        
    def _load_data(self):
        """データ読み込み"""
        self.status_var.set("読み込み中...")
        self.progress.start()
        
        # 既存データをクリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()
        
        self.after(100, self._check_queue)
        
    def _fetch_data(self):
        """バックグラウンドでデータ取得"""
        try:
            username, password = get_api_basic_auth_keys(self.host_config.name)
            client = WPDoctorClient(
                self.host_config.api_url,
                username=username,
                password=password
            )
            
            data = client.plugins_analysis(status='all', with_updates=True)
            self.data_queue.put({"type": "success", "data": data})
            
        except Exception as e:
            self.data_queue.put({"type": "error", "message": str(e)})
            
    def _check_queue(self):
        """キューチェック"""
        try:
            while not self.data_queue.empty():
                msg = self.data_queue.get_nowait()
                
                if msg["type"] == "success":
                    self._display_data(msg["data"])
                    self.status_var.set("完了")
                    self.progress.stop()
                    
                elif msg["type"] == "error":
                    messagebox.showerror("エラー", f"データ取得エラー: {msg['message']}")
                    self.status_var.set("エラー")
                    self.progress.stop()
                    
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_queue)
                
    def _display_data(self, data):
        """データを表示"""
        # プラグインリストを取得
        plugins = data.get('plugins', [])
        
        if not isinstance(plugins, list):
            messagebox.showwarning("警告", "プラグインデータの形式が不正です。")
            return
            
        for plugin in plugins:
            name = plugin.get('name', 'N/A')
            version = plugin.get('version', 'N/A')
            status = plugin.get('status', 'N/A')
            
            # 更新情報
            has_update = plugin.get('update_available', False)
            update_status = "あり" if has_update else "-"
            
            self.tree.insert("", tk.END, values=(name, version, status, update_status))


class LogViewerWindow(tk.Toplevel):
    """ログビューアウィンドウ"""
    
    def __init__(self, parent, host_config):
        super().__init__(parent)
        
        self.title(f"ログ表示 - {host_config.name}")
        self.geometry("800x600")
        self.transient(parent)
        
        self.host_config = host_config
        self.data_queue = queue.Queue()
        
        self._build_ui()
        self._load_data()
        
    def _build_ui(self):
        """UI構築"""
        # ツールバー
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(toolbar, text="更新", command=self._load_data).pack(side=tk.LEFT, padx=5)
        
        # ログ行数
        ttk.Label(toolbar, text="行数:").pack(side=tk.LEFT, padx=(10, 5))
        self.lines_var = tk.StringVar(value="100")
        lines_entry = ttk.Entry(toolbar, textvariable=self.lines_var, width=10)
        lines_entry.pack(side=tk.LEFT, padx=5)
        
        # ログレベル
        ttk.Label(toolbar, text="レベル:").pack(side=tk.LEFT, padx=(10, 5))
        self.level_var = tk.StringVar(value="all")
        level_combo = ttk.Combobox(
            toolbar,
            textvariable=self.level_var,
            values=["all", "error", "warning", "notice"],
            state="readonly",
            width=10
        )
        level_combo.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="準備中...")
        ttk.Label(toolbar, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        
        # プログレスバー
        self.progress = ttk.Progressbar(toolbar, mode='indeterminate', length=100)
        self.progress.pack(side=tk.RIGHT, padx=5)
        
        # ログ表示エリア
        log_frame = ttk.Frame(self)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.log_display.pack(fill=tk.BOTH, expand=True)
        
        # 閉じるボタン
        ttk.Button(self, text="閉じる", command=self.destroy).pack(pady=10)
        
    def _load_data(self):
        """データ読み込み"""
        self.status_var.set("読み込み中...")
        self.progress.start()
        
        thread = threading.Thread(target=self._fetch_data, daemon=True)
        thread.start()
        
        self.after(100, self._check_queue)
        
    def _fetch_data(self):
        """バックグラウンドでデータ取得"""
        try:
            username, password = get_api_basic_auth_keys(self.host_config.name)
            client = WPDoctorClient(
                self.host_config.api_url,
                username=username,
                password=password
            )
            
            lines = int(self.lines_var.get())
            level = self.level_var.get()
            
            data = client.error_logs(lines=lines, level=level, format='json')
            self.data_queue.put({"type": "success", "data": data})
            
        except ValueError:
            self.data_queue.put({"type": "error", "message": "行数は数値で指定してください。"})
        except Exception as e:
            self.data_queue.put({"type": "error", "message": str(e)})
            
    def _check_queue(self):
        """キューチェック"""
        try:
            while not self.data_queue.empty():
                msg = self.data_queue.get_nowait()
                
                if msg["type"] == "success":
                    self._display_data(msg["data"])
                    self.status_var.set("完了")
                    self.progress.stop()
                    
                elif msg["type"] == "error":
                    self.log_display.delete(1.0, tk.END)
                    self.log_display.insert(tk.END, f"エラー: {msg['message']}")
                    self.status_var.set("エラー")
                    self.progress.stop()
                    
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_queue)
                
    def _display_data(self, data):
        """データを表示"""
        self.log_display.delete(1.0, tk.END)
        
        # ログデータの取得
        logs = data.get('tail') or data.get('lines') or data.get('log', [])
        
        if isinstance(logs, list):
            log_text = '\n'.join(logs)
        elif isinstance(logs, str):
            log_text = logs
        else:
            log_text = json.dumps(data, indent=2, ensure_ascii=False)
        
        self.log_display.insert(tk.END, log_text)


def main():
    """GUIアプリケーション起動"""
    app = LauncherWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
