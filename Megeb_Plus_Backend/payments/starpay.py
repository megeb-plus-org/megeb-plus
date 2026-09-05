
import requests
from django.conf import settings


class StarPayError(Exception):
    """Raised when a StarPay API request fails."""
    pass


def normalize_starpay_phone(phone):
    """
    Normalize an Ethiopian phone number for StarPay.

    Accepted input formats:
        09XXXXXXXX
        9XXXXXXXX
        2519XXXXXXXX
        +2519XXXXXXXX

    StarPay receives the final number as:
        +2519XXXXXXXX
    """

    phone = (
        str(phone)
        .strip()
        .replace(" ", "")
        .replace("-", "")
    )

    # 09XXXXXXXX -> +2519XXXXXXXX
    if phone.startswith("09") and len(phone) == 10:
        phone = "+251" + phone[1:]

    # 9XXXXXXXX -> +2519XXXXXXXX
    elif phone.startswith("9") and len(phone) == 9:
        phone = "+251" + phone

    # 2519XXXXXXXX -> +2519XXXXXXXX
    elif phone.startswith("2519") and len(phone) == 12:
        phone = "+" + phone

    # Already normalized
    elif phone.startswith("+2519") and len(phone) == 13:
        pass

    else:
        raise StarPayError(
            "Invalid Ethiopian phone number. "
            "Use 09XXXXXXXX or +2519XXXXXXXX."
        )

    # Final validation
    if not (
        phone.startswith("+2519")
        and len(phone) == 13
        and phone[1:].isdigit()
    ):
        raise StarPayError(
            "Invalid Ethiopian phone number."
        )

    return phone


def create_starpay_transaction(
    *,
    amount,
    description,
    customer_name,
    customer_phone,
    customer_email=None,
    items=None,
    reference=None,
):
    """
    Create a payment session with StarPay.
    """

    # Check configuration
    if not settings.STARPAY_API_SECRET:
        raise StarPayError(
            "STARPAY_API_SECRET is not configured."
        )

    if not settings.STARPAY_API_BASE_URL:
        raise StarPayError(
            "STARPAY_API_BASE_URL is not configured."
        )

    # Normalize customer phone
    customer_phone = normalize_starpay_phone(
        customer_phone
    )

    # Create default item if none was provided
    if not items:
        items = [
            {
                "productId": (
                    reference
                    or "MEGEB_PAYMENT"
                ),
                "quantity": 1,
                "item_name": description,
                "unit_price": float(amount),
            }
        ]

    # StarPay request payload
    payload = {
        "amount": float(amount),
        "description": description,
        "currency": "ETB",
        "customerName": customer_name,
        "customerPhoneNumber": customer_phone,
        "items": items,
    }

    # Callback URL
    if settings.STARPAY_CALLBACK_URL:
        payload["callbackURL"] = (
            settings.STARPAY_CALLBACK_URL
        )

    # Redirect URL
    if settings.STARPAY_REDIRECT_URL:
        payload["redirectUrl"] = (
            settings.STARPAY_REDIRECT_URL
        )

    # Optional email
    if customer_email:
        payload["customerEmail"] = customer_email

    # Internal Megeb+ payment reference
    if reference:
        payload["metadata"] = {
            "order_reference": reference,
        }

    # StarPay create-order endpoint
    url = (
        f"{settings.STARPAY_API_BASE_URL.rstrip('/')}"
        "/trdp/order"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-secret": settings.STARPAY_API_SECRET,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

    except requests.RequestException as exc:
        raise StarPayError(
            f"Could not connect to StarPay: {exc}"
        ) from exc

    # Parse response
    try:
        data = response.json()

    except ValueError as exc:
        raise StarPayError(
            "StarPay returned invalid JSON "
            f"(HTTP {response.status_code}): "
            f"{response.text}"
        ) from exc

    # HTTP error
    if not response.ok:
        raise StarPayError(
            f"StarPay returned HTTP "
            f"{response.status_code}: {data}"
        )

    # StarPay API-level error
    if data.get("status") != "success":
        raise StarPayError(
            "StarPay transaction creation failed: "
            f"{data}"
        )

    return data


def verify_starpay_transaction(order_id):
    """
    Verify a StarPay transaction using the
    StarPay order ID.
    """

    # Check configuration
    if not settings.STARPAY_API_SECRET:
        raise StarPayError(
            "STARPAY_API_SECRET is not configured."
        )

    if not settings.STARPAY_API_BASE_URL:
        raise StarPayError(
            "STARPAY_API_BASE_URL is not configured."
        )

    # StarPay verification endpoint
    url = (
        f"{settings.STARPAY_API_BASE_URL.rstrip('/')}"
        "/trdp/verify"
    )

    headers = {
        "Content-Type": "application/json",
        "x-api-secret": settings.STARPAY_API_SECRET,
    }

    payload = {
        "orderId": order_id,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

    except requests.RequestException as exc:
        raise StarPayError(
            "StarPay verification request failed: "
            f"{exc}"
        ) from exc

    # Parse response
    try:
        data = response.json()

    except ValueError as exc:
        raise StarPayError(
            "StarPay returned invalid JSON: "
            f"{response.text}"
        ) from exc

    # HTTP error
    if not response.ok:
        raise StarPayError(
            data.get("message")
            or data.get("error")
            or (
                "StarPay returned HTTP "
                f"{response.status_code}"
            )
        )

    return data
