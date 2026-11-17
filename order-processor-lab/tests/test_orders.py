"""Базовые тесты счастливого пути. Добавлены проверки граничных значений."""

import pytest

from orders import OrderValidationError, create_db, process_order, process_refund


def test_process_order_saves_total_without_tax() -> None:
    db = create_db()
    order = {"customer": "Anna", "items": [{"price": 100, "qty": 2}]}

    assert process_order(order, db) is True

    row = db.execute("SELECT customer, total, status FROM orders").fetchone()
    assert row == ("Anna", 200, "new")


def test_process_order_applies_discount_and_kz_tax() -> None:
    db = create_db()
    order = {
        "customer": "Bek",
        "items": [{"price": 100, "qty": 1}],
        "discount": 10,
        "country": "KZ",
    }

    assert process_order(order, db) is True

    total = db.execute("SELECT total FROM orders").fetchone()[0]
    assert round(total, 2) == 100.8


def test_process_refund_saves_negative_total() -> None:
    db = create_db()
    order = {"customer": "Anna", "items": [{"price": 50, "qty": 2}]}

    assert process_refund(order, db) is True

    row = db.execute("SELECT total, status FROM orders").fetchone()
    assert row == (-100, "refund")


@pytest.mark.parametrize(
    ("order", "expected_message"),
    [
        (None, "Order payload is required."),
        ({"items": [{"price": 10, "qty": 1}]}, "Order customer must be"),
        (
            {"customer": "   ", "items": [{"price": 10, "qty": 1}]},
            "Order customer must not be empty.",
        ),
    ],
)
def test_process_order_validates_required_fields(
    order: dict[str, object] | None, expected_message: str
) -> None:
    db = create_db()

    with pytest.raises(OrderValidationError, match=expected_message):
        process_order(order, db)


@pytest.mark.parametrize(
    "order",
    [
        {"customer": "Anna", "items": [{"price": -1, "qty": 2}]},
        {"customer": "Anna", "items": [{"price": 10, "qty": -1}]},
        {"customer": "Anna", "items": [{"price": "10", "qty": 2}]},
    ],
)
def test_process_order_rejects_invalid_items(order: dict[str, object]) -> None:
    db = create_db()

    with pytest.raises(OrderValidationError):
        process_order(order, db)


def test_process_refund_validates_customer() -> None:
    db = create_db()

    with pytest.raises(OrderValidationError, match="Order customer must be"):
        process_refund({"items": [{"price": 10, "qty": 2}]}, db)
