# Legacy-модуль обработки заказов.
# ВНИМАНИЕ: код намеренно написан с антипаттернами для учебных целей (см. /analyze-legacy).
import logging
import sqlite3
from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)


class OrderValidationError(ValueError):
    """Raised when an incoming order payload is invalid."""


class OrderStorageError(RuntimeError):
    """Raised when the order cannot be persisted to the database."""


def _validate_customer(customer: object) -> str:
    if customer is None or not isinstance(customer, str):
        raise OrderValidationError("Order customer must be a non-empty string.")
    cleaned_customer = customer.strip()
    if cleaned_customer == "":
        raise OrderValidationError("Order customer must not be empty.")
    return cleaned_customer


def _validate_items(items: object) -> list[dict[str, object]]:
    if items is None:
        raise OrderValidationError("Order items are required.")
    if not isinstance(items, list) or not items:
        raise OrderValidationError("Order items must be a non-empty list.")

    validated_items: list[dict[str, object]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise OrderValidationError(f"Item at index {index} must be a dictionary.")

        price = item.get("price")
        qty = item.get("qty")

        if not isinstance(price, (int, float)) or isinstance(price, bool):
            raise OrderValidationError(f"Item at index {index} has an invalid price.")
        if price < 0:
            raise OrderValidationError(f"Item at index {index} has a negative price.")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 0:
            raise OrderValidationError(f"Item at index {index} has an invalid quantity.")

        validated_items.append({"price": float(price), "qty": qty})
    return validated_items


def _calculate_total(items: Sequence[Mapping[str, object]]) -> float:
    return sum(float(item["price"]) * int(item["qty"]) for item in items)


def _apply_discount(total: float, discount: object) -> float:
    if discount is None:
        return total
    if not isinstance(discount, (int, float)) or isinstance(discount, bool):
        raise OrderValidationError("Order discount must be a number.")
    if discount < 0 or discount > 100:
        raise OrderValidationError("Order discount must be within 0 and 100 percent.")
    return total - total * float(discount) / 100


def _apply_tax(total: float, country: object) -> float:
    if country is None:
        return total
    if not isinstance(country, str):
        raise OrderValidationError("Order country must be a string when provided.")

    normalized_country = country.upper()
    if normalized_country == "KZ":
        return total + total * 12 / 100
    if normalized_country == "RU":
        return total + total * 20 / 100
    if normalized_country == "US":
        return total + total * 8 / 100
    return total


def _save_order(db: sqlite3.Connection, customer: str, total: float, status: str) -> None:
    if db is None:
        raise OrderStorageError("Database connection is required.")

    try:
        db.execute(
            "INSERT INTO orders (customer, total, status) VALUES (?, ?, ?)",
            (customer, total, status),
        )
        db.commit()
    except sqlite3.Error as exc:  # pragma: no cover - exercised via real DB errors in hidden tests
        logger.exception("Failed to save order for %s", customer)
        raise OrderStorageError("Could not save the order to the database.") from exc


def process_order(order: dict[str, object] | None, db: sqlite3.Connection) -> bool:
    """Validate and save a new order."""
    if order is None:
        raise OrderValidationError("Order payload is required.")

    customer = _validate_customer(order.get("customer"))
    items = _validate_items(order.get("items"))

    total = _calculate_total(items)
    total = _apply_discount(total, order.get("discount"))
    total = _apply_tax(total, order.get("country"))

    _save_order(db, customer, total, "new")
    logger.info("Saved order for %s, total %.2f", customer, total)
    return True


def process_refund(order: dict[str, object] | None, db: sqlite3.Connection) -> bool:
    """Validate and save a refund entry."""
    if order is None:
        raise OrderValidationError("Order payload is required.")

    customer = _validate_customer(order.get("customer"))
    items = _validate_items(order.get("items"))

    total = _calculate_total(items)
    _save_order(db, customer, -total, "refund")
    logger.info("Saved refund for %s, total %.2f", customer, total)
    return True


def create_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "customer TEXT, total REAL, status TEXT)"
    )
    return db
