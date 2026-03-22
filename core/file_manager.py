import os
import shlex
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

ALLOWED_EXTENSIONS = {
    '.py', '.js', '.html', '.css', '.json', '.md', '.txt'
}

def is_path_safe(path: str) -> bool:
    """Check if the given path is within the PROJECT_ROOT and has an allowed extension."""
    try:
        abs_path = os.path.abspath(path)
        
        # Check if the path is inside PROJECT_ROOT
        if os.path.commonpath([PROJECT_ROOT, abs_path]) != PROJECT_ROOT:
            return False
            
        # Check for forbidden files/directories anywhere in the path
        path_parts = abs_path.split(os.sep)
        if '.env' in path_parts or '.git' in path_parts:
            return False
            
        # Check if there's an extension and it's allowed (or if it's a directory)
        # For simplicity, if it's an existing directory within root, we allow checking it,
        # but file operations will check extension.
        _, ext = os.path.splitext(abs_path)
        if ext and ext not in ALLOWED_EXTENSIONS:
            return False
            
        return True
    except Exception:
        return False

def _enforce_safety(path: str) -> str:
    if not is_path_safe(path):
        raise PermissionError(f"Access to path '{path}' is denied. Outside project root or forbidden.")
    return os.path.abspath(path)

def read_file(path: str) -> str:
    safe_path = _enforce_safety(path)
    if not os.path.exists(safe_path):
        raise FileNotFoundError(f"File not found: {path}")
    
    with open(safe_path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(path: str, content: str) -> None:
    safe_path = _enforce_safety(path)
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'w', encoding='utf-8') as f:
        f.write(content)

def append_file(path: str, content: str) -> None:
    safe_path = _enforce_safety(path)
    os.makedirs(os.path.dirname(safe_path), exist_ok=True)
    with open(safe_path, 'a', encoding='utf-8') as f:
        f.write(content)
