"""Tests for apps/accounts/sign_in.py: issuing and redeeming links and codes."""

from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
<<<<<<< before updating
from django.db import IntegrityError, transaction
=======
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
>>>>>>> after updating
from django.utils import timezone

from apps.accounts import sign_in
from apps.accounts.models import SignInRequest, User
from tests.factories import SignInRequestFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_issue_stores_hashes_only() -> None:
    """Neither the token nor the code is stored as given."""
    request, token, code = sign_in.issue("  Walker@Example.COM ", "/app/days/")
    assert request.email == "walker@example.com"
    assert len(code) == sign_in.CODE_DIGITS
    assert code.isdigit()
    assert token not in request.token_hash
    assert code not in request.code_hash
    assert request.next_url == "/app/days/"


def test_a_new_request_ends_the_previous_one() -> None:
    """Only the newest email for an address works."""
    first, first_token, _ = sign_in.issue("a@example.com")
    sign_in.issue("a@example.com")
    assert sign_in.redeem_token(first_token) is None
    first.refresh_from_db()
    assert first.used_at is not None


<<<<<<< before updating
def test_one_open_request_per_address() -> None:
    """The database refuses a second unused request for the same address."""
    SignInRequestFactory.create(email="a@example.com")
    with pytest.raises(IntegrityError), transaction.atomic():
        SignInRequestFactory.create(email="a@example.com")
    SignInRequestFactory.create(email="a@example.com", used_at=timezone.now())


def test_issue_retries_when_a_parallel_request_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Losing the race to another issue closes the winner's request and tries again."""
    winner = SignInRequestFactory.create(email="a@example.com")
    real_for_email = SignInRequest.objects.for_email
    calls = iter([SignInRequest.objects.none(), None])

    def for_email(email: str) -> Any:
        # The first look misses the winner, as a parallel transaction would.
        return next(calls) or real_for_email(email)

    monkeypatch.setattr(SignInRequest.objects, "for_email", for_email)
    request, token, _ = sign_in.issue("a@example.com")
    winner.refresh_from_db()
    assert winner.used_at is not None
    assert sign_in.redeem_token(token) == request


def test_issue_gives_up_after_repeated_races(monkeypatch: pytest.MonkeyPatch) -> None:
    """A race that never clears is an error, not a loop."""
    SignInRequestFactory.create(email="a@example.com")
    monkeypatch.setattr(SignInRequest.objects, "for_email", lambda _: SignInRequest.objects.none())
    with pytest.raises(IntegrityError):
        sign_in.issue("a@example.com")
=======
def test_the_database_holds_one_unused_request_per_address() -> None:
    """A second unused request for an address is refused, whoever writes it."""
    request, _, _ = sign_in.issue("a@example.com")
    duplicate = SignInRequest(
        email_key=request.email_key,
        masked_email=request.masked_email,
        token_hash="other",
        code_hash="other",
        expires_at=request.expires_at,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        duplicate.save()


def test_issue_retries_when_a_request_at_the_same_moment_won() -> None:
    """Losing the race to insert retires the winner and stores the newest request."""
    real = sign_in._replace_request
    winners: list[SignInRequest] = []

    def collide(*args: Any) -> SignInRequest:
        if not winners:
            # Another request for the address commits first; this insert collides.
            winners.append(real("a@example.com", "winner", "123456", ""))
            raise IntegrityError
        return real(*args)

    with mock.patch.object(sign_in, "_replace_request", side_effect=collide):
        request, _, _ = sign_in.issue("a@example.com")
    winners[0].refresh_from_db()
    assert winners[0].used_at is not None
    assert SignInRequest.objects.for_email("a@example.com").unused().get() == request


def test_issue_gives_up_after_its_attempts() -> None:
    """A request that keeps colliding fails rather than looping for ever."""
    with (
        mock.patch.object(sign_in, "_replace_request", side_effect=IntegrityError),
        pytest.raises(IntegrityError),
    ):
        sign_in.issue("a@example.com")
    assert not SignInRequest.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_migration_keeps_only_the_newest_unused_request() -> None:
    """Older unused requests for an address are retired so the constraint can be added."""
    executor = MigrationExecutor(connection)
    executor.migrate([("accounts", "0001_initial")])
    old_apps = executor.loader.project_state([("accounts", "0001_initial")]).apps
    model = old_apps.get_model("accounts", "SignInRequest")
    expires_at = timezone.now() + timedelta(minutes=5)
    rows = [
        model.objects.create(
            email_key="k",
            masked_email="m",
            token_hash=f"t{i}",
            code_hash="c",
            expires_at=expires_at,
        )
        for i in range(2)
    ]
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())
    unused = SignInRequest.objects.filter(email_key="k", used_at__isnull=True)
    assert list(unused.values_list("pk", flat=True)) == [rows[1].pk]
