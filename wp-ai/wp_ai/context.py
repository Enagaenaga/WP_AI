from typing import Dict, Any, List

def build_context_text(payloads: Dict[str, Any]) -> str:
    parts: List[str] = []
    si = payloads.get('system_info')
    if si:
        wp = si.get('wordpress_version') or si.get('wp_version') or si.get('wp')
        php = si.get('php_version') or si.get('php')
        os = si.get('server_os') or si.get('os')
        parts.append(f"System: WP={wp} PHP={php} OS={os}")
    pa = payloads.get('plugins_analysis')
    if pa:
        active = pa.get('active_count') or (len([p for p in pa.get('plugins', []) if p.get('status') == 'active']) if isinstance(pa.get('plugins'), list) else None)
        updates = pa.get('updates', [])
        upd_count = len(updates) if isinstance(updates, list) else (updates.get('count') if isinstance(updates, dict) else None)
        parts.append(f"Plugins: active={active} updates={upd_count}")
    el = payloads.get('error_logs')
    if el:
        lines = el.get('tail') or el.get('lines') or el.get('log')
        if isinstance(lines, list):
            tail = '\n'.join(lines[-20:])
        elif isinstance(lines, str):
            tail = '\n'.join(lines.splitlines()[-20:])
        else:
            tail = None
        if tail:
            parts.append("Recent Errors:\n" + tail)
    db = payloads.get('db_check')
    if db:
        autoload = db.get('autoload_size') or db.get('autoload_bytes')
        overhead = db.get('overhead')
        parts.append(f"DB: autoload={autoload} overhead={overhead}")
    return '\n'.join([p for p in parts if p])
