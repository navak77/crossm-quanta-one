from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Length, EqualTo

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class SearchFlightsForm(FlaskForm):
    origin = StringField('Origin', validators=[DataRequired(), Length(min=3, max=3)])
    destination = StringField('Destination', validators=[DataRequired(), Length(min=3, max=3)])
    departure_date = StringField('Departure Date', validators=[DataRequired()])
    submit = SubmitField('Search Flights')

class ProfileForm(FlaskForm):
    preferences = TextAreaField('Preferences')
    submit = SubmitField('Update Preferences')
