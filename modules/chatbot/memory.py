# modules/chatbot/memory.py

from langchain.memory import ConversationBufferMemory


def get_agent_memory(user_id: int, website_id: int):
    """
    Returns conversation memory scoped to (user, website).
    In production, replace with Redis / DB-backed memory.
    """

    return ConversationBufferMemory(
        memory_key="chat_history",
        return_messages=True,
        input_key="input",
    )
