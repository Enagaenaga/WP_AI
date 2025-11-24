"""
Custom widgets for WP-AI GUI
"""

import tkinter as tk
from tkinter import ttk


class StatusBar(tk.Frame):
    """ステータスバーウィジェット"""
    
    def __init__(self, parent):
        super().__init__(parent, relief=tk.SUNKEN, bd=1)
        
        self.status_var = tk.StringVar(value="Ready")
        self.label = tk.Label(self, textvariable=self.status_var, anchor="w")
        self.label.pack(side=tk.LEFT, padx=6, pady=2, fill=tk.X, expand=True)
        
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=150)
        self.progress.pack(side=tk.RIGHT, padx=6, pady=2)
    
    def set_status(self, text: str):
        """ステータステキストを設定"""
        self.status_var.set(text)
    
    def start_progress(self):
        """プログレスバーを開始"""
        self.progress.start(12)
    
    def stop_progress(self):
        """プログレスバーを停止"""
        try:
            self.progress.stop()
        except Exception:
            pass


class ContextControlPanel(tk.Frame):
    """コンテキスト制御パネル"""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # チェックボックス
        self.system_var = tk.BooleanVar(value=True)
        self.plugins_var = tk.BooleanVar(value=True)
        self.logs_var = tk.BooleanVar(value=False)
        
        tk.Checkbutton(self, text="system", variable=self.system_var).pack(side=tk.LEFT)
        tk.Checkbutton(self, text="plugins", variable=self.plugins_var).pack(side=tk.LEFT, padx=(8, 0))
        tk.Checkbutton(self, text="logs", variable=self.logs_var).pack(side=tk.LEFT, padx=(8, 0))
        
        # ログパラメータ
        tk.Label(self, text="log lines:").pack(side=tk.LEFT, padx=(10, 2))
        self.log_lines_var = tk.StringVar(value="120")
        tk.Entry(self, textvariable=self.log_lines_var, width=6).pack(side=tk.LEFT)
        
        tk.Label(self, text="level:").pack(side=tk.LEFT, padx=(10, 2))
        self.log_level_var = tk.StringVar(value="all")
        self.level_menu = tk.OptionMenu(self, self.log_level_var, "all", "error", "warning", "notice")
        self.level_menu.pack(side=tk.LEFT)
    
    def get_context_types(self):
        """選択されたコンテキストタイプのリストを取得"""
        types = []
        if self.system_var.get():
            types.append('system')
        if self.plugins_var.get():
            types.append('plugins')
        if self.logs_var.get():
            types.append('logs')
        return types
    
    def get_log_params(self):
        """ログパラメータを取得"""
        if not self.logs_var.get():
            return None, None
        
        try:
            lines = int(self.log_lines_var.get().strip())
        except Exception:
            lines = 120
        
        level = self.log_level_var.get().strip()
        return lines, level
