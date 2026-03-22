import os
from typing import List, Dict

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

IGNORE_DIRS = {
    '__pycache__',
    'venv',
    '.git',
    'node_modules',
    'dist',
    'build',
    '.cache',
    'instance',
    'tmp'
}

MAX_FILE_SIZE = 200 * 1024  # 200KB

def scan_project() -> List[Dict[str, str]]:
    """
    Recursively scans the project directory.
    Returns a list of dicts with 'path' and 'content'.
    """
    files_data = []
    
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Modify dirs in place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            # Skip ignored files specifically
            if file in {'.env', 'template_generator_best.pth', 'template_generator_model.pth', 'html_dataset.json'}:
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                # Check file size
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    continue
                    
                # We only want text files. Quick check.
                if file.endswith(('.pth', '.sqlite3', '.db', '.pyc', '.png', '.jpg', '.jpeg', '.gif', '.ico')):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Create a relative path for easier use
                rel_path = os.path.relpath(file_path, PROJECT_ROOT)
                
                files_data.append({
                    "path": rel_path,
                    "content": content
                })
            except (UnicodeDecodeError, PermissionError, OSError):
                # Skip binary files or unreadable files
                continue
                
    return files_data
