from .conftest import MOCK_CART_ITEM, MOCK_PRODUCT

CART_ITEM_CREATE_DATA = {
    "productId": "product-1",
    "type": "BUY",
    "quantity": 2,
}


class TestGetCart:
    def test_get_cart(self, patient_client, mock_db):
        mock_db.cartitem.find_many.return_value = [MOCK_CART_ITEM]

        response = patient_client.get("/api/v1/cart")

        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["total"] == 1000.0
        assert body["deliveryFee"] == 150.0
        assert body["grandTotal"] == 1150.0

    def test_get_cart_empty(self, patient_client, mock_db):
        mock_db.cartitem.find_many.return_value = []

        response = patient_client.get("/api/v1/cart")

        assert response.status_code == 200
        body = response.json()
        assert body["items"] == []
        assert body["total"] == 0.0
        assert body["deliveryFee"] == 150.0


class TestAddToCart:
    def test_add_item(self, patient_client, mock_db):
        mock_db.product.find_unique.return_value = MOCK_PRODUCT
        mock_db.cartitem.create.return_value = MOCK_CART_ITEM
        mock_db.cartitem.find_unique.return_value = MOCK_CART_ITEM

        response = patient_client.post("/api/v1/cart", json=CART_ITEM_CREATE_DATA)

        assert response.status_code == 201
        assert response.json()["id"] == "cart-1"

    def test_add_item_product_not_found(self, patient_client, mock_db):
        mock_db.product.find_unique.return_value = None

        response = patient_client.post("/api/v1/cart", json=CART_ITEM_CREATE_DATA)

        assert response.status_code == 404


class TestUpdateCartItem:
    def test_update_item(self, patient_client, mock_db):
        mock_db.cartitem.find_unique.return_value = MOCK_CART_ITEM
        mock_db.cartitem.update.return_value = MOCK_CART_ITEM

        response = patient_client.put(
            "/api/v1/cart/cart-1", json={"quantity": 3}
        )

        assert response.status_code == 200

    def test_update_item_not_found(self, patient_client, mock_db):
        mock_db.cartitem.find_unique.return_value = None

        response = patient_client.put(
            "/api/v1/cart/unknown", json={"quantity": 3}
        )

        assert response.status_code == 404

    def test_update_other_users_item_forbidden(self, therapist_client, mock_db):
        mock_db.cartitem.find_unique.return_value = MOCK_CART_ITEM

        response = therapist_client.put(
            "/api/v1/cart/cart-1", json={"quantity": 3}
        )

        assert response.status_code == 404


class TestDeleteCartItem:
    def test_delete_item(self, patient_client, mock_db):
        mock_db.cartitem.find_unique.return_value = MOCK_CART_ITEM

        response = patient_client.delete("/api/v1/cart/cart-1")

        assert response.status_code == 204

    def test_delete_item_not_found(self, patient_client, mock_db):
        mock_db.cartitem.find_unique.return_value = None

        response = patient_client.delete("/api/v1/cart/unknown")

        assert response.status_code == 404

    def test_delete_other_users_item_forbidden(self, therapist_client, mock_db):
        mock_db.cartitem.find_unique.return_value = MOCK_CART_ITEM

        response = therapist_client.delete("/api/v1/cart/cart-1")

        assert response.status_code == 404


class TestClearCart:
    def test_clear_cart(self, patient_client, mock_db):
        response = patient_client.delete("/api/v1/cart")

        assert response.status_code == 204


class TestCartDeliverFee:
    def test_delivery_fee_applied_below_threshold(self, patient_client, mock_db):
        cheap_item = MOCK_CART_ITEM
        cheap_item.product.price = 100.0
        mock_db.cartitem.find_many.return_value = [cheap_item]

        response = patient_client.get("/api/v1/cart")

        assert response.status_code == 200
        body = response.json()
        assert body["deliveryFee"] == 150.0

    def test_delivery_fee_waived_above_threshold(self, patient_client, mock_db):
        expensive_item = MOCK_CART_ITEM
        expensive_item.product.price = 2500.0
        mock_db.cartitem.find_many.return_value = [expensive_item]

        response = patient_client.get("/api/v1/cart")

        assert response.status_code == 200
        body = response.json()
        assert body["deliveryFee"] == 0.0
