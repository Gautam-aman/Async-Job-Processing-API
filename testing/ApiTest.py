from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_create_product():
    response = client.post(
        "/products", json={"name": "Keyboard", "price_cents": 150000, "stock": 10}
    )

    assert response.status_code == 201

    assert response.json()["name"] == "Keyboard"
