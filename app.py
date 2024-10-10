from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import requests
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Your FlightAPI.io API key
api_key = "6707f1c3fd7916af2b519fdc"  # Replace with your actual API key

# Initialize Database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS flights (flight_id INTEGER PRIMARY KEY, origin TEXT, destination TEXT, status TEXT, departure_time TEXT, arrival_time TEXT, price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (username TEXT, flight_id INTEGER, booking_price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS coupons (username TEXT, coupon_code TEXT, discount REAL)''')
    conn.commit()
    conn.close()

init_db()

# Calculate user savings by comparing booked flight price to average flight prices
def calculate_savings(username):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    standard_price = 500
    c.execute("SELECT SUM(booking_price) FROM bookings WHERE username=?", (username,))
    result = c.fetchone()
    if result and result[0] is not None:
        user_spending = result[0]
        savings = (standard_price * c.execute("SELECT COUNT(*) FROM bookings WHERE username=?", (username,)).fetchone()[0]) - user_spending
    else:
        savings = 0
    conn.close()
    return savings

# Home Route
@app.route('/')
def home():
    return render_template('home.html')

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        savings = calculate_savings(session['user'])
        return render_template('dashboard.html', savings=savings)
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# View Flights Route
@app.route('/view_flights')
def view_flights():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM flights")
    flights = c.fetchall()
    conn.close()
    return render_template('flights.html', flights=flights)

# Show Booked Flights Route
@app.route('/show_booked_flights')
def show_booked_flights():
    if 'user' in session:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT f.flight_id, f.origin, f.destination, b.booking_price FROM bookings b JOIN flights f ON b.flight_id=f.flight_id WHERE b.username=?", (session['user'],))
        flights = c.fetchall()
        conn.close()
        return render_template('show_booked_flights.html', flights=flights)
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
# Book Flight Route
@app.route('/book_flight', methods=['GET', 'POST'])
def book_flight():
    if request.method == 'POST':
        # Process the booking form data
        # You can add code here to handle flight booking
        flight_id = request.form.get('flight_id')
        # Perform booking logic here
        # For now, we'll just redirect to the dashboard with a success message
        flash('Flight booked successfully!', 'success')
        return redirect(url_for('dashboard'))
    else:
        # Render the flight search form or booking page
        return render_template('book_flight.html')

# Rebook Flight Route
@app.route('/rebook_flight')
def rebook_flight():
    if 'user' in session:
        return render_template('rebook_flight.html')
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# Show Coupons Route
@app.route('/show_coupons')
def show_coupons():
    if 'user' in session:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT coupon_code, discount FROM coupons WHERE username=?", (session['user'],))
        coupons = c.fetchall()
        conn.close()
        return render_template('show_coupons.html', coupons=coupons)
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Verify credentials from the database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = username  # Store the username in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials, please try again.', 'danger')

    return render_template('login.html')

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove the user from the session
    flash("You have been logged out.", "info")  # Flash a message to the user
    return redirect(url_for('home'))  # Redirect to the home page

# Add Coupon Route
@app.route('/add_coupon', methods=['GET', 'POST'])
def add_coupon():
    if request.method == 'POST':
        coupon_code = request.form['coupon_code']
        discount = request.form['discount']
        username = request.form['username']  # Associate coupon with a user

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO coupons (username, coupon_code, discount) VALUES (?, ?, ?)", (username, coupon_code, discount))
        conn.commit()
        conn.close()

        flash('Coupon added successfully!', 'success')
        return redirect(url_for('add_coupon'))

    return render_template('add_coupon.html')

# Search Flights Route
@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if request.method == 'POST':
        origin = request.form.get('origin', '').upper()
        destination = request.form.get('destination', '').upper()
        departure_date = request.form.get('departure_date')

        # Validate inputs
        if not origin or not destination or not departure_date:
            flash("Please provide all required fields.", "warning")
            return render_template('search_flights.html')

        # Proceed with API call
        url = f"https://api.flightapi.io/onewaytrip/{api_key}/{origin}/{destination}/{departure_date}/1/0/0/Economy/USD"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                flight_data = response.json()
                # Parse flight data...
                flights = []  # Your parsing logic here
                return render_template('search_flights.html', flights=flights)
            else:
                flash(f"Error fetching flight data: {response.status_code}", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    return render_template('search_flights.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

