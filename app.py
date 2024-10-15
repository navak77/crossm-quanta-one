# app.py
from opensky_api import OpenSkyApi

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import os
from dotenv import load_dotenv
import bcrypt
import google.generativeai as genai  # Import the Google Generative AI library
import base64  # For encoding/decoding hashed passwords
import json  # For parsing JSON responses

# Import Amadeus Client and ResponseError
from amadeus import Client, ResponseError

# Configure Logging (Optional but Recommended)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')  # Securely load SECRET_KEY

# Configure Google Generative AI with your API key
genai.configure(api_key=os.getenv("API_KEY"))

# Initialize Amadeus API Client
amadeus = Client(
    client_id=os.getenv('AMADEUS_CLIENT_ID'),
    client_secret=os.getenv('AMADEUS_CLIENT_SECRET'),
    hostname='test'  # Use 'production' for the production environment
)

# Initialize Database (Assuming you have an init_db function)
import sqlite3

def init_db():
    # Connect to SQLite and enable foreign key support
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()

    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            preferences TEXT
        )
    ''')

    # Create bookings table with the `cancelled` column
    c.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            flight_id TEXT,
            booking_price REAL,
            origin TEXT,
            destination TEXT,
            departure_time TEXT,
            arrival_time TEXT,
            airline TEXT,
            flight_number TEXT,
            cancelled INTEGER DEFAULT 0,  -- Column to track cancellations
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    ''')

    # Create coupons table
    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            coupon_code TEXT,
            discount REAL,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    ''')

    # Commit changes and close the connection
    conn.commit()
    conn.close()

# Call the init_db function to ensure tables are created when the app starts
init_db()


# Call the init_db function to ensure tables are created
init_db()

def get_recommendations(username):
    """
    Fetches the user's booked flights and preferences, then generates flight recommendations using the Gemini API.
    Returns a list of recommended flights.
    """
    # Fetch booked flights
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    c.execute('''
        SELECT flight_id, booking_price, origin, destination, departure_time, arrival_time, airline, flight_number
        FROM bookings
        WHERE username = ?
    ''', (username,))
    booked_flights = c.fetchall()

    # Fetch user preferences
    c.execute('''
        SELECT preferences
        FROM users
        WHERE username = ?
    ''', (username,))
    preferences_result = c.fetchone()
    preferences = preferences_result[0] if preferences_result and preferences_result[0] else ''

    conn.close()

    # Format booked flights into a readable string
    if booked_flights:
        booked_flights_str = "\n".join([
            f"Flight {flight[6]} {flight[7]} from {flight[2]} to {flight[3]} on {flight[4]}"
            for flight in booked_flights
        ])
    else:
        booked_flights_str = "No booked flights."

    # Create a prompt for the Gemini API
    prompt = f"""
Based on the user's booked flights and preferences, recommend some flights for them.

User's Booked Flights:
{booked_flights_str}

User's Preferences:
{preferences}

Please provide a list of 3 recommended flights in the following JSON format:

[
    {{
        "Flight ID": "FL123",
        "Airline": "Airline Name",
        "Flight Number": "Flight Number",
        "Origin": "Origin Airport (IATA Code)",
        "Destination": "Destination Airport (IATA Code)",
        "Departure Time": "mm/dd/yyyy HH:MM AM/PM",
        "Arrival Time": "mm/dd/yyyy HH:MM AM/PM",
        "Price": "$XXX"
    }},
    ...
]
"""

    try:
        # Initialize the Generative Model
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Generate a response from the AI
        response = model.generate_content(prompt)

        # Extract the text from the response
        recommendations_text = response.text.strip()

        # Parse the recommendations_text into JSON
        start = recommendations_text.find('[')
        end = recommendations_text.rfind(']') + 1
        if start == -1 or end == -1:
            raise ValueError("AI did not return a valid JSON array.")

        recommendations_json = recommendations_text[start:end]

        # Load the JSON data
        recommendations = json.loads(recommendations_json)

        # Validate the structure of each recommended flight
        valid_recommendations = []
        for flight in recommendations:
            required_keys = ["Flight ID", "Airline", "Flight Number", "Origin", "Destination", "Departure Time", "Arrival Time", "Price"]
            if all(key in flight for key in required_keys):
                valid_recommendations.append(flight)
            else:
                logger.warning(f"Incomplete flight data: {flight}")

        return valid_recommendations

    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return []

# Home Route
@app.route('/')
def home():
    return render_template('home.html')

# Register Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Input Validation
        if not username or not password or not confirm_password:
            flash('Please fill out all fields.', 'warning')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        
        # Hash the password
        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_base64 = base64.b64encode(hashed).decode('utf-8')  # Encode to base64 string
        
        conn = sqlite3.connect('database.db')
        conn.execute("PRAGMA foreign_keys = ON;")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_base64))
            conn.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Please choose a different one.', 'danger')
        except Exception as e:
            flash('An unexpected error occurred during registration. Please try again.', 'danger')
            logger.error(f"Registration Error: {e}")
        finally:
            conn.close()
    
    return render_template('register.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Input Validation
        if not username or not password:
            flash('Please enter both username and password.', 'warning')
            return render_template('login.html')
        
        # Verify credentials from the database
        conn = sqlite3.connect('database.db')
        conn.execute("PRAGMA foreign_keys = ON;")
        c = conn.cursor()
        c.execute("SELECT password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user:
            try:
                # Decode the stored hashed password from base64 string to bytes
                stored_hashed = base64.b64decode(user[0].encode('utf-8'))
                
                if bcrypt.checkpw(password.encode('utf-8'), stored_hashed):
                    session['user'] = username  # Store the username in session
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
            except Exception as e:
                flash('An error occurred during login. Please try again.', 'danger')
                logger.error(f"Login Error: {e}")
        
        flash('Invalid credentials, please try again.', 'danger')
    
    return render_template('login.html')

# Dashboard Route
@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        savings = calculate_savings(session['user'])
        return render_template('dashboard.html', savings=savings)
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# Calculate user savings
def calculate_savings(username):
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    standard_price = 500
    c.execute("SELECT SUM(booking_price) FROM bookings WHERE username=?", (username,))
    result = c.fetchone()
    if result and result[0] is not None:
        user_spending = result[0]
        c.execute("SELECT COUNT(*) FROM bookings WHERE username=?", (username,))
        num_bookings = c.fetchone()[0]
        savings = (standard_price * num_bookings) - user_spending
    else:
        savings = 0
    conn.close()
    return savings

# Search Flights Route
@app.route('/search_flights', methods=['GET', 'POST'])
def search_flights():
    if 'user' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        origin = request.form.get('origin', '').upper().strip()
        destination = request.form.get('destination', '').upper().strip()
        departure_date = request.form.get('departure_date')

        # Validate inputs
        if not origin or not destination or not departure_date:
            flash("Please provide all required fields.", "warning")
            return render_template('search_flights.html')

        try:
            # Use Amadeus API to search for flights
            response = amadeus.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=departure_date,
                adults=1,
                max=10
            )

            flight_data = response.data
            flights = []
            for offer in flight_data:
                flight = {
                    'flight_id': offer['id'],
                    'price': offer['price']['total'],
                }

                # Extract details from the first segment
                if offer['itineraries'] and offer['itineraries'][0]['segments']:
                    first_segment = offer['itineraries'][0]['segments'][0]
                    flight['airline'] = first_segment['carrierCode']
                    flight['flight_number'] = first_segment['carrierCode'] + first_segment['number']
                    flight['origin'] = first_segment['departure']['iataCode']
                    flight['destination'] = first_segment['arrival']['iataCode']
                    flight['departure_time'] = first_segment['departure']['at']
                    flight['arrival_time'] = first_segment['arrival']['at']
                else:
                    # Handle cases with no segments
                    flight['airline'] = "N/A"
                    flight['flight_number'] = "N/A"
                    flight['origin'] = "N/A"
                    flight['destination'] = "N/A"
                    flight['departure_time'] = "N/A"
                    flight['arrival_time'] = "N/A"

                flights.append(flight)

            # Store flights in session
            session['flights'] = flights

            return render_template('search_flights.html', flights=flights)

        except ResponseError as error:
            flash(f"An error occurred while searching for flights: {error}", "danger")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    else:
        # GET request: generate recommendations
        recommendations = get_recommendations(session['user'])
        return render_template('search_flights.html', recommendations=recommendations)
from opensky_api import OpenSkyApi

@app.route('/analytics')
def analytics():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Query to get booking counts per flight
    c.execute("SELECT flight_id, COUNT(*) FROM bookings GROUP BY flight_id")
    booking_data = c.fetchall()

    # Query to get coupon usage counts
    c.execute("SELECT coupon_code, COUNT(*) FROM coupons GROUP BY coupon_code")
    coupon_data = c.fetchall()

    conn.close()
    return render_template('analytics.html', bookings=booking_data, coupons=coupon_data)



@app.route('/flight_details/<string:flight_number>')
def flight_details(flight_number):
    api = OpenSkyApi()  # Initialize OpenSky API (no authentication needed)

    try:
        # Fetch all available flight states
        states = api.get_states()

        # Filter the flight by matching the flight number with the callsign
        flight_data = next(
            (s for s in states.states if s.callsign and flight_number in s.callsign.strip()), None
        )

        if flight_data:
            # If live data is available, render it
            return render_template(
                'flight_details.html', flight=flight_data, saved_flight=None
            )

        # If no live data is found, fetch the flight details from the database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute(
            '''
            SELECT airline, flight_number, origin, destination, departure_time, arrival_time, booking_price
            FROM bookings WHERE flight_number = ?
            ''', (flight_number,)
        )
        saved_flight = c.fetchone()
        conn.close()

        if saved_flight:
            return render_template(
                'flight_details.html', flight=None, saved_flight=saved_flight
            )

        flash(f"No details found for flight {flight_number}.", "warning")
        return redirect(url_for('show_booked_flights'))

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "danger")
        return redirect(url_for('show_booked_flights'))


@app.route('/book_flight', methods=['POST'])
def book_flight():
    if 'user' not in session:
        flash("Please log in to book a flight.", "warning")
        return redirect(url_for('login'))
    
    # Get flight data from the form
    flight_id = request.form.get('flight_id')
    price = request.form.get('price')
    
    if not flight_id or not price:
        flash("Invalid flight data.", "warning")
        return redirect(url_for('search_flights'))
    
    # Retrieve flights from session
    flights = session.get('flights', [])
    
    # Find the flight with the matching flight_id
    flight_data = next((flight for flight in flights if flight['flight_id'] == flight_id), None)
    
    if not flight_data:
        flash("Flight data not found. Please search again.", "warning")
        return redirect(url_for('search_flights'))
    
    # Extract flight details
    airline = flight_data.get('airline', "N/A")
    flight_number = flight_data.get('flight_number', "N/A")
    origin = flight_data.get('origin', "N/A")
    destination = flight_data.get('destination', "N/A")
    departure_time = flight_data.get('departure_time', "N/A")
    arrival_time = flight_data.get('arrival_time', "N/A")
    price = flight_data.get('price', "N/A")
    
    # Save booking to the database
    conn = sqlite3.connect('database.db')
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO bookings (
                username, flight_id, booking_price, origin, destination, departure_time, arrival_time, airline, flight_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            session['user'], flight_id, float(price), origin, destination, departure_time, arrival_time, airline, flight_number
        ))
        conn.commit()
        flash('Flight booked successfully!', 'success')
    except sqlite3.Error as e:
        flash(f"An error occurred while booking the flight: {e}", 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('dashboard'))

# Show Booked Flights Route
@app.route('/show_booked_flights')
def show_booked_flights():
    if 'user' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    try:
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Fetch user's non-cancelled flights
        c.execute('''
            SELECT id, airline, flight_number, origin, destination, 
                   departure_time, arrival_time, booking_price
            FROM bookings
            WHERE username = ? AND cancelled = 0
        ''', (session['user'],))
        flights = c.fetchall()

        # Fetch live flight statuses (if available)
        c.execute('SELECT flight_id, status FROM live_flights')
        live_data = c.fetchall()

        # Create a dictionary from the live flight data
        live_flights = {flight_id: status for flight_id, status in live_data}

        conn.close()

        # Pass flights and live_flights to the template
        return render_template('show_booked_flights.html', flights=flights, live_flights=live_flights)

    except Exception as e:
        flash(f"An error occurred while fetching booked flights: {e}", "danger")
        logger.exception(f"Error in /show_booked_flights route: {e}")
        return redirect(url_for('dashboard'))

def fetch_live_flight_statuses():
    """
    Fetch live flight statuses from OpenSky API and update the live_flights table.
    """
    logger.info("Fetching live flight statuses from OpenSky API.")
    try:
        # Retrieve flight states from OpenSky API
        states = opensky_api.get_states()
        logger.info(f"Retrieved {len(states.states)} flight states from OpenSky.")

        # Connect to the database
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # Update live_flights table with status data
        for s in states.states:
            flight_id = s.icao24  # This is the flight's unique ID from OpenSky
            status = "On Ground" if s.on_ground else "In Air"
            last_updated = datetime.utcnow()

            # Insert or replace data into the live_flights table
            c.execute('''
                INSERT OR REPLACE INTO live_flights (
                    flight_id, airline, flight_number, origin, destination,
                    departure_time, arrival_time, status, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                flight_id, s.origin_country, s.callsign.strip() if s.callsign else "N/A",
                "N/A", "N/A", "N/A", "N/A", status, last_updated
            ))

        conn.commit()
        logger.info("Live flights data updated successfully.")
        conn.close()
    except Exception as e:
        logger.exception(f"Error fetching live flight statuses: {e}")

