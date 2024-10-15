from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    username = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(128), nullable=False)
    preferences = db.Column(db.Text)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    flight_id = db.Column(db.String(20))
    booking_price = db.Column(db.Float)
    origin = db.Column(db.String(10))
    destination = db.Column(db.String(10))
    departure_time = db.Column(db.String(30))
    arrival_time = db.Column(db.String(30))
    airline = db.Column(db.String(10))
    flight_number = db.Column(db.String(20))

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False)
    coupon_code = db.Column(db.String(20))
    discount = db.Column(db.Float)
