# modules/website/feature_routes.py
# Advanced features: templates, components, SEO, deploy, collaborate, version history

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from database import db
from database.models.website import Website
from database.models.page import Page
from database.models.section import Section
from database.models.snapshot import SectionSnapshot
from database.models.shared_access import SharedAccess
from database.models.user import User
from modules.auth.token_service import TokenService

features_bp = Blueprint("features", __name__)


# ============================================================
# TEMPLATE GALLERY — Pre-built starter templates
# ============================================================

TEMPLATES = [
    {
        "id": "portfolio",
        "name": "Portfolio",
        "desc": "Personal portfolio with hero, about, projects, contact",
        "icon": "fas fa-briefcase",
        "color": "#6366f1",
        "prompt": "A stunning personal portfolio website with hero section, about me, skills grid, project showcase cards, and contact form. Use dark theme with purple accents."
    },
    {
        "id": "landing",
        "name": "SaaS Landing",
        "desc": "Product landing page with features, pricing, CTA",
        "icon": "fas fa-rocket",
        "color": "#10b981",
        "prompt": "A modern SaaS product landing page with hero, feature cards, pricing table (Free/Pro/Enterprise), testimonials, and call-to-action. Dark theme with green accents."
    },
    {
        "id": "ecommerce",
        "name": "E-Commerce",
        "desc": "Online store with product grid and cart UI",
        "icon": "fas fa-shopping-cart",
        "color": "#f59e0b",
        "prompt": "An e-commerce website with hero banner, product grid with cards (image, price, add to cart), categories sidebar, and footer. Dark theme with gold accents."
    },
    {
        "id": "blog",
        "name": "Blog",
        "desc": "Blog with featured posts, categories, sidebar",
        "icon": "fas fa-pen-nib",
        "color": "#ec4899",
        "prompt": "A modern blog website with featured post hero, blog post cards grid, category tags, search bar, and about author sidebar. Dark theme with pink accents."
    },
    {
        "id": "restaurant",
        "name": "Restaurant",
        "desc": "Restaurant with menu, gallery, reservations",
        "icon": "fas fa-utensils",
        "color": "#ef4444",
        "prompt": "A restaurant website with hero image, menu sections (appetizers, mains, desserts) with prices, photo gallery grid, reservation form, and location map. Dark elegant theme."
    },
    {
        "id": "agency",
        "name": "Agency",
        "desc": "Creative agency with services, team, portfolio",
        "icon": "fas fa-palette",
        "color": "#8b5cf6",
        "prompt": "A creative agency website with hero animation, services offered grid, team members section, portfolio gallery, client logos, and contact form. Dark glassmorphism theme."
    },
]


@features_bp.route("/templates")
def template_gallery():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return render_template("templates_gallery.html", templates=TEMPLATES)


