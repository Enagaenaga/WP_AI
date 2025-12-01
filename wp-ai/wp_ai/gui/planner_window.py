"""
WP-AI Planner Window

AIプランナーウィンドウ
plan/sayコマンドのGUI統合
"""

import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import threading
import queue
import json
from typing import Optional, List, Dict, Any

from .utils import setup_encoding
from .widgets import ContextControlPanel

from ..config import load_config, Config, HostConfig, history_append, DockerComposeConfig
from ..llm import LLMClient
from ..runner import SSHRunner, DockerComposeRunner, BaseRunner
from ..api import WPDoctorClient
from ..auth import get_api_basic_auth_keys
from ..context import build_context_text
from ..prompts import build_prompt
from ..main import PlanModel, _validate_ai_response, _policy_violations


class PlannerWindow(tk.Toplevel):
    """AIプランナーウィンドウ
    
    plan/sayコマンドをGUIで実行
    """
    
    def __init__(self, parent, host_config: Optional[HostConfig] = None):
        super().__init__(parent)
        
        # UTF-8設定
        setup_encoding()
        
        self.title("WP-AI プランナー")
        self.geometry("900x700")
        self.transient(parent)
        
        # 設定
        self.config = load_config()
        self.current_host = host_config or (self.config.hosts[0] if self.config.hosts else None)
        self.current_plan: Optional[PlanModel] = None
        
        # キュー
        self.response_queue = queue.Queue()
        
        # UI構築
        self._build_ui()
        
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
        
        # ホスト一覧をセット
        if self.config.hosts:
            host_names = [h.name for h in self.config.hosts]
            self.host_combo['values'] = host_names
            if self.current_host:
                self.host_combo.set(self.current_host.name)
            else:
                self.host_combo.current(0)
                self.current_host = self.config.hosts[0]
        
        # コンテキスト制御パネル
        self.context_panel = ContextControlPanel(self)
        self.context_panel.pack(fill=tk.X, padx=10, pady=5)
        
        # 指示入力エリア
        instruction_frame = ttk.LabelFrame(self, text="指示")
        instruction_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=False)
        
        self.instruction_text = tk.Text(
            instruction_frame,
            height=3,
            wrap=tk.WORD,
            font=("Arial", 10)
        )
        self.instruction_text.pack(fill=tk.BOTH, padx=5, pady=5)
        
        # ボタンエリア
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.plan_btn = ttk.Button(
            button_frame,
            text="📋 Plan生成",
            command=self.generate_plan
        )
        self.plan_btn.pack(side=tk.LEFT, padx=5)
        
        self.say_btn = ttk.Button(
            button_frame,
            text="🚀 Say実行",
            command=self.execute_say,
            state='disabled'
        )
        self.say_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(
            button_frame,
            text="🗑️ クリア",
            command=self.clear_plan
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # ステータス表示
        self.status_var = tk.StringVar(value="準備完了")
        ttk.Label(button_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=20)
        
        # プログレスバー
        self.progress = ttk.Progressbar(button_frame, mode='indeterminate', length=100)
        self.progress.pack(side=tk.LEFT, padx=5)
        
        # プラン表示エリア
        plan_frame = ttk.LabelFrame(self, text="生成されたプラン")
        plan_frame.pack(fill=tk.BOTH, padx=10, pady=5, expand=True)
        
        self.plan_display = scrolledtext.ScrolledText(
            plan_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            state='disabled'
        )
        self.plan_display.pack(fill=tk.BOTH, padx=5, pady=5, expand=True)
        
        # 閉じるボタン
        ttk.Button(self, text="閉じる", command=self.destroy).pack(pady=10)
        
    def on_host_change(self, event=None):
        """ホスト変更時の処理"""
        selected_name = self.host_var.get()
        for host in self.config.hosts:
            if host.name == selected_name:
                self.current_host = host
                break
                
    def generate_plan(self):
        """Plan生成"""
        instruction = self.instruction_text.get("1.0", tk.END).strip()
        if not instruction:
            messagebox.showwarning("警告", "指示を入力してください。")
            return
            
        if not self.current_host:
            messagebox.showwarning("警告", "ホストを選択してください。")
            return
            
        self.status_var.set("プラン生成中...")
        self.progress.start()
        self.plan_btn.config(state='disabled')
        
        # バックグラウンドスレッドで実行
        thread = threading.Thread(
            target=self._generate_plan_thread,
            args=(instruction,),
            daemon=True
        )
        thread.start()
        
        # キューチェック開始
        self.after(100, self._check_queue)
        
    def _generate_plan_thread(self, instruction: str):
        """Plan生成スレッド"""
        try:
            # デバッグ: 現在のホスト情報を出力
            print(f"\n{'='*80}")
            print(f"【デバッグ】プラン生成開始")
            print(f"{'='*80}")
            print(f"選択されたホスト: {self.current_host.name}")
            print(f"ランナー: {self.current_host.runner or self.config.runner.default}")
            if hasattr(self.current_host, 'ssh') and self.current_host.ssh:
                print(f"SSH設定あり: True")
                print(f"  wp_path: {self.current_host.ssh.wp_path}")
                print(f"  wordpress_path: {self.current_host.ssh.wordpress_path}")
            else:
                print(f"SSH設定あり: False")
            print(f"{'='*80}\n")
            
            # コンテキスト取得
            context_text = ""
            context_types = self.context_panel.get_context_types()
            if context_types and self.current_host.api_url:
                try:
                    context_text = self._fetch_context(context_types)
                except Exception as e:
                    self.response_queue.put({
                        "type": "warning",
                        "message": f"コンテキスト取得失敗: {str(e)}"
                    })
            
            # LLM呼び出し
            client = LLMClient(self.config.llm)
            prompt = build_prompt(instruction, host_config=self.current_host, context=context_text)
            
            # デバッグ: プロンプトの一部を出力
            print(f"【デバッグ】プロンプトに含まれるキーワード:")
            print(f"  'CRITICAL COMMAND FORMAT REQUIREMENT': {'CRITICAL COMMAND FORMAT REQUIREMENT' in prompt}")
            print(f"  'wp_path': {'/opt/alt/php81/usr/bin/php' in prompt}")
            print(f"{'='*80}\n")
            
            response_text = client.generate_content(prompt)
            
            # プラン検証
            plan_model = _validate_ai_response(response_text)
            
            # ポリシーチェック
            violations = _policy_violations(
                plan_model.normalized_commands(),
                self.config.policy.blocklist
            )
            
            if violations:
                self.response_queue.put({
                    "type": "policy_violation",
                    "violations": violations
                })
                return
            
            # 成功
            self.response_queue.put({
                "type": "plan_success",
                "plan": plan_model
            })
            
        except Exception as e:
            self.response_queue.put({
                "type": "error",
                "message": str(e)
            })
            
    def _fetch_context(self, context_types: list) -> str:
        """コンテキスト取得"""
        username, password = get_api_basic_auth_keys(self.current_host.name)
        if not username or not password:
            return ""
            
        client = WPDoctorClient(
            self.current_host.api_url,
            username=username,
            password=password
        )
        
        payloads = {}
        log_lines, log_level = self.context_panel.get_log_params()
        
        if 'system' in context_types:
            payloads['system_info'] = client.system_info()
            
        if 'plugins' in context_types:
            payloads['plugins_analysis'] = client.plugins_analysis(
                status='active',
                with_updates=True
            )
            
        if 'logs' in context_types and log_lines and log_level:
            payloads['error_logs'] = client.error_logs(lines=log_lines, level=log_level)
        
        return build_context_text(payloads)
        
    def _check_queue(self):
        """キューチェック"""
        try:
            while not self.response_queue.empty():
                msg = self.response_queue.get_nowait()
                
                if msg["type"] == "plan_success":
                    self._display_plan(msg["plan"])
                    self.status_var.set("プラン生成完了")
                    self.progress.stop()
                    self.plan_btn.config(state='normal')
                    self.say_btn.config(state='normal')
                    
                elif msg["type"] == "policy_violation":
                    violations = msg["violations"]
                    violation_text = "\n".join([
                        f"  - {v['command']} (pattern: {v['pattern']})"
                        for v in violations
                    ])
                    messagebox.showerror(
                        "ポリシー違反",
                        f"以下のコマンドがブロックリストに違反しています:\n{violation_text}"
                    )
                    self.status_var.set("ポリシー違反")
                    self.progress.stop()
                    self.plan_btn.config(state='normal')
                    
                elif msg["type"] == "warning":
                    messagebox.showwarning("警告", msg["message"])
                    
                elif msg["type"] == "error":
                    messagebox.showerror("エラー", f"プラン生成エラー: {msg['message']}")
                    self.status_var.set("エラー")
                    self.progress.stop()
                    self.plan_btn.config(state='normal')
                    
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_queue)
                
    def _display_plan(self, plan: PlanModel):
        """プランを表示"""
        self.current_plan = plan
        
        self.plan_display.config(state='normal')
        self.plan_display.delete(1.0, tk.END)
        
        # プラン詳細を整形
        text = f"Intent: {plan.intent}\n"
        text += f"Risk: {plan.risk}\n"
        text += f"Reason: {plan.reason}\n\n"
        text += "Commands:\n"
        for i, cmd in enumerate(plan.normalized_commands(), 1):
            text += f"  {i}. {cmd}\n"
        
        if plan.steps:
            text += "\nDetailed Steps:\n"
            for i, step in enumerate(plan.steps, 1):
                text += f"  {i}. {step.cmd}\n"
                if step.risk:
                    text += f"     Risk: {step.risk}\n"
                if step.explain:
                    text += f"     Explain: {step.explain}\n"
        
        self.plan_display.insert(tk.END, text)
        self.plan_display.config(state='disabled')
        
    def execute_say(self):
        """Say実行（コマンド確認後にSSH実行）"""
        if not self.current_plan:
            messagebox.showwarning("警告", "プランを生成してください。")
            return
            
        # コマンド確認ダイアログ
        dialog = CommandConfirmDialog(self, self.current_plan)
        self.wait_window(dialog)
        
        if dialog.result:
            # SSH実行ダイアログ
            instruction = self.instruction_text.get("1.0", tk.END).strip()
            ssh_dialog = SSHExecutionDialog(
                self,
                self.current_host,
                self.current_plan,
                instruction
            )
            
    def clear_plan(self):
        """プランをクリア"""
        self.instruction_text.delete("1.0", tk.END)
        self.plan_display.config(state='normal')
        self.plan_display.delete(1.0, tk.END)
        self.plan_display.config(state='disabled')
        self.current_plan = None
        self.say_btn.config(state='disabled')
        self.status_var.set("準備完了")


