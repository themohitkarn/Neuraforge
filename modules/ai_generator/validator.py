# modules/ai_generator/validator.py
# JSON schema validation and auto-repair for LLM outputs

import json
import logging

logger = logging.getLogger(__name__)


# Required schema for a generated website
WEBSITE_SCHEMA = {
    "required_fields": ["website_name", "pages"],
    "page_required_fields": ["name", "slug", "sections"],
    "section_required_fields": ["name", "content", "order"],
}


def validate_website_json(data: dict) -> tuple:
    """
    Validates the parsed JSON against the expected website schema.
    Returns (is_valid, errors_list).
    """
    errors = []
    
    if not isinstance(data, dict):
        return False, ["Root is not a JSON object"]
    
    # Check top-level fields
    for field in WEBSITE_SCHEMA["required_fields"]:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
    
    # Check pages
    pages = data.get("pages", [])
    if not isinstance(pages, list):
        errors.append("'pages' must be an array")
        return len(errors) == 0, errors
    
    if len(pages) == 0:
        errors.append("'pages' array is empty — at least one page required")
    
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            errors.append(f"Page {i} is not an object")
            continue
            
        for field in WEBSITE_SCHEMA["page_required_fields"]:
            if field not in page:
                errors.append(f"Page {i} missing field: '{field}'")
        
        sections = page.get("sections", [])
        if not isinstance(sections, list):
            errors.append(f"Page {i}: 'sections' must be an array")
            continue
            
        if len(sections) == 0:
            errors.append(f"Page {i} '{page.get('name', 'Unknown')}' has no sections")
        
        for j, section in enumerate(sections):
            if not isinstance(section, dict):
                errors.append(f"Page {i}, Section {j} is not an object")
                continue
                
            for field in WEBSITE_SCHEMA["section_required_fields"]:
                if field not in section:
                    errors.append(f"Page {i}, Section {j} missing: '{field}'")
            
            # Content should be a non-empty string
            content = section.get("content", "")
            if isinstance(content, list):
                errors.append(f"Page {i}, Section {j}: 'content' is an array, should be string")
            elif not content or (isinstance(content, str) and len(content.strip()) < 10):
                errors.append(f"Page {i}, Section {j}: 'content' is empty or too short")
    
    return len(errors) == 0, errors


def auto_fix_json(data: dict) -> dict:
    """
    Attempt to auto-fix common issues in the parsed JSON.
    Returns the fixed data.
    """
    if not isinstance(data, dict):
        return {"website_name": "Untitled", "pages": [], "files": []}
    
    # Ensure required fields
    if "website_name" not in data:
        data["website_name"] = "Untitled Website"
    
    if "pages" not in data:
        data["pages"] = []
    
    if "files" not in data:
        data["files"] = []
    
    # Fix each page
    fixed_pages = []
    for i, page in enumerate(data.get("pages", [])):
        if not isinstance(page, dict):
            continue
            
        if "name" not in page:
            page["name"] = f"Page {i+1}"
        if "slug" not in page:
            page["slug"] = page["name"].lower().replace(" ", "-")
        if "sections" not in page:
            page["sections"] = []
        
        # Fix sections
        fixed_sections = []
        for j, section in enumerate(page.get("sections", [])):
            if not isinstance(section, dict):
                continue
                
            if "name" not in section:
                section["name"] = f"Section {j+1}"
            if "order" not in section:
                section["order"] = j
            
            # Fix content type
            content = section.get("content", "")
            if isinstance(content, list):
                section["content"] = "".join([str(c) for c in content])
            elif isinstance(content, dict):
                section["content"] = json.dumps(content)
            elif not isinstance(content, str):
                section["content"] = str(content)
            
            fixed_sections.append(section)
        
        page["sections"] = fixed_sections
        fixed_pages.append(page)
    
    data["pages"] = fixed_pages
    return data


def validate_and_fix(raw_text: str) -> tuple:
    """
    Parse, validate, and auto-fix JSON from LLM output.
    Returns (data, errors) where data is the fixed dict and errors is a list of any remaining issues.
    """
    from generate import clean_json_output
    
    try:
        cleaned = clean_json_output(raw_text)
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}")
        return None, [f"Invalid JSON: {str(e)}"]
    
    # Auto-fix first
    data = auto_fix_json(data)
    
    # Then validate
    is_valid, errors = validate_website_json(data)
    
    if not is_valid:
        logger.warning(f"Validation issues after auto-fix: {errors}")
    
    return data, errors
