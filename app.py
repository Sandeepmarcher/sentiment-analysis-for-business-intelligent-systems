from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import plotly.express as px
import pandas as pd
from meta_ai_api import MetaAI  # Import MetaAI
from google.auth.transport import requests
from google.oauth2 import id_token
import os

app = Flask(__name__,static_folder='static', template_folder='templates')
app.secret_key = "marC12@$"

# Initialize MetaAI for generating reviews
ai = MetaAI()
GOOGLE_CLIENT_ID = "1052942748140-pckh7s60h481t7gcvkjrajg3boi8s8ut.apps.googleusercontent.com"

@app.route("/google-login", methods=["POST"])
def google_login():
    token = request.json.get("token")

    if not token:
        return jsonify({"success": False, "error": "Token missing"}), 400

    try:
        # Verify Google token
        id_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)

        # Extract user details
        email = id_info.get("email")
        name = id_info.get("name")

        if not email:
            return jsonify({"success": False, "error": "Invalid Google response"}), 400

        # Store user session
        session["user"] = email

        return jsonify({"success": True, "user": {"email": email, "name": name}})
    
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

def get_db_connection():
    conn = sqlite3.connect('d1.db')
    conn.row_factory = sqlite3.Row
    return conn

# Create necessary tables
def create_tables():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        fullname TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT NOT NULL,
                        brand_name TEXT NOT NULL,
                        price REAL NOT NULL,
                        rating REAL NOT NULL,
                        reviews TEXT NOT NULL)''')
    conn.commit()
    conn.close()

create_tables()

@app.route("/")
def home():
    return render_template("welcom.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "Passwords do not match"

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        conn = get_db_connection()
        try:
            conn.execute("INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)",
                         (fullname, email, hashed_password))
            conn.commit()
            return redirect("/sign")
        except sqlite3.IntegrityError:
            return "Email already exists!"
        finally:
            conn.close()
    return render_template("signup.html")

@app.route("/sign", methods=["GET", "POST"])
def sign():
    if request.method == "POST":
        email = request.form["login"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")
        else:
            return "Invalid credentials"

    return render_template("sign.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/sign")

# Fetch and clean data
def get_data_from_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM products"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([dict(row) for row in rows])
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['product_name', 'brand_name', 'price', 'rating', 'reviews'])
    df['rating'] = pd.to_numeric(df['rating'], errors='coerce')

    def classify_sentiment(rating):
        if rating >= 4:
            return "Positive"
        elif rating == 3:
            return "Neutral"
        else:
            return "Negative"

    df['sentiment'] = df['rating'].apply(classify_sentiment)
    return df

@app.route('/dashboard')
def index():
    df = get_data_from_db()
    if df.empty:
        return "No products available in database"

    products = df['product_name'].unique().tolist()
    brands = df['brand_name'].unique().tolist()
    return render_template('index.html', products=products, brands=brands)

@app.route('/api/analyze', methods=['GET'])
def sentiment_analysis():
    df = get_data_from_db()
    selected_product = request.args.get('product')
    selected_brand = request.args.get('brand')

    product_data = df[(df['product_name'] == selected_product) & (df['brand_name'] == selected_brand)]

    if product_data.empty:
        return jsonify({"error": "No data found for the selected product and brand."})

    sentiment_counts = product_data['sentiment'].value_counts().reset_index()
    sentiment_counts.columns = ['Sentiment', 'Count']

    color_map = {'Positive': 'green', 'Neutral': 'blue', 'Negative': 'red'}
    fig_bar = px.bar(sentiment_counts, x='Sentiment', y='Count', color='Sentiment',
                     color_discrete_map=color_map, text='Count')
    fig_bar.update_traces(textposition='outside')
    fig_bar.update_layout(title=f"Sentiment Distribution for {selected_product} ({selected_brand})")

    fig_pie = px.pie(sentiment_counts, names='Sentiment', values='Count', title='Sentiment Breakdown')
    fig_hist = px.histogram(product_data, x='rating', nbins=10, title='Rating Distribution')
    fig_scatter = px.scatter(product_data, x='price', y='rating', color='sentiment',
                             title='Price vs Rating')

    sample_reviews = {}
    for sentiment in ['Positive', 'Neutral', 'Negative']:
        reviews = product_data[product_data['sentiment'] == sentiment]['reviews'].sample(
            min(3, len(product_data)), random_state=42)
        sample_reviews[sentiment] = reviews.tolist()

    price = product_data['price'].iloc[0] if not product_data.empty else "N/A"
    avg_rating = product_data['rating'].mean() if not product_data.empty else "N/A"

    return jsonify({
        "charts": {"bar": fig_bar.to_json(), "pie": fig_pie.to_json(),
                   "histogram": fig_hist.to_json(), "scatter": fig_scatter.to_json()},
        "price": price, "avg_rating": round(avg_rating, 2), "reviews": sample_reviews
    })

@app.route('/api/generate_review', methods=['POST'])
def generate_review():
    data = request.get_json()
    product_name = data.get('product_name', '')

    if not product_name:
        return jsonify({"message": "Please enter a valid product name."}), 400

    review_prompt = f"Generate a short review for {product_name}."
    response = ai.prompt(message=review_prompt)

    if isinstance(response, dict):
        response = response.get("message", "No review found.")

    return jsonify({"message": response})



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

