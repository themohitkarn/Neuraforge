# modules/mcp/permissions.py

from database.models.website import Website

class MCPPermission:
    """
    Central permission checks for MCP tools.
    """

    @staticmethod
    def can_read_website(user_id: int, website_id: int) -> bool:
        website = Website.query.get(website_id)
        return website is not None and website.user_id == user_id

    @staticmethod
    def can_modify_website(user_id: int, website_id: int) -> bool:
        website = Website.query.get(website_id)
        return website is not None and website.user_id == user_id
