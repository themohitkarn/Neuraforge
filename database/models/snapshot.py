from database import db
from datetime import datetime


class SectionSnapshot(db.Model):
    """Version history — saves snapshots of section content for undo/redo."""
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("section.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    section = db.relationship("Section", backref=db.backref("snapshots", lazy=True, cascade="all, delete-orphan"))
