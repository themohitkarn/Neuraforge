import json
import logging
import os
import re
from types import SimpleNamespace
from typing import Any, Callable, Optional, TypedDict

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERNS = [
    r"\bfull\s+name\b",
    r"\bshort\s+tagline\b",
    r"\bbrief\s+introduction\b",
    r"\bproject\s+\d+\b",
    r"\bskill\s+\d+\b",
    r"\bblog\s+post\s+\d+\b",
    r"\bemail@example\.com\b",
    r"\blinkedin\.com/in/example\b",
    r"\bgithub\.com/example\b",
    r"\blorem\s+ipsum\b",
    r"\byour\s+name\s+here\b",
    r"\bplaceholder\s+(?:text|content|description)\b",
    r"\bfeatured\s+project\b",
    r"\bskill\s+description\b",
    r"\bexperience\s+details\b",
    r"\bcore\s+capability\b",
    r"\bfeatured\s+insight\b",
    r"\bcase\s+study\s+\d+\b",
]


class PromptReviewModel(BaseModel):
    normalized_intent: str = Field(min_length=5)
    target_audience: str = Field(min_length=3)
    design_direction: str = Field(min_length=5)
    required_pages: int = Field(default=1, ge=1)
    required_sections: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    rewritten_prompt: str = Field(min_length=20)


class SectionSpecModel(BaseModel):
    name: str = Field(min_length=1)
    content: str = Field(min_length=20)
    order: int = Field(default=0, ge=0)

    @field_validator("content")
    @classmethod
    def validate_html_content(cls, value: str) -> str:
        content = value.strip()
        if len(content) < 20:
            raise ValueError("Section content is too short.")
        if "<" not in content or ">" not in content:
            raise ValueError("Section content must look like HTML.")
        return content


class PageSpecModel(BaseModel):
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    sections: list[SectionSpecModel] = Field(min_length=1)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        slug = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("Slug must be kebab-case (lowercase letters, digits, and hyphens).")
        return slug


class FileSpecModel(BaseModel):
    path: str = Field(min_length=1)
    content: str = ""


class WebsiteSpecModel(BaseModel):
    website_name: str = Field(min_length=1)
    framework: str = Field(min_length=1)
    pages: list[PageSpecModel] = Field(min_length=1)
    files: list[FileSpecModel] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_slugs(self) -> "WebsiteSpecModel":
        slugs = [page.slug for page in self.pages]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Page slugs must be unique.")
        return self


class GenerationState(TypedDict, total=False):
    raw_prompt: str
    framework: str
    design_spec_text: str
    layout_spec_text: str
    required_pages: int
    review_data: dict[str, Any]
    reviewed_prompt: str
    candidate_output: str
    validation_errors: list[str]
    retry_count: int
    final_output: dict[str, Any]
    error: str


def _clean_json_output(raw_text: str) -> str:
    if not raw_text or not raw_text.strip():
        return "{}"

    cleaned = raw_text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]

    cleaned = cleaned.strip()
    start_idx = cleaned.find("{")
    if start_idx == -1:
        return "{}"
    cleaned = cleaned[start_idx:]
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

    open_curly = cleaned.count("{")
    close_curly = cleaned.count("}")
    open_square = cleaned.count("[")
    close_square = cleaned.count("]")
    if open_square > close_square:
        cleaned += "]" * (open_square - close_square)
    if open_curly > close_curly:
        cleaned += "}" * (open_curly - close_curly)
    return cleaned


def _extract_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            else:
                text = getattr(item, "text", None)
                if text:
                    parts.append(str(text))
                else:
                    parts.append(str(item))
        return "\n".join(parts).strip()
    return str(content)


