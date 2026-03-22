from database import db

class Page(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    slug = db.Column(db.String(50), nullable=False)
    order = db.Column(db.Integer, default=0)

    website_id = db.Column(db.Integer, db.ForeignKey("website.id"), nullable=False)

    sections = db.relationship("Section", backref="page", lazy=True, cascade="all, delete-orphan")