# Profile Route
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' in session:
        username = session['user']
        conn = sqlite3.connect('database.db')
        conn.execute("PRAGMA foreign_keys = ON;")
        c = conn.cursor()

        # Retrieve user preferences
        c.execute("SELECT preferences FROM users WHERE username=?", (username,))
        result = c.fetchone()
        preferences = result[0] if result and result[0] else ''

        # Fetch analytics data for the user
        # Get flight booking counts for the user
        c.execute("SELECT flight_id, COUNT(*) FROM bookings WHERE username=? GROUP BY flight_id", (username,))
        booking_data = c.fetchall()

        # Get coupon usage data for the user
        c.execute("SELECT coupon_code, COUNT(*) FROM coupons WHERE username=? GROUP BY coupon_code", (username,))
        coupon_data = c.fetchall()

        conn.close()

        if request.method == 'POST':
            new_preferences = request.form.get('preferences', '').strip()
            # Save the updated preferences
            try:
                conn = sqlite3.connect('database.db')
                conn.execute("PRAGMA foreign_keys = ON;")
                c = conn.cursor()
                c.execute("UPDATE users SET preferences=? WHERE username=?", (new_preferences, username))
                conn.commit()
                flash('Preferences updated successfully!', 'success')
            except sqlite3.Error as e:
                flash(f"An error occurred while updating preferences: {e}", 'danger')
            finally:
                conn.close()
            return redirect(url_for('profile'))

        return render_template('profile.html', username=username, preferences=preferences,
                               bookings=booking_data, coupons=coupon_data)
    else:
        flash('Please log in first.', 'warning')
        return redirect(url_for('login'))

