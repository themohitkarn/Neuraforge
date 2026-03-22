import json
import time
import logging
from database import db
from database.models.website import Website
from database.models.page import Page
from database.models.section import Section
from database.models.project_file import ProjectFile
from modules.auth.token_service import TokenService
from modules.ai_generator.layout_generator import LayoutGenerator
from modules.ai_generator.design_engine import DesignEngine
from modules.ai_generator.design_memory import design_memory
from generate import AIEngineRouter, clean_json_output

logger = logging.getLogger(__name__)

# Shared router instance (avoid re-initializing every request)
_router = None

def _get_router():
    global _router
    if _router is None:
        _router = AIEngineRouter()
    return _router


class AIGeneratorService:
    
    MAX_RETRIES = 3
    
    @staticmethod
    def generate_website(prompt, user_id, framework="tailwind", engine="groq", existing_website_id=None):
        # 1. Token validation
        can_afford, cost, balance = TokenService.can_afford(user_id, "generate_website")
        if not can_afford:
            return None, f"Insufficient tokens. Need {cost}, have {balance}."
            
        try:
            # 2. Generate design and layout specs (true randomness each time)
            design_spec = DesignEngine.process(prompt)
            layout_spec = LayoutGenerator().generate_layout(1)
            
            logger.info(f"Design: {design_spec.theme_name} | Layout: {layout_spec.layout_variation}")
            print(f"[Service] Design: {design_spec.theme_name} ({design_spec.mood})")
            print(f"[Service] Layout: {layout_spec.layout_variation}")
            print(f"[Service] Engine: {engine}")
            
            # 3. Generation with anti-duplication retry
            router = _get_router()
            raw_output = None
            temperature = 1.0
            
            for attempt in range(AIGeneratorService.MAX_RETRIES):
                raw_output = router.generate(
                    engine=engine,
                    prompt=prompt,
                    framework=framework,
                    user_preferences=None,
                    temperature=temperature,
                    design_spec=design_spec,
                    layout_spec=layout_spec
                )
                
                # Check for duplicates
                if design_memory.is_duplicate(user_id, raw_output):
                    logger.warning(f"Duplicate detected! Attempt {attempt + 1}/{AIGeneratorService.MAX_RETRIES}")
                    print(f"[Service] DUPLICATE DETECTED — regenerating with higher temperature...")
                    temperature = min(temperature + 0.2, 1.5)
                    
                    # Get fresh design/layout specs
                    design_spec = DesignEngine.process(prompt)
                    layout_spec = LayoutGenerator().generate_layout(1)
                    continue
                else:
                    break
            
            # Store in design memory
            output_hash = design_memory.store(user_id, raw_output)
            
            # 4. Clean and parse JSON
            cleaned = clean_json_output(raw_output)
            data = json.loads(cleaned.strip())
            
            # 5. Handle existing website (regenerate_all) vs new website
            if existing_website_id:
                target_website = Website.query.get(existing_website_id)
                if not target_website:
                    return None, "Website not found."
                
                # Delete old pages and sections
                for page in target_website.pages:
                    for section in page.sections:
                        db.session.delete(section)
                    db.session.delete(page)
                
                # Delete old project files
                for pf in target_website.project_files:
                    db.session.delete(pf)
                
                target_website.name = data.get("website_name", target_website.name)
                target_website.engine_used = engine
                target_website.layout_used = layout_spec.layout_variation
                target_website.output_hash = output_hash
                db.session.commit()
                new_website = target_website
            else:
                website_name = data.get("website_name", "Untitled Website")
                new_website = Website(
                    name=website_name,
                    user_id=user_id,
                    framework=framework,
                    engine_used=engine,
                    layout_used=layout_spec.layout_variation,
                    output_hash=output_hash
                )
                db.session.add(new_website)
                db.session.commit()
            
            # 6. Create pages and sections
            pages_data = data.get("pages", [])
            for page_data in pages_data:
                page = Page(
                    name=page_data.get("name", "Home"),
                    slug=page_data.get("slug", "home"),
                    website_id=new_website.id
                )
                db.session.add(page)
                db.session.commit()
                
                sections_data = page_data.get("sections", [])
                for idx, sec_data in enumerate(sections_data):
                    content = sec_data.get("content", "")
                    if isinstance(content, list):
                        content = "".join([str(c) for c in content])
                    elif isinstance(content, dict):
                        content = json.dumps(content)
                        
                    section = Section(
                        name=sec_data.get("name", f"Section {idx+1}"),
                        content=content,
                        order=sec_data.get("order", idx),
                        page_id=page.id
                    )
                    db.session.add(section)
                    
            # 7. Create project files
            files_data = data.get("files", [])
            for file_data in files_data:
                pf = ProjectFile(
                    path=file_data.get("path", "unnamed.txt"),
                    content=file_data.get("content", ""),
                    website_id=new_website.id
                )
                db.session.add(pf)
                
            # 8. Deduct tokens and commit
            TokenService.deduct(user_id, "generate_website")
            db.session.commit()
            
            return new_website, None
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return None, f"AI generated invalid JSON. Please try again."
            
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return None, f"An error occurred during generation: {str(e)}"

    @staticmethod
    def regenerate_section(section_id, prompt, user_id):
        """
        Regenerate a single section's content using AI.
        Returns (new_content, error).
        """
        try:
            section = Section.query.get(section_id)
            if not section:
                return None, "Section not found."
            
            # Token check
            can_afford, cost, balance = TokenService.can_afford(user_id, "regenerate_section")
            if not can_afford:
                # Allow regeneration even without specific token type — use generate_website cost
                can_afford, cost, balance = TokenService.can_afford(user_id, "generate_website")
                if not can_afford:
                    return None, f"Insufficient tokens. Need {cost}, have {balance}."
            
            from core.groq_llm import GroqLLM
            llm = GroqLLM(model="llama-3.3-70b-versatile")
            
            messages = [
                {
                    "role": "system",
                    "content": f"""You are NEURAFORGE Section Designer — an elite UI expert.
Regenerate the HTML for a website section based on the user's instruction.

RULES:
1. Output ONLY the raw HTML code for the section. No JSON wrapper, no markdown.
2. Use Tailwind CSS for all styling.
3. Make it PREMIUM: glassmorphism, gradients, hover effects, transitions.
4. Responsive design (mobile-first).
5. Keep the same general purpose but dramatically improve the design.

CURRENT SECTION NAME: {section.name}
CURRENT CONTENT (for reference):
{section.content[:3000]}"""
                },
                {
                    "role": "user",
                    "content": f"Regenerate this section: {prompt}"
                }
            ]
            
            new_content = llm.invoke(messages, temperature=0.9, max_tokens=4096)
            
            # Clean markdown fences if present
            if new_content.startswith("```html"):
                new_content = new_content[7:]
            if new_content.startswith("```"):
                new_content = new_content[3:]
            if new_content.endswith("```"):
                new_content = new_content[:-3]
            new_content = new_content.strip()
            
            # Update the section
            section.content = new_content
            db.session.commit()
            
            # Deduct tokens
            try:
                TokenService.deduct(user_id, "regenerate_section")
            except Exception:
                try:
                    TokenService.deduct(user_id, "generate_website")
                except Exception:
                    pass
            
            return new_content, None
            
        except Exception as e:
            logger.error(f"Section regeneration failed: {e}")
            return None, f"Failed to regenerate section: {str(e)}"