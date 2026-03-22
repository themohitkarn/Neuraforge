# modules/chatbot/website_bot.py
# Website chatbot — gives code suggestions only, does NOT modify the IDE

from core.groq_llm import GroqLLM


class WebsiteChatbot:
    """AI chatbot that helps users with website code — gives code snippets and advice only."""

    def __init__(self, website_context: dict = None):
        self.llm = GroqLLM(model="llama-3.1-8b-instant")
        self.context = website_context or {}

    def get_response(self, user_message: str) -> str:
        context_info = ""
        if self.context:
            context_info = f"\nThe user is working on a website called '{self.context.get('name', 'Unknown')}' with {self.context.get('page_count', 0)} pages."

        messages = [
            {
                "role": "system",
                "content": f"""You are NeuraForge AI Assistant — an elite coding expert for web development.

CRITICAL RULES:
1. You MUST output ONLY raw, valid JSON. No markdown backticks around the JSON.
2. You can chat with the user AND perform actions on their website sections.
3. Supported actions: 'none' (just chat), 'edit' (replace current section code), 'redesign_all' (redesign all pages of the entire website).
4. For styling, use advanced Tailwind CSS with modern, gorgeous design trends (glassmorphism, gradients).
{context_info}

JSON SCHEMA:
{{
  "message": "String (Your conversational reply to the user, explaining what you are doing)",
  "action": {{
    "type": "String (Must be exactly one of: 'none', 'edit')",
    "code": "String (If type is 'edit', the COMPLETE HTML code for the updated section. Otherwise, empty string.)"
  }}
}}

Example 'edit' response:
{{
  "message": "I've styled your pricing section with a modern glassmorphism effect and gradients.",
  "action": {{
    "type": "edit",
    "code": "<section class=\\"py-24 bg-gray-900\\">...</section>"
  }}
}}

Example 'redesign_all' response:
{{
  "message": "I will redesign your entire website based on your request. This will take a moment...",
  "action": {{
    "type": "redesign_all",
    "code": "User's redesign prompt goes here (e.g. A dark cyberpunk theme with neon green accents, 3 pages, heavy glassmorphism)"
  }}
}}

Example 'none' response:
{{
  "message": "I can help you build that! Select a section you want me to update, or ask me a coding question.",
  "action": {{
    "type": "none",
    "code": ""
  }}
}}"""
            },
            {"role": "user", "content": user_message}
        ]

        try:
            return self.llm.invoke_json(messages, temperature=0.7, max_tokens=4096)
        except Exception as e:
            return '{"message": "Sorry, I had trouble generating that code.", "action": {"type": "none", "code": ""}}'
