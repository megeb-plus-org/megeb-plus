import requests
from django.conf import settings


def send_otp(phone):
    url = "https://api.afromessage.com/api/challenge"

    headers = {
        "Authorization": f"Bearer {settings.AFROMESSAGE_TOKEN}",
    }

    params = {
        "from": settings.AFROMESSAGE_IDENTIFIER_ID,
        "to": phone,
        "pr": "Your MegebPlus verification code is",
        "ps": "",
        "ttl": 300,
        "len": 6,
        "t": 0,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=15,
        )

        print("AFROMESSAGE STATUS:", response.status_code)
        print("AFROMESSAGE RESPONSE:", response.text)

        return response.json()

    except requests.RequestException as e:
        print("AFROMESSAGE ERROR:", str(e))

        return {
            "acknowledge": "error",
            "response": {
                "errors": [str(e)]
            }
        }


def verify_otp(phone, otp, verification_id):
    url = "https://api.afromessage.com/api/verify"

    headers = {
        "Authorization": f"Bearer {settings.AFROMESSAGE_TOKEN}",
    }

    params = {
        "vc": verification_id,
        "to": phone,
        "code": otp,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=15,
        )

        print("AFROMESSAGE VERIFY STATUS:", response.status_code)
        print("AFROMESSAGE VERIFY RESPONSE:", response.text)

        return response.json()

    except requests.RequestException as e:
        print("AFROMESSAGE VERIFY ERROR:", str(e))

        return {
            "acknowledge": "error",
            "response": {
                "errors": [str(e)]
            }
        }