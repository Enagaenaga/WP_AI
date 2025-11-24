import paramiko
from typing import Optional
from .config import SSHConfig
from pathlib import Path

class SSHRunner:
    def __init__(self, config: SSHConfig):
        self.config = config
        self.client = paramiko.SSHClient()
        # Enforce strict host key checking by default
        if self.config.strict_host_key_checking:
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            known_hosts = self.config.known_hosts_path or str(Path.home() / ".ssh" / "known_hosts")
            try:
                self.client.load_host_keys(known_hosts)
            except FileNotFoundError:
                # If known_hosts missing and strict is on, connection will fail; that's intended.
                pass
        else:
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        """Establish SSH connection."""
        connect_kwargs = {
            "hostname": self.config.host,
            "username": self.config.user,
            "port": self.config.port,
            "allow_agent": True,
            "look_for_keys": True,
        }

        # 公開鍵認証を優先
        if self.config.key_path:
            connect_kwargs["key_filename"] = self.config.key_path
        
        # パスワードが設定されている場合のみパスワード認証を許可
        # ただし、公開鍵認証が失敗した場合のフォールバックとして使用
        if self.config.password:
            connect_kwargs["password"] = self.config.password

        try:
            self.client.connect(**connect_kwargs)
        except paramiko.ssh_exception.AuthenticationException as e:
            # 認証エラーの場合、より詳細なメッセージを提供
            if self.config.key_path:
                raise Exception(f"SSH認証失敗: 指定された鍵ファイル '{self.config.key_path}' での認証に失敗しました。鍵ファイルのパスとパーミッションを確認してください。")
            else:
                raise Exception(f"SSH認証失敗: 公開鍵認証が必要です。config.tomlでkey_pathを設定して ください。元のエラー: {str(e)}")

    def run_command(self, command: str) -> int:
        """
        Run a command and stream output.
        Returns exit code.
        """
        if not self.client.get_transport() or not self.client.get_transport().is_active():
            self.connect()

        # wpコマンドのパス解決
        if self.config.wp_path and command.strip().startswith("wp "):
            command = self.config.wp_path + command.strip()[2:]
            
        # WordPressパスの指定
        if self.config.wordpress_path and (command.strip().startswith("wp ") or (self.config.wp_path and command.startswith(self.config.wp_path))):
            command += f" --path='{self.config.wordpress_path}'"

        stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)

        # Stream output (stdout)
        for line in iter(stdout.readline, ""):
            print(line, end="")
        # Stream stderr as well
        for line in iter(stderr.readline, ""):
            print(line, end="")

        # Wait for exit status
        exit_status = stdout.channel.recv_exit_status()
        return exit_status

    def run_command_with_callback(self, command: str, output_callback=None, error_callback=None) -> int:
        """
        Run a command with callback for real-time output.
        
        Args:
            command: Command to execute
            output_callback: Callback function for stdout lines (optional)
            error_callback: Callback function for stderr lines (optional)
            
        Returns:
            Exit code
        """
        if not self.client.get_transport() or not self.client.get_transport().is_active():
            self.connect()

        # wpコマンドのパス解決
        if self.config.wp_path and command.strip().startswith("wp "):
            command = self.config.wp_path + command.strip()[2:]
            
        # WordPressパスの指定
        if self.config.wordpress_path and (command.strip().startswith("wp ") or (self.config.wp_path and command.startswith(self.config.wp_path))):
            command += f" --path='{self.config.wordpress_path}'"

        stdin, stdout, stderr = self.client.exec_command(command, get_pty=True)

        # Stream output (stdout)
        for line in iter(stdout.readline, ""):
            if output_callback:
                output_callback(line)
            else:
                print(line, end="")
                
        # Stream stderr as well
        for line in iter(stderr.readline, ""):
            if error_callback:
                error_callback(line)
            elif output_callback:
                # If no error callback, send to output callback
                output_callback(line)
            else:
                print(line, end="")

        # Wait for exit status
        exit_status = stdout.channel.recv_exit_status()
        return exit_status

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
