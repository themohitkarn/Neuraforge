# core/gemini_llm.py
# Google Gemini LLM client — matches GroqLLM interface

import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class GeminiLLM:
    """
    General-purpose Gemini LLM client.
    Provides the same interface as GroqLLM for drop-in usage.
    """

    def __init__(self, model: str = "models/gemini-2.5-flash"):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the .env file.")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    def invoke(self, messages: list, temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """
        Send a chat request to Gemini.
        Converts OpenAI-style messages to Gemini format.
        """
        try:
            # Combine messages into a single prompt (Gemini doesn't use system/user roles the same way)
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{content}")
                elif role == "assistant":
                    prompt_parts.append(f"PREVIOUS RESPONSE:\n{content}")
                else:
                    prompt_parts.append(f"USER:\n{content}")

            full_prompt = "\n\n".join(prompt_parts)

            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                "top_p": 0.95,
            }

            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

    def invoke_json(self, messages: list, temperature: float = 0.7, max_tokens: int = 8192) -> str:
        """
        Send a chat request with JSON output expectation.
        Adds explicit JSON-only instructions.
        """
        try:
            # Inject JSON enforcement into system prompt
            enhanced_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    enhanced_messages.append({
                        "role": "system",
                        "content": msg["content"] + "\n\nCRITICAL: Output ONLY raw valid JSON. No markdown, no code fences, no explanation."
                    })
                else:
                    enhanced_messages.append(msg)
            
            result = self.invoke(enhanced_messages, temperature=temperature, max_tokens=max_tokens)
            
            # Clean potential markdown fences
            cleaned = result.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            
            return cleaned.strip()

        except Exception as e:
            logger.error(f"Gemini API JSON error: {e}")
            raise
