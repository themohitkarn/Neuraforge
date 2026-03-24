import json
from types import SimpleNamespace

from modules.ai_generator.agent_graph import GroqWebsiteGenerationGraph


class _FakeLLM:
    def __init__(self, responder):
        self._responder = responder

    def invoke(self, _messages):
        return SimpleNamespace(content=self._responder())


class _Factory:
    def __init__(self, review_payload, builder_payloads):
        self.review_payload = review_payload
        self.builder_payloads = list(builder_payloads)
        self.builder_calls = 0

    def __call__(self, model_name):
        if model_name == "review-model":
            return _FakeLLM(lambda: self.review_payload)

        def _builder_response():
            self.builder_calls += 1
            if self.builder_payloads:
                return self.builder_payloads.pop(0)
            return '{"website_name":"Fallback","framework":"tailwind","pages":[],"files":[]}'

        return _FakeLLM(_builder_response)


def _review_json():
    return json.dumps(
        {
            "normalized_intent": "Create a premium SaaS landing page.",
            "target_audience": "startup founders",
            "design_direction": "clean modern glassmorphism",
            "required_pages": 3,
            "required_sections": ["hero", "features", "pricing", "footer"],
            "constraints": ["responsive", "fast loading"],
            "rewritten_prompt": "Build a premium SaaS landing page with hero, feature grid, pricing cards, and footer.",
        }
    )


def _rich_section(title: str, body: str, order: int):
    return {
        "name": title,
        "content": (
            "<section class=\"py-16 px-8 bg-slate-950 text-white\">"
            f"<div class=\"max-w-5xl mx-auto\"><h2 class=\"text-4xl font-bold mb-4\">{title}</h2>"
            f"<p class=\"text-slate-300 leading-8 text-lg\">{body}</p>"
            "<div class=\"mt-8 grid md:grid-cols-2 gap-6\">"
            "<article class=\"rounded-2xl p-6 bg-slate-900/60 border border-indigo-500/30 shadow-xl\">"
            "<h3 class=\"text-xl font-semibold mb-2\">Outcome</h3>"
            "<p class=\"text-slate-300\">High-fidelity UI with polished interactions and conversion-focused content.</p>"
            "</article>"
            "<article class=\"rounded-2xl p-6 bg-slate-900/60 border border-indigo-500/30 shadow-xl\">"
            "<h3 class=\"text-xl font-semibold mb-2\">Impact</h3>"
            "<p class=\"text-slate-300\">Performance-first implementation, responsive layouts, and premium visual direction.</p>"
            "</article></div></div></section>"
        ),
        "order": order,
    }


def _valid_builder_json():
    return json.dumps(
        {
            "website_name": "LaunchPad",
            "framework": "tailwind",
            "pages": [
                {
                    "name": "Home",
                    "slug": "home",
                    "sections": [
                        _rich_section("Hero", "LaunchPad helps ambitious teams ship credible products with premium design systems, persuasive copywriting, and fast iteration loops that shorten time to market.", 0),
                        _rich_section("Features", "Explore modular generation, structured content systems, and visual refinement controls designed for real business websites rather than generic demos.", 1),
                        _rich_section("Pricing", "Choose plans built for solo builders, startup teams, and agencies that need repeatable quality with measurable output improvements.", 2),
                    ],
                },
                {
                    "name": "Projects",
                    "slug": "projects",
                    "sections": [
                        _rich_section("Case Studies", "Dive into detailed project snapshots showing strategy, design decisions, and measurable outcomes with concise storytelling.", 0),
                        _rich_section("Build Process", "Understand discovery, wireframing, visual design, and launch workflows with transparent milestones and deliverables.", 1),
                    ],
                },
                {
                    "name": "Contact",
                    "slug": "contact",
                    "sections": [
                        _rich_section("Contact Form", "Start a project conversation with clear timelines, budget framing, and scope guidance for a faster kickoff.", 0),
                        _rich_section("FAQ", "Get practical answers about delivery timelines, revisions, stack choices, and deployment handoff expectations.", 1),
                    ],
                }
            ],
            "files": [{"path": "README.md", "content": "# LaunchPad"}],
        }
    )


