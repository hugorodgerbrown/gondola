"""Tests for apps/accounts/passkeys.py and the passkey views.

The browser's signature can't be produced here, so py_webauthn's two
verify functions are replaced with stubs that return what a real
verification would; everything around them runs for real.
"""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from django.contrib.sessions.backends.base import SessionBase
from django.contrib.sessions.backends.db import SessionStore
from django.test import Client
from django.urls import reverse

from apps.accounts import passkeys
from apps.accounts.models import Passkey
from tests.factories import PasskeyFactory, UserFactory

pytestmark = pytest.mark.django_db

CREDENTIAL = {"id": "credential-new", "rawId": "credential-new", "type": "public-key"}


def _stub_registration(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> None:
    result = SimpleNamespace(
        **{
            "credential_id": b"new-credential",
            "credential_public_key": b"public-key",
            "sign_count": 0,
            "credential_backed_up": True,
            **overrides,
        }
    )
    monkeypatch.setattr(
        passkeys.webauthn, "verify_registration_response", lambda **_: result
    )


def _stub_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(new_sign_count=5, credential_backed_up=True)
    monkeypatch.setattr(
        passkeys.webauthn, "verify_authentication_response", lambda **_: result
    )


def _fail(**_: Any) -> None:
    raise ValueError("bad signature")


@pytest.fixture
def session() -> SessionBase:
    return SessionStore()


# --- Service --------------------------------------------------------------


def test_registration_options_name_the_site_and_exclude_existing_keys(
    session: SessionBase,
) -> None:
    user = UserFactory.create()
    PasskeyFactory.create(user=user, credential_id="AAAA")
    options = passkeys.registration_options(user, session)
    assert options["rp"] == {"id": "localhost", "name": "Resort planner"}
    assert options["user"]["name"] == user.email
    assert [c["id"] for c in options["excludeCredentials"]] == ["AAAA"]
    assert options["authenticatorSelection"]["residentKey"] == "required"
    assert session[passkeys.REGISTRATION_CHALLENGE_KEY] == options["challenge"]


def test_save_registration_stores_the_key_once(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = UserFactory.create()
    _stub_registration(monkeypatch)
    passkeys.registration_options(user, session)
    passkey = passkeys.save_registration(user, json.dumps(CREDENTIAL), session)
    assert passkey.user == user
    assert passkey.backed_up
    assert passkey.name == "Synced passkey"
    # The challenge is spent: a replay is refused.
    with pytest.raises(passkeys.PasskeyError, match="No passkey request"):
        passkeys.save_registration(user, json.dumps(CREDENTIAL), session)


def test_save_registration_names_a_device_bound_key(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_registration(monkeypatch, credential_backed_up=False)
    user = UserFactory.create()
    passkeys.registration_options(user, session)
    passkey = passkeys.save_registration(user, "{}", session)
    assert passkey.name == "Device passkey"


def test_save_registration_refuses_a_bad_signature(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(passkeys.webauthn, "verify_registration_response", _fail)
    user = UserFactory.create()
    passkeys.registration_options(user, session)
    with pytest.raises(passkeys.PasskeyError, match="could not be checked"):
        passkeys.save_registration(user, "{}", session)
    assert not Passkey.objects.exists()


def test_save_registration_refuses_a_key_already_stored(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_registration(monkeypatch, credential_id=b"\x01\x02")
    PasskeyFactory.create(credential_id="AQI")  # base64url of b"\x01\x02"
    user = UserFactory.create()
    passkeys.registration_options(user, session)
    with pytest.raises(passkeys.PasskeyError, match="already on an account"):
        passkeys.save_registration(user, "{}", session)


def test_verify_authentication_signs_in_and_records_use(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_authentication(monkeypatch)
    passkey = PasskeyFactory.create(credential_id="credential-new")
    options = passkeys.authentication_options(session)
    assert options["rpId"] == "localhost"
    assert "allowCredentials" not in options or options["allowCredentials"] == []
    user = passkeys.verify_authentication(json.dumps(CREDENTIAL), session)
    assert user == passkey.user
    passkey.refresh_from_db()
    assert passkey.sign_count == 5
    assert passkey.last_used_at is not None


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("not json", "could not be read"),
        ("{}", "could not be read"),
        (json.dumps({"id": "unknown"}), "isn't on any account"),
    ],
)
def test_verify_authentication_refuses_what_it_cannot_match(
    session: SessionBase, body: str, message: str
) -> None:
    passkeys.authentication_options(session)
    with pytest.raises(passkeys.PasskeyError, match=message):
        passkeys.verify_authentication(body, session)


def test_verify_authentication_needs_a_challenge(session: SessionBase) -> None:
    with pytest.raises(passkeys.PasskeyError, match="No sign-in"):
        passkeys.verify_authentication(json.dumps(CREDENTIAL), session)


def test_verify_authentication_refuses_a_bad_signature(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(passkeys.webauthn, "verify_authentication_response", _fail)
    PasskeyFactory.create(credential_id="credential-new")
    passkeys.authentication_options(session)
    with pytest.raises(passkeys.PasskeyError, match="could not be checked"):
        passkeys.verify_authentication(json.dumps(CREDENTIAL), session)


def test_verify_authentication_refuses_a_switched_off_account(
    session: SessionBase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_authentication(monkeypatch)
    PasskeyFactory.create(
        credential_id="credential-new", user=UserFactory.create(is_active=False)
    )
    passkeys.authentication_options(session)
    with pytest.raises(passkeys.PasskeyError, match="switched off"):
        passkeys.verify_authentication(json.dumps(CREDENTIAL), session)


# --- Views ----------------------------------------------------------------


def _post_json(client: Client, name: str, body: object) -> Any:
    return client.post(
        reverse(name), data=json.dumps(body), content_type="application/json"
    )


def test_sign_in_page_offers_a_passkey(client: Client) -> None:
    page = client.get(reverse("accounts:sign_in"))
    assert b"data-passkey-sign-in" in page.content
    assert b'autocomplete="email webauthn"' in page.content


def test_passkey_sign_in_logs_in_and_goes_next(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_authentication(monkeypatch)
    passkey = PasskeyFactory.create(credential_id="credential-new")
    assert client.get(reverse("accounts:passkey_sign_in_options")).status_code == 200
    response = _post_json(
        client,
        "accounts:passkey_sign_in",
        {"credential": CREDENTIAL, "next": "/days/"},
    )
    assert response.json() == {"next": "/days/"}
    assert int(client.session["_auth_user_id"]) == passkey.user.pk


def test_passkey_sign_in_ignores_an_offsite_next(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_authentication(monkeypatch)
    PasskeyFactory.create(credential_id="credential-new")
    client.get(reverse("accounts:passkey_sign_in_options"))
    response = _post_json(
        client,
        "accounts:passkey_sign_in",
        {"credential": CREDENTIAL, "next": "https://evil.example/"},
    )
    assert response.json() == {"next": reverse("planning:map")}


def test_passkey_sign_in_asks_a_nameless_account_its_name(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_authentication(monkeypatch)
    PasskeyFactory.create(
        credential_id="credential-new", user=UserFactory.create(display_name="")
    )
    client.get(reverse("accounts:passkey_sign_in_options"))
    response = _post_json(
        client, "accounts:passkey_sign_in", {"credential": CREDENTIAL}
    )
    assert response.json()["next"].startswith(reverse("accounts:welcome"))


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]"])
def test_passkey_sign_in_rejects_a_malformed_body(client: Client, body: bytes) -> None:
    client.get(reverse("accounts:passkey_sign_in_options"))
    response = client.post(
        reverse("accounts:passkey_sign_in"), data=body, content_type="application/json"
    )
    assert response.status_code == 400
    assert "_auth_user_id" not in client.session


def test_adding_a_passkey_needs_a_signed_in_account(client: Client) -> None:
    response = client.get(reverse("accounts:passkey_add_options"))
    assert response.status_code == 302


def test_add_a_passkey_from_the_account_page(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_registration(monkeypatch)
    user = UserFactory.create()
    client.force_login(user)
    page = client.get(reverse("accounts:settings"))
    assert b"Add a passkey for this device" in page.content
    options = client.get(reverse("accounts:passkey_add_options")).json()
    assert options["user"]["name"] == user.email
    response = _post_json(client, "accounts:passkey_add", {"credential": CREDENTIAL})
    assert response.status_code == 200
    page = client.get(reverse("accounts:settings"))
    assert b"Synced passkey" in page.content
    assert b"not used yet" in page.content


def test_add_a_passkey_reports_a_failure(client: Client) -> None:
    client.force_login(UserFactory.create())
    response = _post_json(client, "accounts:passkey_add", {"credential": CREDENTIAL})
    assert response.status_code == 400
    assert "No passkey request" in response.json()["error"]


def test_remove_a_passkey(client: Client) -> None:
    passkey = PasskeyFactory.create()
    client.force_login(passkey.user)
    response = client.post(
        reverse("accounts:passkey_remove", kwargs={"passkey_uuid": passkey.uuid})
    )
    assert response["Location"] == reverse("accounts:settings")
    assert not Passkey.objects.exists()


def test_cannot_remove_someone_elses_passkey(client: Client) -> None:
    passkey = PasskeyFactory.create()
    client.force_login(UserFactory.create())
    response = client.post(
        reverse("accounts:passkey_remove", kwargs={"passkey_uuid": passkey.uuid})
    )
    assert response.status_code == 404
    assert Passkey.objects.exists()


def test_passkey_to_string() -> None:
    passkey = PasskeyFactory.create(name="Phone")
    assert str(passkey) == f"Phone ({passkey.user.email})"
    assert list(Passkey.objects.for_user(passkey.user)) == [passkey]
