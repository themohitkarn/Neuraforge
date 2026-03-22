from flask import Blueprint, request, jsonify, session, redirect, url_for, flash
from modules.ai_generator.service import AIGeneratorService

ai_generator_bp = Blueprint("ai_generator", __name__)

@ai_generator_bp.route("/", methods=["POST"])
def generate():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    prompt = request.form.get("prompt")
    framework = request.form.get("framework", "tailwind")
    engine = request.form.get("engine", "groq")
    
    if not prompt:
        flash("Prompt cannot be empty.", "danger")
        return redirect(url_for('auth.dashboard'))
        
    website, error = AIGeneratorService.generate_website(prompt, session["user_id"], framework=framework, engine=engine)
    
    if website:
        flash(f"Website generated! ({framework.upper()} framework via {engine.upper()})", "success")
        return redirect(url_for("website_bp.ide_website", website_id=website.id))
    else:
        flash(f"Error: {error}", "danger")
        return redirect(url_for("auth.dashboard"))