def _invalid_builder_json():
    return json.dumps(
        {
            "website_name": "Broken",
            "framework": "tailwind",
            "pages": [
                {
                    "name": "Home",
                    "slug": "home",
                    "sections": [{"name": "Hero", "content": "short", "order": 0}],
                }
            ],
            "files": [],
        }
    )


def _local_asset_builder_json():
    return json.dumps(
        {
            "website_name": "AssetSite",
            "framework": "tailwind",
            "pages": [
                {
                    "name": "Home",
                    "slug": "home",
                    "sections": [
                        {
                            "name": "Hero",
                            "content": (
                                "<section class=\"py-16 px-8 bg-slate-950 text-white\">"
                                "<div class=\"max-w-5xl mx-auto\"><img src=\"assets/about.jpg\" alt=\"about\" class=\"rounded-2xl mb-6\">"
                                "<h1 class=\"text-5xl font-bold mb-4\">Modern Portfolio</h1>"
                                "<p class=\"text-slate-300 text-lg\">A polished portfolio direction with detailed storytelling, impactful visuals, and conversion-ready structure.</p>"
                                "</div></section>"
                            ),
                            "order": 0,
                        },
                        _rich_section("Highlights", "A refined design language with strong typography and layered depth effects keeps the experience distinctive.", 1),
                        _rich_section("CTA", "Encourage visitors to book discovery calls with frictionless actions and confidence-building trust signals.", 2),
                    ],
                },
                {
                    "name": "Projects",
                    "slug": "projects",
                    "sections": [
                        _rich_section("Selected Work", "A curated project gallery with metrics, timeline context, and implementation details.", 0),
                        _rich_section("Client Outcomes", "Quantified improvements across acquisition, engagement, and conversion performance.", 1),
                    ],
                },
                {
                    "name": "Contact",
                    "slug": "contact",
                    "sections": [
                        _rich_section("Reach Out", "A concise form flow and scheduling links keep communication clear and professional.", 0),
                        _rich_section("Social Proof", "Testimonials and endorsement snippets reinforce credibility before conversion.", 1),
                    ],
                }
            ],
            "files": [],
        }
    )


def _generic_builder_json():
    return json.dumps(
        {
            "website_name": "Prime Portfolio",
            "framework": "tailwind",
            "pages": [
                {
                    "name": "Home",
                    "slug": "home",
                    "sections": [
                        _rich_section("Hero", "AI/ML Engineer building robust machine learning products for enterprise deployment.", 0),
                        {
                            "name": "Projects",
                            "content": (
                                "<section class=\"py-16 px-8 bg-slate-950 text-white\">"
                                "<div class=\"max-w-5xl mx-auto\"><h2 class=\"text-4xl font-bold mb-6\">Projects</h2>"
                                "<div class=\"grid md:grid-cols-3 gap-5\">"
                                "<article class=\"rounded-2xl bg-slate-900/60 p-6\"><h3 class=\"text-2xl font-bold\">Featured Project</h3><p>Problem Statement:</p><p>Project description</p></article>"
                                "<article class=\"rounded-2xl bg-slate-900/60 p-6\"><h3 class=\"text-2xl font-bold\">Project 2</h3><p>Problem Statement:</p><p>Project description</p></article>"
                                "<article class=\"rounded-2xl bg-slate-900/60 p-6\"><h3 class=\"text-2xl font-bold\">Project 3</h3><p>Problem Statement:</p><p>Project description</p></article>"
                                "</div></div></section>"
                            ),
                            "order": 1,
                        },
                        {
                            "name": "Skills",
                            "content": (
                                "<section class=\"py-16 px-8 bg-slate-950 text-white\">"
                                "<div class=\"max-w-5xl mx-auto\"><h2 class=\"text-4xl font-bold mb-6\">Skills</h2>"
                                "<p>Skill 1</p><p>Skill description</p><p>Core Capability</p>"
                                "</div></section>"
                            ),
                            "order": 2,
                        },
                    ],
                },
                {
                    "name": "Projects",
                    "slug": "projects",
                    "sections": [
                        _rich_section("Case Studies", "Project 1 and project 2 delivered measurable gains in model throughput.", 0),
                        _rich_section("Experience", "Experience details with placeholder content for now.", 1),
                    ],
                },
                {
                    "name": "Contact",
                    "slug": "contact",
                    "sections": [
                        _rich_section("Reach Out", "email@example.com | linkedin.com/in/example | github.com/example", 0),
                        _rich_section("Availability", "Open to collaborations on applied AI products.", 1),
                    ],
                },
            ],
            "files": [],
        }
    )


