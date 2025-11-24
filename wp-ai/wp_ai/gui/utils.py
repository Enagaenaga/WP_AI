"""
Utility functions for WP-AI GUI
"""

import sys
import os


def setup_encoding():
    """UTF-8エンコーディングを設定"""
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    os.environ['PYTHONUNBUFFERED'] = '1'
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_font_family():
    """OSに応じた適切なフォントファミリーを取得"""
    import platform
    system = platform.system()
    
    if system == "Windows":
        return ("Meiryo UI", "メイリオ", "MS Gothic", "Arial")
    elif system == "Darwin":  # macOS
        return ("Hiragino Sans", "Arial")
    else:  # Linux
        return ("Noto Sans CJK JP", "DejaVu Sans", "Arial")


def center_window(window, width=None, height=None):
    """ウィンドウを画面中央に配置"""
    window.update_idletasks()
    
    if width is None:
        width = window.winfo_width()
    if height is None:
        height = window.winfo_height()
    
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    window.geometry(f"{width}x{height}+{x}+{y}")


def truncate_text(text: str, max_length: int = 100) -> str:
    """テキストを指定長で切り詰め"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