class GroqWebsiteGenerationGraph:
    MAX_CORRECTION_RETRIES = 2

    def __init__(
        self,
        review_model: Optional[str] = None,
        builder_model: Optional[str] = None,
        llm_factory: Optional[Callable[[str], Any]] = None,
        max_correction_retries: int = MAX_CORRECTION_RETRIES,
    ):
        self.review_model = review_model or os.getenv("GROQ_PROMPT_REVIEW_MODEL", "llama-3.1-8b-instant")
        self.builder_model = builder_model or os.getenv("GROQ_WEBSITE_BUILDER_MODEL", "llama-3.3-70b-versatile")
        self.max_correction_retries = max_correction_retries
        self._llm_factory = llm_factory or self._default_llm_factory
        self._graph = self._build_graph()

    def _default_llm_factory(self, model_name: str) -> Any:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")

        try:
            from langchain_groq import ChatGroq
        except ModuleNotFoundError as exc:
            raise RuntimeError("langchain-groq is not installed.") from exc

        return ChatGroq(
            model=model_name,
            temperature=0.4,
            groq_api_key=api_key,
        )

    def _build_graph(self):
        try:
            from langgraph.graph import END, START, StateGraph
        except ModuleNotFoundError as exc:
            raise RuntimeError("langgraph is not installed.") from exc

        workflow = StateGraph(GenerationState)
        workflow.add_node("review_prompt_agent", self._review_prompt_agent)
        workflow.add_node("website_builder_agent", self._website_builder_agent)
        workflow.add_node("validate_output", self._validate_output)
        workflow.add_node("finalize_failure", self._finalize_failure)

        workflow.add_edge(START, "review_prompt_agent")
        workflow.add_conditional_edges(
            "review_prompt_agent",
            self._route_after_review,
            {"continue": "website_builder_agent", "fail": "finalize_failure"},
        )
        workflow.add_conditional_edges(
            "website_builder_agent",
            self._route_after_builder,
            {"continue": "validate_output", "fail": "finalize_failure"},
        )
        workflow.add_conditional_edges(
            "validate_output",
            self._route_after_validation,
            {"retry": "website_builder_agent", "success": END, "fail": "finalize_failure"},
        )
        workflow.add_edge("finalize_failure", END)
        return workflow.compile()

    def generate(
        self,
        raw_prompt: str,
        framework: str,
        design_spec: Any = None,
        layout_spec: Any = None,
    ) -> tuple[Optional[dict[str, Any]], Optional[str], dict[str, Any]]:
        initial_state: GenerationState = {
            "raw_prompt": raw_prompt,
            "framework": framework,
            "design_spec_text": self._to_prompt_text(design_spec),
            "layout_spec_text": self._to_prompt_text(layout_spec),
            "retry_count": 0,
            "validation_errors": [],
        }

        try:
            result_state = self._graph.invoke(initial_state)
        except Exception as exc:
            logger.error("LangGraph execution failed: %s", exc)
            return None, f"Groq graph pipeline failed: {str(exc)}", {
                "review_data": None,
                "reviewed_prompt": None,
                "retry_count": 0,
                "validation_errors": [str(exc)],
            }

        final_output = result_state.get("final_output")
        error = result_state.get("error")
        debug_info = {
            "review_data": result_state.get("review_data"),
            "reviewed_prompt": result_state.get("reviewed_prompt"),
            "retry_count": result_state.get("retry_count", 0),
            "validation_errors": result_state.get("validation_errors", []),
        }

        if final_output:
            return final_output, None, debug_info
        if error:
            return None, error, debug_info
        return None, "Website generation failed with an unknown graph error.", debug_info

    def _route_after_review(self, state: GenerationState) -> str:
        return "fail" if state.get("error") else "continue"

    def _route_after_builder(self, state: GenerationState) -> str:
        return "fail" if state.get("error") else "continue"

    def _route_after_validation(self, state: GenerationState) -> str:
        if state.get("final_output"):
            return "success"
        if state.get("retry_count", 0) <= self.max_correction_retries:
            return "retry"
        return "fail"

    def _review_prompt_agent(self, state: GenerationState) -> dict[str, Any]:
        raw_prompt = state.get("raw_prompt", "").strip()
        if not raw_prompt:
            return {"error": "Prompt cannot be empty."}

        try:
            llm = self._llm_factory(self.review_model)
        except Exception as exc:
            return {"error": f"Prompt review agent unavailable: {str(exc)}"}

        messages = [
            self._system_message(
                """You are a prompt-review agent for a website builder.
Return JSON only with these keys:
- normalized_intent
- target_audience
- design_direction
- required_pages (integer >= 1)
- required_sections (array of strings)
- constraints (array of strings)
- rewritten_prompt

Rules:
- Preserve user intent exactly.
- Expand the prompt into clear implementation directives for a frontend website generator.
- rewritten_prompt must be detailed, actionable, and production-oriented."""
            ),
            self._human_message(f"User prompt:\n{raw_prompt}"),
        ]

        try:
            structured_llm = llm.with_structured_output(PromptReviewModel)
            review_payload = structured_llm.invoke(messages)
            review = self._coerce_prompt_review(review_payload)
        except Exception as exc:
            try:
                response = llm.invoke(messages)
                text = _extract_text(response)
                payload = json.loads(_clean_json_output(text))
                review = self._coerce_prompt_review(payload)
            except Exception as parse_exc:
                logger.warning(
                    "Prompt review parsing failed; falling back to deterministic rewrite. Error: %s",
                    parse_exc,
                )
                review = PromptReviewModel(
                    normalized_intent=raw_prompt,
                    target_audience="general web users",
                    design_direction="modern, responsive, polished interface",
                    required_pages=3,
                    required_sections=["hero", "features", "cta", "footer"],
                    constraints=["responsive design", "semantic HTML", "strong visual hierarchy"],
                    rewritten_prompt=(
                        "Build a high-quality, production-ready website based on this request: "
                        f"{raw_prompt}. Include clear sections, polished visual design and premium typography. "
                        "Use Tailwind classes with strong spacing, gradients, and responsive design."
                    ),
                )

        required_pages = self._determine_required_pages(raw_prompt, review.required_pages)
        reviewed_prompt = review.rewritten_prompt.strip()
        page_instruction = (
            f"Generate at least {required_pages} distinct pages. "
            "Use meaningful slugs and avoid generic placeholders."
        )
        if page_instruction.lower() not in reviewed_prompt.lower():
            reviewed_prompt = f"{reviewed_prompt}\n\n{page_instruction}"

        review = review.model_copy(
            update={
                "required_pages": required_pages,
                "rewritten_prompt": reviewed_prompt,
            }
        )

        return {
            "review_data": review.model_dump(),
            "reviewed_prompt": review.rewritten_prompt,
            "required_pages": required_pages,
        }

    def _website_builder_agent(self, state: GenerationState) -> dict[str, Any]:
        reviewed_prompt = state.get("reviewed_prompt", "")
        if not reviewed_prompt:
            return {"error": "Reviewed prompt is missing."}

        try:
            llm = self._llm_factory(self.builder_model)
        except Exception as exc:
            return {"error": f"Website builder agent unavailable: {str(exc)}"}

        framework = state.get("framework", "tailwind")
        required_pages = max(1, int(state.get("required_pages", 1)))
        design_spec_text = state.get("design_spec_text", "")
        layout_spec_text = state.get("layout_spec_text", "")
        correction_errors = state.get("validation_errors") or []
        correction_hint = ""
        if correction_errors:
            correction_hint = (
                "\nPrevious validation errors (must fix all):\n- "
                + "\n- ".join(correction_errors)
            )

        messages = [
            self._system_message(
                f"""You are the main website builder agent.
Output ONLY valid JSON. No markdown and no surrounding explanation.

Schema:
{{
  "website_name": "string",
  "framework": "{framework}",
  "pages": [
    {{
      "name": "string",
      "slug": "kebab-case-string",
      "sections": [
        {{
          "name": "string",
          "content": "raw HTML string",
          "order": 0
        }}
      ]
    }}
  ],
  "files": [
    {{"path": "string", "content": "string"}}
  ]
}}

Requirements:
- At least {required_pages} pages.
- Every page must contain at least one section.
- Section content must be real non-trivial HTML.
- Page slugs must be unique and kebab-case.
- Keep framework value exactly '{framework}'.
- Use premium, modern visual design quality (not plain boilerplate).
- Do NOT output placeholder or generic filler like "Full Name", "Project 1", "Featured Project", or "Short tagline".
- Every page must include concrete, specific copy tied to a real use-case, not abstract labels.
- Portfolio/project sections must include distinct project names, tech context, and measurable outcomes.
- Prefer public HTTPS image URLs (Unsplash/Pexels style links) for images.
- Do NOT reference local asset paths like assets/... unless you include matching entries in files[].

Design constraints:
{design_spec_text}

Layout constraints:
{layout_spec_text}
{correction_hint}
"""
            ),
            self._human_message(f"Build website JSON from this reviewed prompt:\n{reviewed_prompt}"),
        ]

        try:
            structured_llm = llm.with_structured_output(WebsiteSpecModel)
            structured_result = structured_llm.invoke(messages)
            structured_spec = self._coerce_website_spec(structured_result)
            candidate_output = json.dumps(structured_spec.model_dump(), ensure_ascii=False)
        except Exception as exc:
            try:
                response = llm.invoke(messages)
                candidate_output = _extract_text(response)
            except Exception as raw_exc:
                return {"error": f"Builder agent failed: {str(raw_exc)}"}

        return {"candidate_output": candidate_output}

    def _validate_output(self, state: GenerationState) -> dict[str, Any]:
        candidate_output = state.get("candidate_output", "")
        if not candidate_output:
            return {
                "validation_errors": ["Builder returned empty output."],
                "retry_count": state.get("retry_count", 0) + 1,
            }

        try:
            payload = json.loads(_clean_json_output(candidate_output))
            spec = WebsiteSpecModel.model_validate(payload)
        except ValidationError as exc:
            errors = [self._format_validation_error(err) for err in exc.errors()]
            return {
                "validation_errors": errors,
                "retry_count": state.get("retry_count", 0) + 1,
            }
        except Exception as exc:
            return {
                "validation_errors": [f"Invalid JSON output: {str(exc)}"],
                "retry_count": state.get("retry_count", 0) + 1,
            }

        min_pages = max(1, int(state.get("required_pages", 1)))
        spec = self._auto_repair_spec(
            spec,
            min_pages=min_pages,
            raw_prompt=state.get("raw_prompt", ""),
        )

        semantic_errors = self._validate_semantics(spec, min_pages=min_pages)
        if semantic_errors:
            return {
                "validation_errors": semantic_errors,
                "retry_count": state.get("retry_count", 0) + 1,
            }

        return {
            "final_output": spec.model_dump(),
            "validation_errors": [],
        }

    def _finalize_failure(self, state: GenerationState) -> dict[str, Any]:
        errors = state.get("validation_errors") or []
        if not errors and state.get("error"):
            errors = [state["error"]]

        message = (
            f"Website generation failed after {self.max_correction_retries} correction retries."
        )
        if errors:
            message += " " + " | ".join(errors[:3])
        return {"error": message}

    @staticmethod
    def _to_prompt_text(spec: Any) -> str:
        if spec is None:
            return ""
        if hasattr(spec, "to_prompt_string"):
            return str(spec.to_prompt_string())
        if isinstance(spec, dict):
            return json.dumps(spec)
        return str(spec)

    @staticmethod
    def _validate_semantics(spec: WebsiteSpecModel, min_pages: int = 1) -> list[str]:
        errors: list[str] = []
        if len(spec.pages) < min_pages:
            errors.append(f"Website must include at least {min_pages} pages.")

        file_paths = {
            file.path.strip().lstrip("./")
            for file in spec.files
            if file.path and file.path.strip()
        }

        slug_set = set()
        for page_idx, page in enumerate(spec.pages):
            if not page.sections:
                errors.append(f"Page {page_idx + 1} must include at least one section.")
            min_sections_for_page = 3 if page_idx == 0 else 2
            if len(page.sections) < min_sections_for_page:
                errors.append(
                    f"Page {page_idx + 1} should include at least {min_sections_for_page} sections for richer output."
                )
            if page.slug in slug_set:
                errors.append(f"Duplicate page slug detected: '{page.slug}'.")
            slug_set.add(page.slug)
            for section_idx, section in enumerate(page.sections):
                text = section.content.strip()
                if len(text) < 20 or "<" not in text or ">" not in text:
                    errors.append(
                        f"Page {page_idx + 1}, section {section_idx + 1} content must be non-trivial HTML."
                    )
                if len(text) < 120:
                    errors.append(
                        f"Page {page_idx + 1}, section {section_idx + 1} content is too minimal; expand detail and styling."
                    )
                if "<section" not in text.lower():
                    errors.append(
                        f"Page {page_idx + 1}, section {section_idx + 1} should use semantic section wrappers."
                    )
                if GroqWebsiteGenerationGraph._contains_placeholder_copy(text):
                    errors.append(
                        f"Page {page_idx + 1}, section {section_idx + 1} contains placeholder copy; replace with concrete content."
                    )
                class_matches = re.findall(r'class\s*=\s*["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
                if not class_matches:
                    errors.append(
                        f"Page {page_idx + 1}, section {section_idx + 1} has no styling classes; add rich visual classes."
                    )
                refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', text, flags=re.IGNORECASE)
                for ref in refs:
                    ref_clean = ref.strip()
                    normalized = ref_clean.lstrip("./")
                    if not normalized:
                        continue
                    if ref_clean.startswith("/assets/") or normalized.startswith("assets/"):
                        normalized_asset = normalized.lstrip("/")
                        if normalized_asset not in file_paths:
                            errors.append(
                                f"Page {page_idx + 1}, section {section_idx + 1} references local asset "
                                f"'{ref_clean}' but it is missing from files[]."
                            )
                        continue
                    if normalized.startswith(
                        ("http://", "https://", "data:", "mailto:", "tel:", "#", "/", "javascript:")
                    ):
                        continue
                    if re.search(r"\.(png|jpe?g|gif|webp|svg|ico|css|js)$", normalized, flags=re.IGNORECASE):
                        if normalized not in file_paths:
                            errors.append(
                                f"Page {page_idx + 1}, section {section_idx + 1} references local asset "
                                f"'{normalized}' but it is missing from files[]."
                            )
        return errors

    @staticmethod
    def _auto_repair_spec(
        spec: WebsiteSpecModel,
        min_pages: int = 1,
        raw_prompt: str = "",
    ) -> WebsiteSpecModel:
        payload = spec.model_dump()
        website_name = payload.get("website_name", "NeuraForge Site")
        framework = payload.get("framework", "tailwind")
        pages = payload.get("pages", [])
        files = payload.get("files", [])

        file_paths = {
            str(file_obj.get("path", "")).strip().lstrip("./")
            for file_obj in files
            if isinstance(file_obj, dict)
        }

        while len(pages) < min_pages:
            page_idx = len(pages)
            pages.append(
                {
                    "name": f"Page {page_idx + 1}",
                    "slug": f"page-{page_idx + 1}",
                    "sections": [],
                }
            )

        if GroqWebsiteGenerationGraph._is_portfolio_prompt(raw_prompt):
            pages = GroqWebsiteGenerationGraph._enforce_portfolio_page_set(
                pages=pages,
                website_name=website_name,
                raw_prompt=raw_prompt,
            )

        slug_seen: set[str] = set()
        for page_idx, page in enumerate(pages):
            page_name = str(page.get("name") or f"Page {page_idx + 1}").strip()
            page["name"] = page_name
            raw_slug = str(page.get("slug") or page_name).strip().lower().replace(" ", "-")
            raw_slug = re.sub(r"[^a-z0-9-]", "-", raw_slug)
            raw_slug = re.sub(r"-+", "-", raw_slug).strip("-") or f"page-{page_idx + 1}"
            slug = raw_slug
            suffix = 2
            while slug in slug_seen:
                slug = f"{raw_slug}-{suffix}"
                suffix += 1
            slug_seen.add(slug)
            page["slug"] = slug

            sections = page.get("sections") or []
            if not isinstance(sections, list):
                sections = []
            page["sections"] = sections

            min_sections = 3 if page_idx == 0 else 2
            while len(sections) < min_sections:
                sections.append(
                    GroqWebsiteGenerationGraph._default_section_payload(
                        section_idx=len(sections),
                        page_name=page_name,
                        website_name=website_name,
                    )
                )

            section_name_seen: set[str] = set()
            for section_idx, section in enumerate(sections):
                if not isinstance(section, dict):
                    section = {}
                    sections[section_idx] = section

                section_name = str(section.get("name") or f"Section {section_idx + 1}").strip()
                if GroqWebsiteGenerationGraph._looks_generic_section_name(section_name):
                    section_name = GroqWebsiteGenerationGraph._contextual_section_title(page_name, section_idx)
                section_name = GroqWebsiteGenerationGraph._dedupe_name(section_name, section_name_seen)
                section["name"] = section_name

                content = str(section.get("content") or "").strip()
                if "<" not in content or ">" not in content:
                    content = GroqWebsiteGenerationGraph._default_section_html(
                        section_title=section["name"],
                        body_text=f"{website_name} presents a curated {section['name'].lower()} experience for {page_name}.",
                        website_name=website_name,
                    )

                content = GroqWebsiteGenerationGraph._replace_placeholder_copy(content, website_name)
                content = GroqWebsiteGenerationGraph._replace_missing_local_asset_links(content, file_paths)
                if GroqWebsiteGenerationGraph._contains_placeholder_copy(content):
                    content = GroqWebsiteGenerationGraph._default_section_html(
                        section_title=section["name"],
                        body_text=(
                            f"{website_name} delivers concrete, project-specific content for {page_name} "
                            "with production-ready visual polish."
                        ),
                        website_name=website_name,
                    )

                if "<section" not in content.lower():
                    content = (
                        "<section class=\"py-16 px-6 md:px-10 bg-slate-950 text-slate-100\">"
                        "<div class=\"max-w-6xl mx-auto\">"
                        f"{content}"
                        "</div></section>"
                    )

                if not re.search(r'class\s*=\s*["\']([^"\']+)["\']', content, flags=re.IGNORECASE):
                    content = (
                        "<section class=\"py-16 px-6 md:px-10 bg-slate-950 text-slate-100\">"
                        "<div class=\"max-w-6xl mx-auto\">"
                        f"{content}"
                        "</div></section>"
                    )

                if len(content.strip()) < 120:
                    content += (
                        "<p class=\"mt-6 text-slate-300 leading-relaxed\">"
                        f"{website_name} delivers concrete outcomes with thoughtful design, "
                        "clear messaging, and production-ready implementation."
                        "</p>"
                    )

                section["content"] = content
                section["order"] = section_idx

        repaired_payload = {
            "website_name": website_name,
            "framework": framework,
            "pages": pages,
            "files": files,
        }
        return WebsiteSpecModel.model_validate(repaired_payload)

    @staticmethod
    def _is_portfolio_prompt(raw_prompt: str) -> bool:
        prompt_lower = (raw_prompt or "").lower()
        signals = [
            "portfolio",
            "resume",
            "ai/ml engineer",
            "machine learning engineer",
            "projects page",
            "about / experience",
            "about me",
        ]
        return any(token in prompt_lower for token in signals)

    @staticmethod
    def _extract_prompt_profile(raw_prompt: str) -> dict[str, str]:
        text = raw_prompt or ""

        def _extract(pattern: str) -> str:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                return ""
            value = match.group(1).strip()
            value = value.strip("\"'`")
            return re.sub(r"\s+", " ", value)

        return {
            "name": _extract(r"name\s*:\s*([^\n\r*#]+)"),
            "title": _extract(r"title\s*:\s*([^\n\r*#]+)"),
            "tagline": _extract(r"tagline\s*:\s*([^\n\r*#]+)"),
        }

    @staticmethod
    def _find_page_index(pages: list[dict[str, Any]], keywords: tuple[str, ...]) -> Optional[int]:
        for idx, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            candidate = f"{page.get('name', '')} {page.get('slug', '')}".lower()
            if any(keyword in candidate for keyword in keywords):
                return idx
        return None

    @staticmethod
    def _page_visible_text(page: dict[str, Any]) -> str:
        sections = page.get("sections") or []
        text_parts: list[str] = []
        if not isinstance(sections, list):
            return ""
        for section in sections:
            if not isinstance(section, dict):
                continue
            content = str(section.get("content") or "")
            text_parts.append(GroqWebsiteGenerationGraph._extract_visible_text(content))
        return " ".join(text_parts).strip().lower()

    @staticmethod
    def _enforce_portfolio_page_set(
        pages: list[dict[str, Any]],
        website_name: str,
        raw_prompt: str,
    ) -> list[dict[str, Any]]:
        normalized_pages = [page if isinstance(page, dict) else {} for page in (pages or [])]
        profile = GroqWebsiteGenerationGraph._extract_prompt_profile(raw_prompt)
        profile_name = profile.get("name") or f"{website_name} Team"
        profile_title = profile.get("title") or "AI/ML Engineer | Building Intelligent Systems"
        profile_tagline = profile.get("tagline") or (
            "Focused on real-world ML systems, LLM workflows, and scalable AI delivery."
        )

        home_idx = GroqWebsiteGenerationGraph._find_page_index(normalized_pages, ("home", "landing"))
        projects_idx = GroqWebsiteGenerationGraph._find_page_index(
            normalized_pages,
            ("project", "work", "case-study", "case study"),
        )
        about_idx = GroqWebsiteGenerationGraph._find_page_index(
            normalized_pages,
            ("about", "experience", "profile"),
        )

        if home_idx is None:
            normalized_pages.append({"name": "Home", "slug": "home", "sections": []})
            home_idx = len(normalized_pages) - 1
        if projects_idx is None:
            normalized_pages.append({"name": "Projects", "slug": "projects", "sections": []})
            projects_idx = len(normalized_pages) - 1
        if about_idx is None:
            normalized_pages.append({"name": "About", "slug": "about", "sections": []})
            about_idx = len(normalized_pages) - 1

        home_page = normalized_pages[home_idx]
        projects_page = normalized_pages[projects_idx]
        about_page = normalized_pages[about_idx]

        home_text = GroqWebsiteGenerationGraph._page_visible_text(home_page)
        home_score = sum(
            term in home_text
            for term in ("view projects", "contact me", "resume", "featured projects", "skills", "ai/ml engineer")
        )
        if home_score < 4 or (profile.get("name") and profile.get("name", "").lower() not in home_text):
            home_page["name"] = home_page.get("name") or "Home"
            home_page["sections"] = [
                {
                    "name": "Hero",
                    "content": GroqWebsiteGenerationGraph._portfolio_home_hero_html(
                        name=profile_name,
                        title=profile_title,
                        tagline=profile_tagline,
                    ),
                    "order": 0,
                },
                {
                    "name": "Featured Projects",
                    "content": GroqWebsiteGenerationGraph._portfolio_home_projects_preview_html(),
                    "order": 1,
                },
                {
                    "name": "Skills Overview",
                    "content": GroqWebsiteGenerationGraph._portfolio_home_skills_html(),
                    "order": 2,
                },
                {
                    "name": "Call To Action",
                    "content": GroqWebsiteGenerationGraph._portfolio_home_cta_html(website_name=website_name),
                    "order": 3,
                },
            ]

        projects_text = GroqWebsiteGenerationGraph._page_visible_text(projects_page)
        project_score = sum(
            term in projects_text
            for term in (
                "problem statement",
                "approach",
                "architecture",
                "tech stack",
                "results",
                "github",
            )
        )
        project_section_count = len(projects_page.get("sections") or [])
        if project_score < 5 or project_section_count < 3:
            projects_page["name"] = projects_page.get("name") or "Projects"
            projects_page["sections"] = [
                {
                    "name": "Project Deep Dive",
                    "content": GroqWebsiteGenerationGraph._portfolio_projects_showcase_html(),
                    "order": 0,
                },
                {
                    "name": "Engineering Process",
                    "content": GroqWebsiteGenerationGraph._portfolio_projects_process_html(),
                    "order": 1,
                },
                {
                    "name": "Delivery Metrics",
                    "content": GroqWebsiteGenerationGraph._portfolio_projects_metrics_html(),
                    "order": 2,
                },
            ]

        about_text = GroqWebsiteGenerationGraph._page_visible_text(about_page)
        about_score = sum(
            term in about_text
            for term in ("journey", "engineering mindset", "experience", "achievements", "contact")
        )
        if about_score < 4 or len(about_page.get("sections") or []) < 3:
            about_page["name"] = about_page.get("name") or "About"
            about_page["sections"] = [
                {
                    "name": "About Me",
                    "content": GroqWebsiteGenerationGraph._portfolio_about_story_html(
                        name=profile_name,
                        title=profile_title,
                    ),
                    "order": 0,
                },
                {
                    "name": "Experience",
                    "content": GroqWebsiteGenerationGraph._portfolio_about_experience_html(),
                    "order": 1,
                },
                {
                    "name": "Achievements and Contact",
                    "content": GroqWebsiteGenerationGraph._portfolio_about_achievements_contact_html(),
                    "order": 2,
                },
            ]

        priority_pages: list[dict[str, Any]] = []
        used_ids: set[int] = set()
        for idx in (home_idx, projects_idx, about_idx):
            if idx not in used_ids and 0 <= idx < len(normalized_pages):
                priority_pages.append(normalized_pages[idx])
                used_ids.add(idx)
        for idx, page in enumerate(normalized_pages):
            if idx not in used_ids:
                priority_pages.append(page)
        return priority_pages

    @staticmethod
    def _portfolio_home_hero_html(name: str, title: str, tagline: str) -> str:
        return (
            "<section class=\"relative overflow-hidden py-24 px-6 md:px-12 bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 text-white\">"
            "<div class=\"absolute inset-0 opacity-25 bg-[radial-gradient(circle_at_20%_20%,rgba(56,189,248,0.4),transparent_40%),radial-gradient(circle_at_80%_30%,rgba(129,140,248,0.45),transparent_45%),radial-gradient(circle_at_50%_80%,rgba(139,92,246,0.35),transparent_35%)]\"></div>"
            "<div class=\"relative max-w-7xl mx-auto grid lg:grid-cols-12 gap-10 items-center\">"
            "<div class=\"lg:col-span-8\">"
            f"<p class=\"text-sm uppercase tracking-[0.22em] text-cyan-300 mb-4\">{name}</p>"
            f"<h1 class=\"text-4xl md:text-6xl font-extrabold leading-tight mb-6\">{title}</h1>"
            f"<p class=\"text-lg md:text-2xl text-slate-200 leading-relaxed max-w-3xl\">{tagline}</p>"
            "<div class=\"mt-10 flex flex-wrap gap-4\">"
            "<a href=\"#featured-projects\" class=\"px-6 py-3 rounded-xl bg-cyan-500 text-slate-950 font-semibold hover:bg-cyan-400 transition\">View Projects</a>"
            "<a href=\"#contact\" class=\"px-6 py-3 rounded-xl border border-indigo-300/60 text-indigo-100 hover:bg-indigo-500/20 transition\">Contact Me</a>"
            "<a href=\"#resume\" class=\"px-6 py-3 rounded-xl bg-indigo-600 text-white font-semibold hover:bg-indigo-500 transition\">Resume Download</a>"
            "</div>"
            "</div>"
            "<aside class=\"lg:col-span-4 rounded-2xl border border-indigo-400/30 bg-slate-900/60 p-6 shadow-2xl\">"
            "<h2 class=\"text-xl font-semibold mb-4\">Engineering Focus</h2>"
            "<ul class=\"space-y-3 text-slate-200\">"
            "<li class=\"flex items-start gap-3\"><span class=\"mt-1 h-2 w-2 rounded-full bg-cyan-400\"></span><span>Production-grade machine learning systems</span></li>"
            "<li class=\"flex items-start gap-3\"><span class=\"mt-1 h-2 w-2 rounded-full bg-indigo-400\"></span><span>LLM applications with RAG and evaluation loops</span></li>"
            "<li class=\"flex items-start gap-3\"><span class=\"mt-1 h-2 w-2 rounded-full bg-violet-400\"></span><span>Scalable data and inference pipelines</span></li>"
            "</ul>"
            "</aside>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_home_projects_preview_html() -> str:
        return (
            "<section id=\"featured-projects\" class=\"py-20 px-6 md:px-12 bg-slate-950 text-white\">"
            "<div class=\"max-w-7xl mx-auto\">"
            "<h2 class=\"text-3xl md:text-4xl font-bold tracking-tight mb-4\">Featured Projects</h2>"
            "<p class=\"text-slate-300 mb-10 max-w-3xl\">Selected work focused on applied AI systems, low-latency inference, and measurable business impact.</p>"
            "<div class=\"grid md:grid-cols-3 gap-6\">"
            "<article class=\"rounded-2xl border border-cyan-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-2\">LLM Summarization Engine</h3>"
            "<p class=\"text-slate-300 mb-3\">Reduced analyst reading time by 42% using domain-tuned summarization workflows.</p>"
            "<p class=\"text-sm text-cyan-300\">Tech: Python, Transformers, FastAPI, Redis</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-2\">RAG Knowledge Assistant</h3>"
            "<p class=\"text-slate-300 mb-3\">Improved answer grounding with retrieval scoring and citation-aware responses.</p>"
            "<p class=\"text-sm text-indigo-300\">Tech: LangChain, Vector DB, OpenSearch, Docker</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-violet-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-2\">Personal Finance Intelligence</h3>"
            "<p class=\"text-slate-300 mb-3\">Generated behavior-aware recommendations with explainable risk signals.</p>"
            "<p class=\"text-sm text-violet-300\">Tech: XGBoost, Pandas, Airflow, PostgreSQL</p>"
            "</article>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_home_skills_html() -> str:
        return (
            "<section class=\"py-18 px-6 md:px-12 bg-gradient-to-br from-slate-900 to-slate-950 text-white\">"
            "<div class=\"max-w-7xl mx-auto\">"
            "<h2 class=\"text-3xl font-bold mb-6\">Skills Overview</h2>"
            "<div class=\"flex flex-wrap gap-3\">"
            "<span class=\"px-4 py-2 rounded-full bg-cyan-500/20 border border-cyan-400/40\">Machine Learning</span>"
            "<span class=\"px-4 py-2 rounded-full bg-indigo-500/20 border border-indigo-400/40\">NLP</span>"
            "<span class=\"px-4 py-2 rounded-full bg-violet-500/20 border border-violet-400/40\">LLMs</span>"
            "<span class=\"px-4 py-2 rounded-full bg-blue-500/20 border border-blue-400/40\">Data Engineering</span>"
            "<span class=\"px-4 py-2 rounded-full bg-emerald-500/20 border border-emerald-400/40\">MLOps</span>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_home_cta_html(website_name: str) -> str:
        return (
            "<section id=\"contact\" class=\"py-20 px-6 md:px-12 bg-slate-950 text-white\">"
            "<div class=\"max-w-4xl mx-auto rounded-3xl border border-indigo-500/40 bg-slate-900/70 p-10 text-center shadow-2xl\">"
            "<h2 class=\"text-3xl md:text-4xl font-bold mb-4\">Let us build something impactful</h2>"
            f"<p class=\"text-slate-300 mb-8\">{website_name} delivers practical AI systems with clear technical depth and business relevance.</p>"
            "<div id=\"resume\" class=\"flex flex-wrap justify-center gap-4\">"
            "<a href=\"mailto:hello@portfolio.dev\" class=\"px-6 py-3 rounded-xl bg-cyan-500 text-slate-950 font-semibold\">Contact</a>"
            "<a href=\"https://github.com\" target=\"_blank\" rel=\"noopener\" class=\"px-6 py-3 rounded-xl border border-cyan-300/50 text-cyan-100\">GitHub</a>"
            "<a href=\"https://www.linkedin.com\" target=\"_blank\" rel=\"noopener\" class=\"px-6 py-3 rounded-xl border border-indigo-300/50 text-indigo-100\">LinkedIn</a>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_projects_showcase_html() -> str:
        return (
            "<section class=\"py-20 px-6 md:px-12 bg-gradient-to-b from-slate-950 to-slate-900 text-white\">"
            "<div class=\"max-w-7xl mx-auto\">"
            "<h2 class=\"text-3xl md:text-4xl font-bold mb-4\">AI/ML Projects Deep Dive</h2>"
            "<p class=\"text-slate-300 mb-10\">Each project includes problem context, approach, architecture decisions, stack, and measurable outcomes.</p>"
            "<div class=\"grid lg:grid-cols-2 gap-6\">"
            "<article class=\"rounded-2xl border border-cyan-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold mb-4\">LLM-based Text Summarization System</h3>"
            "<p><strong>Problem Statement:</strong> Analysts spent too much time digesting long reports and support transcripts.</p>"
            "<p class=\"mt-2\"><strong>Approach:</strong> Fine-tuned encoder-decoder transformers with domain-specific prompt templates.</p>"
            "<p class=\"mt-2\"><strong>Architecture / Pipeline:</strong> Ingestion -> chunking -> summarization -> quality scoring -> API serving.</p>"
            "<p class=\"mt-2\"><strong>Tech Stack:</strong> Python, PyTorch, HuggingFace, FastAPI, Redis.</p>"
            "<p class=\"mt-2\"><strong>Results:</strong> ROUGE-L improved by 14%; average reading time reduced by 42%.</p>"
            "<p class=\"mt-2\"><strong>Links:</strong> <a class=\"text-cyan-300 underline\" href=\"https://github.com/example/llm-summarizer\" target=\"_blank\" rel=\"noopener\">GitHub</a> | <a class=\"text-cyan-300 underline\" href=\"https://demo.example.com/summarizer\" target=\"_blank\" rel=\"noopener\">Live Demo</a></p>"
            "</article>"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold mb-4\">RAG Chatbot with LangChain + Vector DB</h3>"
            "<p><strong>Problem Statement:</strong> Internal teams needed accurate answers over constantly changing policy documents.</p>"
            "<p class=\"mt-2\"><strong>Approach:</strong> Hybrid retrieval, embedding reranking, and guarded response generation.</p>"
            "<p class=\"mt-2\"><strong>Architecture / Pipeline:</strong> ETL -> embeddings -> vector index -> retrieval -> grounded generation.</p>"
            "<p class=\"mt-2\"><strong>Tech Stack:</strong> LangChain, FAISS, FastAPI, PostgreSQL, Docker.</p>"
            "<p class=\"mt-2\"><strong>Results:</strong> Answer grounding rate reached 91%; median response latency under 1.4 seconds.</p>"
            "<p class=\"mt-2\"><strong>Links:</strong> <a class=\"text-indigo-300 underline\" href=\"https://github.com/example/rag-assistant\" target=\"_blank\" rel=\"noopener\">GitHub</a> | <a class=\"text-indigo-300 underline\" href=\"https://demo.example.com/rag\" target=\"_blank\" rel=\"noopener\">Live Demo</a></p>"
            "</article>"
            "<article class=\"rounded-2xl border border-violet-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold mb-4\">AI Personal Finance Advisor</h3>"
            "<p><strong>Problem Statement:</strong> Users lacked actionable monthly spending guidance tied to real behavior patterns.</p>"
            "<p class=\"mt-2\"><strong>Approach:</strong> Time-series features plus gradient boosting for category-level spend forecasting.</p>"
            "<p class=\"mt-2\"><strong>Architecture / Pipeline:</strong> Transaction ingestion -> feature store -> model scoring -> insight API.</p>"
            "<p class=\"mt-2\"><strong>Tech Stack:</strong> Python, XGBoost, Pandas, Airflow, Postgres.</p>"
            "<p class=\"mt-2\"><strong>Results:</strong> Forecast MAE improved by 22%; monthly budget adherence improved by 17%.</p>"
            "<p class=\"mt-2\"><strong>Links:</strong> <a class=\"text-violet-300 underline\" href=\"https://github.com/example/finance-advisor\" target=\"_blank\" rel=\"noopener\">GitHub</a> | <a class=\"text-violet-300 underline\" href=\"https://demo.example.com/finance\" target=\"_blank\" rel=\"noopener\">Live Demo</a></p>"
            "</article>"
            "<article class=\"rounded-2xl border border-blue-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold mb-4\">Time Series Forecasting Platform</h3>"
            "<p><strong>Problem Statement:</strong> Operations teams needed demand forecasts to reduce inventory volatility.</p>"
            "<p class=\"mt-2\"><strong>Approach:</strong> Ensemble of temporal CNN and gradient models with drift monitoring.</p>"
            "<p class=\"mt-2\"><strong>Architecture / Pipeline:</strong> Data warehouse -> feature engineering -> model registry -> inference service.</p>"
            "<p class=\"mt-2\"><strong>Tech Stack:</strong> Python, TensorFlow, MLflow, BigQuery, FastAPI.</p>"
            "<p class=\"mt-2\"><strong>Results:</strong> MAPE reduced by 19%; stockout incidents reduced by 24% quarter-over-quarter.</p>"
            "<p class=\"mt-2\"><strong>Links:</strong> <a class=\"text-blue-300 underline\" href=\"https://github.com/example/demand-forecast\" target=\"_blank\" rel=\"noopener\">GitHub</a> | <a class=\"text-blue-300 underline\" href=\"https://demo.example.com/forecast\" target=\"_blank\" rel=\"noopener\">Live Demo</a></p>"
            "</article>"
            "<article class=\"rounded-2xl border border-emerald-500/30 bg-slate-900/60 p-6 lg:col-span-2\">"
            "<h3 class=\"text-2xl font-semibold mb-4\">Computer Vision Quality Inspection</h3>"
            "<p><strong>Problem Statement:</strong> Manual inspection lines produced inconsistent defect detection and delayed triage.</p>"
            "<p class=\"mt-2\"><strong>Approach:</strong> Transfer learning with attention-based CNNs and active-learning feedback loops.</p>"
            "<p class=\"mt-2\"><strong>Architecture / Pipeline:</strong> Camera stream -> preprocessing -> model inference -> defect analytics dashboard.</p>"
            "<p class=\"mt-2\"><strong>Tech Stack:</strong> PyTorch, OpenCV, ONNX Runtime, FastAPI, Grafana.</p>"
            "<p class=\"mt-2\"><strong>Results:</strong> Defect recall reached 95%; false rejection reduced by 18% while latency stayed under 120ms.</p>"
            "<p class=\"mt-2\"><strong>Links:</strong> <a class=\"text-emerald-300 underline\" href=\"https://github.com/example/cv-quality\" target=\"_blank\" rel=\"noopener\">GitHub</a> | <a class=\"text-emerald-300 underline\" href=\"https://demo.example.com/cv\" target=\"_blank\" rel=\"noopener\">Live Demo</a></p>"
            "</article>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_projects_process_html() -> str:
        return (
            "<section class=\"py-16 px-6 md:px-12 bg-slate-950 text-white\">"
            "<div class=\"max-w-7xl mx-auto grid md:grid-cols-3 gap-6\">"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-3\">Discovery</h3>"
            "<p class=\"text-slate-300\">Clarify user pain, data constraints, and success metrics before modeling.</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-3\">Implementation</h3>"
            "<p class=\"text-slate-300\">Ship reproducible pipelines with experiment tracking, validation checks, and CI gates.</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-xl font-semibold mb-3\">Production</h3>"
            "<p class=\"text-slate-300\">Monitor drift, latency, and quality; iterate with feedback-informed model updates.</p>"
            "</article>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_projects_metrics_html() -> str:
        return (
            "<section class=\"py-16 px-6 md:px-12 bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-white\">"
            "<div class=\"max-w-5xl mx-auto\">"
            "<h2 class=\"text-3xl font-bold mb-6\">Engineering Outcomes</h2>"
            "<div class=\"grid sm:grid-cols-2 lg:grid-cols-4 gap-4\">"
            "<div class=\"rounded-xl border border-cyan-500/30 p-5 bg-slate-900/60\"><p class=\"text-sm text-slate-300\">Model Accuracy</p><p class=\"text-3xl font-bold\">+11%</p></div>"
            "<div class=\"rounded-xl border border-indigo-500/30 p-5 bg-slate-900/60\"><p class=\"text-sm text-slate-300\">Latency</p><p class=\"text-3xl font-bold\">-37%</p></div>"
            "<div class=\"rounded-xl border border-violet-500/30 p-5 bg-slate-900/60\"><p class=\"text-sm text-slate-300\">Deployment Time</p><p class=\"text-3xl font-bold\">-45%</p></div>"
            "<div class=\"rounded-xl border border-emerald-500/30 p-5 bg-slate-900/60\"><p class=\"text-sm text-slate-300\">Business Lift</p><p class=\"text-3xl font-bold\">+18%</p></div>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_about_story_html(name: str, title: str) -> str:
        return (
            "<section class=\"py-20 px-6 md:px-12 bg-slate-950 text-white\">"
            "<div class=\"max-w-5xl mx-auto\">"
            "<h2 class=\"text-4xl font-bold mb-4\">About Me</h2>"
            f"<p class=\"text-lg text-slate-300 leading-relaxed mb-6\">{name} is a {title} focused on building dependable AI systems from data pipelines to model serving. The work emphasizes practical problem framing, maintainable architecture, and measurable outcomes over demo-only prototypes.</p>"
            "<p class=\"text-lg text-slate-300 leading-relaxed\">Engineering mindset: define clear constraints, design for reliability first, and optimize for delivery speed without sacrificing quality.</p>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_about_experience_html() -> str:
        return (
            "<section class=\"py-16 px-6 md:px-12 bg-gradient-to-br from-slate-900 to-slate-950 text-white\">"
            "<div class=\"max-w-6xl mx-auto\">"
            "<h2 class=\"text-3xl font-bold mb-8\">Experience</h2>"
            "<div class=\"space-y-6\">"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold\">AI Engineer Intern - Product Intelligence Team</h3>"
            "<p class=\"mt-2\"><strong>Problem tackled:</strong> Fragmented customer feedback prevented consistent issue prioritization.</p>"
            "<p class=\"mt-2\"><strong>Solution built:</strong> LLM-assisted triage service with topic clustering and sentiment calibration.</p>"
            "<p class=\"mt-2\"><strong>Tools used:</strong> Python, LangChain, FastAPI, PostgreSQL, Docker.</p>"
            "<p class=\"mt-2\"><strong>Outcome:</strong> Ticket categorization time reduced by 38% and triage consistency improved across teams.</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-cyan-500/30 bg-slate-900/60 p-6\">"
            "<h3 class=\"text-2xl font-semibold\">Freelance ML Engineer - Analytics Platform</h3>"
            "<p class=\"mt-2\"><strong>Problem tackled:</strong> Forecasting errors caused recurring inventory and staffing mismatches.</p>"
            "<p class=\"mt-2\"><strong>Solution built:</strong> Time-series forecasting API with drift alerts and retraining workflow.</p>"
            "<p class=\"mt-2\"><strong>Tools used:</strong> TensorFlow, MLflow, Airflow, BigQuery, FastAPI.</p>"
            "<p class=\"mt-2\"><strong>Outcome:</strong> Forecast quality improved by 19% and planning variance dropped significantly.</p>"
            "</article>"
            "</div>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _portfolio_about_achievements_contact_html() -> str:
        return (
            "<section class=\"py-16 px-6 md:px-12 bg-slate-950 text-white\">"
            "<div class=\"max-w-6xl mx-auto grid lg:grid-cols-2 gap-8\">"
            "<article class=\"rounded-2xl border border-violet-500/30 bg-slate-900/60 p-6\">"
            "<h2 class=\"text-2xl font-bold mb-4\">Achievements</h2>"
            "<ul class=\"space-y-3 text-slate-300\">"
            "<li>Top 5% finish in a production-ML Kaggle competition with reproducible training pipeline.</li>"
            "<li>Hackathon winner for a healthcare triage assistant with grounded retrieval architecture.</li>"
            "<li>Certification: Advanced MLOps deployment and model monitoring specialization.</li>"
            "</ul>"
            "<h3 class=\"text-xl font-semibold mt-6 mb-3\">Blog Insights</h3>"
            "<ul class=\"space-y-2 text-slate-300\">"
            "<li>Fine-Tuning LLMs for Domain Precision</li>"
            "<li>RAG vs Fine-Tuning: Choosing the Right Pattern</li>"
            "<li>Scaling ML Systems with Observability and Guardrails</li>"
            "</ul>"
            "</article>"
            "<article id=\"contact\" class=\"rounded-2xl border border-cyan-500/30 bg-slate-900/60 p-6\">"
            "<h2 class=\"text-2xl font-bold mb-4\">Contact</h2>"
            "<form class=\"space-y-4\">"
            "<input class=\"w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3\" type=\"text\" name=\"name\" placeholder=\"Your Name\">"
            "<input class=\"w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3\" type=\"email\" name=\"email\" placeholder=\"Your Email\">"
            "<textarea class=\"w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 min-h-[120px]\" name=\"message\" placeholder=\"Project details\"></textarea>"
            "<button class=\"rounded-xl bg-cyan-500 text-slate-950 font-semibold px-6 py-3\" type=\"submit\">Send Message</button>"
            "</form>"
            "<div class=\"mt-6 space-y-2 text-slate-300\">"
            "<p><strong>GitHub:</strong> <a class=\"text-cyan-300 underline\" href=\"https://github.com\" target=\"_blank\" rel=\"noopener\">github.com</a></p>"
            "<p><strong>LinkedIn:</strong> <a class=\"text-cyan-300 underline\" href=\"https://www.linkedin.com\" target=\"_blank\" rel=\"noopener\">linkedin.com</a></p>"
            "</div>"
            "</article>"
            "</div>"
            "</section>"
        )

    @staticmethod
    def _default_section_payload(section_idx: int, page_name: str, website_name: str) -> dict[str, Any]:
        presets = GroqWebsiteGenerationGraph._section_presets(page_name=page_name, website_name=website_name)
        title, body = presets[section_idx % len(presets)]
        return {
            "name": title,
            "content": GroqWebsiteGenerationGraph._default_section_html(title, body, website_name=website_name),
            "order": section_idx,
        }

    @staticmethod
    def _section_presets(page_name: str, website_name: str) -> list[tuple[str, str]]:
        page_key = (page_name or "").lower()
        if any(token in page_key for token in ("project", "work", "case")):
            return [
                ("Project Spotlight", f"{website_name} showcases delivery-focused case studies with business context."),
                ("Architecture Decisions", "Each case study explains stack choices, data flow, and deployment tradeoffs."),
                ("Measured Outcomes", "Every build highlights concrete impact using adoption, speed, and accuracy metrics."),
            ]
        if any(token in page_key for token in ("skill", "expertise", "stack")):
            return [
                ("Core Expertise", f"{website_name} applies ML, LLM, and data engineering skills in production settings."),
                ("Tooling and Workflow", "The workflow covers prototyping, evaluation, CI/CD, observability, and iteration."),
                ("Applied Impact", "Capabilities are tied to real outcomes such as faster releases and better model quality."),
            ]
        if any(token in page_key for token in ("contact", "reach", "book")):
            return [
                ("Start a Conversation", f"{website_name} invites clear project briefs, constraints, and expected outcomes."),
                ("Engagement Process", "The process includes discovery, proposal, implementation, and deployment support."),
                ("Next Steps", "Visitors can schedule a session, share requirements, and receive a practical roadmap."),
            ]
        if any(token in page_key for token in ("about", "home", "landing", "portfolio")):
            return [
                ("Hero Narrative", f"{website_name} presents a clear value proposition backed by practical engineering depth."),
                ("Proof of Capability", "Highlighted work demonstrates end-to-end delivery from ideation to production."),
                ("Conversion Callout", "A focused call-to-action guides visitors toward consultation or collaboration."),
            ]
        return [
            ("Overview", f"{website_name} introduces a high-impact overview for {page_name}."),
            ("Highlights", f"Key highlights and practical advantages are presented for {page_name}."),
            ("Call to Action", f"Clear action points help visitors move forward with {website_name}."),
        ]

    @staticmethod
    def _default_section_html(section_title: str, body_text: str, website_name: str = "NeuraForge") -> str:
        cards = GroqWebsiteGenerationGraph._contextual_cards(section_title=section_title, website_name=website_name)
        return (
            "<section class=\"py-16 px-6 md:px-10 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950 text-white\">"
            "<div class=\"max-w-6xl mx-auto\">"
            f"<h2 class=\"text-3xl md:text-4xl font-bold tracking-tight mb-4\">{section_title}</h2>"
            f"<p class=\"text-lg text-slate-300 leading-relaxed mb-8\">{body_text}</p>"
            "<div class=\"grid md:grid-cols-2 gap-6\">"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6 shadow-xl\">"
            f"<h3 class=\"text-xl font-semibold mb-3\">{cards[0][0]}</h3>"
            f"<p class=\"text-slate-300\">{cards[0][1]}</p>"
            "</article>"
            "<article class=\"rounded-2xl border border-indigo-500/30 bg-slate-900/60 p-6 shadow-xl\">"
            f"<h3 class=\"text-xl font-semibold mb-3\">{cards[1][0]}</h3>"
            f"<p class=\"text-slate-300\">{cards[1][1]}</p>"
            "</article>"
            "</div></div></section>"
        )

    @staticmethod
    def _contextual_cards(section_title: str, website_name: str) -> list[tuple[str, str]]:
        section_key = (section_title or "").lower()
        if any(token in section_key for token in ("project", "case", "portfolio", "work")):
            return [
                (
                    "Fraud Detection Platform",
                    "Designed a streaming ML scoring pipeline that reduced false positives by 28% and improved review speed.",
                ),
                (
                    "Demand Forecasting Engine",
                    "Built multi-horizon forecasting models with automated drift checks, improving planning accuracy by 19%.",
                ),
            ]
        if any(token in section_key for token in ("skill", "expertise", "stack", "tool")):
            return [
                (
                    "LLM Product Engineering",
                    "Shipped retrieval-augmented workflows, prompt-evaluation harnesses, and observability for production usage.",
                ),
                (
                    "Data Platform Delivery",
                    "Implemented robust ETL orchestration, schema contracts, and dashboard-ready data marts for decision teams.",
                ),
            ]
        if any(token in section_key for token in ("contact", "reach", "cta", "call")):
            return [
                (
                    "Discovery Session",
                    f"{website_name} gathers scope, constraints, and target KPIs to align delivery from day one.",
                ),
                (
                    "Execution Roadmap",
                    "A practical roadmap covers milestones, ownership, and launch-readiness checkpoints for predictable outcomes.",
                ),
            ]
        return [
            (
                "Strategy",
                "A tailored content and visual strategy aligned with user intent, conversion goals, and measurable outcomes.",
            ),
            (
                "Execution",
                "Production-ready implementation with responsive structure, clear hierarchy, and modern visual polish.",
            ),
        ]

    @staticmethod
    def _looks_generic_section_name(name: str) -> bool:
        if not name:
            return True
        lowered = name.strip().lower()
        patterns = [
            r"^section\s+\d+$",
            r"^page\s+\d+$",
            r"^project\s+\d+$",
            r"^skill\s+\d+$",
            r"^blog\s+post\s+\d+$",
            r"^featured\s+project$",
            r"^core\s+capability$",
            r"^featured\s+insight$",
            r"^untitled$",
            r"^placeholder$",
        ]
        return any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _contextual_section_title(page_name: str, section_idx: int) -> str:
        page_key = (page_name or "").lower()
        if any(token in page_key for token in ("project", "work", "case")):
            titles = ["Case Study", "Delivery Architecture", "Business Impact", "Lessons Learned"]
            return titles[section_idx % len(titles)]
        if any(token in page_key for token in ("skill", "expertise", "stack")):
            titles = ["Applied Expertise", "Tooling", "Implementation Notes", "Operational Readiness"]
            return titles[section_idx % len(titles)]
        if any(token in page_key for token in ("contact", "reach", "book")):
            titles = ["Get In Touch", "Engagement Flow", "Response Timeline", "Project Intake"]
            return titles[section_idx % len(titles)]
        titles = ["Overview", "Highlights", "Build Process", "Call to Action"]
        return titles[section_idx % len(titles)]

    @staticmethod
    def _dedupe_name(name: str, seen_names: set[str]) -> str:
        base = re.sub(r"\s+", " ", (name or "").strip()) or "Section"
        candidate = base
        suffix = 2
        while candidate.lower() in seen_names:
            candidate = f"{base} {suffix}"
            suffix += 1
        seen_names.add(candidate.lower())
        return candidate

    @staticmethod
    def _replace_placeholder_copy(content: str, website_name: str) -> str:
        website_slug = re.sub(r"[^a-z0-9]+", "-", website_name.lower()).strip("-") or "neuraforge"
        project_titles = [
            "Real-Time Fraud Detection Platform",
            "Multi-Modal Document Intelligence System",
            "Demand Forecasting and Inventory Optimizer",
            "Customer Churn Prediction and Retention Engine",
        ]
        skill_titles = [
            "ML System Design",
            "LLM Application Engineering",
            "Data Pipeline Architecture",
            "MLOps and Model Governance",
        ]
        insight_titles = [
            "Scaling LLM Features in Production",
            "Designing Reliable Evaluation Pipelines",
            "Improving Inference Cost and Latency",
            "Shipping Trustworthy AI Experiences",
        ]

        def _replace_numbered(text: str, pattern: str, choices: list[str]) -> str:
            def _replacement(match: re.Match[str]) -> str:
                raw_idx = match.group(1)
                if raw_idx and raw_idx.isdigit():
                    return choices[(int(raw_idx) - 1) % len(choices)]
                return choices[0]

            return re.sub(pattern, _replacement, text, flags=re.IGNORECASE)

        result = content
        result = _replace_numbered(result, r"\bproject\s+(\d+)\b", project_titles)
        result = _replace_numbered(result, r"\bskill\s+(\d+)\b", skill_titles)
        result = _replace_numbered(result, r"\bblog\s+post\s+(\d+)\b", insight_titles)

        replacements = [
            (r"\bfull\s+name\b", f"{website_name} Team"),
            (r"\bshort\s+tagline\b", "Building measurable digital products with strong engineering and design execution."),
            (r"\bbrief\s+introduction\b", f"{website_name} combines product strategy, visual systems, and delivery excellence."),
            (r"\bfeatured\s+project\b", "AI Workflow Automation Platform"),
            (r"\bskill\s+description\b", "Applied capability demonstrated through production delivery."),
            (r"\bexperience\s+details\b", "Delivery timeline, technical decisions, and measurable impact."),
            (r"\bcore\s+capability\b", "Applied Expertise"),
            (r"\bfeatured\s+insight\b", "Practical Engineering Insight"),
            (r"\bemail@example\.com\b", f"hello@{website_slug}.com"),
            (r"\blinkedin\.com/in/example\b", f"linkedin.com/company/{website_slug}"),
            (r"\bgithub\.com/example\b", f"github.com/{website_slug}"),
            (r"\blorem\s+ipsum\b", "Practical insights backed by delivery outcomes"),
            (r"\byour\s+name\s+here\b", f"{website_name}"),
            (r"\bplaceholder\s+(?:text|content|description)\b", "production-ready content"),
        ]
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    @staticmethod
    def _replace_missing_local_asset_links(content: str, file_paths: set[str]) -> str:
        refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', content, flags=re.IGNORECASE)
        updated = content
        for ref in refs:
            ref_clean = ref.strip()
            normalized = ref_clean.lstrip("./")
            if not normalized:
                continue
            if ref_clean.startswith("/assets/") or normalized.startswith("assets/"):
                asset_key = normalized.lstrip("/")
                if asset_key not in file_paths:
                    placeholder = "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
                    updated = updated.replace(ref, placeholder)
                continue
            if normalized.startswith(("http://", "https://", "data:", "mailto:", "tel:", "#", "/", "javascript:")):
                continue
            if normalized in file_paths:
                continue
            if re.search(r"\.(png|jpe?g|gif|webp|svg)$", normalized, flags=re.IGNORECASE):
                placeholder = "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
                updated = updated.replace(ref, placeholder)
        return updated

    @staticmethod
    def _extract_visible_text(html_content: str) -> str:
        text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html_content, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _contains_placeholder_copy(html_content: str) -> bool:
        visible = GroqWebsiteGenerationGraph._extract_visible_text(html_content).lower()
        if not visible:
            return False
        for pattern in PLACEHOLDER_PATTERNS:
            if re.search(pattern, visible, flags=re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _determine_required_pages(raw_prompt: str, model_pages: int) -> int:
        prompt_lower = (raw_prompt or "").lower()
        explicit_pages = re.search(r"\b([1-9])\s*[-\s]?page(?:s)?\b", prompt_lower)
        if explicit_pages:
            return max(1, min(6, int(explicit_pages.group(1))))

        if any(term in prompt_lower for term in ["single page", "one page", "landing page"]):
            return 1

        default_multi_page = any(
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
        )

        if default_multi_page:
            return max(3, model_pages)

        return max(2, model_pages)

    @staticmethod
    def _format_validation_error(error: dict[str, Any]) -> str:
        location = ".".join([str(part) for part in error.get("loc", [])])
        message = error.get("msg", "Validation error")
        if location:
            return f"{location}: {message}"
        return str(message)

    @staticmethod
    def _system_message(content: str) -> Any:
        try:
            from langchain_core.messages import SystemMessage

            return SystemMessage(content=content)
        except Exception:
            return SimpleNamespace(role="system", content=content)

    @staticmethod
    def _human_message(content: str) -> Any:
        try:
            from langchain_core.messages import HumanMessage

            return HumanMessage(content=content)
        except Exception:
            return SimpleNamespace(role="user", content=content)

    @staticmethod
    def _coerce_prompt_review(review_payload: Any) -> PromptReviewModel:
        if isinstance(review_payload, PromptReviewModel):
            return review_payload

        if isinstance(review_payload, dict):
            payload = dict(review_payload)
        else:
            payload = {"rewritten_prompt": str(review_payload)}

        rewritten_prompt = payload.get("rewritten_prompt")
        if isinstance(rewritten_prompt, dict):
            rewritten_prompt = (
                rewritten_prompt.get("prompt")
                or rewritten_prompt.get("text")
                or json.dumps(rewritten_prompt, ensure_ascii=False)
            )
        elif isinstance(rewritten_prompt, list):
            rewritten_prompt = " ".join([str(item) for item in rewritten_prompt])

        required_sections = payload.get("required_sections", [])
        if isinstance(required_sections, str):
            required_sections = [part.strip() for part in required_sections.split(",") if part.strip()]

        constraints = payload.get("constraints", [])
        if isinstance(constraints, str):
            constraints = [part.strip() for part in constraints.split(",") if part.strip()]

        required_pages = payload.get("required_pages", 1)
        if not isinstance(required_pages, int):
            try:
                required_pages = int(required_pages)
            except Exception:
                required_pages = 1

        normalized_payload = {
            "normalized_intent": str(payload.get("normalized_intent") or payload.get("intent") or "Website request"),
            "target_audience": str(payload.get("target_audience") or "general web users"),
            "design_direction": str(payload.get("design_direction") or "modern responsive interface"),
            "required_pages": max(1, required_pages),
            "required_sections": [str(item) for item in required_sections] if required_sections else [],
            "constraints": [str(item) for item in constraints] if constraints else [],
            "rewritten_prompt": str(
                rewritten_prompt
                or payload.get("normalized_intent")
                or "Build a modern, responsive website with strong visual design."
            ),
        }
        return PromptReviewModel.model_validate(normalized_payload)

    @staticmethod
    def _coerce_website_spec(structured_result: Any) -> WebsiteSpecModel:
        if isinstance(structured_result, WebsiteSpecModel):
            return structured_result
        if isinstance(structured_result, dict):
            return WebsiteSpecModel.model_validate(structured_result)
        return WebsiteSpecModel.model_validate(json.loads(_clean_json_output(str(structured_result))))
