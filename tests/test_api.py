import base64

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model import gemini_client, model_error, read_gemini_text

# smallest bytes that pass the jpeg check, the fake model never looks inside
fake_jpeg = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0fake").decode()


class fake_client:
    name = "fake"

    def __init__(self, reply="", fail=False):
        self.reply = reply
        self.fail = fail
        self.prompts = []

    async def ask(self, prompt, image_bytes):
        self.prompts.append(prompt)
        if self.fail:
            raise model_error("down")
        return self.reply


@pytest.fixture
def client():
    original = app.state.model_client
    yield TestClient(app)
    app.state.model_client = original


def test_health(client):
    app.state.model_client = fake_client()
    assert client.get("/api/health").json() == {"ok": True, "backend": "fake"}


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "GemmaSight" in response.text


def test_describe_returns_answer(client):
    app.state.model_client = fake_client('{"speech": "A door ahead, open.", "hazard": true}')
    response = client.post("/api/ask", json={"mode": "describe", "image": fake_jpeg})
    assert response.status_code == 200
    body = response.json()
    assert body["speech"] == "A door ahead, open."
    assert body["hazard"] is True


def test_find_passes_target_to_prompt(client):
    fake = fake_client('{"found": true, "label": "phone", "position": "left", "distance": "far"}')
    app.state.model_client = fake
    response = client.post("/api/ask", json={"mode": "find", "text": "phone", "image": fake_jpeg})
    assert response.json()["speech"] == "phone, at 10 o'clock, far away."
    assert '"phone"' in fake.prompts[0]


def test_find_with_word_directions(client):
    app.state.model_client = fake_client('{"found": true, "label": "cup", "position": "slightly right", "distance": "near"}')
    response = client.post("/api/ask", json={"mode": "find", "text": "cup", "directions": "words", "image": fake_jpeg})
    assert response.json()["speech"] == "cup, slightly to your right, within reach."


def test_unknown_direction_style_is_rejected(client):
    response = client.post("/api/ask", json={"mode": "find", "text": "cup", "directions": "compass", "image": fake_jpeg})
    assert response.status_code == 422


def test_find_without_text_is_rejected(client):
    app.state.model_client = fake_client()
    response = client.post("/api/ask", json={"mode": "find", "image": fake_jpeg})
    assert response.status_code == 400


def test_non_jpeg_is_rejected(client):
    app.state.model_client = fake_client()
    png = base64.b64encode(b"\x89PNG....").decode()
    response = client.post("/api/ask", json={"mode": "read", "image": png})
    assert response.status_code == 400


def test_bad_base64_is_rejected(client):
    app.state.model_client = fake_client()
    response = client.post("/api/ask", json={"mode": "read", "image": "not base64!!"})
    assert response.status_code == 400


def test_unknown_mode_is_rejected(client):
    response = client.post("/api/ask", json={"mode": "drive", "image": fake_jpeg})
    assert response.status_code == 422


def test_model_failure_gives_spoken_error(client):
    app.state.model_client = fake_client(fail=True)
    response = client.post("/api/ask", json={"mode": "read", "image": fake_jpeg, "lang": "sw"})
    body = response.json()
    assert body["error"] is True
    assert "Tafadhali" in body["speech"]


def test_gemini_body_has_image_and_text():
    body = gemini_client("key", "gemma-4-26b-a4b-it").build_body("hello", b"\xff\xd8")
    parts = body["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/jpeg"
    assert parts[1]["text"] == "hello"
    assert body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "minimal"


def test_gemini_text_skips_thoughts():
    data = {"candidates": [{"content": {"parts": [
        {"text": "let me think", "thought": True},
        {"text": '{"speech": "hi"}'},
    ]}}]}
    assert read_gemini_text(data) == '{"speech": "hi"}'


def test_gemini_text_raises_without_candidates():
    with pytest.raises(model_error):
        read_gemini_text({"promptFeedback": {"blockReason": "SAFETY"}})
