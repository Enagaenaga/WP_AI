"""
WP-AI History Window

実行履歴ウィンドウ
履歴の表示、検索、再実行機能
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from .utils import setup_encoding

from ..config import HISTORY_FILE


class HistoryWindow(tk.Toplevel):
    """実行履歴ウィンドウ
    
    履歴の表示、検索、再実行
    """
    
    def __init__(self, parent):
        super().__init__(parent)
        
        # UTF-8設定
        setup_encoding()
        
        self.title("WP-AI 実行履歴")
        self.geometry("1000x600")
        self.transient(parent)
        
        self.parent = parent
        self.history_data: List[Dict[str, Any]] = []
        self.filtered_data: List[Dict[str, Any]] = []
        
        # UI構築
        self._build_ui()
        
        # 履歴読み込み
        self.load_history()
        
    def _build_ui(self):
        """UI構築"""
        # ツールバー
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # 更新ボタン
        ttk.Button(
            toolbar_frame,
            text="🔄 更新",
            command=self.load_history
        ).pack(side=tk.LEFT, padx=5)
        
        # 検索フィルタ
        ttk.Label(toolbar_frame, text="ホスト:").pack(side=tk.LEFT, padx=(20, 5))
        self.host_filter_var = tk.StringVar()
        self.host_filter = ttk.Entry(
            toolbar_frame,
            textvariable=self.host_filter_var,
            width=15
        )
        self.host_filter.pack(side=tk.LEFT, padx=5)
        self.host_filter.bind("<KeyRelease>", lambda e: self.apply_filters())
        
        ttk.Label(toolbar_frame, text="検索:").pack(side=tk.LEFT, padx=(20, 5))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(
            toolbar_frame,
            textvariable=self.search_var,
            width=30
        )
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())
        
        ttk.Button(
            toolbar_frame,
            text="クリア",
            command=self.clear_filters
        ).pack(side=tk.LEFT, padx=5)
        
        # メインコンテンツエリア（左右分割）
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 左側: 履歴一覧
        left_frame = ttk.Frame(paned_window)
        paned_window.add(left_frame, weight=1)
        
        # Treeview
        columns = ("timestamp", "host", "instruction", "status")
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=15)
        
        self.tree.heading("timestamp", text="日時")
        self.tree.heading("host", text="ホスト")
        self.tree.heading("instruction", text="指示")
        self.tree.heading("status", text="結果")
        
        self.tree.column("timestamp", width=150)
        self.tree.column("host", width=100)
        self.tree.column("instruction", width=300)
        self.tree.column("status", width=80)
        
        # スクロールバー
        tree_scroll = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 選択イベント
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        # 右側: 詳細表示
        right_frame = ttk.Frame(paned_window)
        paned_window.add(right_frame, weight=1)
        
        # 詳細表示ラベル
        ttk.Label(right_frame, text="詳細", font=("Arial", 10, "bold")).pack(pady=5)
        
        # 詳細テキスト
        self.detail_display = scrolledtext.ScrolledText(
            right_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state='disabled'
        )
        self.detail_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ボタンエリア
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.rerun_btn = ttk.Button(
            button_frame,
            text="🔁 再実行",
            command=self.rerun_selected,
            state='disabled'
        )
        self.rerun_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="閉じる",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)
        
        # ステータス
        self.status_var = tk.StringVar(value="履歴なし")
        ttk.Label(button_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=20)
        
    def load_history(self):
        """履歴ファイルを読み込み"""
        self.history_data = []
        
        if not HISTORY_FILE.exists():
            self.status_var.set("履歴ファイルが見つかりません")
            return
            
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entry = json.loads(line)
                        self.history_data.append(entry)
            
            # 新しい順にソート
            self.history_data.sort(key=lambda x: x.get("ts", ""), reverse=True)
            
            self.status_var.set(f"履歴: {len(self.history_data)}件")
            self.apply_filters()
            
        except Exception as e:
            messagebox.showerror("エラー", f"履歴読み込みエラー: {str(e)}")
            self.status_var.set("エラー")
            
    def apply_filters(self):
        """フィルタを適用"""
        host_filter = self.host_filter_var.get().lower()
        search_term = self.search_var.get().lower()
        
        self.filtered_data = []
        
        for entry in self.history_data:
            # ホストフィルタ
            if host_filter and host_filter not in entry.get("host", "").lower():
                continue
                
            # 検索フィルタ
            if search_term:
                instruction = entry.get("instruction", "").lower()
                if search_term not in instruction:
                    continue
            
            self.filtered_data.append(entry)
        
        self.update_tree()
        
    def update_tree(self):
        """Treeviewを更新"""
        # クリア
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # データ追加
        for entry in self.filtered_data:
            timestamp = entry.get("ts", "")
            # ISO形式をローカル時刻に変換
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                timestamp_str = timestamp
            
            host = entry.get("host", "N/A")
            instruction = entry.get("instruction", "N/A")
            
            # 結果を判定
            results = entry.get("results", [])
            if results:
                # 最後のコマンドの結果をチェック
                last_result = results[-1]
                exit_code = last_result.get("exit_code", -1)
                status = "成功" if exit_code == 0 else "失敗"
            else:
                status = "不明"
            
            self.tree.insert(
                "",
                tk.END,
                values=(timestamp_str, host, instruction, status),
                tags=(status,)
            )
        
        # タグに色を設定
        self.tree.tag_configure("成功", foreground="#4CAF50")
        self.tree.tag_configure("失敗", foreground="#F44336")
        
        self.status_var.set(f"表示: {len(self.filtered_data)}件 / 全{len(self.history_data)}件")
        
    def clear_filters(self):
        """フィルタをクリア"""
        self.host_filter_var.set("")
        self.search_var.set("")
        self.apply_filters()
        
    def on_select(self, event=None):
        """履歴項目選択時"""
        selection = self.tree.selection()
        if not selection:
            self.rerun_btn.config(state='disabled')
            self.detail_display.config(state='normal')
            self.detail_display.delete(1.0, tk.END)
            self.detail_display.config(state='disabled')
            return
        
        # 選択されたインデックスを取得
        item = selection[0]
        index = self.tree.index(item)
        
        if index < len(self.filtered_data):
            entry = self.filtered_data[index]
            self.display_detail(entry)
            self.rerun_btn.config(state='normal')
        
    def display_detail(self, entry: Dict[str, Any]):
        """詳細を表示"""
        self.detail_display.config(state='normal')
        self.detail_display.delete(1.0, tk.END)
        
        # 整形して表示
        text = f"日時: {entry.get('ts', 'N/A')}\n"
        text += f"ホスト: {entry.get('host', 'N/A')}\n"
        text += f"指示: {entry.get('instruction', 'N/A')}\n\n"
        
        # プラン
        plan = entry.get("plan", {})
        if plan:
            text += "--- プラン ---\n"
            text += f"Intent: {plan.get('intent', 'N/A')}\n"
            text += f"Risk: {plan.get('risk', 'N/A')}\n"
            text += f"Reason: {plan.get('reason', 'N/A')}\n\n"
            
            commands = plan.get("commands", [])
            if commands:
                text += "Commands:\n"
                for i, cmd in enumerate(commands, 1):
                    text += f"  {i}. {cmd}\n"
            text += "\n"
        
        # 実行結果
        results = entry.get("results", [])
        if results:
            text += "--- 実行結果 ---\n"
            for i, result in enumerate(results, 1):
                cmd = result.get("command", "N/A")
                exit_code = result.get("exit_code", -1)
                status = "成功" if exit_code == 0 else "失敗"
                text += f"{i}. {cmd}\n"
                text += f"   結果: {status} (exit code: {exit_code})\n\n"
        
        # JSON全体も表示（折りたたみ可能にしたい場合は別途実装）
        text += "\n--- JSON (Raw) ---\n"
        text += json.dumps(entry, indent=2, ensure_ascii=False)
        
        self.detail_display.insert(tk.END, text)
        self.detail_display.config(state='disabled')
        
    def rerun_selected(self):
        """選択した履歴を再実行"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = selection[0]
        index = self.tree.index(item)
        
        if index >= len(self.filtered_data):
            return
            
        entry = self.filtered_data[index]
        instruction = entry.get("instruction", "")
        host = entry.get("host", "")
        
        if not instruction:
            messagebox.showwarning("警告", "指示が見つかりません。")
            return
        
        # プランナーウィンドウを開く
        try:
            from .planner_window import PlannerWindow
            
            # ホストを取得
            from ..config import load_config
            config = load_config()
            host_config = config.get_host(host)
            
            # プランナーウィンドウを開く
            planner = PlannerWindow(self.parent, host_config)
            
            # 指示を設定
            planner.instruction_text.insert("1.0", instruction)
            
        except Exception as e:
            messagebox.showerror("エラー", f"プランナー起動エラー: {str(e)}")


def main():
    """テスト用エントリポイント"""
    root = tk.Tk()
    root.withdraw()
    
    window = HistoryWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