>>>>>>> after updating


def test_token_works_once() -> None:
    """A link signs in once; the second click finds nothing."""
    request, token, _ = sign_in.issue("a@example.com")
    assert sign_in.find_by_token(token) == request
    assert sign_in.redeem_token(token) == request
    assert sign_in.redeem_token(token) is None
    assert sign_in.find_by_token(token) is None


def test_token_expires() -> None:
    """A link past its time doesn't work."""
    request, token, _ = sign_in.issue("a@example.com")
    SignInRequest.objects.filter(pk=request.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert sign_in.redeem_token(token) is None


def test_unknown_token() -> None:
    """A made-up link finds nothing."""
    assert sign_in.redeem_token("nope") is None


def test_code_works_once() -> None:
    """The right code, with spaces, redeems the request once."""
    request, _, code = sign_in.issue("a@example.com")
    assert sign_in.redeem_code(str(request.uuid), f" {code} ") == request
    assert sign_in.redeem_code(str(request.uuid), code) is None


def test_wrong_codes_run_out(settings: Any) -> None:
    """After the allowed wrong guesses, even the right code is refused."""
    request, _, code = sign_in.issue("a@example.com")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.SIGN_IN_MAX_CODE_ATTEMPTS):
        assert sign_in.redeem_code(str(request.uuid), wrong) is None
    request.refresh_from_db()
    assert request.code_attempts == settings.SIGN_IN_MAX_CODE_ATTEMPTS
    assert sign_in.redeem_code(str(request.uuid), code) is None


def test_the_attempt_limit_is_checked_in_the_database(settings: Any) -> None:
    """A guess is refused once the stored count is at the limit, whatever was read earlier."""
    request, _, code = sign_in.issue("a@example.com")
    SignInRequest.objects.filter(pk=request.pk).update(
        code_attempts=settings.SIGN_IN_MAX_CODE_ATTEMPTS
    )
    assert sign_in.redeem_code(str(request.uuid), code) is None


def test_code_for_another_request_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A code only fits the request it was made for."""
    codes = iter([111111, 222222])
    monkeypatch.setattr(sign_in.secrets, "randbelow", lambda _: next(codes))
    _, _, first_code = sign_in.issue("a@example.com")
    second, _, second_code = sign_in.issue("b@example.com")
    assert (first_code, second_code) == ("111111", "222222")
    assert sign_in.redeem_code(str(second.uuid), first_code) is None


def test_first_sign_in_creates_the_account() -> None:
    """There is no sign-up step: the first redeemed email makes the account."""
    request, token, _ = sign_in.issue("New@example.com")
    user = sign_in.user_for(sign_in.redeem_token(token) or request)
    assert user is not None
    assert user.email == "new@example.com"
    assert not user.display_name
    assert not user.has_usable_password()


def test_existing_accounts_are_found_by_email() -> None:
    """An account made any other way (the admin, a factory) is found by its email."""
    admin = User.objects.create_superuser("Boss@example.com")
    request, _, _ = sign_in.issue("boss@example.com")
    assert sign_in.user_for(request) == admin
    assert User.objects.count() == 1


def test_a_switched_off_account_cannot_sign_in() -> None:
    """An inactive account stays out."""
    UserFactory.create(email="gone@example.com", is_active=False)
    request, _, _ = sign_in.issue("gone@example.com")
    assert sign_in.user_for(request) is None
