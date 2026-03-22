from database import db

class Section(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    order = db.Column(db.Integer, default=0)

    page_id = db.Column(db.Integer, db.ForeignKey("page.id"), nullable=False)
