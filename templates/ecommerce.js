// Import required modules
const express = require('express');
const app = express();
const mongoose = require('mongoose');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const tf = require('@tensorflow/tfjs');
const brain = require('brain.js');

// Connect to MongoDB
mongoose.connect('mongodb://localhost/ecommerce', { useNewUrlParser: true, useUnifiedTopology: true });

// Define schema for products
const productSchema = new mongoose.Schema({
  name: String,
  description: String,
  price: Number,
  image: String,
  category: String,
  rating: Number
});

// Define schema for users
const userSchema = new mongoose.Schema({
  name: String,
  email: String,
  password: String,
  purchases: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Product' }]
});

// Compile schema into models
const Product = mongoose.model('Product', productSchema);
const User = mongoose.model('User', userSchema);

// Middlewares
app.use(express.json());
app.use(cors());

// Routes
app.post('/register', async (req, res) => {
  const { name, email, password } = req.body;
  const hashedPassword = await bcrypt.hash(password, 10);
  const user = new User({ name, email, password: hashedPassword });
  await user.save();
  res.send('User registered successfully');
});

app.post('/login', async (req, res) => {
  const { email, password } = req.body;
  const user = await User.findOne({ email });
  if (!user) return res.status(401).send('Invalid email or password');
  const isValidPassword = await bcrypt.compare(password, user.password);
  if (!isValidPassword) return res.status(401).send('Invalid email or password');
  const token = jwt.sign({ userId: user._id }, 'secretkey');
  res.send(token);
});

app.get('/products', async (req, res) => {
  const products = await Product.find();
  res.send(products);
});

app.post('/products', async (req, res) => {
  const { name, description, price, image, category } = req.body;
  const product = new Product({ name, description, price, image, category });
  await product.save();
  res.send('Product added successfully');
});

app.get('/products/:id', async (req, res) => {
  const id = req.params.id;
  const product = await Product.findById(id);
  res.send(product);
});

app.put('/products/:id', async (req, res) => {
  const id = req.params.id;
  const { name, description, price, image, category } = req.body;
  const product = await Product.findByIdAndUpdate(id, { name, description, price, image, category }, { new: true });
  res.send(product);
});

app.delete('/products/:id', async (req, res) => {
  const id = req.params.id;
  await Product.findByIdAndDelete(id);
  res.send('Product deleted successfully');
});

// AI-powered product recommendation
app.get('/recommendations', async (req, res) => {
  const products = await Product.find();
  const users = await User.find();
  const neuralNetwork = new brain.recurrent.LSTM();
  const trainingData = [];

  // Prepare training data
  for (const user of users) {
    for (const purchase of user.purchases) {
      const product = await Product.findById(purchase);
      trainingData.push({
        input: [product.category, product.price, product.rating],
        output: [1] // 1 represents a purchase
      });
    }
  }

  // Train the neural network
  neuralNetwork.train(trainingData, {
    iterations: 1000,
    errorThresh: 0.005
  });

  // Make predictions
  const predictions = [];
  for (const product of products) {
    const input = [product.category, product.price, product.rating];
    const output = neuralNetwork.run(input);
    predictions.push({
      product: product,
      score: output
    });
  }

  // Sort predictions by score
  predictions.sort((a, b) => b.score - a.score);

  // Return top 5 recommendations
  res.send(predictions.slice(0, 5));
});

// Natural Language Processing (NLP) for product search
app.get('/search', async (req, res) => {
  const query = req.query.q;
  const products = await Product.find();
  const results = [];

  // Tokenize the query
  const tokens = query.split(' ');

  // Calculate TF-IDF scores
  for (const product of products) {
    const tfidf = tf.tensor2d([product.name, product.description].map((text) => {
      const vector = tf.tensor1d(text.split(' ').map((word) => word.toLowerCase()));
      return vector.dot(tf.tensor1d(tokens.map((token) => token.toLowerCase())));
    }));
    const score = tfidf.sum().dataSync()[0];
    results.push({
      product: product,
      score: score
    });
  }

  // Sort results by score
  results.sort((a, b) => b.score - a.score);

  // Return top 5 results
  res.send(results.slice(0, 5));
});

// Start server
const port = 3000;
app.listen(port, () => {
  console.log(`Server started on port ${port}`);
});// Import required modules
const express = require('express');
const app = express();
const mongoose = require('mongoose');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const cors = require('cors');
const tf = require('@tensorflow/tfjs');
const brain = require('brain.js');

// Connect to MongoDB
mongoose.connect('mongodb://localhost/ecommerce', { useNewUrlParser: true, useUnifiedTopology: true });

// Define schema for products
const productSchema = new mongoose.Schema({
  name: String,
  description: String,
  price: Number,
  image: String,
  category: String,
  rating: Number
});

