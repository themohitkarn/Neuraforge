import os
import pytest
from core.file_manager import read_file, write_file, is_path_safe, PROJECT_ROOT
from core.terminal_runner import is_command_safe, run_command

def test_path_traversal_blocked():
    """Attempt path traversal '../' must raise PermissionError."""
    unsafe_path = os.path.join(PROJECT_ROOT, "..", "secret.txt")
    
    assert is_path_safe(unsafe_path) is False
    
    with pytest.raises(PermissionError):
        read_file(unsafe_path)
        
    with pytest.raises(PermissionError):
        write_file(unsafe_path, "hacked")

def test_rm_rf_blocked():
    """Attempt command 'rm -rf' must be blocked."""
    unsafe_cmd = "rm -rf /"
    
    assert is_command_safe(unsafe_cmd) is False
    
    result = run_command(unsafe_cmd)
    assert result["exit_code"] != 0
    assert "PermissionError" in result["stderr"] or "not allowed" in result["stderr"]

def test_safe_file_creation():
    """Verify that a file can be created safely inside the tmp/ directory."""
    tmp_dir = os.path.join(PROJECT_ROOT, "tmp")
    safe_file_path = os.path.join(tmp_dir, "hello_world.txt")
    
    # Ensure creation works without errors
    write_file(safe_file_path, "Hello World")
    
    assert os.path.exists(safe_file_path)
    
    content = read_file(safe_file_path)
    assert content == "Hello World"
    
    # Cleanup
    os.remove(safe_file_path)

def test_env_git_blocked():
    """Attempting to access .env or .git should be blocked."""
    assert is_path_safe(os.path.join(PROJECT_ROOT, ".env")) is False
    assert is_path_safe(os.path.join(PROJECT_ROOT, ".git", "config")) is False
