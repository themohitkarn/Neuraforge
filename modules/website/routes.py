from flask import Blueprint, render_template, abort, redirect, url_for
from flask import request, jsonify, session
from database import db
from database.models.website import Website
from database.models.page import Page
from database.models.section import Section
from modules.auth.token_service import TokenService

import io
import zipfile
from flask import send_file

website_bp = Blueprint("website_bp", __name__)


# ============================================================
# VIEW ROUTES (Public Preview)
# ============================================================

@website_bp.route("/view/<int:website_id>")
def view_website(website_id):
    website = Website.query.get_or_404(website_id)
    home_page = next((p for p in website.pages if p.slug.lower() == 'home'), None)

    if not home_page and website.pages:
        home_page = website.pages[0]

    if not home_page:
        abort(404, "Website has no pages generated.")

    return render_template("preview.html", website=website, current_page=home_page)


@website_bp.route("/view/<int:website_id>/<string:slug>")
def view_page(website_id, slug):
    website = Website.query.get_or_404(website_id)
    current_page = next((p for p in website.pages if p.slug.lower() == slug.lower()), None)

    if not current_page:
        abort(404, "Page not found.")

    return render_template("preview.html", website=website, current_page=current_page)


# ============================================================
# OLD EDITOR ROUTES (kept for backward compat)
# ============================================================

