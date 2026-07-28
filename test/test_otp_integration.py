import asyncio
import time

import httpx
from prisma import Prisma

BASE = "http://localhost:9292/api/v1"
EMAIL = f"otptest_{int(time.time())}@test.com"
PASSWORD = "StrongPass1!"

db = Prisma()


async def _get_otp_code(email: str) -> str:
    await db.connect()
    record = await db.emailverification.find_first(
        where={"email": email, "purpose": "signup", "used": False},
        order={"createdAt": "desc"},
    )
    return record.code if record else ""


def _msg(r):
    try:
        return r.json().get("message") or r.json().get("detail") or r.text
    except Exception:
        return r.text


def test_send_otp():
    r = httpx.post(f"{BASE}/auth/send-otp", json={"email": EMAIL, "name": "OTP Tester"})
    assert r.status_code == 200, r.text
    print(f"  send-otp: {r.json()}")


def test_send_otp_resends_and_invalidates():
    r = httpx.post(f"{BASE}/auth/send-otp", json={"email": EMAIL, "name": "OTP Tester"})
    assert r.status_code == 200, r.text
    print("  resend ok, old OTP invalidated")


def test_send_otp_duplicate_email():
    r = httpx.post(f"{BASE}/auth/send-otp", json={"email": "patient@test.com", "name": "X"})
    assert r.status_code == 409
    print("  registered email blocked: 409")


def test_verify_wrong_code():
    r = httpx.post(f"{BASE}/auth/verify-otp", json={"email": EMAIL, "code": "000000"})
    assert r.status_code == 400
    print(f"  wrong code: {_msg(r)}")


def test_verify_correct_code():
    code = asyncio.run(_get_otp_code(EMAIL))
    assert code, "OTP not found in DB"
    r = httpx.post(f"{BASE}/auth/verify-otp", json={"email": EMAIL, "code": code})
    assert r.status_code == 200
    assert r.json()["verified"] is True
    print(f"  correct code verified: {code}")


def test_signup_without_otp():
    r = httpx.post(f"{BASE}/auth/signup", json={
        "name": "No OTP",
        "email": f"no_otp_{int(time.time())}@test.com",
        "password": PASSWORD,
        "role": "PATIENT",
    })
    assert r.status_code == 400
    assert "not verified" in _msg(r)
    print("  signup without otp: 400")


def test_signup_after_otp():
    r = httpx.post(f"{BASE}/auth/signup", json={
        "name": "OTP Verified",
        "email": EMAIL,
        "password": PASSWORD,
        "role": "PATIENT",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == EMAIL
    print(f"  signup success: user={body['user']['id']}")


def test_login_with_new_user():
    r = httpx.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert "access_token" in r.json()
    print(f"  login success: token received")


if __name__ == "__main__":
    print("1. send_otp")
    test_send_otp()
    print("2. resend otp (old invalidated)")
    test_send_otp_resends_and_invalidates()
    print("3. send_otp to registered email")
    test_send_otp_duplicate_email()
    print("4. verify wrong code")
    test_verify_wrong_code()
    print("5. verify correct code")
    test_verify_correct_code()
    print("6. signup without otp")
    test_signup_without_otp()
    print("7. signup after otp")
    test_signup_after_otp()
    print("8. login with new user")
    test_login_with_new_user()
    print("\nAll integration tests passed!")
