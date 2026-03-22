from database import db


class SharedAccess(db.Model):
    """Collaboration — stores shared access permissions for websites."""
    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey("website.id"), nullable=False)
    shared_with_email = db.Column(db.String(120), nullable=False)
    permission = db.Column(db.String(20), default="view")  # "view" or "edit"
    created_at = db.Column(db.DateTime, default=db.func.now())

    website = db.relationship("Website", backref=db.backref("shared_access", lazy=True, cascade="all, delete-orphan"))
