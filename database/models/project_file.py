from database import db


class ProjectFile(db.Model):
    """Stores individual project files for framework-based projects (React, Vue, Node, etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey("website.id"), nullable=False)

    path = db.Column(db.String(255), nullable=False)  # e.g. "src/App.jsx", "package.json"
    content = db.Column(db.Text, nullable=False)
    file_type = db.Column(db.String(30), default="text")  # "text", "json", "jsx", "py", etc.

    website = db.relationship("Website", backref=db.backref("project_files", lazy=True, cascade="all, delete-orphan"))