def _weak_portfolio_builder_json():
    return json.dumps(
        {
            "website_name": "AI Engineer Portfolio",
            "framework": "tailwind",
            "pages": [
                {
                    "name": "Home",
                    "slug": "home-page",
                    "sections": [
                        {
                            "name": "Hero",
                            "content": (
                                "<section class=\"py-24 px-8 bg-gradient-to-r from-indigo-500 to-violet-500 text-white\">"
                                "<h1 class=\"text-6xl font-bold\">Samantha Lee</h1>"
                                "<p class=\"text-4xl mt-4\">AI/ML Engineer & Data Scientist</p>"
                                "<p class=\"text-3xl mt-4\">Building intelligent systems that drive business results</p>"
                                "</section>"
                            ),
                            "order": 0,
                        }
                    ],
                },
                {
                    "name": "Projects",
                    "slug": "ai-ml-projects",
                    "sections": [
                        {
                            "name": "Projects",
                            "content": (
                                "<section class=\"py-12 px-6 bg-slate-900 text-white\">"
                                "<h2 class=\"text-4xl\">Predictive Maintenance for Industrial Equipment</h2>"
                                "<p class=\"text-2xl\">Built a predictive model using machine learning algorithms and sensor data.</p>"
                                "<img src=\"/assets/industrial-equipment.jpg\" alt=\"Industrial Equipment\">"
                                "</section>"
                            ),
                            "order": 0,
                        }
                    ],
                },
                {
                    "name": "About",
                    "slug": "about-me",
                    "sections": [
                        {
                            "name": "About Me",
                            "content": (
                                "<section class=\"py-10 px-8 bg-gray-800 text-white\">"
                                "<h2 class=\"text-5xl\">About Me</h2>"
                                "<p class=\"text-3xl\">Highly motivated and experienced AI/ML engineer.</p>"
                                "</section>"
                            ),
                            "order": 0,
                        }
                    ],
                },
            ],
            "files": [],
        }
    )


