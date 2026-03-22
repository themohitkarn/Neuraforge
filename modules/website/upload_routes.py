# modules/website/upload_routes.py
# ZIP upload for importing existing websites

import os
import zipfile
import io
from flask import Blueprint, request, jsonify, session, flash, redirect, url_for
from database import db
from database.models.website import Website
from database.models.page import Page
from database.models.section import Section
from database.models.project_file import ProjectFile
from modules.auth.token_service import TokenService

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload", methods=["POST"])
def upload_website():
    """Upload a ZIP file containing an existing website."""
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # Check tokens
    can_afford, cost, balance = TokenService.can_afford(session["user_id"], "upload_website")
    if not can_afford:
        flash(f"Insufficient tokens! Need {cost}, have {balance}.", "danger")
        return redirect(url_for("auth.dashboard"))

    file = request.files.get("zipfile")
    website_name = request.form.get("name", "Uploaded Website")

    if not file or not file.filename.endswith(".zip"):
        flash("Please upload a .zip file.", "danger")
        return redirect(url_for("auth.dashboard"))

    try:
        # Read the ZIP
        zip_data = io.BytesIO(file.read())
        with zipfile.ZipFile(zip_data, "r") as zf:
            # Create website
            website = Website(
                name=website_name,
                user_id=session["user_id"],
                framework="vanilla"
            )
            db.session.add(website)
            db.session.flush()

            html_files = []
            other_files = []

            for name in zf.namelist():
                # Skip directories and hidden files
                if name.endswith("/") or name.startswith("__MACOSX") or name.startswith("."):
                    continue

                content = zf.read(name).decode("utf-8", errors="ignore")

                if name.lower().endswith((".html", ".htm")):
                    html_files.append((name, content))
                else:
                    other_files.append((name, content))

            # Convert HTML files to pages with sections
            for idx, (fname, content) in enumerate(html_files):
                page_name = os.path.splitext(os.path.basename(fname))[0].replace("-", " ").replace("_", " ").title()
                slug = os.path.splitext(os.path.basename(fname))[0].lower().replace(" ", "-")

                if slug == "index":
                    page_name = "Home"
                    slug = "home"

                page = Page(
                    name=page_name,
                    slug=slug,
                    website_id=website.id,
                    order=idx
                )
                db.session.add(page)
                db.session.flush()

                # Store entire HTML as one section
                section = Section(
                    name=f"{page_name} Content",
                    content=content,
                    page_id=page.id,
                    order=0
                )
                db.session.add(section)

            # Store other files as project files
            for fname, content in other_files:
                ext = fname.rsplit(".", 1)[-1] if "." in fname else "text"
                pf = ProjectFile(
                    website_id=website.id,
                    path=fname,
                    content=content,
                    file_type=ext
                )
                db.session.add(pf)

            # If no HTML files found, create a default page
            if not html_files:
                page = Page(name="Home", slug="home", website_id=website.id, order=0)
                db.session.add(page)
                db.session.flush()
                section = Section(
                    name="Content",
                    content="<div class='p-8'><h1>Uploaded Website</h1><p>No HTML files found in the upload. Check the file tree for your project files.</p></div>",
                    page_id=page.id,
                    order=0
                )
                db.session.add(section)

            TokenService.deduct(session["user_id"], "upload_website")
            db.session.commit()

            flash(f"Website imported! {len(html_files)} pages, {len(other_files)} files.", "success")
            return redirect(url_for("website_bp.ide_website", website_id=website.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Upload failed: {str(e)}", "danger")
        return redirect(url_for("auth.dashboard"))
