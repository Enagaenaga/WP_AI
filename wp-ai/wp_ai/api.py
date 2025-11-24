from typing import Optional, Dict, Any, List
import requests
from requests.auth import HTTPBasicAuth

class WPDoctorClient:
    def __init__(self, base_wp_json_url: str, username: Optional[str] = None, password: Optional[str] = None, timeout: int = 15):
        # base_wp_json_url example: https://example.com/wp-json
        self.base = base_wp_json_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, password) if username and password else None
        self.timeout = timeout

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None):
        url = f"{self.base}/{path.lstrip('/')}"
        resp = requests.get(url, auth=self.auth, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_body: Optional[Dict[str, Any]] = None):
        url = f"{self.base}/{path.lstrip('/')}"
        resp = requests.post(url, auth=self.auth, json=json_body or {}, timeout=self.timeout)
        resp.raise_for_status()
        # actions may return JSON or text
        try:
            return resp.json()
        except ValueError:
            return {"raw": resp.text}

    # Diagnostics
    def quick_checks(self) -> Dict[str, Any]:
        return self._get('wpdoctor/v1/quick-checks')

    def system_info(self) -> Dict[str, Any]:
        return self._get('wpdoctor/v1/system-info')

    def plugins_analysis(self, status: str = 'active', with_updates: bool = True) -> Dict[str, Any]:
        return self._get('wpdoctor/v1/plugins-analysis', params={"status": status, "with_updates": str(with_updates).lower()})

    def error_logs(self, lines: int = 50, level: str = 'all', format: str = 'json', source: str = 'auto', since: Optional[str] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"lines": lines, "level": level, "format": format, "source": source}
        if since:
            params["since"] = since
        return self._get('wpdoctor/v1/error-logs', params=params)

    def db_check(self) -> Dict[str, Any]:
        return self._get('wpdoctor/v1/db-check')

    # Actions
    def action_rewrite_flush(self, hard: bool = True) -> Dict[str, Any]:
        return self._post('wpdoctor/v1/actions', {"action": "rewrite_flush", "hard": hard})

    def action_cache_flush(self) -> Dict[str, Any]:
        return self._post('wpdoctor/v1/actions', {"action": "cache_flush"})

    def action_transients_flush(self) -> Dict[str, Any]:
        return self._post('wpdoctor/v1/actions', {"action": "transients_flush"})

    def action_plugin_toggle(self, plugin_file: str, enable: bool) -> Dict[str, Any]:
        return self._post('wpdoctor/v1/actions', {"action": "plugin_toggle", "plugin": plugin_file, "enable": enable})

    # LLM config and chat (server-side)
    def llm_config_get(self) -> Dict[str, Any]:
        return self._get('wpdoctor/v1/llm-config')

    def llm_config_set(self, provider: str, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"provider": provider, "model": model}
        if api_key:
            payload["api_key"] = api_key
        if base_url:
            payload["base_url"] = base_url
        return self._post('wpdoctor/v1/llm-config', payload)

    def llm_chat(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        return self._post('wpdoctor/v1/llm-chat', {"messages": messages})
