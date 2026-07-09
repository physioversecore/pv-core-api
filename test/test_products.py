from .conftest import MOCK_PRODUCT

PRODUCT_CREATE_DATA = {
    "name": "New Product",
    "category": "EQUIPMENT",
    "price": 500.0,
}


class TestListProducts:
    def test_list_products(self, client, mock_db):
        mock_db.product.find_many.return_value = [MOCK_PRODUCT]
        mock_db.product.count.return_value = 1

        response = client.get("/api/v1/products")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["products"][0]["name"] == "Test Product"

    def test_list_products_with_category_filter(self, client, mock_db):
        mock_db.product.find_many.return_value = [MOCK_PRODUCT]
        mock_db.product.count.return_value = 1

        response = client.get("/api/v1/products?category=EQUIPMENT")

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_list_products_empty(self, client, mock_db):
        mock_db.product.find_many.return_value = []
        mock_db.product.count.return_value = 0

        response = client.get("/api/v1/products")

        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestGetProduct:
    def test_get_by_id(self, client, mock_db):
        mock_db.product.find_unique.return_value = MOCK_PRODUCT

        response = client.get("/api/v1/products/product-1")

        assert response.status_code == 200
        assert response.json()["id"] == "product-1"

    def test_get_not_found(self, client, mock_db):
        mock_db.product.find_unique.return_value = None

        response = client.get("/api/v1/products/unknown")

        assert response.status_code == 404


class TestCreateProduct:
    def test_create_by_admin(self, admin_client, mock_db):
        mock_db.product.create.return_value = MOCK_PRODUCT

        response = admin_client.post("/api/v1/products", json=PRODUCT_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "product-1"

    def test_create_by_non_admin_forbidden(self, patient_client):
        response = patient_client.post("/api/v1/products", json=PRODUCT_CREATE_DATA)

        assert response.status_code == 403


class TestUpdateProduct:
    def test_update_by_admin(self, admin_client, mock_db):
        mock_db.product.find_unique.return_value = MOCK_PRODUCT
        mock_db.product.update.return_value = MOCK_PRODUCT

        response = admin_client.put(
            "/api/v1/products/product-1", json={"price": 600.0}
        )

        assert response.status_code == 200
        assert response.json()["id"] == "product-1"

    def test_update_by_non_admin_forbidden(self, patient_client):
        response = patient_client.put(
            "/api/v1/products/product-1", json={"price": 600.0}
        )

        assert response.status_code == 403

    def test_update_not_found(self, admin_client, mock_db):
        mock_db.product.find_unique.return_value = None

        response = admin_client.put(
            "/api/v1/products/unknown", json={"price": 600.0}
        )

        assert response.status_code == 404


class TestDeleteProduct:
    def test_delete_by_admin(self, admin_client, mock_db):
        mock_db.product.find_unique.return_value = MOCK_PRODUCT

        response = admin_client.delete("/api/v1/products/product-1")

        assert response.status_code == 204

    def test_delete_by_non_admin_forbidden(self, patient_client):
        response = patient_client.delete("/api/v1/products/product-1")

        assert response.status_code == 403

    def test_delete_not_found(self, admin_client, mock_db):
        mock_db.product.find_unique.return_value = None

        response = admin_client.delete("/api/v1/products/unknown")

        assert response.status_code == 404
