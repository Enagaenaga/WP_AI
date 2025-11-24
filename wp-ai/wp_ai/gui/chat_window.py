"""
WP-AI Chat Window

メインのGUIチャットウィンドウ
ストリーミングモードでAIとチャット可能
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinter import ttk
import threading
import queue
import sys
import os

# UTF-8設定
from .utils import setup_encoding, get_font_family, center_window
from .widgets import StatusBar, ContextControlPanel
from .dialogs import LLMSettingsDialog, HostManagerDialog

from ..config import load_config, Config
from ..llm import LLMClient
from ..api import WPDoctorClient
from ..context import build_context_text
from ..auth import get_api_basic_auth_keys


class ChatWindow(tk.Toplevel):
    """メインチャットウィンドウ
    
    AIとのチャット、ホスト選択、LLM設定などを提供
    """
    
    def __init__(self, parent=None):
        # 親がない場合は独立ウィンドウとして起動（Tkとして扱う）
        if parent is None:
            # 一時的な隠しTkルートを作成
            root = tk.Tk()
            root.withdraw()  # 表示しない
            super().__init__(root)
            self.protocol("WM_DELETE_WINDOW", lambda: (self.destroy(), root.destroy()))
        else:
            # 子ウィンドウとして起動
            super().__init__(parent)
            self.transient(parent)
        
        # UTF-8設定
        setup_encoding()
        
        # 設定読込
        try:
            self.config = load_config()
        except Exception as e:
            messagebox.showerror("設定エラー", f"config.tomlの読み込みに失敗しました:\n{e}\n\n初期設定を使用します")
            self.config = Config()
        
        # LLMクライアント初期化
        try:
            self.client = LLMClient(self.config.llm)
        except Exception as e:
            messagebox.showwarning(
                "LLM初期化エラー",
                f"LLMクライアントの初期化に失敗しました:\n{e}\n\n「LLM設定」から設定してください"
            )
            self.client = None
        
        # キュー・イベント
        self.response_queue = queue.Queue()
        self._cancel_event = threading.Event()
        self._typing_phase = None
        self._typing_dots = 0
        self._typing_after_id = None
        
        self._build_ui()
        self._load_hosts()
        
        # キューチェック開始
        self.after(100, self.check_queue)
    
    def _build_ui(self):
        """UI構築"""
        self.title("WP-AI Chat")
        self.geometry("800x600")
        
        # フォント設定
        font_family = get_font_family()
        
        # ===== トップバー: ホスト選択とボタン =====
        top_bar = tk.Frame(self)
        top_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(8, 0))
        
        tk.Label(top_bar, text="Host:").pack(side=tk.LEFT)
        
        self.host_var = tk.StringVar()
        self.host_combo = ttk.Combobox(
            top_bar,
            textvariable=self.host_var,
            state="readonly",
            width=20
        )
        self.host_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.host_combo.bind("<<ComboboxSelected>>", self.on_host_change)
        
        tk.Button(top_bar, text="Reload", command=self.reload_hosts).pack(side=tk.LEFT)
        tk.Button(top_bar, text="Manage", command=self.open_host_manager).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(top_bar, text="LLM設定...", command=self.open_llm_settings).pack(side=tk.LEFT, padx=(6, 0))
        
        # ===== チャット表示エリア =====
        self.chat_display = scrolledtext.ScrolledText(
            self,
            state="disabled",
            wrap=tk.WORD,
            padx=8,
            pady=8,
            font=(font_family[0], 10)
        )
        self.chat_display.pack(padx=10, pady=10, expand=True, fill=tk.BOTH)
        
        # タグ設定（ユーザー/AI表示用）
        self.chat_display.tag_config("user_label", foreground="#1976D2", font=(font_family[0], 10, "bold"))
        self.chat_display.tag_config("ai_label", foreground="#388E3C", font=(font_family[0], 10, "bold"))
        self.chat_display.tag_config("system_msg", foreground="#757575", font=(font_family[0], 9, "italic"))
        
        # ===== コンテキスト制御パネル =====
        self.context_panel = ContextControlPanel(self)
        self.context_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 6))
        
        # ===== 入力エリア =====
        input_frame = tk.Frame(self)
        input_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))
        
        self.prompt_input = tk.Entry(input_frame, font=(font_family[0], 10))
        self.prompt_input.pack(side=tk.LEFT, expand=True, fill=tk.X, ipady=4)
        self.prompt_input.bind("<Return>", self.send_message)
        
        self.send_button = tk.Button(input_frame, text="Send", command=self.send_message, width=8)
        self.send_button.pack(side=tk.LEFT, padx=(5, 0))
        
        self.stop_button = tk.Button(
            input_frame,
            text="Stop",
            command=self.stop_stream,
            state="disabled",
            width=8
        )
        self.stop_button.pack(side=tk.LEFT, padx=(5, 0))
        
        # ===== ステータスバー =====
        self.status_bar = StatusBar(self)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_bar.set_status("Ready")
        
        # ウィンドウを中央に配置
        center_window(self, 800, 600)
    
    def _load_hosts(self):
        """ホスト一覧を読み込み"""
        try:
            self.config = load_config()
            host_names = [h.name for h in self.config.hosts]
            
            if not host_names:
                host_names = ["(ホストが未設定)"]
            
            self.host_combo["values"] = host_names
            
            if host_names and host_names[0] != "(ホストが未設定)":
                self.host_combo.current(0)
                self.host_var.set(host_names[0])
        except Exception as e:
            messagebox.showerror("ホスト読込エラー", f"ホストの読み込みに失敗しました:\n{e}")
    
    def reload_hosts(self):
        """ホストをリロード"""
        self._load_hosts()
        self.status_bar.set_status("ホストをリロードしました")
    
    def on_host_change(self, event=None):
        """ホスト変更時の処理"""
        selected = self.host_var.get()
        self.status_bar.set_status(f"ホスト切替: {selected}")
    
    def open_host_manager(self):
        """ホスト管理ダイアログを開く"""
        try:
            dialog = HostManagerDialog(self)
            self.wait_window(dialog)
            self.reload_hosts()
        except Exception as e:
            messagebox.showerror("ホスト管理エラー", f"ホスト管理の起動に失敗しました:\n{e}")
    
    def open_llm_settings(self):
        """LLM設定ダイアログを開く"""
        try:
            dialog = LLMSettingsDialog(self)
            self.wait_window(dialog)
        except Exception as e:
            messagebox.showerror("LLM設定エラー", f"LLM設定の起動に失敗しました:\n{e}")
    
    def reload_llm_client(self):
        """LLMクライアントを再初期化"""
        try:
            self.config = load_config()
            self.client = LLMClient(self.config.llm)
            self.status_bar.set_status("LLM設定を再読込しました")
        except Exception as e:
            messagebox.showerror("LLM再初期化エラー", f"LLMクライアントの再初期化に失敗しました:\n{e}")
            self.client = None
    
    def add_message(self, sender: str, message: str, is_streaming=False):
        """メッセージをチャット表示に追加"""
        self.chat_display.config(state="normal")
        
        if not is_streaming:
            # 新しいメッセージの開始
            if sender == "You":
                self.chat_display.insert(tk.END, f"{sender}:\n", "user_label")
            elif sender == "System":
                self.chat_display.insert(tk.END, f"[{sender}]\n", "system_msg")
            else:
                self.chat_display.insert(tk.END, f"{sender}:\n", "ai_label")
        
        self.chat_display.insert(tk.END, message)
        
        if not is_streaming:
            self.chat_display.insert(tk.END, "\n\n")
        
        self.chat_display.config(state="disabled")
        self.chat_display.see(tk.END)
    
    def send_message(self, event=None):
        """メッセージ送信"""
        prompt = self.prompt_input.get().strip()
        if not prompt:
            return
        
        # LLMクライアントチェック
        if self.client is None:
            messagebox.showwarning(
                "LLM未設定",
                "LLMクライアントが初期化されていません。\n「LLM設定」から設定してください"
            )
            return
        
        # ユーザーメッセージ表示
        self.add_message("You", prompt)
        self.prompt_input.delete(0, tk.END)
        
        # UI状態変更
        self.prompt_input.config(state="disabled")
        self.send_button.config(state="disabled")
        self.stop_button.config(state="normal")
        
        # キャンセルフラグリセット
        self._cancel_event.clear()
        
        # AIメッセージのプレースホルダー
        self.add_message("AI", "", is_streaming=False)
        
        # ステータス更新
        self.status_bar.set_status("準備中…")
        self.status_bar.start_progress()
        self.configure(cursor="watch")
        
        # タイピングインジケーター開始
        self._typing_phase = "thinking"
        self._typing_dots = 0
        self._typing_after_id = self.after(350, self._update_typing_indicator)
        
        # コンテキスト設定の取得（メインスレッドで行う）
        host_name = self.host_var.get()
        context_types = self.context_panel.get_context_types()
        log_lines, log_level = self.context_panel.get_log_params()
        
        # バックグラウンドスレッド開始
        thread = threading.Thread(
            target=self.run_chat_stream, 
            args=(prompt, host_name, context_types, log_lines, log_level), 
            daemon=True
        )
        thread.start()
    
    def run_chat_stream(self, prompt: str, host_name: str, context_types: list, log_lines: int, log_level: str):
        """バックグラウンドスレッドでストリーミング実行"""
        try:
            # コンテキスト取得
            context_text = ""
            if context_types and host_name and host_name != "(ホストが未設定)":
                try:
                    host_config = self.config.get_host(host_name)
                    if host_config and host_config.api_url:
                        user, pwd = get_api_basic_auth_keys(host_name)
                        if user and pwd:
                            # 取得中メッセージ
                            self.response_queue.put({"type": "status", "text": "コンテキスト情報を取得中..."})
                            
                            api_client = WPDoctorClient(host_config.api_url, username=user, password=pwd)
                            payloads = {}
                            
                            if 'system' in context_types:
                                payloads['system_info'] = api_client.system_info()
                                payloads['db_check'] = api_client.db_check()
                            
                            if 'plugins' in context_types:
                                payloads['plugins_analysis'] = api_client.plugins_analysis(status='active', with_updates=True)
                            
                            if 'logs' in context_types:
                                payloads['error_logs'] = api_client.error_logs(lines=log_lines, level=log_level)
                            
                            context_text = build_context_text(payloads)
                        else:
                            self.response_queue.put({
                                "type": "error_log", 
                                "text": f"WordPressホスト '{host_name}' のAPI認証情報が見つかりません。\n"
                                        f"CLIで以下のコマンドを実行して設定してください:\n"
                                        f"wp-ai creds set --host {host_name}"
                            })
                except Exception as e:
                    self.response_queue.put({"type": "error_log", "text": f"コンテキスト取得エラー: {e}"})

            # システムプロンプト構築
            base_system_prompt = (
                "You are WP-AI assistant. "
                "Reply in natural Japanese prose aimed at WordPress site administrators. "
                "Provide helpful and accurate information about WordPress management and troubleshooting."
            )
            
            if context_text:
                system_prompt = f"{base_system_prompt}\n\nHere is the current system context:\n{context_text}"
            else:
                system_prompt = base_system_prompt
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
            
            # ステータス更新
            self.response_queue.put({"type": "status", "text": "AI応答を生成中..."})
            
            # ストリーミング実行
            for chunk in self.client.generate_content_stream(messages):
                if self._cancel_event.is_set():
                    break
                
                text = chunk.decode("utf-8", errors="ignore")
                if text:
                    self.response_queue.put({"type": "chunk", "text": text})
            
            # 完了シグナル
            self.response_queue.put({"type": "done"})
            
        except Exception as e:
            error_message = f"\n--- ERROR ---\n{str(e)}"
            self.response_queue.put({"type": "error", "text": error_message})
    
    def check_queue(self):
        """メインスレッドでキューをチェック"""
        try:
            while not self.response_queue.empty():
                message = self.response_queue.get_nowait()
                
                if isinstance(message, dict):
                    mtype = message.get("type")
                    
                    if mtype == "chunk":
                        text = message.get("text", "")
                        
                        # 最初のチャンクでフェーズ切替
                        if self._typing_phase == "thinking":
                            self._typing_phase = "streaming"
                            self.status_bar.set_status("出力中…")
                        
                        self.add_message("AI", text, is_streaming=True)
                    
                    elif mtype == "done":
                        # ストリーム完了
                        self._on_stream_complete()
                    
                    elif mtype == "status":
                        self.status_bar.set_status(message.get("text", ""))
                    
                    elif mtype == "error_log":
                        self.add_message("System", message.get("text", ""), is_streaming=False)
                    
                    elif mtype == "error":
                        # エラー
                        self._on_stream_error(message.get("text", "Unknown error"))
        
        finally:
            self.after(100, self.check_queue)
    
    def _on_stream_complete(self):
        """ストリーム完了時の処理"""
        self.prompt_input.config(state="normal")
        self.send_button.config(state="normal")
        self.stop_button.config(state="disabled")
        
        # 改行追加
        self.chat_display.config(state="normal")
        self.chat_display.insert(tk.END, "\n\n")
        self.chat_display.config(state="disabled")
        
        # ステータス更新
        self.status_bar.set_status("完了")
        self.status_bar.stop_progress()
        self.configure(cursor="")
        
        # タイピングインジケーター停止
        if self._typing_after_id:
            try:
                self.after_cancel(self._typing_after_id)
            except Exception:
                pass
            self._typing_after_id = None
            self._typing_phase = None
    
    def _on_stream_error(self, error_text: str):
        """ストリームエラー時の処理"""
        self.prompt_input.config(state="normal")
        self.send_button.config(state="normal")
        self.stop_button.config(state="disabled")
        
        self.add_message("AI", error_text, is_streaming=False)
        
        # ステータス更新
        self.status_bar.set_status("エラー")
        self.status_bar.stop_progress()
        self.configure(cursor="")
        
        # タイピングインジケーター停止
        if self._typing_after_id:
            try:
                self.after_cancel(self._typing_after_id)
            except Exception:
                pass
            self._typing_after_id = None
            self._typing_phase = None
    
    def _update_typing_indicator(self):
        """タイピングインジケーター更新"""
        try:
            if self._typing_phase in ("thinking", "streaming"):
                self._typing_dots = (self._typing_dots + 1) % 4
                dots = "…" * self._typing_dots
                
                if self._typing_phase == "thinking":
                    base = "準備中"
                else:
                    base = "出力中"
                
                self.status_bar.set_status(f"{base}{dots}")
                self._typing_after_id = self.after(350, self._update_typing_indicator)
        except Exception:
            try:
                self._typing_after_id = self.after(350, self._update_typing_indicator)
            except Exception:
                pass
    
    def stop_stream(self):
        """ストリーミング中断"""
        try:
            self._cancel_event.set()
            self.stop_button.config(state="disabled")
            
            # ステータス更新
            self.status_bar.set_status("中断しました")
            self.status_bar.stop_progress()
            self.configure(cursor="")
            
            # タイピングインジケーター停止
            if self._typing_after_id:
                try:
                    self.after_cancel(self._typing_after_id)
                except Exception:
                    pass
                self._typing_after_id = None
                self._typing_phase = None
        except Exception:
            pass


def main():
    """GUIアプリケーション起動"""
    app = ChatWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
