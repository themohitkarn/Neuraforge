from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length, EqualTo
from flask_bcrypt import Bcrypt
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.generate_password_hash(password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)

    def __init__(self, name, price, description):
        self.name = name
        self.price = price
        self.description = description

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    review = db.Column(db.Text, nullable=False)

    def __init__(self, product_id, user_id, review):
        self.product_id = product_id
        self.user_id = user_id
        self.review = review

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=15)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class ProductForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired()])
    price = StringField('Price', validators=[InputRequired()])
    description = StringField('Description', validators=[InputRequired()])
    submit = SubmitField('Add Product')

class ReviewForm(FlaskForm):
    review = StringField('Review', validators=[InputRequired()])
    submit = SubmitField('Submit Review')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(form.username.data, form.email.data, form.password.data)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        new_product = Product(form.name.data, form.price.data, form.description.data)
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_product.html', form=form)

@app.route('/product/<int:product_id>')
def product(product_id):
    product = Product.query.get(product_id)
    reviews = Review.query.filter_by(product_id=product_id).all()
    return render_template('product.html', product=product, reviews=reviews)

@app.route('/product/<int:product_id>/review', methods=['GET', 'POST'])
@login_required
def review(product_id):
    form = ReviewForm()
    if form.validate_on_submit():
        new_review = Review(product_id, current_user.id, form.review.data)
        db.session.add(new_review)
        db.session.commit()
        return redirect(url_for('product', product_id=product_id))
    return render_template('review.html', form=form)

@app.route('/recommendations')
@login_required
def recommendations():
    user_id = current_user.id
    user_reviews = Review.query.filter_by(user_id=user_id).all()
    user_reviewed_products = [review.product_id for review in user_reviews]
    similar_products = []
    for product_id in user_reviewed_products:
        product = Product.query.get(product_id)
        similar_products.extend([p for p in Product.query.all() if p.id not in user_reviewed_products and p.name != product.name])
    return render_template('recommendations.html', products=similar_products)

@app.route('/ai_recommendations')
@login_required
def ai_recommendations():
    user_id = current_user.id
    user_reviews = Review.query.filter_by(user_id=user_id).all()
    user_reviewed_products = [review.product_id for review in user_reviews]
    product_features = []
    for product in Product.query.all():
        features = [product.name, product.price, product.description]
        product_features.append(features)
    product_features = np.array(product_features)
    user_features = []
    for review in user_reviews:
        features = [review.review]
        user_features.append(features)
    user_features = np.array(user_features)
    model = keras.Sequential([
        keras.layers.Dense(64, activation='relu', input_shape=(len(product_features[0]),)),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dense(len(product_features))
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(product_features, user_features, epochs=10)
    predictions = model.predict(product_features)
    recommended_products = []
    for i, prediction in enumerate(predictions):
        if prediction > 0.5:
            recommended_products.append(Product.query.get(i+1))
    return render_template('ai_recommendations.html', products=recommended_products)

if __name__ == '__main__':
    app.run(debug=True)from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Email, Length, EqualTo
from flask_bcrypt import Bcrypt
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np
import pandas as pd

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = bcrypt.generate_password_hash(password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)

    def __init__(self, name, price, description):
        self.name = name
        self.price = price
        self.description = description

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    review = db.Column(db.Text, nullable=False)

    def __init__(self, product_id, user_id, review):
        self.product_id = product_id
        self.user_id = user_id
        self.review = review

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=15)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    confirm_password = PasswordField('Confirm Password', validators=[InputRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class ProductForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired()])
    price = StringField('Price', validators=[InputRequired()])
    description = StringField('Description', validators=[InputRequired()])
    submit = SubmitField('Add Product')

class ReviewForm(FlaskForm):
    review = StringField('Review', validators=[InputRequired()])
    submit = SubmitField('Submit Review')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        new_user = User(form.username.data, form.email.data, form.password.data)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    form = ProductForm()
    if form.validate_on_submit():
        new_product = Product(form.name.data, form.price.data, form.description.data)
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add_product.html', form=form)

@app.route('/product/<int:product_id>')
def product(product_id):
    product = Product.query.get(product_id)
    reviews = Review.query.filter_by(product_id=product_id).all()
    return render_template('product.html', product=product, reviews=reviews)

@app.route('/product/<int:product_id>/review', methods=['GET', 'POST'])
@login_required
def review(product_id):
    form = ReviewForm()
    if form.validate_on_submit():
        new_review = Review(product_id, current_user.id, form.review.data)
        db.session.add(new_review)
        db.session.commit()
        return redirect(url_for('product', product_id=product_id))
    return render_template('review.html', form=form)

@app.route('/recommendations')
@login_required
def recommendations():
    user_id = current_user.id
    user_reviews = Review.query.filter_by(user_id=user_id).all()
    user_reviewed_products = [review.product_id for review in user_reviews]
    similar_products = []
    for product_id in user_reviewed_products:
        product = Product.query.get(product_id)
        similar_products.extend([p for p in Product.query.all() if p.id not in user_reviewed_products and p.name != product.name])
    return render_template('recommendations.html', products=similar_products)

@app.route('/ai_recommendations')
@login_required
def ai_recommendations():
    user_id = current_user.id
    user_reviews = Review.query.filter_by(user_id=user_id).all()
    user_reviewed_products = [review.product_id for review in user_reviews]
    product_features = []
    for product in Product.query.all():
        features = [product.name, product.price, product.description]
        product_features.append(features)
    product_features = np.array(product_features)
    user_features = []
    for review in user_reviews:
        features = [review.review]
        user_features.append(features)
    user_features = np.array(user_features)
    model = keras.Sequential([
        keras.layers.Dense(64, activation='relu', input_shape=(len(product_features[0]),)),
        keras.layers.Dense(32, activation='relu'),
        keras.layers.Dense(len(product_features))
    ])
    model.compile(optimizer='adam', loss='mean_squared_error')
    model.fit(product_features, user_features, epochs=10)
    predictions = model.predict(product_features)
    recommended_products = []
    for i, prediction in enumerate(predictions):
        if prediction > 0.5:
            recommended_products.append(Product.query.get(i+1))
    return render_template('ai_recommendations.html', products=recommended_products)

@app.route('/chatbot')
@login_required
def chatbot():
    return render_template('chatbot.html')

@app.route('/chatbot_response', methods=['POST'])
@login_required
def chatbot_response():
    user_input = request.form['user_input']
    response = ''
    if user_input.lower() == 'hello':
        response = 'Hello! How can I assist you today?'
    elif user_input.lower() == 'what is your purpose?':
        response = 'I am an AI chatbot designed to assist you with your e-commerce needs.'
    else:
        response = 'I did not understand your input. Please try again.'
    return render_template('chatbot_response.html', response=response)

@app.route('/product_search', methods=['GET', 'POST'])
@login_required
def product_search():
    if request.method == 'POST':
        search_term = request.form['search_term']
        products = Product.query.filter(Product.name.like('%' + search_term + '%')).all()
        return render_template('product_search.html', products=products)
    return render_template('product_search.html')

if __name__ == '__main__':
    app.run(debug=True)