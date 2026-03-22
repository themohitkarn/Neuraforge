# modules/mcp/tools.py
# MCP Tools — callable by the LangChain agent to read/modify websites

from modules.mcp.permissions import MCPPermission
from modules.website.service import WebsiteService
from database import db
from database.models.page import Page
from database.models.section import Section


def get_website_pages(user_id: int, website_id: int, **kwargs) -> dict:
    """Fetch all pages and sections of a website."""
    if not MCPPermission.can_read_website(user_id, website_id):
        return {"error": "Permission denied"}
    return WebsiteService.get_pages(website_id)


def update_section_text(user_id: int, website_id: int, section_id: int, new_text: str, **kwargs) -> dict:
    """Update the HTML content of a specific section."""
    if not MCPPermission.can_modify_website(user_id, website_id):
        return {"error": "Permission denied"}

    section = Section.query.get(section_id)
    if not section:
        return {"error": "Section not found"}

    section.content = new_text
    db.session.commit()

    return {"status": "success", "section_id": section_id, "updated": True}


def add_section_tool(user_id: int, website_id: int, page_id: int, name: str = "New Section",
                     content: str = "<div class='p-8'><h2>New Section</h2></div>", **kwargs) -> dict:
    """Add a new section to a page."""
    if not MCPPermission.can_modify_website(user_id, website_id):
        return {"error": "Permission denied"}

    page = Page.query.get(page_id)
    if not page:
        return {"error": "Page not found"}

    # Get max order
    max_order = db.session.query(db.func.max(Section.order)).filter_by(page_id=page_id).scalar() or 0

    section = Section(
        name=name,
        content=content,
        page_id=page_id,
        order=max_order + 1
    )
    db.session.add(section)
    db.session.commit()

    return {"status": "success", "section_id": section.id, "name": name}


def delete_section_tool(user_id: int, website_id: int, section_id: int, **kwargs) -> dict:
    """Delete a section from a page."""
    if not MCPPermission.can_modify_website(user_id, website_id):
        return {"error": "Permission denied"}

    section = Section.query.get(section_id)
    if not section:
        return {"error": "Section not found"}

    db.session.delete(section)
    db.session.commit()
    return {"status": "success", "deleted_section_id": section_id}


def add_page_tool(user_id: int, website_id: int, name: str = "New Page",
                  slug: str = "new-page", **kwargs) -> dict:
    """Add a new page to the website."""
    if not MCPPermission.can_modify_website(user_id, website_id):
        return {"error": "Permission denied"}

    max_order = db.session.query(db.func.max(Page.order)).filter_by(website_id=website_id).scalar() or 0

    page = Page(
        name=name,
        slug=slug,
        website_id=website_id,
        order=max_order + 1
    )
    db.session.add(page)
    db.session.flush()

    # Add default section
    section = Section(
        name="Content",
        content=f"<div class='p-8'><h2>{name}</h2><p>Edit this section in the IDE.</p></div>",
        page_id=page.id,
        order=0
    )
    db.session.add(section)
    db.session.commit()

    return {"status": "success", "page_id": page.id, "name": name, "slug": slug}