def get_flights_in_area(min_lat, max_lat, min_lon, max_lon):
    api = OpenSkyApi()
    try:
        states = api.get_states(bbox=(min_lat, max_lat, min_lon, max_lon))
        flights = []
        for s in states.states:
            flights.append({
                'airline': s.callsign,
                'origin': s.origin_country,
                'longitude': s.longitude,
                'latitude': s.latitude,
                'altitude': s.baro_altitude,
                'velocity': s.velocity
            })
        return flights
    except Exception as e:
        print(f"Error retrieving flight data: {e}")
        return []

# Add Coupon Route
@app.route('/add_coupon', methods=['GET', 'POST'])
def add_coupon():
    if 'user' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        coupon_code = request.form.get('coupon_code', '').strip()
        discount = request.form.get('discount')
        
        # Input Validation
        if not coupon_code or not discount:
            flash("Please provide both coupon code and discount.", "warning")
            return render_template('add_coupon.html')
        
        try:
            discount = float(discount)
        except ValueError:
            flash("Discount must be a number.", "danger")
            return render_template('add_coupon.html')
        
        # Save coupon to the database associated with the current user
        conn = sqlite3.connect('database.db')
        conn.execute("PRAGMA foreign_keys = ON;")
        c = conn.cursor()
        try:
            c.execute("INSERT INTO coupons (username, coupon_code, discount) VALUES (?, ?, ?)", 
                      (session['user'], coupon_code, discount))
            conn.commit()
            flash('Coupon added successfully!', 'success')
        except sqlite3.Error as e:
            flash(f"An error occurred while adding the coupon: {e}", "danger")
        finally:
            conn.close()
        
        return redirect(url_for('add_coupon'))
    
    return render_template('add_coupon.html')
