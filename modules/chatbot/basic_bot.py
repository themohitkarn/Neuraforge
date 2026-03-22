# modules/chatbot/basic_bot.py

from core.groq_llm import GroqLLM


class BasicChatbot:
    def __init__(self, user_id: int, website_id: int):
        self.user_id = user_id
        self.website_id = website_id
        self.llm = GroqLLM()

    def run(self, message: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are an AI website assistant for NeuraForge.\n"
                    f"User ID: {self.user_id}\nWebsite ID: {self.website_id}\n"
                    f"Reply clearly and helpfully."
                )
            },
            {
                "role": "user",
                "content": message
            }
        ]
        return self.llm.invoke(messages)
