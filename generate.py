import json
import random
import re
import logging

logger = logging.getLogger(__name__)

# ============================================================
# CLEAN JSON UTILITY
# ============================================================

def clean_json_output(raw_text):
    """
    Extract and repair JSON from potentially malformed LLM output.
    Handles markdown fences, trailing commas, and unbalanced brackets.
    """
    if not raw_text or not raw_text.strip():
        return "{}"
    
    cleaned = raw_text.strip()
    
    # Remove markdown code fences
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0]
    elif "```" in cleaned:
        parts = cleaned.split("```")
        if len(parts) >= 3:
            cleaned = parts[1]
        elif len(parts) >= 2:
            cleaned = parts[1]
    
    cleaned = cleaned.strip()
    
    # Find start of JSON
    start_idx = cleaned.find('{')
    if start_idx == -1:
        return "{}"
    
    cleaned = cleaned[start_idx:]
    
    # Remove trailing commas before } or ]
    import re as _re
    cleaned = _re.sub(r',\s*([}\]])', r'\1', cleaned)
    
    # Balance brackets
    open_curly = cleaned.count('{')
    close_curly = cleaned.count('}')
    open_square = cleaned.count('[')
    close_square = cleaned.count(']')
    
    if open_square > close_square:
        cleaned += ']' * (open_square - close_square)
    if open_curly > close_curly:
        cleaned += '}' * (open_curly - close_curly)
    
    return cleaned


# ============================================================
# GEMINI GENERATOR
# ============================================================

class GeminiGenerator:
    """Uses Google's Gemini API to generate unique website templates."""
    
    def __init__(self):
        import google.generativeai as genai
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set in the .env file.")
            
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')

    def generate(self, prompt="", max_length=None, temperature=1.0, top_k=None,
                 framework="tailwind", user_preferences=None, design_seed=0,
                 design_spec=None, layout_spec=None):
        """Generate website JSON using Gemini with injected design/layout specs."""
        
        print(f"[Gemini] Generating {framework} website (Temp: {temperature})...")
        
        # Build design injection
        design_injection = ""
        if design_spec and hasattr(design_spec, 'to_prompt_string'):
            design_injection = design_spec.to_prompt_string()
        elif isinstance(design_spec, dict):
            design_injection = f"DESIGN SPEC: {json.dumps(design_spec, indent=2)}"
        
        layout_injection = ""
        if layout_spec and hasattr(layout_spec, 'to_prompt_string'):
            layout_injection = layout_spec.to_prompt_string()
        elif isinstance(layout_spec, dict):
            layout_injection = f"LAYOUT SPEC: {json.dumps(layout_spec, indent=2)}"
        
        system_instructions = f"""You are NEURAFORGE AI — an experimental, award-winning Design Agency AI.
You generate UNIQUE, NEVER-REPEATED website structures and code.

ABSOLUTE RULES:
1. Output ONLY raw, valid JSON. No markdown, no code fences, no explanations.
2. NEVER generate the same layout twice. Every generation must be structurally different.
3. NEVER use the standard "Hero → Features → Pricing → CTA → Footer" pattern unless explicitly asked.
4. You MUST follow the Design Specification and Layout Specification below.

JSON SCHEMA:
{{
  "website_name": "String",
  "framework": "{framework}",
  "pages": [
    {{
      "name": "String",
      "slug": "String",
      "sections": [
        {{
          "name": "String (descriptive section name)",
          "content": "COMPLETE HTML string with {framework} classes for this section",
          "order": Integer
        }}
      ]
    }}
  ],
  "files": []
}}

{design_injection}

{layout_injection}

DESIGN PHILOSOPHY:
- Think like a Dribbble/Awwwards winning designer
- Massive hero typography (text-6xl md:text-8xl font-black tracking-tighter)
- Generous spacing (py-20 md:py-32 px-6 md:px-12)
- Advanced effects: backdrop-blur-xl, gradients, shadows, transforms
- Every interactive element MUST have hover states and transitions
- Responsive design with mobile-first approach
- All buttons must have onclick="alert('Action!')" or similar
- Use high-quality Unsplash images: https://images.unsplash.com/photo-ID?auto=format&fit=crop&w=800&q=80
- Navigation links between pages must use correct slugs

ANTI-REPETITION ENFORCEMENT:
- Vary section heights, widths, and padding dramatically
- Mix column counts (2, 3, 4, asymmetric)
- Alternate between image-heavy and text-heavy sections
- Use different background treatments per section (solid, gradient, image, pattern)
"""

        full_prompt = f"{system_instructions}\n\nUSER REQUEST:\n{prompt}"

        generation_config = {
            "temperature": temperature,
            "top_p": 0.95,
        }

        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )
        
        return response.text


