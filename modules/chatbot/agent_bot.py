# modules/chatbot/agent_bot.py
# Code advisor agent — gives code suggestions only (no direct edits)

from core.groq_llm import GroqLLM


class NeuraAgent:
    """AI Agent that acts as a code advisor — gives code snippets, never modifies directly."""

    def __init__(self, user_id: int, website_id: int):
        self.user_id = user_id
        self.website_id = website_id
        self.llm = GroqLLM(model="llama-3.1-8b-instant")

    def run(self, instruction: str) -> str:
        messages = [
            {
                "role": "system",
                "content": """You are NeuraForge AI Code Advisor. You help users build better websites.

IMPORTANT RULES:
1. You ONLY give code suggestions — you do NOT modify the website
2. Provide code in proper markdown blocks (```html, ```css, ```js, ```python)
3. Be concise — show working code the user can copy-paste
4. If asked to fix something, show the corrected code
5. You can help with: HTML, CSS, Tailwind, React, Vue, Next.js, Python, Node.js, databases
6. For Tailwind, provide utility classes directly
7. Keep answers short and practical"""
            },
            {"role": "user", "content": instruction}
        ]

        return self.llm.invoke(messages, temperature=0.7, max_tokens=4096)
