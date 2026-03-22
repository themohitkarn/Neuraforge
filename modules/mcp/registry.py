# modules/mcp/registry.py

from modules.mcp.tools import (
    get_website_pages,
    update_section_text,
    add_section_tool,
    delete_section_tool,
    add_page_tool,
)


class MCPToolRegistry:
    """Registry for all MCP tools available to agents."""

    @staticmethod
    def get_tools(user_id: int, website_id: int):
        """Return tool list bound to user & website context."""
        return [
            get_website_pages,
            update_section_text,
            add_section_tool,
            delete_section_tool,
            add_page_tool,
        ]
