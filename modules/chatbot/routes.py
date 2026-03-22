# modules/chatbot/routes.py

from flask import Blueprint, request, jsonify
from modules.chatbot.website_bot import WebsiteChatbot

chatbot_bp = Blueprint("chatbot", __name__, url_prefix="/api/chat")


@chatbot_bp.route("/basic", methods=["POST"])
def basic_chat():
    data = request.json
    bot = WebsiteChatbot(website_context={"name": "General", "page_count": 0})
    reply = bot.get_response(data["message"])
    return jsonify({"reply": reply})


@chatbot_bp.route("/website", methods=["POST"])
def website_chat():
    data = request.json
    website_id = data.get("website_id", 1)

    # Get website context if possible
    context = {"name": "Website", "page_count": 0}
    try:
        from database.models.website import Website
        website = Website.query.get(website_id)
        if website:
            context = {"name": website.name, "page_count": len(website.pages)}
    except:
        pass

    bot = WebsiteChatbot(website_context=context)
    reply_json = bot.get_response(data["message"])
    import json
    try:
        reply_data = json.loads(reply_json)
        return jsonify(reply_data)
    except:
        return jsonify({"message": reply_json, "action": {"type": "none", "code": ""}})
