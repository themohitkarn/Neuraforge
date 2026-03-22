import random

class DesignSpec:
    def __init__(self, theme_name, primary_color, secondary_color, bg_color, text_color,
                 font_heading, font_body, ui_style, rounding, mood, accent_color):
        self.theme_name = theme_name
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.bg_color = bg_color
        self.text_color = text_color
        self.font_heading = font_heading
        self.font_body = font_body
        self.ui_style = ui_style
        self.rounding = rounding
        self.mood = mood
        self.accent_color = accent_color
        
    def to_dict(self):
        return {
            "theme_name": self.theme_name,
            "mood": self.mood,
            "colors": {
                "primary": self.primary_color,
                "secondary": self.secondary_color,
                "accent": self.accent_color,
                "background": self.bg_color,
                "text": self.text_color
            },
            "typography": {
                "heading": self.font_heading,
                "body": self.font_body
            },
            "ui_style": self.ui_style,
            "rounding": self.rounding
        }
    
    def to_prompt_string(self):
        """Convert to a string that can be injected directly into LLM prompts."""
        return f"""DESIGN SPECIFICATION (You MUST follow this exactly):
  Theme: {self.theme_name}
  Mood: {self.mood}
  Primary Color: {self.primary_color}
  Secondary Color: {self.secondary_color}
  Accent Color: {self.accent_color}
  Background: {self.bg_color}
  Text Color: {self.text_color}
  Heading Font: {self.font_heading}
  Body Font: {self.font_body}
  UI Style: {self.ui_style}
  Border Rounding: {self.rounding}"""


