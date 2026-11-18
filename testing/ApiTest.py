from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_create_product():
    response = client.post(
        "/products", json={"name": "Keyboard", "price_cents": 150000, "stock": 10}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Keyboard"
    assert data["price_cents"] == 150000
    assert data["stock"] == 10
    assert "id" in data


def test_list_and_get_product():
    create_res = client.post(
        "/products", json={"name": "Mouse", "price_cents": 2500, "stock": 50}
    )
    product_id = create_res.json()["id"]

    # List products
    list_res = client.get("/products")
    assert list_res.status_code == 200
    assert any(p["id"] == product_id for p in list_res.json())

    # Get product
    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Mouse"


def test_update_product():
    create_res = client.post(
        "/products", json={"name": "Monitor", "price_cents": 30000, "stock": 5}
    )
    product_id = create_res.json()["id"]

    # Update product
    update_res = client.put(
        f"/products/{product_id}",
        json={"name": "4K Monitor", "price_cents": 35000, "stock": 8},
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "4K Monitor"
    assert update_res.json()["price_cents"] == 35000
    assert update_res.json()["stock"] == 8


def test_delete_product():
    create_res = client.post(
        "/products", json={"name": "Headphones", "price_cents": 8000, "stock": 15}
    )
    product_id = create_res.json()["id"]

    # Delete product
    del_res = client.delete(f"/products/{product_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_res = client.get(f"/products/{product_id}")
    assert get_res.status_code == 404


def test_product_not_found():
    assert client.get("/products/999999").status_code == 404
    assert (
        client.put(
            "/products/999999",
            json={"name": "None", "price_cents": 100, "stock": 1},
        ).status_code
        == 404
    )
    assert client.delete("/products/999999").status_code == 404
