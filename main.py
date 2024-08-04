import os
import re
from datetime import datetime, date
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

# Configuration from environment variables
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_HOST = os.environ.get("DB_HOST")

# Configure SQLAlchemy
if os.environ.get("FLASK_ENV") == "production":
    # Connect to CLoud SQL instance using socket
    DATABASE_URL = f"postgresql+pg8000://{DB_USER}:{DB_PASS}@/{DB_NAME}?unix_sock=/cloudsql/{DB_HOST}/.s.PGSQL.5432"
else:
    # connect to PostgreSQL directly
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):
    __tablename__ = "users"
    username = db.Column(db.String, primary_key=True, index=True)
    dateOfBirth = db.Column(db.Date, nullable=False)


def is_valid_username(username):
    """Check if the given username is valid, containing only letters."""
    return re.match("^[A-Za-z]+$", username) is not None


def init_db():
    """Initialize the database, creating tables if they don't exist."""
    with app.app_context():
        db.create_all()


@app.route("/hello/<username>", methods=["PUT"])
def save_user(username):
    if not is_valid_username(username):
        return jsonify({"error": "Invalid username"}), 400

    data = request.get_json()
    dateOfBirth = data.get("dateOfBirth")

    try:
        dob = datetime.strptime(dateOfBirth, "%Y-%m-%d").date()
        if dob >= date.today():
            return jsonify({"error": "Date of birth must be in the past"}), 400
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    try:
        with db.session.begin():
            user = User.query.filter_by(username=username).first()
            if user:
                user.dateOfBirth = dob
            else:
                user = User(username=username, dateOfBirth=dob)
                db.session.add(user)
            db.session.commit()
            return "", 204
    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/hello/<username>", methods=["GET"])
def get_user(username):
    if not is_valid_username(username):
        return jsonify({"error": "Invalid username"}), 400
    try:
        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        dateOfBirth = user.dateOfBirth
        today = date.today()

        # Calculate the next birthday
        next_birthday = dateOfBirth.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)

        days_until_birthday = (next_birthday - today).days

        if days_until_birthday == 0:
            message = f"Hello, {username}! Happy birthday!"
        else:
            message = (
                f"Hello, {username}! Your birthday is in {days_until_birthday} day(s)"
            )

        return jsonify({"message": message}), 200
    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