def test_graph_returns_valid_output_and_review_data():
    factory = _Factory(_review_json(), [_valid_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
    )

    output, error, debug = graph.generate(
        raw_prompt="Make a startup website",
        framework="tailwind",
        design_spec=None,
        layout_spec=None,
    )

    assert error is None
    assert output is not None
    assert output["website_name"] == "LaunchPad"
    assert debug["review_data"]["target_audience"] == "startup founders"
    assert "Generate at least 3 distinct pages." in debug["reviewed_prompt"]
    assert factory.builder_calls == 1


def test_graph_retries_once_after_validation_failure():
    factory = _Factory(_review_json(), [_invalid_builder_json(), _valid_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
    )

    output, error, debug = graph.generate(
        raw_prompt="Build a modern website",
        framework="tailwind",
    )

    assert error is None
    assert output is not None
    assert output["website_name"] == "LaunchPad"
    assert factory.builder_calls == 2
    assert debug["retry_count"] == 1


def test_graph_stops_after_max_correction_retries():
    factory = _Factory(_review_json(), [_invalid_builder_json(), _invalid_builder_json(), _invalid_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
        max_correction_retries=2,
    )

    output, error, debug = graph.generate(
        raw_prompt="Need a portfolio site",
        framework="tailwind",
    )

    assert output is None
    assert error is not None
    assert "failed after 2 correction retries" in error.lower()
    assert factory.builder_calls == 3
    assert debug["retry_count"] >= 3


def test_graph_retries_when_local_asset_reference_missing():
    factory = _Factory(_review_json(), [_local_asset_builder_json(), _valid_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
    )

    output, error, debug = graph.generate(
        raw_prompt="Need a clean portfolio site",
        framework="tailwind",
    )

    assert error is None
    assert output is not None
    assert output["website_name"] == "AssetSite"
    assert factory.builder_calls == 1
    assert debug["retry_count"] == 0


def test_graph_auto_repairs_generic_placeholder_copy_without_retry():
    factory = _Factory(_review_json(), [_generic_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
    )

    output, error, debug = graph.generate(
        raw_prompt="Build a premium AI engineer portfolio website",
        framework="tailwind",
    )

    assert error is None
    assert output is not None
    assert factory.builder_calls == 1
    assert debug["retry_count"] == 0

    bad_phrases = [
        "skill description",
        "core capability",
        "email@example.com",
        "linkedin.com/in/example",
        "github.com/example",
    ]

    rendered_text = " ".join(
        GroqWebsiteGenerationGraph._extract_visible_text(section["content"]).lower()
        for page in output["pages"]
        for section in page["sections"]
    )
    for phrase in bad_phrases:
        assert phrase not in rendered_text


def test_graph_enforces_portfolio_quality_from_strict_prompt():
    factory = _Factory(_review_json(), [_weak_portfolio_builder_json()])
    graph = GroqWebsiteGenerationGraph(
        review_model="review-model",
        builder_model="builder-model",
        llm_factory=factory,
    )

    strict_prompt = """
Build a modern, high-impact 3-page portfolio website for an AI/ML Engineer.
Name: Mohit Karan
Title: "AI/ML Engineer | Building Intelligent Systems"
Tagline: Focused on real-world ML systems, LLMs, and scalable AI solutions
"""

    output, error, debug = graph.generate(
        raw_prompt=strict_prompt,
        framework="tailwind",
    )

    assert error is None
    assert output is not None
    assert factory.builder_calls == 1
    assert debug["retry_count"] == 0

    def _find_page(*keywords):
        for page in output["pages"]:
            candidate = f"{page.get('name', '')} {page.get('slug', '')}".lower()
            if any(keyword in candidate for keyword in keywords):
                return page
        return None

    home_page = _find_page("home", "landing")
    projects_page = _find_page("project", "work", "case")
    about_page = _find_page("about", "experience", "profile")

    assert home_page is not None
    assert projects_page is not None
    assert about_page is not None

    home_text = " ".join(
        GroqWebsiteGenerationGraph._extract_visible_text(section["content"]).lower()
        for section in home_page["sections"]
    )
    assert "mohit karan" in home_text
    assert "building intelligent systems" in home_text
    assert "view projects" in home_text

    projects_text = " ".join(
        GroqWebsiteGenerationGraph._extract_visible_text(section["content"]).lower()
        for section in projects_page["sections"]
    )
    for required_phrase in [
        "problem statement",
        "approach",
        "architecture / pipeline",
        "tech stack",
        "results",
        "github",
    ]:
        assert required_phrase in projects_text

    about_text = " ".join(
        GroqWebsiteGenerationGraph._extract_visible_text(section["content"]).lower()
        for section in about_page["sections"]
    )
    for required_phrase in ["engineering mindset", "experience", "achievements", "contact"]:
        assert required_phrase in about_text
