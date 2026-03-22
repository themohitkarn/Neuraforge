# core/llm.py

import requests

class OllamaLLM:
    def __init__(self, model: str = "mistral"):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def invoke(self, messages):
        """
        messages = [
          {"role": "system", "content": "..."},
          {"role": "user", "content": "..."}
        ]
        """

        # ✅ Convert messages → single prompt string
        prompt_text = ""
        for m in messages:
            role = m.get("role", "user").upper()
            content = m.get("content", "")
            prompt_text += f"{role}:\n{content}\n\n"

        payload = {
            "model": self.model,
            "prompt": prompt_text.strip(),
            "stream": False
        }

        response = requests.post(self.url, json=payload, timeout=120)

        # Debug help (future ke liye)
        if response.status_code != 200:
            raise Exception(
                f"Ollama error {response.status_code}: {response.text}"
            )

        return response.json()["response"]
