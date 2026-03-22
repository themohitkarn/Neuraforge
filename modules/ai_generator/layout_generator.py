import random

class LayoutSpec:
    def __init__(self, page_count: int, pages_blueprint: list, layout_variation: str):
        self.page_count = page_count
        self.pages_blueprint = pages_blueprint
        self.layout_variation = layout_variation
        
    def to_dict(self):
        return {
            "layout_variation": self.layout_variation,
            "page_count": self.page_count,
            "pages": self.pages_blueprint
        }
    
    def to_prompt_string(self):
        pages_str = ""
        for p in self.pages_blueprint:
            sections_str = " -> ".join(p["sections"])
            pages_str += f"\n  Page '{p['page_name']}' (/{p['page_slug']}): {sections_str}"
        
        return f"""LAYOUT SPECIFICATION (You MUST follow this):
  Overall Layout Style: {self.layout_variation}
  Total Pages: {self.page_count}
  Page Blueprints:{pages_str}

  CRITICAL: Use the '{self.layout_variation}' layout pattern. Do NOT fall back to standard hero+features+pricing."""

class LayoutGenerator:
    """
    Phase 2: Generates dynamic, non-repetitive layout blueprints.
    Uses TRUE randomness for maximum variety.
    """
    
    # Layout variation archetypes — the core innovation
    LAYOUT_VARIATIONS = [
        "bento grid (asymmetric card grid with varying sizes, like Apple's design)",
        "zigzag storytelling (alternating left-right content blocks with images)",
        "horizontal scroll showcase (full-width horizontal scrolling sections)",
        "split screen (50/50 or 60/40 vertical splits between content and media)",
        "magazine editorial (newspaper-style multi-column layouts with pull quotes)",
        "asymmetrical grid (off-center, overlapping elements, artistic placement)",
        "fullscreen slides (each section is a full viewport slide)",
        "masonry waterfall (Pinterest-style staggered grid layout)",
        "timeline narrative (vertical timeline connecting sections chronologically)",
        "dashboard-style cards (data-centric layout with metric cards and charts)",
        "immersive parallax (layered depth scrolling with foreground/background)",
        "modular blocks (Lego-like stackable content blocks with clear boundaries)",
        "floating islands (content blocks floating on a gradient/image background)",
        "overlapping layers (sections that overlap each other with z-index depth)",
    ]
    
    # Section types — NOT fixed order, shuffled per generation    
    SECTION_POOL_HERO = [
        "Cinematic Full-Screen Hero with overlay text",
        "Split Hero (image left, text right)",
        "Centered Hero with particle/gradient background",
        "Asymmetric Hero with off-center typography",
        "Video Background Hero with floating CTA",
        "Minimal Text Hero with huge typography",
        "3D Perspective Hero with tilted cards",
        "Animated Gradient Hero with morphing shapes",
    ]
    
    SECTION_POOL_CONTENT = [
        "Bento Grid Features (mixed card sizes)",
        "Icon Card Grid (3 or 4 columns with icons)",
        "Zigzag Feature Blocks (alternating image/text)",
        "Stats Counter Bar with animated numbers",
        "Comparison Table (side-by-side tiers)",
        "Process Timeline (numbered steps)",
        "Accordion FAQ Section",
        "Tabbed Content Panels",
        "Floating Image Gallery with lightbox",
        "Masonry Portfolio Grid",
        "Team Carousel with hover bios",
        "Client Logo Cloud with hover effects",
        "Interactive Map Section",
        "Video Showcase with thumbnails",
        "Scrolling Marquee / Ticker",
    ]
    
    SECTION_POOL_SOCIAL = [
        "Testimonial Carousel with star ratings",
        "Review Grid (2x2 or 3x3 cards)",
        "Case Study Spotlight with metrics",
        "Social Media Feed Embed",
        "User-Generated Content Mosaic",
        "Quote Slider with avatars",
    ]
    
    SECTION_POOL_CALL_TO_ACTION = [
        "Simple CTA Button",
        "CTA with Gradient Background",
        "CTA with Icon",
        "CTA with Countdown Timer",
        "CTA with Testimonial Quote",
    ]
    
    def generate_layout(self, page_count: int):
        layout_variation = random.choice(self.LAYOUT_VARIATIONS)
        pages_blueprint = []
        
        for i in range(page_count):
            page_name = f"Page {i+1}"
            page_slug = f"page-{i+1}"
            sections = []
            
            if i == 0:
                sections.append(random.choice(self.SECTION_POOL_HERO))
            
            sections.append(random.choice(self.SECTION_POOL_CONTENT))
            sections.append(random.choice(self.SECTION_POOL_SOCIAL))
            sections.append(random.choice(self.SECTION_POOL_CALL_TO_ACTION))
            
            pages_blueprint.append({
                "page_name": page_name,
                "page_slug": page_slug,
                "sections": sections
            })
        
        return LayoutSpec(page_count, pages_blueprint, layout_variation)

