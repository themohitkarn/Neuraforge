import os
import shlex
import subprocess

PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

ALLOWED_COMMANDS = {
    'python',
    'pytest',
    'pip',
    'git',
    'node',
    'npm',
    'ls',
    'mkdir'
}

BLOCKED_PATTERN = {
    'rm',
    'sudo',
    'chmod',
    'curl',
    'wget'
}

def is_command_safe(command: str) -> bool:
    """Check if the command is safe to execute."""
    try:
        parts = shlex.split(command)
        if not parts:
            return False
            
        base_cmd = parts[0]
        
        # Check against explicitly blocked commands anywhere in the parts
        for part in parts:
            if part in BLOCKED_PATTERN:
                return False
                
        # Must start with allowed command
        if base_cmd not in ALLOWED_COMMANDS:
            return False
            
        # Specific pip check
        if base_cmd == 'pip':
            if len(parts) > 1 and parts[1] == 'install':
                pass # allow pip install (including dependencies or -r)
            elif len(parts) > 1 and parts[1] == 'list':
                pass # allow pip list
            else:
                return False
                
        # Avoid explicit network outbound except pip/npm/git
        # If user runs 'python -c "import urllib..."', it's hard to block entirely,
        # but we strictly block curl and wget above.
        
        return True
    except Exception:
        return False

def run_command(command: str) -> dict:
    """
    Run a terminal command securely inside the project directory.
    Returns:
        {
            "command": "original command",
            "exit_code": int,
            "stdout": "output",
            "stderr": "error"
        }
    """
    if not is_command_safe(command):
        return {
            "command": command,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"PermissionError: Command '{command}' is not allowed or failed security checks."
        }
        
    parts = shlex.split(command)
    
    try:
        result = subprocess.run(
            parts,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=20,
            text=True
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "exit_code": 124,  # Standard timeout exit code
            "stdout": e.stdout.decode() if e.stdout else "",
            "stderr": f"TimeoutError: Command '{command}' exceeded 20 second limit."
        }
    except Exception as e:
        return {
            "command": command,
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}"
        }
