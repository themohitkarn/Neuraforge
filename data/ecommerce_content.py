import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

from tensorflow.keras.models import load_model
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# ================= INIT =================
app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)

# Load AI model (optional)
try:
    model = load_model('ai_model.h5')
except:
    model = None

# ================= MODELS =================

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(300))
    price = db.Column(db.Float)
    image = db.Column(db.String(200))
    category = db.Column(db.String(50))
    brand = db.Column(db.String(50))
    review = db.Column(db.String(500))
    rating = db.Column(db.Float)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(200))
    email = db.Column(db.String(100))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    product_id = db.Column(db.Integer)
    quantity = db.Column(db.Integer)
    total_price = db.Column(db.Float)

# ================= SCHEMAS =================

class ProductSchema(ma.Schema):
    class Meta:
        fields = ("id","name","description","price","image","category","brand","review","rating")

product_schema = ProductSchema()
products_schema = ProductSchema(many=True)

class UserSchema(ma.Schema):
    class Meta:
        fields = ("id","username","email")

user_schema = UserSchema()

class OrderSchema(ma.Schema):
    class Meta:
        fields = ("id","user_id","product_id","quantity","total_price")

order_schema = OrderSchema()
orders_schema = OrderSchema(many=True)

# ================= ROUTES =================

# 🔹 PRODUCTS

@app.route('/products', methods=['GET'])
def get_products():
    return jsonify(products_schema.dump(Product.query.all()))

@app.route('/product/<int:id>', methods=['GET'])
def get_product(id):
    product = Product.query.get(id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return product_schema.jsonify(product)

@app.route('/product', methods=['POST'])
def create_product():
    data = request.json
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
    return product_schema.jsonify(product)

@app.route('/product/<int:id>', methods=['PUT'])
def update_product(id):
    product = Product.query.get(id)
    if not product:
        return jsonify({"error": "Not found"}), 404

    data = request.json
    for key, value in data.items():
        setattr(product, key, value)

    db.session.commit()
    return product_schema.jsonify(product)

@app.route('/product/<int:id>', methods=['DELETE'])
def delete_product(id):
    product = Product.query.get(id)
    if not product:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Deleted"})

# 🔹 SEARCH

@app.route('/search')
def search():
    query = request.args.get('query', '')

    products = Product.query.all()
    tfidf = TfidfVectorizer(stop_words='english')

    texts = [p.name + " " + p.description for p in products]
    tfidf_matrix = tfidf.fit_transform(texts)

    query_vec = tfidf.transform([query])
    sim = linear_kernel(query_vec, tfidf_matrix)[0]

    results = sorted(enumerate(sim), key=lambda x: x[1], reverse=True)

    filtered = [products[i] for i, score in results if score > 0.1]

    return jsonify(products_schema.dump(filtered))

# 🔹 RECOMMENDATION

@app.route('/recommend/<int:id>')
def recommend(id):
    products = Product.query.all()
    tfidf = TfidfVectorizer(stop_words='english')

    desc = [p.description for p in products]
    tfidf_matrix = tfidf.fit_transform(desc)
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)

    ids = [p.id for p in products]
    idx = ids.index(id)

    scores = list(enumerate(cosine_sim[idx]))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)[1:6]

    result = [products[i] for i, _ in scores]
    return jsonify(products_schema.dump(result))

# 🔹 USER AUTH

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hashed = generate_password_hash(data['password'])

    user = User(
        username=data['username'],
        password=hashed,
        email=data['email']
    )
    db.session.add(user)
    db.session.commit()

    return user_schema.jsonify(user)

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data['username']).first()

    if user and check_password_hash(user.password, data['password']):
        return user_schema.jsonify(user)

    return jsonify({"error": "Invalid credentials"}), 401

# 🔹 ORDER

@app.route('/order', methods=['POST'])
def order():
    data = request.json

    order = Order(**data)
    db.session.add(order)
    db.session.commit()

    return order_schema.jsonify(order)

@app.route('/orders')
def get_orders():
    return jsonify(orders_schema.dump(Order.query.all()))

# 🔹 REVIEW / RATING

@app.route('/review', methods=['POST'])
def review():
    data = request.json
    product = Product.query.get(data['product_id'])

    if not product:
        return jsonify({"error": "Not found"}), 404

    product.review = data['review']
    db.session.commit()

    return jsonify({"message": "Review added"})

@app.route('/rate', methods=['POST'])
def rate():
    data = request.json
    product = Product.query.get(data['product_id'])

    if not product:
        return jsonify({"error": "Not found"}), 404

    product.rating = data['rating']
    db.session.commit()

    return jsonify({"message": "Rating added"})

# 🔹 CHATBOT

@app.route('/chatbot', methods=['POST'])
def chatbot():
    if not model:
        return jsonify({"error": "Model not loaded"})

    text = request.json['input']

    # Basic dummy preprocessing
    vector = np.array([[len(text)]])  # placeholder

    prediction = model.predict(vector).tolist()

    return jsonify({"response": prediction})

# ================= RUN =================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)