# Cancel Flight Route
# Cancel Flight Route
@app.route('/cancel_flight/<int:flight_id>', methods=['POST'])
def cancel_flight(flight_id):
    if 'user' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    try:
        # Delete the selected flight
        c.execute('DELETE FROM bookings WHERE id = ?', (flight_id,))
        conn.commit()
        flash('Flight canceled successfully! Please rebook a new flight.', 'success')
    except sqlite3.Error as e:
        flash(f"An error occurred while canceling the flight: {e}", 'danger')
    finally:
        conn.close()

    # Redirect to the search flights page after cancellation
    return redirect(url_for('search_flights'))

# Rebook Flights Route
@app.route('/rebook_flights', methods=['GET', 'POST'])
def rebook_flights():
    if 'user' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # Fetch the user's booked flights
    c.execute('''
        SELECT id, airline, flight_number, origin, destination, 
               departure_time, arrival_time, booking_price
        FROM bookings
        WHERE username = ?
    ''', (session['user'],))
    flights = c.fetchall()
    conn.close()

    return render_template('rebook_flights.html', flights=flights)

# Show Coupons Route
@app.route('/show_coupons')
def show_coupons():
    if 'user' in session:
        conn = sqlite3.connect('database.db')
        conn.execute("PRAGMA foreign_keys = ON;")
        c = conn.cursor()
        c.execute("SELECT coupon_code, discount FROM coupons WHERE username=?", (session['user'],))
        coupons = c.fetchall()
        conn.close()
        return render_template('show_coupons.html', coupons=coupons)
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove the user from the session
    flash("You have been logged out.", "info")  # Flash a message to the user
    return redirect(url_for('home'))  # Redirect to the home page

# AI Chatbot Route
@app.route('/chatbot', methods=['GET'])
def chatbot():
    if 'user' in session:
        return render_template('chatbot.html')
    else:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))

# AI Chatbot Response Route using Google Generative AI (Gemini API)
@app.route('/get_response', methods=['POST'])
def get_response():
    if 'user' not in session:
        return jsonify({'response': "Please log in to use the chatbot."}), 403
    
    user_message = request.form.get('message', '').strip()
    
    if not user_message:
        return jsonify({'response': "Please enter a message."}), 400
    
    try:
        # Initialize the Generative Model
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Generate a response from the AI
        response = model.generate_content(user_message)
        
        # Extract the text from the response
        bot_response = response.text
        
        # Log the conversation (Optional)
        logger.info(f"User: {user_message}")
        logger.info(f"Bot: {bot_response}")
        
    except Exception as e:
        # Log the exception details (avoid printing sensitive information)
        logger.error(f"Error interacting with Gemini API: {e}")
        bot_response = "I'm sorry, I can't assist with that right now."
    
    return jsonify({'response': bot_response})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
