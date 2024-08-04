import json
from unittest.mock import patch, MagicMock
from datetime import date
import pytest
from sqlalchemy.exc import SQLAlchemyError
from main import app


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


@patch("main.db.session")
@patch("main.User")
def test_save_user_valid_data(mock_user, mock_session, client):
    # Arrange
    mock_user.query.filter_by.return_value.first.return_value = (
        None  # Simulate no existing user
    )
    mock_session.begin.return_value = MagicMock()  # Simulate beginning a transaction

    # Act
    response = client.put(
        "/hello/testuser",
        data=json.dumps({"dateOfBirth": "1990-01-01"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 204
    mock_session.commit.assert_called_once()
    mock_user.query.filter_by.assert_called_once_with(username="testuser")
    # Verify User creation
    _, kwargs = mock_user.call_args
    assert kwargs["dateOfBirth"] == date(1990, 1, 1)


@patch("main.db.session")
@patch("main.User")
def test_save_user_invalid_username(mock_user, mock_session, client):
    # Act
    response = client.put(
        "/hello/invalid_username!",
        data=json.dumps({"dateOfBirth": "1990-01-01"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    assert response.json == {"error": "Invalid username"}


@patch("main.db.session")
@patch("main.User")
def test_save_user_invalid_date_format(mock_user, mock_session, client):
    # Act
    response = client.put(
        "/hello/testuser",
        data=json.dumps({"dateOfBirth": "01-01-1990"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    assert response.json == {"error": "Invalid date format"}


@patch("main.db.session")
@patch("main.User")
def test_save_user_date_in_future(mock_user, mock_session, client):
    # Act
    response = client.put(
        "/hello/testuser",
        data=json.dumps({"dateOfBirth": "3000-01-01"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 400
    assert response.json == {"error": "Date of birth must be in the past"}


@patch("main.db.session")
@patch("main.User")
def test_save_user_database_error(mock_user, mock_session, client):
    # Arrange
    mock_user.query.filter_by.return_value.first.side_effect = SQLAlchemyError(
        "Database error"
    )

    # Act
    response = client.put(
        "/hello/testuser",
        data=json.dumps({"dateOfBirth": "1990-01-01"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 500
    assert response.json == {"error": "Database error"}


@patch("main.db.session")
@patch("main.User")
def test_save_user_update_existing_user(mock_user, mock_session, client):
    # Arrange
    existing_user = MagicMock()
    existing_user.dateOfBirth = date(1990, 1, 1)

    # Set up the mock to return an existing user
    mock_user.query.filter_by.return_value.first.return_value = existing_user

    # Simulate the behavior of committing to the database
    mock_session.begin.return_value = MagicMock()
    mock_session.commit = MagicMock()

    # Act
    response = client.put(
        "/hello/testuser",
        data=json.dumps({"dateOfBirth": "2000-01-01"}),
        content_type="application/json",
    )

    # Assert
    assert response.status_code == 204

    # Verify that the user's dateOfBirth was updated
    assert existing_user.dateOfBirth == date(2000, 1, 1)
    mock_session.commit.assert_called_once()
    mock_user.query.filter_by.assert_called_once_with(username="testuser")


@patch("main.User")
def test_get_user_valid_user(mock_user, client):
    # Arrange
    today = date.today()
    dob = date(1990, 1, 1)
    mock_user_instance = MagicMock()
    mock_user_instance.username = "testuser"
    mock_user_instance.dateOfBirth = dob

    # Set up the mock to return the existing user
    mock_user.query.filter_by.return_value.first.return_value = mock_user_instance

    # Calculate the next birthday and days until birthday
    next_birthday = dob.replace(year=today.year)
    if next_birthday < today:
        next_birthday = next_birthday.replace(year=today.year + 1)
    days_until_birthday = (next_birthday - today).days

    # Act
    response = client.get("/hello/testuser")

    # Assert
    assert response.status_code == 200
    expected_message = (
        f"Hello, testuser! Your birthday is in {days_until_birthday} day(s)"
    )
    assert response.json == {"message": expected_message}


@patch("main.User")
def test_get_user_valid_user_birthday_today(mock_user, client):
    # Arrange
    mock_user.query.filter_by.return_value.first.return_value = MagicMock(
        username="testuser", dateOfBirth=date.today()
    )

    # Act
    response = client.get("/hello/testuser")

    # Assert
    assert response.status_code == 200
    assert response.json == {"message": "Hello, testuser! Happy birthday!"}


@patch("main.User")
def test_get_user_user_not_found(mock_user, client):
    # Arrange
    mock_user.query.filter_by.return_value.first.return_value = None

    # Act
    response = client.get("/hello/testuser")

    # Assert
    assert response.status_code == 404
    assert response.json == {"error": "User not found"}


def test_get_user_invalid_username(client):
    # Act
    response = client.get("/hello/invalid_username!")

    # Assert
    assert response.status_code == 400
    assert response.json == {"error": "Invalid username"}
