# modules/website/service.py
from database import db
from database.models.website import Website
from database.models.section import Section

class WebsiteService:

    @staticmethod
    def get_pages(website_id: int) -> dict:
        website = Website.query.get(website_id)
        if not website:
            return {"error": "Website not found"}
            
        data = {
            "website_id": website.id,
            "name": website.name,
            "pages": []
        }
        for page in website.pages:
            page_data = {
                "id": page.id,
                "name": page.name,
                "sections": []
            }
            for section in page.sections:
                page_data["sections"].append({
                    "id": section.id,
                    "name": section.name,
                    "content": section.content
                })
            data["pages"].append(page_data)
        return data

    @staticmethod
    def update_section_text(website_id: int, section_id: int, text: str):
        section = Section.query.get(section_id)
        if section and section.page.website_id == website_id:
            section.content = text
            db.session.commit()
            return True
        return False
