# core/config.py

class Settings:
    DEBUG = True
    TESTING = False   # 🔥 REAL MODE

    # LLM PROVIDER
    LLM_PROVIDER = "grok"

    # GROK
    import os
    GROK_API_KEY = os.getenv("GROK_API_KEY", "")
    GROK_BASE_URL = "https://api.x.ai/v1"
    GROK_MODEL = "grok-1"

    # FUTURE OPENAI
    OPENAI_API_KEY = ""
    LLM_MODEL = "gpt-4o-mini"


settings = Settings()