@features_bp.route("/templates/use/<template_id>", methods=["POST"])
def use_template(template_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    template = next((t for t in TEMPLATES if t["id"] == template_id), None)
    if not template:
        return jsonify({"error": "Template not found"}), 404

    framework = request.form.get("framework", "tailwind")
    from modules.ai_generator.service import AIGeneratorService
    website, error = AIGeneratorService.generate_website(
        template["prompt"], session["user_id"], framework=framework
    )

    if website:
        return redirect(url_for("website_bp.ide_website", website_id=website.id))
    return jsonify({"error": error}), 500


# ============================================================
# COMPONENT LIBRARY — Drag & drop sections
# ============================================================

COMPONENTS = [
    {"id": "hero_gradient", "name": "Hero — Gradient", "category": "Hero",
     "content": '<section class="min-h-[60vh] flex items-center justify-center bg-gradient-to-br from-indigo-900 via-purple-900 to-pink-800 text-white text-center px-6"><div><h1 class="text-5xl md:text-7xl font-bold mb-4">Your Heading Here</h1><p class="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">A compelling tagline that captures attention and drives action.</p><div class="flex gap-4 justify-center"><a href="#" class="px-8 py-3 bg-white text-indigo-900 rounded-full font-semibold hover:scale-105 transition">Get Started</a><a href="#" class="px-8 py-3 border border-white/30 rounded-full hover:bg-white/10 transition">Learn More</a></div></div></section>'},
    {"id": "features_grid", "name": "Features Grid", "category": "Features",
     "content": '<section class="py-20 px-6 bg-gray-950"><div class="max-w-6xl mx-auto"><h2 class="text-3xl font-bold text-center text-white mb-12">Features</h2><div class="grid md:grid-cols-3 gap-8"><div class="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 hover:border-indigo-500/50 transition"><div class="w-12 h-12 bg-indigo-500/20 rounded-xl flex items-center justify-center mb-4"><i class="fas fa-bolt text-indigo-400"></i></div><h3 class="text-lg font-semibold text-white mb-2">Fast Performance</h3><p class="text-gray-400 text-sm">Lightning fast load times and smooth interactions.</p></div><div class="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 hover:border-green-500/50 transition"><div class="w-12 h-12 bg-green-500/20 rounded-xl flex items-center justify-center mb-4"><i class="fas fa-shield-alt text-green-400"></i></div><h3 class="text-lg font-semibold text-white mb-2">Secure</h3><p class="text-gray-400 text-sm">Enterprise-grade security for your data.</p></div><div class="bg-gray-900/50 border border-gray-800 rounded-2xl p-6 hover:border-purple-500/50 transition"><div class="w-12 h-12 bg-purple-500/20 rounded-xl flex items-center justify-center mb-4"><i class="fas fa-magic text-purple-400"></i></div><h3 class="text-lg font-semibold text-white mb-2">AI Powered</h3><p class="text-gray-400 text-sm">Intelligent features that adapt to your needs.</p></div></div></div></section>'},
    {"id": "pricing_table", "name": "Pricing Table", "category": "Pricing",
     "content": '<section class="py-20 px-6 bg-gray-950"><div class="max-w-5xl mx-auto"><h2 class="text-3xl font-bold text-center text-white mb-12">Pricing</h2><div class="grid md:grid-cols-3 gap-6"><div class="bg-gray-900/50 border border-gray-800 rounded-2xl p-8 text-center"><h3 class="text-lg font-semibold text-gray-300">Free</h3><p class="text-4xl font-bold text-white my-4">$0</p><ul class="text-gray-400 text-sm space-y-2 mb-8"><li>5 Projects</li><li>Basic Support</li><li>1GB Storage</li></ul><button class="w-full py-2 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-800 transition">Get Started</button></div><div class="bg-indigo-600/10 border-2 border-indigo-500 rounded-2xl p-8 text-center relative"><span class="absolute -top-3 left-1/2 -translate-x-1/2 bg-indigo-500 text-xs font-bold px-3 py-1 rounded-full">POPULAR</span><h3 class="text-lg font-semibold text-indigo-300">Pro</h3><p class="text-4xl font-bold text-white my-4">$19<span class="text-base text-gray-400">/mo</span></p><ul class="text-gray-400 text-sm space-y-2 mb-8"><li>Unlimited Projects</li><li>Priority Support</li><li>50GB Storage</li></ul><button class="w-full py-2 bg-indigo-600 rounded-lg text-white font-semibold hover:bg-indigo-700 transition">Upgrade</button></div><div class="bg-gray-900/50 border border-gray-800 rounded-2xl p-8 text-center"><h3 class="text-lg font-semibold text-gray-300">Enterprise</h3><p class="text-4xl font-bold text-white my-4">$49<span class="text-base text-gray-400">/mo</span></p><ul class="text-gray-400 text-sm space-y-2 mb-8"><li>Everything in Pro</li><li>Custom Integrations</li><li>Unlimited Storage</li></ul><button class="w-full py-2 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-800 transition">Contact</button></div></div></div></section>'},
    {"id": "testimonials", "name": "Testimonials", "category": "Social Proof",
     "content": '<section class="py-20 px-6 bg-gray-900"><div class="max-w-5xl mx-auto"><h2 class="text-3xl font-bold text-center text-white mb-12">What People Say</h2><div class="grid md:grid-cols-3 gap-6"><div class="bg-gray-800/50 border border-gray-700 rounded-2xl p-6"><div class="flex items-center gap-3 mb-4"><div class="w-10 h-10 bg-indigo-500 rounded-full flex items-center justify-center text-white font-bold">A</div><div><p class="text-white font-semibold text-sm">Alex Johnson</p><p class="text-gray-500 text-xs">CEO, TechCorp</p></div></div><p class="text-gray-400 text-sm">"Absolutely incredible product. Transformed our workflow completely."</p><div class="text-yellow-400 mt-3 text-sm">★★★★★</div></div><div class="bg-gray-800/50 border border-gray-700 rounded-2xl p-6"><div class="flex items-center gap-3 mb-4"><div class="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center text-white font-bold">S</div><div><p class="text-white font-semibold text-sm">Sarah Chen</p><p class="text-gray-500 text-xs">Designer</p></div></div><p class="text-gray-400 text-sm">"The best tool I\'ve used this year. Clean, fast, and intuitive."</p><div class="text-yellow-400 mt-3 text-sm">★★★★★</div></div><div class="bg-gray-800/50 border border-gray-700 rounded-2xl p-6"><div class="flex items-center gap-3 mb-4"><div class="w-10 h-10 bg-pink-500 rounded-full flex items-center justify-center text-white font-bold">M</div><div><p class="text-white font-semibold text-sm">Mike Rivera</p><p class="text-gray-500 text-xs">Freelancer</p></div></div><p class="text-gray-400 text-sm">"Saved me hours of work. The AI features are game-changing."</p><div class="text-yellow-400 mt-3 text-sm">★★★★★</div></div></div></div></section>'},
    {"id": "cta_banner", "name": "CTA Banner", "category": "Call to Action",
     "content": '<section class="py-16 px-6 bg-gradient-to-r from-indigo-600 to-purple-600"><div class="max-w-4xl mx-auto text-center"><h2 class="text-3xl md:text-4xl font-bold text-white mb-4">Ready to Get Started?</h2><p class="text-indigo-200 mb-8 text-lg">Join thousands of creators building amazing websites with AI.</p><div class="flex gap-4 justify-center"><a href="#" class="px-8 py-3 bg-white text-indigo-600 rounded-full font-semibold hover:scale-105 transition">Start Free</a><a href="#" class="px-8 py-3 border border-white/40 text-white rounded-full hover:bg-white/10 transition">Watch Demo</a></div></div></section>'},
    {"id": "contact_form", "name": "Contact Form", "category": "Contact",
     "content": '<section class="py-20 px-6 bg-gray-950"><div class="max-w-2xl mx-auto"><h2 class="text-3xl font-bold text-center text-white mb-12">Get In Touch</h2><form class="space-y-4"><div class="grid md:grid-cols-2 gap-4"><input type="text" placeholder="Your Name" class="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-white placeholder-gray-500 focus:border-indigo-500 outline-none transition"><input type="email" placeholder="Your Email" class="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-white placeholder-gray-500 focus:border-indigo-500 outline-none transition"></div><textarea rows="5" placeholder="Your Message" class="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-xl text-white placeholder-gray-500 focus:border-indigo-500 outline-none transition resize-none"></textarea><button type="submit" class="w-full py-3 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 transition">Send Message</button></form></div></section>'},
    {"id": "faq_section", "name": "FAQ Accordion", "category": "FAQ",
     "content": '<section class="py-20 px-6 bg-gray-950"><div class="max-w-3xl mx-auto"><h2 class="text-3xl font-bold text-center text-white mb-12">Frequently Asked Questions</h2><div class="space-y-4"><details class="bg-gray-900/50 border border-gray-800 rounded-xl p-4 group"><summary class="text-white font-semibold cursor-pointer flex justify-between items-center">How does it work?<span class="text-gray-500 group-open:rotate-180 transition">▼</span></summary><p class="text-gray-400 text-sm mt-3">Simply describe your website and our AI generates a complete, production-ready website in seconds.</p></details><details class="bg-gray-900/50 border border-gray-800 rounded-xl p-4 group"><summary class="text-white font-semibold cursor-pointer flex justify-between items-center">Can I customize the output?<span class="text-gray-500 group-open:rotate-180 transition">▼</span></summary><p class="text-gray-400 text-sm mt-3">Yes! Use our built-in IDE to edit code, rearrange sections, and regenerate with AI.</p></details><details class="bg-gray-900/50 border border-gray-800 rounded-xl p-4 group"><summary class="text-white font-semibold cursor-pointer flex justify-between items-center">Is it free?<span class="text-gray-500 group-open:rotate-180 transition">▼</span></summary><p class="text-gray-400 text-sm mt-3">We offer a free tier with 50 tokens. Upgrade to Premium for more power!</p></details></div></div></section>'},
    {"id": "footer_dark", "name": "Footer — Dark", "category": "Footer",
     "content": '<footer class="py-12 px-6 bg-gray-950 border-t border-gray-800"><div class="max-w-6xl mx-auto grid md:grid-cols-4 gap-8"><div><h3 class="text-white font-bold text-lg mb-3">Brand</h3><p class="text-gray-500 text-sm">Building the future with AI-powered tools.</p></div><div><h4 class="text-gray-300 font-semibold mb-3 text-sm">Product</h4><ul class="space-y-2 text-gray-500 text-sm"><li><a href="#" class="hover:text-white transition">Features</a></li><li><a href="#" class="hover:text-white transition">Pricing</a></li><li><a href="#" class="hover:text-white transition">Docs</a></li></ul></div><div><h4 class="text-gray-300 font-semibold mb-3 text-sm">Company</h4><ul class="space-y-2 text-gray-500 text-sm"><li><a href="#" class="hover:text-white transition">About</a></li><li><a href="#" class="hover:text-white transition">Blog</a></li><li><a href="#" class="hover:text-white transition">Careers</a></li></ul></div><div><h4 class="text-gray-300 font-semibold mb-3 text-sm">Connect</h4><div class="flex gap-3"><a href="#" class="w-9 h-9 bg-gray-800 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-indigo-600 transition"><i class="fab fa-github"></i></a><a href="#" class="w-9 h-9 bg-gray-800 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-blue-600 transition"><i class="fab fa-linkedin"></i></a><a href="#" class="w-9 h-9 bg-gray-800 rounded-lg flex items-center justify-center text-gray-400 hover:text-white hover:bg-pink-600 transition"><i class="fab fa-twitter"></i></a></div></div></div><div class="mt-8 pt-6 border-t border-gray-800 text-center text-gray-600 text-sm">© 2026 All rights reserved.</div></footer>'},
]


@features_bp.route("/api/components")
def get_components():
    return jsonify(COMPONENTS)


@features_bp.route("/api/component/<component_id>/add/<int:page_id>", methods=["POST"])
def add_component(component_id, page_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    component = next((c for c in COMPONENTS if c["id"] == component_id), None)
    if not component:
        return jsonify({"error": "Component not found"}), 404

    page = Page.query.get_or_404(page_id)
    if page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    max_order = db.session.query(db.func.max(Section.order)).filter_by(page_id=page_id).scalar() or 0

    section = Section(
        name=component["name"],
        content=component["content"],
        page_id=page_id,
        order=max_order + 1
    )
    db.session.add(section)
    db.session.commit()

    return jsonify({"success": True, "section_id": section.id, "name": section.name, "content": section.content})


# ============================================================
# SEO ASSISTANT — AI-powered SEO analysis
# ============================================================

@features_bp.route("/api/website/<int:website_id>/seo", methods=["GET"])
def seo_analysis(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    from core.groq_llm import GroqLLM
    llm = GroqLLM(model="llama-3.1-8b-instant")

    # Collect all page content
    pages_summary = []
    for page in website.pages:
        content = " ".join([s.content[:200] for s in page.sections])
        pages_summary.append(f"Page: {page.name} ({page.slug})\nContent preview: {content[:500]}")

    all_content = "\n\n".join(pages_summary)

    messages = [
        {"role": "system", "content": """You are an SEO expert. Analyze the website and provide a JSON response with:
{
  "score": 0-100,
  "issues": ["issue1", "issue2"],
  "suggestions": ["suggestion1", "suggestion2"],
  "meta_tags": "<meta> tags they should add"
}
Output ONLY valid JSON."""},
        {"role": "user", "content": f"Website: {website.name}\n\n{all_content}"}
    ]

    result = llm.invoke_json(messages, temperature=0.3, max_tokens=2048)
    import json
    try:
        data = json.loads(result) if isinstance(result, str) else result
        return jsonify(data)
    except:
        return jsonify({"score": 50, "issues": ["Could not fully analyze"], "suggestions": ["Add meta descriptions to each page"]})


# ============================================================
# VERSION HISTORY — Snapshots for undo/redo
# ============================================================

@features_bp.route("/api/section/<int:section_id>/snapshot", methods=["POST"])
def save_snapshot(section_id):
    """Save a snapshot of current section content before editing."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    snapshot = SectionSnapshot(section_id=section_id, content=section.content)
    db.session.add(snapshot)
    db.session.commit()

    return jsonify({"success": True, "snapshot_id": snapshot.id})


@features_bp.route("/api/section/<int:section_id>/history")
def get_history(section_id):
    """Get version history for a section."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    snapshots = SectionSnapshot.query.filter_by(section_id=section_id)\
        .order_by(SectionSnapshot.created_at.desc()).limit(20).all()

    return jsonify([{
        "id": s.id,
        "created_at": s.created_at.isoformat(),
        "preview": s.content[:100]
    } for s in snapshots])


@features_bp.route("/api/section/<int:section_id>/restore/<int:snapshot_id>", methods=["POST"])
def restore_snapshot(section_id, snapshot_id):
    """Restore a section to a previous snapshot."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    snapshot = SectionSnapshot.query.get_or_404(snapshot_id)

    # Save current as new snapshot before restoring
    current_snap = SectionSnapshot(section_id=section_id, content=section.content)
    db.session.add(current_snap)

    section.content = snapshot.content
    db.session.commit()

    return jsonify({"success": True, "content": section.content})


# ============================================================
# COLLABORATION — Share website access
# ============================================================

@features_bp.route("/api/website/<int:website_id>/share", methods=["POST"])
def share_website(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    email = data.get("email")
    permission = data.get("permission", "view")

    if not email:
        return jsonify({"error": "Email required"}), 400

    # Check if already shared
    existing = SharedAccess.query.filter_by(website_id=website_id, shared_with_email=email).first()
    if existing:
        existing.permission = permission
    else:
        access = SharedAccess(website_id=website_id, shared_with_email=email, permission=permission)
        db.session.add(access)

    db.session.commit()
    return jsonify({"success": True, "email": email, "permission": permission})


@features_bp.route("/api/website/<int:website_id>/collaborators")
def get_collaborators(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    collabs = SharedAccess.query.filter_by(website_id=website_id).all()
    return jsonify([{"email": c.shared_with_email, "permission": c.permission, "id": c.id} for c in collabs])


@features_bp.route("/api/website/shared/<int:access_id>", methods=["DELETE"])
def remove_collaborator(access_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    access = SharedAccess.query.get_or_404(access_id)
    if access.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(access)
    db.session.commit()
    return jsonify({"success": True})


# ============================================================
# DEPLOY — Placeholder for Vercel/Netlify deployment
# ============================================================

@features_bp.route("/api/website/<int:website_id>/deploy", methods=["POST"])
def deploy_website(website_id):
    """Generate a deployable package (future: auto-deploy to Vercel/Netlify)."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    # For now, return deployment info — actual API integration in future
    return jsonify({
        "success": True,
        "message": "Deployment package ready! Export your website and upload to Vercel/Netlify.",
        "deploy_options": [
            {"name": "Vercel", "url": "https://vercel.com/new", "icon": "▲"},
            {"name": "Netlify", "url": "https://app.netlify.com/drop", "icon": "◆"},
            {"name": "GitHub Pages", "url": "https://pages.github.com", "icon": "🐙"},
        ],
        "tip": "Export your website as ZIP, then drag-and-drop to Netlify Drop for instant deployment!"
    })
