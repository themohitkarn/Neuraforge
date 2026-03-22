from database import db


class AIFeedback(db.Model):
    """Tracks AI generation feedback for learning user preferences."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    
    prompt = db.Column(db.Text, nullable=False)
    framework = db.Column(db.String(30), default="tailwind")
    generated_output = db.Column(db.Text, nullable=True)
    
    # User behavior tracking
    user_edits_count = db.Column(db.Integer, default=0)
    style_notes = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)  # 1-5
    
    # Design tracking
    output_hash = db.Column(db.String(64), nullable=True)
    layout_used = db.Column(db.String(100), nullable=True)
    engine_used = db.Column(db.String(20), nullable=True)
    
    created_at = db.Column(db.DateTime, default=db.func.now())
    
    user = db.relationship("User", backref=db.backref("ai_feedback", lazy=True))