@website_bp.route("/edit/<int:website_id>")
def edit_website(website_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        abort(403)

    # Redirect to IDE instead
    return redirect(url_for("website_bp.ide_website", website_id=website_id))


@website_bp.route("/edit/<int:website_id>/<string:slug>")
def edit_page(website_id, slug):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        abort(403)

    return redirect(url_for("website_bp.ide_website", website_id=website_id))


# ============================================================
# IDE ROUTE
# ============================================================

@website_bp.route("/ide/<int:website_id>")
def ide_website(website_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        abort(403)

    # Sort pages by their order
    sorted_pages = sorted(website.pages, key=lambda p: p.order)
    first_page = sorted_pages[0] if sorted_pages else None

    return render_template("ide.html", website=website, pages=sorted_pages, current_page=first_page)


# ============================================================
# SECTION CRUD API
# ============================================================

@website_bp.route("/api/section/<int:section_id>", methods=["PUT"])
def update_section(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    if "content" in data:
        section.content = data["content"]
    if "name" in data:
        section.name = data["name"]
    db.session.commit()
    return jsonify({"success": True, "message": "Section updated"})


@website_bp.route("/api/section/add/<int:page_id>", methods=["POST"])
def add_section(page_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    page = Page.query.get_or_404(page_id)
    if page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    name = data.get("name", "New Section")
    content = data.get("content", "<div class='p-12 text-center text-gray-400'>New section — click to edit</div>")

    # Set order to be last
    max_order = max([s.order for s in page.sections], default=-1)

    new_section = Section(
        name=name,
        content=content,
        order=max_order + 1,
        page_id=page.id
    )
    db.session.add(new_section)
    db.session.commit()

    return jsonify({
        "success": True,
        "section": {
            "id": new_section.id,
            "name": new_section.name,
            "content": new_section.content,
            "order": new_section.order
        }
    })


@website_bp.route("/api/section/<int:section_id>", methods=["DELETE"])
def delete_section(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(section)
    db.session.commit()
    return jsonify({"success": True, "message": "Section deleted"})


@website_bp.route("/api/section/<int:section_id>/reorder", methods=["PUT"])
def reorder_section(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    new_order = data.get("order")
    if new_order is not None:
        section.order = new_order
        db.session.commit()

    return jsonify({"success": True})


@website_bp.route("/api/section/<int:section_id>/regenerate", methods=["POST"])
def regenerate_section(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    prompt = data.get("prompt", "Make this section better")

    from modules.ai_generator.service import AIGeneratorService
    result, error = AIGeneratorService.regenerate_section(section_id, prompt, session["user_id"])

    if result:
        return jsonify({"success": True, "content": result})
    else:
        return jsonify({"error": error}), 500


@website_bp.route("/api/website/<int:website_id>/regenerate_all", methods=["POST"])
def regenerate_all(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    prompt = data.get("prompt", "Redesign the website completely")

    from modules.ai_generator.service import AIGeneratorService
    result, error = AIGeneratorService.generate_website(
        prompt=prompt, 
        user_id=session["user_id"], 
        framework=website.framework,
        existing_website_id=website_id
    )

    if result:
        return jsonify({"success": True, "message": "Website completely redesigned"})
    else:
        return jsonify({"error": error}), 500



# ============================================================
# PAGE CRUD API
# ============================================================

@website_bp.route("/api/page/<int:website_id>", methods=["POST"])
def add_page(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}
    name = data.get("name", "New Page")
    slug = data.get("slug", name.lower().replace(" ", "-"))

    max_order = max([p.order for p in website.pages], default=-1)

    new_page = Page(
        name=name,
        slug=slug,
        order=max_order + 1,
        website_id=website.id
    )
    db.session.add(new_page)
    db.session.flush()

    # Add a default section
    default_section = Section(
        name="Hero",
        content="<div class='min-h-[50vh] flex items-center justify-center bg-gradient-to-br from-gray-900 to-gray-800'><h1 class='text-4xl font-bold text-white'>" + name + "</h1></div>",
        order=0,
        page_id=new_page.id
    )
    db.session.add(default_section)
    db.session.commit()

    return jsonify({
        "success": True,
        "page": {
            "id": new_page.id,
            "name": new_page.name,
            "slug": new_page.slug,
            "order": new_page.order,
            "sections": [{
                "id": default_section.id,
                "name": default_section.name,
                "content": default_section.content,
                "order": default_section.order
            }]
        }
    })


@website_bp.route("/api/page/<int:page_id>", methods=["PUT"])
def update_page(page_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    page = Page.query.get_or_404(page_id)
    if page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    if "name" in data:
        page.name = data["name"]
        if "slug" not in data:
            page.slug = data["name"].lower().replace(" ", "-")
    if "slug" in data:
        page.slug = data["slug"]
    if "order" in data:
        page.order = data["order"]

    db.session.commit()
    return jsonify({"success": True})


@website_bp.route("/api/page/<int:page_id>", methods=["DELETE"])
def delete_page(page_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    page = Page.query.get_or_404(page_id)
    if page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(page)
    db.session.commit()
    return jsonify({"success": True, "message": "Page deleted"})


# ============================================================
# WEBSITE CRUD API
# ============================================================

@website_bp.route("/api/website/<int:website_id>", methods=["PUT"])
def update_website(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    if "name" in data:
        website.name = data["name"]
    db.session.commit()
    return jsonify({"success": True})


@website_bp.route("/api/website/<int:website_id>", methods=["DELETE"])
def delete_website(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(website)
    db.session.commit()
    return jsonify({"success": True, "message": "Website deleted"})


# ============================================================
# PROJECT FILE CRUD API (Multi-Language IDE Support)
# ============================================================

@website_bp.route("/api/file/<int:website_id>", methods=["POST"])
def add_project_file(website_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    from database.models.project_file import ProjectFile

    data = request.get_json() or {}
    path = data.get("path", "new_file.txt")
    content = data.get("content", "")
    
    # Determine basic file_type from extension
    ext = path.split('.')[-1].lower() if '.' in path else 'text'
    
    new_file = ProjectFile(
        website_id=website.id,
        path=path,
        content=content,
        file_type=ext
    )
    db.session.add(new_file)
    db.session.commit()

    return jsonify({
        "success": True,
        "file": {
            "id": new_file.id,
            "path": new_file.path,
            "content": new_file.content,
            "file_type": new_file.file_type
        }
    })

@website_bp.route("/api/file/<int:file_id>", methods=["PUT"])
def update_project_file(file_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    from database.models.project_file import ProjectFile
    file_obj = ProjectFile.query.get_or_404(file_id)
    if file_obj.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    if "content" in data:
        file_obj.content = data["content"]
    db.session.commit()
    return jsonify({"success": True})


@website_bp.route("/api/file/<int:file_id>/rename", methods=["PUT"])
def rename_project_file(file_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    from database.models.project_file import ProjectFile
    file_obj = ProjectFile.query.get_or_404(file_id)
    if file_obj.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json()
    if "path" in data:
        file_obj.path = data["path"]
        # Update file_type based on new extension
        file_obj.file_type = file_obj.path.split('.')[-1].lower() if '.' in file_obj.path else 'text'
        
    db.session.commit()
    return jsonify({"success": True})


@website_bp.route("/api/file/<int:file_id>", methods=["DELETE"])
def delete_project_file(file_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    from database.models.project_file import ProjectFile
    file_obj = ProjectFile.query.get_or_404(file_id)
    if file_obj.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    db.session.delete(file_obj)
    db.session.commit()
    return jsonify({"success": True, "message": "File deleted"})

# ============================================================
# EXPORT
# ============================================================

@website_bp.route("/export/<int:website_id>")
def export_website(website_id):
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        abort(403)

    # Token check for export
    can_afford, cost, balance = TokenService.can_afford(session["user_id"], "export_website")
    if not can_afford:
        abort(403, f"Insufficient tokens! Need {cost}, have {balance}.")
    TokenService.deduct(session["user_id"], "export_website")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for page in website.pages:
            page_content = f"<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
            page_content += f"    <meta charset='UTF-8'>\n"
            page_content += f"    <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
            page_content += f"    <title>{page.name} - {website.name}</title>\n"
            page_content += f"    <script src='https://cdn.tailwindcss.com'></script>\n"
            page_content += f"    <link rel='stylesheet' href='https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'>\n"
            
            # Inject CSS links for any generated CSS files
            for pf in website.project_files:
                if pf.file_type == 'css' or pf.path.endswith('.css'):
                    page_content += f"    <link rel='stylesheet' href='{pf.path}'>\n"
                    
            page_content += f"</head>\n<body>\n"

            # Navigation bar for multi-page sites
            if len(website.pages) > 1:
                page_content += "    <nav class='p-4 bg-gray-900 text-white flex gap-4'>\n"
                for p in sorted(website.pages, key=lambda x: x.order):
                    active = " font-bold underline" if p.id == page.id else ""
                    page_content += f"        <a href='{p.slug}.html' class='{active}'>{p.name}</a>\n"
                page_content += "    </nav>\n"

            sorted_sections = sorted(page.sections, key=lambda s: s.order)
            for section in sorted_sections:
                page_content += f"\n    <!-- {section.name} -->\n"
                page_content += f"    {section.content}\n"

            page_content += "\n</body>\n</html>"
            zf.writestr(f"{page.slug}.html", page_content)

        # Include project files (React, backend, etc.)
        for pf in website.project_files:
            zf.writestr(pf.path, pf.content)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{website.name.replace(' ', '_').lower()}_export.zip"
    )


# ============================================================
# WEBSITE DATA API (for IDE)
# ============================================================

@website_bp.route("/api/website/<int:website_id>/data")
def get_website_data(website_id):
    """Return full website structure as JSON for the IDE frontend."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    website = Website.query.get_or_404(website_id)
    if website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    data = {
        "id": website.id,
        "name": website.name,
        "framework": website.framework,
        "pages": [],
        "project_files": []
    }

    for page in sorted(website.pages, key=lambda p: p.order):
        page_data = {
            "id": page.id,
            "name": page.name,
            "slug": page.slug,
            "order": page.order,
            "sections": []
        }
        for section in sorted(page.sections, key=lambda s: s.order):
            page_data["sections"].append({
                "id": section.id,
                "name": section.name,
                "content": section.content,
                "order": section.order
            })
        data["pages"].append(page_data)

    for pf in website.project_files:
        data["project_files"].append({
            "id": pf.id,
            "path": pf.path,
            "content": pf.content,
            "file_type": pf.file_type
        })

    return jsonify(data)


# ============================================================
# SNAPSHOT API
# ============================================================

@website_bp.route("/api/section/<int:section_id>/snapshot", methods=["POST"])
def create_snapshot(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403

    from database.models.snapshot import SectionSnapshot
    data = request.get_json()
    new_snapshot = SectionSnapshot(
        section_id=section_id,
        content=data.get('content', section.content)
    )
    db.session.add(new_snapshot)
    
    # Keep only last 10 snapshots to save space
    snapshots = SectionSnapshot.query.filter_by(section_id=section_id).order_by(SectionSnapshot.created_at.asc()).all()
    if len(snapshots) >= 10:
        for old in snapshots[:-9]:
            db.session.delete(old)
            
    db.session.commit()
    return jsonify({"success": True})


@website_bp.route("/api/section/<int:section_id>/snapshots", methods=["GET"])
def get_snapshots(section_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    section = Section.query.get_or_404(section_id)
    if section.page.website.user_id != session["user_id"]:
        return jsonify({"error": "Forbidden"}), 403
        
    from database.models.snapshot import SectionSnapshot
    snapshots = SectionSnapshot.query.filter_by(section_id=section_id).order_by(SectionSnapshot.created_at.desc()).all()
    
    return jsonify({
        "success": True, 
        "snapshots": [{"id": s.id, "content": s.content, "created_at": s.created_at.isoformat()} for s in snapshots]
    })


# ============================================================
# SEO API
# ============================================================

@website_bp.route("/api/seo/analyze", methods=["POST"])
def analyze_seo():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json()
    html_content = data.get("html", "")
    
    from modules.website.seo_analyzer import SEOAnalyzer
    result = SEOAnalyzer.analyze(html_content)
    
    return jsonify({"success": True, "analysis": result})