class DesignEngine:
    """
    Phase 1: Generates strict design constraints for the LLM.
    Uses TRUE randomness (no seeded RNG) for maximum variety.
    """
    
    THEMES = [
        {"name": "Stark Noir", "primary": "white", "secondary": "zinc-500", "bg": "black", "text": "zinc-100", "accent": "rose-500"},
        {"name": "Cyber Neon", "primary": "fuchsia-500", "secondary": "cyan-400", "bg": "slate-950", "text": "white", "accent": "lime-400"},
        {"name": "Clean Minimal", "primary": "blue-600", "secondary": "slate-500", "bg": "white", "text": "slate-900", "accent": "sky-400"},
        {"name": "Verdant Eco", "primary": "emerald-500", "secondary": "teal-600", "bg": "stone-50", "text": "stone-800", "accent": "lime-500"},
        {"name": "Warm Corporate", "primary": "orange-500", "secondary": "amber-400", "bg": "white", "text": "slate-800", "accent": "red-500"},
        {"name": "Midnight Ocean", "primary": "indigo-500", "secondary": "blue-400", "bg": "slate-900", "text": "blue-50", "accent": "violet-400"},
        {"name": "Sunset Blaze", "primary": "rose-500", "secondary": "orange-400", "bg": "zinc-950", "text": "rose-50", "accent": "amber-500"},
        {"name": "Arctic Frost", "primary": "sky-400", "secondary": "blue-200", "bg": "slate-50", "text": "slate-800", "accent": "cyan-500"},
        {"name": "Royal Purple", "primary": "violet-600", "secondary": "purple-400", "bg": "gray-950", "text": "violet-50", "accent": "fuchsia-400"},
        {"name": "Forest Depth", "primary": "green-700", "secondary": "emerald-400", "bg": "stone-900", "text": "green-50", "accent": "yellow-500"},
        {"name": "Candy Pop", "primary": "pink-500", "secondary": "violet-400", "bg": "white", "text": "gray-800", "accent": "yellow-400"},
        {"name": "Monochrome Elite", "primary": "gray-200", "secondary": "gray-500", "bg": "gray-950", "text": "gray-100", "accent": "white"},
        {"name": "Golden Hour", "primary": "amber-500", "secondary": "yellow-300", "bg": "stone-100", "text": "stone-900", "accent": "orange-600"},
        {"name": "Electric Blue", "primary": "blue-500", "secondary": "cyan-300", "bg": "gray-900", "text": "white", "accent": "blue-300"},
        {"name": "Terracotta", "primary": "orange-700", "secondary": "amber-600", "bg": "stone-50", "text": "stone-800", "accent": "red-700"},
    ]
    
    FONT_PAIRS = [
        ("Inter", "Inter"),
        ("Playfair Display", "Source Sans Pro"),
        ("Space Grotesk", "Outfit"),
        ("Oswald", "Roboto"),
        ("Plus Jakarta Sans", "Inter"),
        ("Bebas Neue", "Poppins"),
        ("Archivo Black", "Work Sans"),
        ("DM Sans", "DM Serif Display"),
        ("Montserrat", "Lora"),
        ("Satoshi", "Cabinet Grotesk"),
        ("Clash Display", "General Sans"),
    ]
    
    UI_STYLES = [
        "Glassmorphism (heavy backdrop-blur-xl, bg-white/5, semi-transparent borders, border-white/10)",
        "Neumorphism (soft drop shadows, rounded edges, muted bg tones, shadow-inner + shadow-lg)",
        "Brutalism (stark high-contrast borders, solid box shadows, sharp corners, bold typography)",
        "Minimalist (extreme whitespace, hairline dividers, understated color, typographic focus)",
        "Gradient Mesh (vibrant gradient backgrounds, mesh-like color blends, floating elements)",
        "Retro Pixel (pixel-art borders, retro color palettes, blocky layouts, monospace fonts)",
        "Organic Flow (rounded blob shapes, natural curves, warm tones, hand-drawn feel)",
        "Futuristic HUD (grid overlays, neon outlines, tech-inspired decorations, dark bg)",
    ]
    
    ROUNDING = [
        "rounded-none",
        "rounded-sm",
        "rounded-md",
        "rounded-lg",
        "rounded-xl",
        "rounded-2xl",
        "rounded-3xl",
        "rounded-full",
    ]
    
    MOODS = [
        "futuristic and cutting-edge",
        "organic and natural",
        "retro and nostalgic",
        "luxurious and premium",
        "playful and vibrant",
        "corporate and professional",
        "artistic and experimental",
        "dark and mysterious",
        "clean and zen-like",
        "bold and rebellious",
    ]
    
    @staticmethod
    def process(prompt: str, design_seed: int = None) -> DesignSpec:
        """Generate a design spec. Uses TRUE randomness — no seed."""
        prompt_lower = prompt.lower()
        
        # Keyword overrides for theme
        selected_theme = None
        if "dark" in prompt_lower or "black" in prompt_lower:
            dark_themes = [t for t in DesignEngine.THEMES if "950" in t["bg"] or "900" in t["bg"] or t["bg"] == "black"]
            selected_theme = random.choice(dark_themes)
        elif "neon" in prompt_lower or "cyber" in prompt_lower:
            selected_theme = DesignEngine.THEMES[1]
        elif "eco" in prompt_lower or "green" in prompt_lower or "nature" in prompt_lower:
            selected_theme = DesignEngine.THEMES[3]
        elif "blue" in prompt_lower or "ocean" in prompt_lower:
            selected_theme = DesignEngine.THEMES[5]
        elif "pink" in prompt_lower or "candy" in prompt_lower:
            selected_theme = DesignEngine.THEMES[10]
        elif "gold" in prompt_lower or "luxury" in prompt_lower:
            selected_theme = DesignEngine.THEMES[12]
            
        if not selected_theme:
            selected_theme = random.choice(DesignEngine.THEMES)
            
        font_pair = random.choice(DesignEngine.FONT_PAIRS)
        ui_style = random.choice(DesignEngine.UI_STYLES)
        rounding = random.choice(DesignEngine.ROUNDING)
        mood = random.choice(DesignEngine.MOODS)
        
        # Keyword overrides for UI style
        if "glass" in prompt_lower:
            ui_style = DesignEngine.UI_STYLES[0]
        elif "brutal" in prompt_lower:
            ui_style = DesignEngine.UI_STYLES[2]
            rounding = "rounded-none"
        elif "retro" in prompt_lower:
            ui_style = DesignEngine.UI_STYLES[5]
        elif "organic" in prompt_lower:
            ui_style = DesignEngine.UI_STYLES[6]
        
        return DesignSpec(
            theme_name=selected_theme["name"],
            primary_color=selected_theme["primary"],
            secondary_color=selected_theme["secondary"],
            bg_color=selected_theme["bg"],
            text_color=selected_theme["text"],
            accent_color=selected_theme.get("accent", "sky-400"),
            font_heading=font_pair[0],
            font_body=font_pair[1],
            ui_style=ui_style,
            rounding=rounding,
            mood=mood
        )
