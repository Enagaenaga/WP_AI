import os
import sys
from pathlib import Path

# Python 3.11+ uses tomllib (standard library), older versions use tomli
if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli
from typing import Optional, List
import keyring
from pydantic import BaseModel
import json
import datetime

APP_NAME = "wp-ai"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.toml"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"

class LLMConfig(BaseModel):
    provider: str = "gemini"
    model: str = "gemini-1.5-flash"

class PolicyConfig(BaseModel):
    blocklist: List[str] = [r"^wp db drop", r"^wp user delete"]
    allow_risk: str = "low"

class RunnerConfig(BaseModel):
    default: str = "ssh"

class SSHConfig(BaseModel):
    host: str
    user: str
    key_path: Optional[str] = None
    port: int = 22
    password: Optional[str] = None  # For testing/password auth
    strict_host_key_checking: bool = True
    known_hosts_path: Optional[str] = None
    wp_path: Optional[str] = None
    wordpress_path: Optional[str] = None

class HostConfig(BaseModel):
    name: str
    ssh: SSHConfig
    api_url: Optional[str] = None

class Config(BaseModel):
    llm: LLMConfig = LLMConfig()
    policy: PolicyConfig = PolicyConfig()
    runner: RunnerConfig = RunnerConfig()
    hosts: list[HostConfig] = []

    def get_host(self, name: str) -> Optional[HostConfig]:
        for host in self.hosts:
            if host.name == name:
                return host
        return None

def ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config() -> Config:
    """Load configuration from config.toml."""
    # Check current directory first
    local_config = Path.cwd() / "config.toml"
    if local_config.exists():
        config_path = local_config
    elif CONFIG_FILE.exists():
        config_path = CONFIG_FILE
    else:
        return Config()

    with open(config_path, "rb") as f:
        data = tomli.load(f)

    return Config(**data)

def write_default_config(path: Optional[Path] = None):
    """Write a default config.toml to the given path or the app config directory."""
    ensure_config_dir()
    if path is None:
        path = CONFIG_FILE
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    template = (
        "[llm]\n"
        "provider = \"gemini\"\n"
        "model = \"gemini-1.5-flash\"\n\n"
        "[policy]\n"
        "allow_risk = \"low\"\n"
        "blocklist = [ \"^wp db drop\", \"^wp user delete\" ]\n\n"
        "[runner]\n"
        "default = \"ssh\"\n\n"
        "[[hosts]]\n"
        "name = \"docker\"\n"
        "[hosts.ssh]\n"
        "host = \"localhost\"\n"
        "port = 2222\n"
        "user = \"kusanagi\"\n"
        "password = \"password\"\n"
        "strict_host_key_checking = false\n"
    )
    path.write_text(template, encoding="utf-8")


def history_append(entry: dict):
    """Append a JSON object to history.jsonl in the config dir."""
    ensure_config_dir()
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.datetime.utcnow().isoformat() + "Z", **entry}, ensure_ascii=False) + "\n")


def get_api_key(provider: str) -> Optional[str]:
    """Retrieve API key from keyring or environment variable."""
    # Try env var first
    env_key = os.getenv(f"{provider.upper()}_API_KEY")
    if env_key:
        return env_key

    # Try keyring
    return keyring.get_password(APP_NAME, f"{provider}_api_key")


def set_api_key(provider: str, key: str):
    """Save API key to keyring."""
    keyring.set_password(APP_NAME, f"{provider}_api_key", key)
