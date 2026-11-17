import copy
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import src.app as app_module


ACTIVITY_NAME = "Chess Club"
PARTICIPANT_EMAIL = "test.student@mergington.edu"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "activities", copy.deepcopy(app_module.activities))

    with TestClient(app_module.app) as test_client:
        yield test_client


def test_get_activities_returns_activity_data(client):
    # Arrange
    expected_activity = ACTIVITY_NAME

    # Act
    response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    activities = response.json()
    assert expected_activity in activities
    assert {
        "description",
        "schedule",
        "max_participants",
        "participants",
    } <= activities[expected_activity].keys()


def test_signup_adds_participant(client):
    # Arrange
    activity_url = f"/activities/{ACTIVITY_NAME.replace(' ', '%20')}/signup"

    # Act
    response = client.post(activity_url, params={"email": PARTICIPANT_EMAIL})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {
        "message": f"Signed up {PARTICIPANT_EMAIL} for {ACTIVITY_NAME}"
    }
    assert PARTICIPANT_EMAIL in activities_response.json()[ACTIVITY_NAME]["participants"]


def test_signup_rejects_duplicate_participant(client):
    # Arrange
    activity_url = f"/activities/{ACTIVITY_NAME.replace(' ', '%20')}/signup"
    client.post(activity_url, params={"email": PARTICIPANT_EMAIL})

    # Act
    response = client.post(activity_url, params={"email": PARTICIPANT_EMAIL})
    participants = client.get("/activities").json()[ACTIVITY_NAME]["participants"]

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"
    assert participants.count(PARTICIPANT_EMAIL) == 1


def test_concurrent_signups_reject_duplicate_participant(client):
    def signup():
        try:
            app_module.signup_for_activity(ACTIVITY_NAME, PARTICIPANT_EMAIL)
            return 200
        except HTTPException as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(lambda _: signup(), range(8)))

    assert statuses.count(200) == 1
    assert statuses.count(400) == 7
    participants = client.get("/activities").json()[ACTIVITY_NAME]["participants"]
    assert participants.count(PARTICIPANT_EMAIL) == 1


def test_signup_returns_404_for_unknown_activity(client):
    # Arrange
    activity_url = "/activities/Unknown%20Activity/signup"

    # Act
    response = client.post(activity_url, params={"email": PARTICIPANT_EMAIL})

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_delete_removes_participant(client):
    # Arrange
    email = "michael@mergington.edu"
    activity_url = f"/activities/{ACTIVITY_NAME.replace(' ', '%20')}/signup"

    # Act
    response = client.delete(activity_url, params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {ACTIVITY_NAME}"}
    assert email not in activities_response.json()[ACTIVITY_NAME]["participants"]


def test_delete_is_idempotent_for_unregistered_participant(client):
    # Arrange
    email = PARTICIPANT_EMAIL
    activity_url = f"/activities/{ACTIVITY_NAME.replace(' ', '%20')}/signup"

    # Act
    response = client.delete(activity_url, params={"email": email})
    activities_response = client.get("/activities")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {ACTIVITY_NAME}"}
    assert email not in activities_response.json()[ACTIVITY_NAME]["participants"]


def test_delete_returns_404_for_unknown_activity(client):
    # Arrange
    activity_url = "/activities/Unknown%20Activity/signup"

    # Act
    response = client.delete(activity_url, params={"email": PARTICIPANT_EMAIL})

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"