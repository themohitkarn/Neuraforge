import json
import logging
from typing import Dict, Any
from core.groq_llm import GroqLLM
from ai_agents.coder_agent import CoderAgent
from core.terminal_runner import run_command

logger = logging.getLogger(__name__)

MAX_DEBUG_RETRIES = 5


class DebuggerAgent:
    def __init__(self):
        self.llm = GroqLLM(model="llama-3.3-70b-versatile")
        self.coder = CoderAgent()

    def debug_loop(self, failed_command: str, stderr: str, original_instruction: str) -> Dict[str, Any]:
        """
        Attempts to fix an error from a failed terminal command.
        Classifies the error and applies targeted fixes.
        """
        logs = []
        logs.append(f"🔧 Starting debug loop for: {failed_command}")
        
        current_stderr = stderr
        
        for attempt in range(1, MAX_DEBUG_RETRIES + 1):
            logs.append(f"\n--- Debug Attempt {attempt}/{MAX_DEBUG_RETRIES} ---")
            
            # 1. Classify the error
            error_type = self._classify_error(current_stderr)
            logs.append(f"Error classification: {error_type}")
            
            # 2. Generate fix plan
            fix_plan = self._generate_fix_plan(failed_command, current_stderr, original_instruction, error_type)
            logs.append(f"Fix plan: {len(fix_plan.get('steps', []))} steps")
            
            # 3. Apply fix
            coder_result = self.coder.execute_plan(fix_plan, f"Fix {error_type} error for: {failed_command}")
            logs.extend(coder_result["logs"])
            
            # 4. Re-run command
            logs.append(f"Re-running: {failed_command}")
            result = run_command(failed_command)
            
            if result['exit_code'] == 0:
                logs.append(f"✅ Command succeeded on attempt {attempt}!")
                if result['stdout']:
                    logs.append(f"Output: {result['stdout'][:300]}")
                break
            else:
                current_stderr = result['stderr']
                logs.append(f"❌ Still failing. stderr: {current_stderr[:300]}")
                
                if attempt == MAX_DEBUG_RETRIES:
                    logs.append(f"⚠️ Max retries reached ({MAX_DEBUG_RETRIES}). Aborting.")
                    
                    # Offer rollback
                    rolled_back = self.coder.rollback()
                    if rolled_back:
                        logs.append(f"🔄 Rolled back: {', '.join(rolled_back)}")
                    
        return {"logs": logs}

    def _classify_error(self, stderr: str) -> str:
        """Classify the error type for smarter fixing."""
        stderr_lower = stderr.lower()
        
        if "syntaxerror" in stderr_lower or "indentationerror" in stderr_lower:
            return "syntax"
        elif "modulenotfounderror" in stderr_lower or "importerror" in stderr_lower:
            return "import"
        elif "typeerror" in stderr_lower or "attributeerror" in stderr_lower:
            return "type"
        elif "filenotfounderror" in stderr_lower or "no such file" in stderr_lower:
            return "file_missing"
        elif "permissionerror" in stderr_lower:
            return "permission"
        elif "connectionerror" in stderr_lower or "timeout" in stderr_lower:
            return "network"
        else:
            return "runtime"

    def _generate_fix_plan(self, command: str, stderr: str, instruction: str, error_type: str) -> Dict[str, Any]:
        """Generate a targeted fix plan based on error classification."""
        
        error_strategies = {
            "syntax": "Focus on fixing syntax/indentation errors. Look for missing colons, brackets, or wrong indentation.",
            "import": "Focus on installing missing packages or fixing import paths.",
            "type": "Focus on type mismatches, wrong method calls, or missing attributes.",
            "file_missing": "Focus on creating missing files or fixing file paths.",
            "permission": "Focus on file permission issues.",
            "network": "Focus on network/connection issues — add retries or fix URLs.",
            "runtime": "Analyze the full stack trace and fix the root cause."
        }
        
        strategy = error_strategies.get(error_type, error_strategies["runtime"])
        
        system_prompt = f"""You are the NEURAFORGE Debugger Agent.
A terminal command failed. Analyze and generate a fix plan.

ERROR TYPE: {error_type}
STRATEGY: {strategy}
COMMAND: {command}
ORIGINAL INSTRUCTION: {instruction}
STDERR:
{stderr[:2000]}

Generate a JSON plan with allowed actions: "edit_file", "create_file", "append_file", "delete_file", "run_command"
Each step should have: "action", required fields, and "description" explaining the fix.
Output strictly valid JSON with a "steps" array."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Provide the JSON fix plan."}
        ]
        
        try:
            response_json = self.llm.invoke_json(messages, temperature=0.3, max_tokens=2000)
            data = json.loads(response_json)
            if "steps" not in data:
                return {"steps": []}
            return data
        except Exception as e:
            logger.error(f"Fix plan generation failed: {e}")
            return {"steps": []}