// Define schema for users
const userSchema = new mongoose.Schema({
  name: String,
  email: String,
  password: String,
  purchases: [{ type: mongoose.Schema.Types.ObjectId, ref: 'Product' }]
});

// Compile schema into models
const Product = mongoose.model('Product', productSchema);
const User = mongoose.model('User', userSchema);

// Middlewares
app.use(express.json());
app.use(cors());

// Routes
app.post('/register', async (req, res) => {
  const { name, email, password } = req.body;
  const hashedPassword = await bcrypt.hash(password, 10);
  const user = new User({ name, email, password: hashedPassword });
  await user.save();
  res.send('User registered successfully');
});

app.post('/login', async (req, res) => {
  const { email, password } = req.body;
  const user = await User.findOne({ email });
  if (!user) return res.status(401).send('Invalid email or password');
  const isValidPassword = await bcrypt.compare(password, user.password);
  if (!isValidPassword) return res.status(401).send('Invalid email or password');
  const token = jwt.sign({ userId: user._id }, 'secretkey');
  res.send(token);
});

app.get('/products', async (req, res) => {
  const products = await Product.find();
  res.send(products);
});

app.post('/products', async (req, res) => {
  const { name, description, price, image, category } = req.body;
  const product = new Product({ name, description, price, image, category });
  await product.save();
  res.send('Product added successfully');
});

app.get('/products/:id', async (req, res) => {
  const id = req.params.id;
  const product = await Product.findById(id);
  res.send(product);
});

app.put('/products/:id', async (req, res) => {
  const id = req.params.id;
  const { name, description, price, image, category } = req.body;
  const product = await Product.findByIdAndUpdate(id, { name, description, price, image, category }, { new: true });
  res.send(product);
});

app.delete('/products/:id', async (req, res) => {
  const id = req.params.id;
  await Product.findByIdAndDelete(id);
  res.send('Product deleted successfully');
});

// AI-powered product recommendation
app.get('/recommendations', async (req, res) => {
  const products = await Product.find();
  const users = await User.find();
  const neuralNetwork = new brain.recurrent.LSTM();
  const trainingData = [];

  // Prepare training data
  for (const user of users) {
    for (const purchase of user.purchases) {
      const product = await Product.findById(purchase);
      trainingData.push({
        input: [product.category, product.price, product.rating],
        output: [1] // 1 represents a purchase
      });
    }
  }

  // Train the neural network
  neuralNetwork.train(trainingData, {
    iterations: 1000,
    errorThresh: 0.005
  });

  // Make predictions
  const predictions = [];
  for (const product of products) {
    const input = [product.category, product.price, product.rating];
    const output = neuralNetwork.run(input);
    predictions.push({
      product: product,
      score: output
    });
  }

  // Sort predictions by score
  predictions.sort((a, b) => b.score - a.score);

  // Return top 5 recommendations
  res.send(predictions.slice(0, 5));
});

// Natural Language Processing (NLP) for product search
app.get('/search', async (req, res) => {
  const query = req.query.q;
  const products = await Product.find();
  const results = [];

  // Tokenize the query
  const tokens = query.split(' ');

  // Calculate TF-IDF scores
  for (const product of products) {
    const tfidf = tf.tensor2d([product.name, product.description].map((text) => {
      const vector = tf.tensor1d(text.split(' ').map((word) => word.toLowerCase()));
      return vector.dot(tf.tensor1d(tokens.map((token) => token.toLowerCase())));
    }));
    const score = tfidf.sum().dataSync()[0];
    results.push({
      product: product,
      score: score
    });
  }

  // Sort results by score
  results.sort((a, b) => b.score - a.score);

  // Return top 5 results
  res.send(results.slice(0, 5));
});

// Chatbot for customer support
app.post('/chat', async (req, res) => {
  const message = req.body.message;
  const intent = await getIntent(message);
  const response = await getResponse(intent);
  res.send(response);
});

// Intent recognition
async function getIntent(message) {
  const intents = {
    'hello': 'greeting',
    'how are you': 'greeting',
    'what is your name': 'introduction',
    'i want to buy a product': 'purchase',
    'i have a question': 'question'
  };
  const tokens = message.split(' ');
  for (const token of tokens) {
    if (intents[token]) return intents[token];
  }
  return 'unknown';
}

// Response generation
async function getResponse(intent) {
  const responses = {
    'greeting': 'Hello! How can I assist you today?',
    'introduction': 'My name is Ecommerce Bot. I am here to help you with your shopping needs.',
    'purchase': 'What product are you looking for?',
    'question': 'Please ask your question, and I will do my best to answer it.',
    'unknown': 'I did not understand your message. Please try again.'
  };
  return responses[intent];
}

// Start server
const port = 3000;
app.listen(port, () => {
  console.log(`Server started on port ${port}`);
});