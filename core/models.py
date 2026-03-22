# core/models.py

MODEL_REGISTRY = {
    "chat": {
        "model": "mistral",
        "description": "General purpose chat"
    },
    "agent": {
        "model": "llama3",
        "description": "Reasoning + agent tasks"
    },
    "code": {
        "model": "codellama",
        "description": "Website / code generation"
    },
    "lite": {
        "model": "phi3",
        "description": "Low resource fallback"
    }
}
