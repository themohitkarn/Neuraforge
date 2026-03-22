# tests/test_agent.py

import os
import pytest

from modules.chatbot.agent_bot import NeuraAgent


@pytest.fixture
def agent():
    """
    Create a NeuraAgent instance for testing.
    """
    # Dummy IDs for test
    return NeuraAgent(user_id=1, website_id=1)


def test_agent_reads_website(agent):
    """
    Agent should call get_website_pages tool
    when asked about website content.
    """

    response = agent.run("What pages does this website have?")

    assert response is not None
    assert isinstance(response, str)
    assert "Home" in response or "page" in response


def test_agent_updates_section(agent):
    """
    Agent should call update_section_text tool
    when explicitly asked to modify content.
    """

    response = agent.run(
        "Change the hero section text to 'AI Powered Platform'"
    )

    assert response is not None
    assert isinstance(response, str)