# ============================================================
# GROQ GENERATOR
# ============================================================

class GroqGenerator:
    
    def __init__(self):
        from core.groq_llm import GroqLLM
        self.llm = GroqLLM(model="llama-3.3-70b-versatile")

    def generate(self, prompt="", max_length=None, temperature=1.0,
                 framework="tailwind", user_preferences=None, design_seed=0,
                 design_spec=None, layout_spec=None):
        """Generate website JSON using Groq with injected design/layout specs."""
        
        print(f"[Groq] Generating {framework} website (Temp: {temperature})...")
        
        # Build design injection
        design_injection = ""
        if design_spec and hasattr(design_spec, 'to_prompt_string'):
            design_injection = design_spec.to_prompt_string()
        elif isinstance(design_spec, dict):
            design_injection = f"DESIGN SPEC: {json.dumps(design_spec, indent=2)}"
        
        layout_injection = ""
        if layout_spec and hasattr(layout_spec, 'to_prompt_string'):
            layout_injection = layout_spec.to_prompt_string()
        elif isinstance(layout_spec, dict):
            layout_injection = f"LAYOUT SPEC: {json.dumps(layout_spec, indent=2)}"
        
        # Auto-detect page count
        page_match = re.search(r'(\d+)\s*[-\s]?page', prompt.lower())
        page_hint = ""
        if page_match:
            num_pages = int(page_match.group(1))
            page_hint = f"\nThe user wants EXACTLY {num_pages} pages."

        system_prompt = f"""You are NEURAFORGE — an experimental, elite Design AI.
You generate UNIQUE, NEVER-REPEATED website structures. Every output must be structurally different from any previous one.

CRITICAL RULES:
1. Output ONLY raw, valid JSON. No markdown, no code fences, no explanations.
2. NEVER generate the same layout twice.
3. NEVER default to "Hero → Features → Pricing → CTA → Footer" unless explicitly asked.
4. Follow the Design and Layout Specifications EXACTLY.

JSON SCHEMA:
{{
  "website_name": "String",
  "framework": "{framework}",
  "pages": [
    {{
      "name": "String",
      "slug": "String",
      "sections": [
        {{
          "name": "String",
          "content": "Complete HTML/{framework} code for this section",
          "order": Integer (0, 1, 2...)
        }}
      ]
    }}
  ],
  "files": []
}}

{design_injection}

{layout_injection}

{page_hint}

DESIGN RULES:
- Massive hero typography (text-6xl md:text-8xl font-black tracking-tighter)
- Generous spacing (py-20 md:py-32 px-6 lg:px-16)
- Advanced effects: backdrop-blur-xl, gradients, box-shadows, transforms
- Every button/card MUST have hover transitions (transition-all duration-500 hover:-translate-y-2)
- Responsive mobile-first design
- Unsplash images: https://images.unsplash.com/photo-ID?auto=format&fit=crop&w=800&q=80
- All action buttons: onclick="alert('Action!')"
- Nav links must use correct page slugs

FAIL CONDITIONS (your output is REJECTED if):
- Same hero layout as standard templates
- Same section order as standard landing pages
- Generic boilerplate without personality
- Missing hover states / transitions"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Build a unique website for: {prompt}"}
        ]
        
        return self.llm.invoke_json(messages, temperature=temperature, max_tokens=8192)


# ============================================================
# AI ENGINE ROUTER
# ============================================================

class AIEngineRouter:
    """
    Multi-engine LLM router with smart task routing.
    Gemini for UI generation, Groq for JSON structure.
    """
    
    def __init__(self):
        self.groq_gen = GroqGenerator()
        self.gemini_gen = None
        self.local_gen = None

    def generate(self, engine="groq", prompt="", framework="tailwind",
                 user_preferences=None, temperature=1.0,
                 design_spec=None, layout_spec=None):
        
        print(f"[AIEngineRouter] Engine: {engine}, Temp: {temperature}")

        try:
            if engine == "gemini":
                if not self.gemini_gen:
                    self.gemini_gen = GeminiGenerator()
                return self.gemini_gen.generate(
                    prompt=prompt, framework=framework,
                    temperature=temperature,
                    design_spec=design_spec, layout_spec=layout_spec
                )

            elif engine == "auto":
                # Smart routing: randomly pick for variety
                chosen = random.choice(["groq", "gemini"])
                print(f"[AIEngineRouter] Auto-selected: {chosen}")
                return self.generate(
                    engine=chosen, prompt=prompt, framework=framework,
                    temperature=temperature,
                    design_spec=design_spec, layout_spec=layout_spec
                )

            elif engine == "local":
                if not self.local_gen:
                    self.local_gen = TemplateGenerator()
                return self.local_gen.generate(prompt=prompt, temperature=temperature)

            else:  # Default: groq
                return self.groq_gen.generate(
                    prompt=prompt, framework=framework,
                    temperature=temperature,
                    design_spec=design_spec, layout_spec=layout_spec
                )

        except Exception as e:
            logger.error(f"Engine '{engine}' failed: {e}")
            print(f"Engine '{engine}' failed: {e}. Falling back to Groq.")
            return self.groq_gen.generate(
                prompt=prompt, framework=framework,
                temperature=temperature,
                design_spec=design_spec, layout_spec=layout_spec
            )


# ============================================================
# LEGACY: LOCAL TEMPLATE GENERATOR (kept for fallback)
# ============================================================

class TemplateGenerator:
    """Local model generator — kept for offline fallback."""
    
    def __init__(self, model_path="template_generator_model.pth", dataset_path="html_dataset.json"):
        import torch
        from tokenizer import TemplateTokenizer # type: ignore
        from ml.model_architecture import TemplateGeneratorModel
        
        self.tokenizer = TemplateTokenizer()
        self.tokenizer.fit_on_dataset(dataset_path)
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = TemplateGeneratorModel(
            vocab_size=self.tokenizer.vocab_size,
            d_model=512, nhead=8, num_layers=6, max_seq_length=512
        ).to(self.device)
        
        from core.groq_llm import GroqLLM
        self.llm = GroqLLM()
        
        if model_path == "template_generator_model.pth":
            import os
            if os.path.exists("template_generator_best.pth"):
                model_path = "template_generator_best.pth"
        
        try:
            state_dict = torch.load(model_path, map_location=self.device, weights_only=True)
            new_state_dict = {}
            for k, v in state_dict.items():
                name = k[7:] if k.startswith('module.') else k
                new_state_dict[name] = v
            self.model.load_state_dict(new_state_dict)
            print(f"Loaded trained weights from {model_path}.")
        except FileNotFoundError:
            print(f"Warning: No weights at {model_path}.")
        
        self.model.eval()

    def generate(self, prompt="", max_length=None, temperature=0.9,
                 top_k=None, framework="tailwind",
                 user_preferences=None, design_seed=None):
        
        messages = [
            {"role": "system", "content": "You are NEURAFORGE AI. Generate a website in JSON format."},
            {"role": "user", "content": prompt}
        ]
        
        try:
            return self.llm.invoke_json(messages, temperature=temperature, max_tokens=8192)
        except AttributeError:
            from core.groq_llm import GroqLLM
            llm = GroqLLM()
            return llm.invoke_json(messages, temperature=temperature, max_tokens=8192)


# ============================================================
# UTILITY
# ============================================================

def detect_and_setup(filename):
    ext = filename.split('.')[-1]
    mapping = {
        "py": {"mode": "python", "interpreter": "python3.11"},
        "js": {"mode": "javascript"},
        "html": {"mode": "htmlmixed", "preview": True},
        "css": {"mode": "css"},
        "json": {"mode": "javascript"}
    }
    return mapping.get(ext, {"mode": "text"})
