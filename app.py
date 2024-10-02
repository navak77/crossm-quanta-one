from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import timedelta
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.permanent_session_lifetime = timedelta(days=5)

# Database setup
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, preferences TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS flights
                 (flight_id INTEGER PRIMARY KEY, origin TEXT, destination TEXT,
                  status TEXT, departure_time TEXT, arrival_time TEXT, price REAL)''')
    conn.commit()
    conn.close()

init_db()

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        preferences = request.form["preferences"]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password, preferences) VALUES (?, ?, ?)",
                      (username, password, preferences))
            conn.commit()
            conn.close()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("Username already exists. Please try again.", "danger")
            return redirect(url_for("register"))
    return render_template('register.html')

@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "POST":
        session.permanent = True
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        conn.close()
        if result:
            session["user"] = username
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(url_for("login"))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

@app.route('/profile', methods=["GET", "POST"])
def profile():
    if "user" in session:
        user = session["user"]
        if request.method == "POST":
            preferences = request.form["preferences"]
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET preferences=? WHERE username=?", (preferences, user))
            conn.commit()
            conn.close()
            flash("Preferences updated.", "success")
            return redirect(url_for("profile"))
        else:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("SELECT preferences FROM users WHERE username=?", (user,))
            result = c.fetchone()
            conn.close()
            preferences = result[0] if result else ""
            return render_template('profile.html', username=user, preferences=preferences)
    else:
        flash("Please log in to access your profile.", "warning")
        return redirect(url_for("login"))

@app.route('/flights')
def view_flights():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM flights")
    flights = c.fetchall()
    conn.close()
    return render_template('flights.html', flights=flights)

@app.route('/book_flight/<int:flight_id>')
def book_flight(flight_id):
    if "user" in session:
        # Simulate booking process
        flash(f"Flight {flight_id} booked successfully!", "success")
        return redirect(url_for("view_flights"))
    else:
        flash("Please log in to book flights.", "warning")
        return redirect(url_for("login"))

@app.route('/search_flights', methods=["GET", "POST"])
def search_flights():
    flights = []
    if request.method == "POST":
        origin = request.form["origin"]
        destination = request.form["destination"]
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM flights WHERE origin LIKE ? AND destination LIKE ?", 
                  ('%' + origin + '%', '%' + destination + '%'))
        flights = c.fetchall()
        conn.close()
    return render_template('search_flights.html', flights=flights)

@app.route('/update_flights')
def update_flights():
    # Simulate flight updates
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # For simplicity, we just toggle the status of all flights
    c.execute("UPDATE flights SET status = CASE WHEN status='On Time' THEN 'Delayed' ELSE 'On Time' END")
    conn.commit()
    conn.close()
    flash("Flight statuses updated.", "info")
    return redirect(url_for("view_flights"))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    # Initialize some flight data
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS flights (flight_id INTEGER PRIMARY KEY, origin TEXT, destination TEXT, status TEXT, departure_time TEXT, arrival_time TEXT, price REAL)")
    c.execute("DELETE FROM flights")  # Clear existing data
    flights_data = [
        (1, 'New York', 'Los Angeles', 'On Time', '10:00 AM', '1:00 PM', 299.99),
        (2, 'Chicago', 'Miami', 'On Time', '11:00 AM', '2:30 PM', 199.99),
        (3, 'San Francisco', 'Seattle', 'On Time', '1:00 PM', '3:00 PM', 149.99),
        (4, 'Boston', 'Dallas', 'On Time', '2:00 PM', '5:00 PM', 249.99),
    ]
    c.executemany("INSERT INTO flights (flight_id, origin, destination, status, departure_time, arrival_time, price) VALUES (?, ?, ?, ?, ?, ?, ?)", flights_data)
    conn.commit()
    conn.close()
    app.run(debug=True)
