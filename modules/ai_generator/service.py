import json
import logging
import re

from database import db
from database.models.page import Page
from database.models.project_file import ProjectFile
from database.models.section import Section
from database.models.website import Website
from generate import AIEngineRouter, clean_json_output
from modules.ai_generator.design_engine import DesignEngine
from modules.ai_generator.design_memory import design_memory
from modules.ai_generator.layout_generator import LayoutGenerator
from modules.auth.token_service import TokenService

logger = logging.getLogger(__name__)

# Shared instances (avoid re-initializing every request)
_router = None
_graph_pipeline = None
_graph_pipeline_error = None


def _get_router():
    global _router
    if _router is None:
        _router = AIEngineRouter()
    return _router


def _get_langgraph_pipeline():
    global _graph_pipeline, _graph_pipeline_error
    if _graph_pipeline is not None:
        return _graph_pipeline
    if _graph_pipeline_error:
        return None

    try:
        from modules.ai_generator.agent_graph import GroqWebsiteGenerationGraph

        _graph_pipeline = GroqWebsiteGenerationGraph()
    except Exception as exc:
        _graph_pipeline_error = str(exc)
        logger.error("Groq LangGraph pipeline unavailable: %s", exc)
        return None

    return _graph_pipeline


class AIGeneratorService:

    MAX_RETRIES = 3

    @staticmethod
    def _determine_layout_page_count(prompt: str) -> int:
        prompt_lower = (prompt or "").lower()

        explicit_pages = re.search(r"\b([1-9])\s*[-\s]?page(?:s)?\b", prompt_lower)
        if explicit_pages:
            return max(1, min(6, int(explicit_pages.group(1))))

        if any(term in prompt_lower for term in ["single page", "one page", "landing page"]):
            return 1

        if any(
            term in prompt_lower
            for term in [
                "portfolio",
                "agency",
                "business",
                "company",
                "startup",
                "saas",
                "blog",
                "ecommerce",
                "store",
                "restaurant",
                "course",
            ]
        ):
            return 3

        return 2

    @staticmethod
    def _generate_with_engine(prompt, framework, engine, design_spec, layout_spec, temperature):
        """
        Returns (data_dict, raw_output_string, error_message).
        Groq path uses LangGraph+Pydantic pipeline.
        Non-groq path uses legacy router+JSON cleaning.
        """
        if engine == "groq":
            graph_pipeline = _get_langgraph_pipeline()
            if graph_pipeline is None:
                reason = _graph_pipeline_error or "Missing dependencies or configuration."
                return None, None, f"Groq generation is unavailable: {reason}"

            data, graph_error, graph_debug = graph_pipeline.generate(
                raw_prompt=prompt,
                framework=framework,
                design_spec=design_spec,
                layout_spec=layout_spec,
            )
            if graph_error:
                return None, None, graph_error

            logger.info(
                "Groq graph generation complete. review_retries=%s",
                graph_debug.get("retry_count", 0),
            )
            raw_output = json.dumps(data, ensure_ascii=False, sort_keys=True)
            return data, raw_output, None

        router = _get_router()
        raw_output = router.generate(
            engine=engine,
            prompt=prompt,
            framework=framework,
            user_preferences=None,
            temperature=temperature,
            design_spec=design_spec,
            layout_spec=layout_spec,
        )
        cleaned = clean_json_output(raw_output)
        data = json.loads(cleaned.strip())
        return data, raw_output, None

    @staticmethod
    def generate_website(prompt, user_id, framework="tailwind", engine="groq", existing_website_id=None):
        # 1. Token validation
        can_afford, cost, balance = TokenService.can_afford(user_id, "generate_website")
        if not can_afford:
            return None, f"Insufficient tokens. Need {cost}, have {balance}."

        try:
            # 2. Generate design and layout specs (true randomness each time)
            design_spec = DesignEngine.process(prompt)
            page_count = AIGeneratorService._determine_layout_page_count(prompt)
            layout_spec = LayoutGenerator().generate_layout(page_count)

            logger.info("Design: %s | Layout: %s", design_spec.theme_name, layout_spec.layout_variation)
            print(f"[Service] Design: {design_spec.theme_name} ({design_spec.mood})")
            print(f"[Service] Layout: {layout_spec.layout_variation}")
            print(f"[Service] Engine: {engine}")

            # 3. Generation with anti-duplication retry
            data = None
            raw_output = None
            temperature = 1.0

            for attempt in range(AIGeneratorService.MAX_RETRIES):
                data, raw_output, generation_error = AIGeneratorService._generate_with_engine(
                    prompt=prompt,
                    framework=framework,
                    engine=engine,
                    design_spec=design_spec,
                    layout_spec=layout_spec,
                    temperature=temperature,
                )
                if generation_error:
                    return None, generation_error

                if raw_output is None:
                    return None, "Generation failed to produce output."

                # Check for duplicates
                if design_memory.is_duplicate(user_id, raw_output):
                    logger.warning("Duplicate detected! Attempt %s/%s", attempt + 1, AIGeneratorService.MAX_RETRIES)
                    print("[Service] DUPLICATE DETECTED - regenerating with higher temperature...")
                    temperature = min(temperature + 0.2, 1.5)

                    # Get fresh design/layout specs
                    design_spec = DesignEngine.process(prompt)
                    layout_spec = LayoutGenerator().generate_layout(page_count)
                    continue

                break

            if data is None or raw_output is None:
                return None, "Generation failed to produce website data."

            # Store in design memory
            output_hash = design_memory.store(user_id, raw_output)

            # 4. Handle existing website (regenerate_all) vs new website
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
                    output_hash=output_hash,
                )
                db.session.add(new_website)
                db.session.commit()

            # 5. Create pages and sections
            pages_data = data.get("pages", [])
            for page_data in pages_data:
                page = Page(
                    name=page_data.get("name", "Home"),
                    slug=page_data.get("slug", "home"),
                    website_id=new_website.id,
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
                        name=sec_data.get("name", f"Section {idx + 1}"),
                        content=content,
                        order=sec_data.get("order", idx),
                        page_id=page.id,
                    )
                    db.session.add(section)

            # 6. Create project files
            files_data = data.get("files", [])
            for file_data in files_data:
                pf = ProjectFile(
                    path=file_data.get("path", "unnamed.txt"),
                    content=file_data.get("content", ""),
                    website_id=new_website.id,
                )
                db.session.add(pf)

            # 7. Deduct tokens and commit
            TokenService.deduct(user_id, "generate_website")
            db.session.commit()

            return new_website, None

        except json.JSONDecodeError as exc:
            logger.error("JSON parse error: %s", exc)
            return None, "AI generated invalid JSON. Please try again."

        except Exception as exc:
            logger.error("Generation failed: %s", exc)
            return None, f"An error occurred during generation: {str(exc)}"

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
                # Allow regeneration even without specific token type; use generate_website cost
                can_afford, cost, balance = TokenService.can_afford(user_id, "generate_website")
                if not can_afford:
                    return None, f"Insufficient tokens. Need {cost}, have {balance}."

            from core.groq_llm import GroqLLM

            llm = GroqLLM(model="llama-3.3-70b-versatile")

            messages = [
                {
                    "role": "system",
                    "content": f"""You are NEURAFORGE Section Designer - an elite UI expert.
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
                    "content": f"Regenerate this section: {prompt}",
                },
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

        except Exception as exc:
            logger.error("Section regeneration failed: %s", exc)
            return None, f"Failed to regenerate section: {str(exc)}"
