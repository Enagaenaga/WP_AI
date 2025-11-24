from typing import Optional, Tuple
import keyring
from .config import APP_NAME

# Store API creds as separate entries per host: "<host_name>:api_user" and ":api_pass"

def get_api_basic_auth_keys(host_name: str) -> Tuple[Optional[str], Optional[str]]:
    user = keyring.get_password(APP_NAME, f"{host_name}:api_user")
    pwd = keyring.get_password(APP_NAME, f"{host_name}:api_pass")
    return user, pwd

def set_api_basic_auth_keys(host_name: str, username: str, password: str) -> None:
    keyring.set_password(APP_NAME, f"{host_name}:api_user", username)
    keyring.set_password(APP_NAME, f"{host_name}:api_pass", password)