class CommandConfirmDialog(tk.Toplevel):
    """コマンド確認ダイアログ"""
    
    def __init__(self, parent, plan: PlanModel):
        super().__init__(parent)
        
        self.title("コマンド確認")
        self.geometry("600x400")
        self.transient(parent)
        self.grab_set()
        
        self.plan = plan
        self.result = False
        
        self._build_ui()
        
    def _build_ui(self):
        """UI構築"""
        # メッセージ
        ttk.Label(self, text="以下のコマンドを実行しますか？", font=("Arial", 10, "bold")).pack(padx=10, pady=10, anchor='w')
        
        # ボタン
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        ttk.Button(
            btn_frame,
            text="実行する",
            command=self.on_execute,
            style="Accent.TButton"  # もしスタイルがあれば
        ).pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="キャンセル",
            command=self.destroy
        ).pack(side=tk.RIGHT, padx=5)

        # コマンド表示
        text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD, font=("Consolas", 9))
        text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        text = ""
        for i, cmd in enumerate(self.plan.normalized_commands(), 1):
            text += f"{i}. {cmd}\n"
        
        text_area.insert(tk.END, text)
        text_area.config(state='disabled')
        
    def on_execute(self):
        """実行ボタン押下"""
        self.result = True
        self.destroy()


class SSHExecutionDialog(tk.Toplevel):
    """SSH実行ダイアログ"""
    
    def __init__(self, parent, host_config: HostConfig, plan: PlanModel, instruction: str):
        super().__init__(parent)
        
        self.title("コマンド実行中")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()
        
        self.host_config = host_config
        self.plan = plan
        self.instruction = instruction
        self.runner: Optional[BaseRunner] = None
        self.results = []
        self.config = load_config()
        
        self._build_ui()
        
        # 実行開始
        self.after(100, self.start_execution)
        
    def _build_ui(self):
        """UI構築"""
        # ステータス
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.status_var = tk.StringVar(value="準備中...")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side=tk.LEFT, padx=10)
        
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate', length=200)
        self.progress.pack(side=tk.LEFT, padx=5)
        self.progress.start()
        
        # 出力表示
        output_frame = ttk.LabelFrame(self, text="実行ログ")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.output_display = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Consolas", 9)
        )
        self.output_display.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 閉じるボタン
        self.close_btn = ttk.Button(
            self,
            text="閉じる",
            command=self.destroy,
            state='disabled'
        )
        self.close_btn.pack(pady=10)
        
    def start_execution(self):
        """実行開始"""
        thread = threading.Thread(target=self._execute_commands, daemon=True)
        thread.start()
        
    def _execute_commands(self):
        """コマンド実行"""
        try:
            # Determine which runner to use
            runner_type = self.host_config.runner or self.config.runner.default
            
            if runner_type == "ssh":
                if not self.host_config.ssh:
                    raise Exception(f"Runner for host '{self.host_config.name}' is 'ssh' but no SSH config found.")
                self.runner = SSHRunner(self.host_config.ssh)
            elif runner_type == "docker_compose":
                dc_config = self.host_config.docker_compose or DockerComposeConfig()
                self.runner = DockerComposeRunner(dc_config)
            else:
                raise Exception(f"Unknown runner type '{runner_type}' for host '{self.host_config.name}'.")
            
            self.runner.connect()
            
            commands = self.plan.normalized_commands()
            
            for i, cmd in enumerate(commands, 1):
                self.status_var.set(f"実行中 ({i}/{len(commands)}): {cmd[:50]}...")
                self.append_output(f"\n[コマンド {i}] {cmd}\n")
                
                # コールバック付きで実行
                exit_code = self.runner.run_command_with_callback(
                    cmd,
                    output_callback=self.append_output
                )
                
                self.results.append({"command": cmd, "exit_code": exit_code})
                
                if exit_code != 0:
                    self.append_output(f"\n[エラー] 終了コード: {exit_code}\n")
                    break
                else:
                    self.append_output(f"\n[成功] 終了コード: 0\n")
            
            # 履歴保存
            history_append({
                "host": self.host_config.name,
                "instruction": self.instruction,
                "plan": self.plan.model_dump(mode="json"),
                "results": self.results,
            })
            
            self.status_var.set("完了")
            self.progress.stop()
            self.close_btn.config(state='normal')
            
        except Exception as e:
            self.append_output(f"\n[エラー] {str(e)}\n")
            self.status_var.set("エラー")
            self.progress.stop()
            self.close_btn.config(state='normal')
            
        finally:
            if self.runner:
                self.runner.close()
                
    def append_output(self, text: str):
        """出力を追加"""
        self.output_display.insert(tk.END, text)
        self.output_display.see(tk.END)


def main():
    """テスト用エントリポイント"""
    root = tk.Tk()
    root.withdraw()
    
    window = PlannerWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
