# core/groq_llm.py
# Groq LLM client — ultra-fast inference via Groq Cloud

import os
import logging
from groq import Groq # type: ignore
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GroqLLM:
    """
    General-purpose Groq LLM client using the official Groq SDK.
    Used by chatbots and any component needing fast LLM inference.
    """

    def __init__(self, model: str = "llama-3.1-8b-versatile"):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set in the .env file.")

        self.client = Groq(api_key=api_key)
        self.model = model

    def invoke(self, messages: list, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        Send a chat completion request to Groq.
        
        Args:
            messages: List of dicts with 'role' and 'content' keys. 
                      Roles: 'system', 'user', 'assistant'
            temperature: Controls randomness (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum response length
            
        Returns:
            The assistant's reply as a string.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.8,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    def invoke_json(self, messages: list, temperature: float = 0.7, max_tokens: int = 8192) -> str:
        """
        Send a chat completion request with JSON response format enforced.
        Used for structured generation (website layouts, etc.)
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.8,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API JSON error: {e}")
            raise
