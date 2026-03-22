import json
import difflib
import os
import shutil
import logging
from typing import Dict, Any, List
from core.groq_llm import GroqLLM
from core.file_manager import read_file, write_file, append_file
from core.terminal_runner import run_command

logger = logging.getLogger(__name__)

ROLLBACK_DIR = os.path.join(os.path.dirname(__file__), "..", "tmp", "rollback")


class CoderAgent:
    def __init__(self):
        self.llm = GroqLLM(model="llama-3.3-70b-versatile")
        self._rollback_store = {}  # path -> original content

    def execute_plan(self, plan: Dict[str, Any], instruction: str) -> Dict[str, Any]:
        """
        Executes the given plan with diff tracking and rollback support.
        """
        logs = []
        files_modified = []
        actions_executed = []
        failed_commands = []
        diffs = []
        
        steps = plan.get("steps", [])
        
        for idx, step in enumerate(steps):
            action = step.get("action")
            description = step.get("description", "")
            logs.append(f"Step {idx+1}/{len(steps)}: {action} — {description or step}")
            actions_executed.append(step)
            
            try:
                if action == "create_file":
                    path = step.get("path")
                    content = self._generate_code_for_file(instruction, path, "create", "")
                    write_file(path, content)
                    files_modified.append(path)
                    diffs.append({"path": path, "type": "created", "lines_added": len(content.splitlines())})
                    logs.append(f"  ✓ Created {path} ({len(content)} bytes)")
                    
                elif action == "edit_file":
                    path = step.get("path")
                    try:
                        current_content = read_file(path)
                        self._save_rollback(path, current_content)
                        
                        new_content = self._generate_code_for_file(instruction, path, "edit", current_content)
                        write_file(path, new_content)
                        files_modified.append(path)
                        
                        # Generate diff
                        diff = self._generate_diff(current_content, new_content, path)
                        diffs.append({"path": path, "type": "edited", "diff": diff})
                        logs.append(f"  ✓ Edited {path}")
                    except FileNotFoundError:
                        logs.append(f"  ✗ Error: {path} does not exist")
                        
                elif action == "append_file":
                    path = step.get("path")
                    try:
                        current_content = read_file(path)
                        self._save_rollback(path, current_content)
                        
                        new_content = self._generate_code_for_file(instruction, path, "append", current_content)
                        append_file(path, new_content)
                        files_modified.append(path)
                        diffs.append({"path": path, "type": "appended", "lines_added": len(new_content.splitlines())})
                        logs.append(f"  ✓ Appended to {path}")
                    except FileNotFoundError:
                        logs.append(f"  ✗ Error: {path} does not exist")
                        
                elif action == "read_file":
                    path = step.get("path")
                    try:
                        content = read_file(path)
                        logs.append(f"  ✓ Read {path} ({len(content)} bytes)")
                    except FileNotFoundError:
                        logs.append(f"  ✗ Error: {path} does not exist")
                        
                elif action == "delete_file":
                    path = step.get("path")
                    try:
                        if os.path.exists(path):
                            current_content = read_file(path)
                            self._save_rollback(path, current_content)
                            os.remove(path)
                            files_modified.append(path)
                            diffs.append({"path": path, "type": "deleted"})
                            logs.append(f"  ✓ Deleted {path}")
                        else:
                            logs.append(f"  ✗ Error: {path} does not exist")
                    except Exception as e:
                        logs.append(f"  ✗ Error deleting {path}: {e}")
                        
                elif action == "run_command":
                    cmd = step.get("command")
                    result = run_command(cmd)
                    exit_code = result['exit_code']
                    
                    if exit_code == 0:
                        logs.append(f"  ✓ Command succeeded: {cmd}")
                        if result['stdout']:
                            logs.append(f"    stdout: {result['stdout'][:500]}")
                    else:
                        logs.append(f"  ✗ Command failed (exit {exit_code}): {cmd}")
                        logs.append(f"    stderr: {result['stderr'][:500]}")
                        failed_commands.append({
                            "command": cmd,
                            "stderr": result['stderr']
                        })
                        
            except Exception as e:
                logs.append(f"  ✗ Exception: {str(e)}")

        return {
            "logs": logs,
            "actions_executed": actions_executed,
            "files_modified": files_modified,
            "failed_commands": failed_commands,
            "diffs": diffs
        }
    
    def rollback(self, paths: List[str] = None) -> List[str]:
        """Rollback modified files to their original state."""
        rolled_back = []
        targets = paths or list(self._rollback_store.keys())
        
        for path in targets:
            if path in self._rollback_store:
                try:
                    write_file(path, self._rollback_store[path])
                    rolled_back.append(path)
                    logger.info(f"Rolled back: {path}")
                except Exception as e:
                    logger.error(f"Rollback failed for {path}: {e}")
        
        return rolled_back
    
    def _save_rollback(self, path: str, content: str):
        """Save original content for potential rollback."""
        if path not in self._rollback_store:
            self._rollback_store[path] = content
    
    def _generate_diff(self, old_content: str, new_content: str, path: str) -> str:
        """Generate a unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm=""
        )
        return "".join(diff)

    def _generate_code_for_file(self, instruction: str, path: str, mode: str, current_content: str) -> str:
        """Prompts LLM to generate code for the requested file."""
        system_prompt = f"""You are the NEURAFORGE Coder Agent.
Your job is to generate purely the code for the requested file modifications.

FILE: {path}
MODE: {mode}

RULES:
1. ONLY output raw code. No explanations, no markdown code blocks.
2. If mode is "edit", output the FULL REPLACEMENT for the file.
3. If mode is "append", output ONLY the new code to append.
4. If mode is "create", output the entire initial content.

CURRENT CONTENT (if applicable):
{current_content[:4000]}
"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction}
        ]
        try:
            response = self.llm.invoke(messages, temperature=0.1, max_tokens=4000)
            # Strip markdown fences if present
            if response.startswith("```"):
                lines = response.splitlines()
                if len(lines) > 2 and lines[-1].strip() == "```":
                    response = "\n".join(lines[1:-1])
            return response
        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return ""
