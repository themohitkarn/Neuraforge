import json
import logging
from typing import List, Dict, Any
from core.groq_llm import GroqLLM

logger = logging.getLogger(__name__)


class PlannerAgent:
    def __init__(self):
        self.llm = GroqLLM(model="llama-3.3-70b-versatile")
        
    def generate_plan(self, instruction: str, context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates an execution plan based on user instruction and retrieved code context.
        """
        
        context_str = ""
        for i, snippet in enumerate(context):
            context_str += f"\n--- Context snippet {i+1} ---\n"
            context_str += f"File: {snippet.get('file_path')}\n"
            context_str += f"Content:\n{snippet.get('content', '')[:2000]}\n"
            
        system_prompt = f"""You are NEURAFORGE AI Systems Planner.
Read the user instruction and generate a JSON execution plan using specific allowed actions.

ALLOWED ACTIONS:
- "create_file": Create a new file. Needs "path" and "description".
- "edit_file": Modify an existing file. Needs "path" and "description".
- "append_file": Append text to a file. Needs "path" and "description".
- "read_file": Read an existing file. Needs "path".
- "delete_file": Delete a file. Needs "path" and "description".
- "run_command": Run a terminal command safely. Needs "command" and "description".

RULES:
1. Output strictly valid JSON with a "steps" array.
2. No markdown, no explanatory text outside JSON.
3. Only use allowed actions.
4. Keep plans minimal, logical, and safe.
5. Each step MUST have a "description" field explaining what it does and why.
6. Order steps logically (create dependencies first, then dependents).

CONTEXT CODE:
{context_str}

OUTPUT FORMAT:
{{
  "steps": [
    {{"action": "create_file", "path": "utils/math.py", "description": "Create math utility with helper functions"}},
    {{"action": "edit_file", "path": "app.py", "description": "Import and wire up the new math utility"}},
    {{"action": "run_command", "command": "pytest test_units.py", "description": "Run tests to verify changes"}}
  ]
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction}
        ]
        
        try:
            response_json = self.llm.invoke_json(messages, temperature=0.3, max_tokens=2000)
            data = json.loads(response_json)
            if "steps" not in data:
                return {"steps": []}
            return data
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return {"steps": []}
