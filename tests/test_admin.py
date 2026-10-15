"""Smoke tests: every registered admin's list and add pages render."""

import pytest
from django.contrib import admin
from django.test import Client
from django.urls import reverse

from apps.accounts.models import SignInRequest
from tests.factories import (
    MembershipFactory,
    PasskeyFactory,
    PlanDayFactory,
    ReviewerAccountFactory,
    SignInRequestFactory,
    UserFactory,
)

APPS = {"accounts", "resorts", "groups"}
MODELS = [
    (model._meta.app_label, model._meta.model_name)
    for model in admin.site._registry
    if model._meta.app_label in APPS
]
# Admins that only show what the app made: no add page.
READ_ONLY = {("accounts", "signinrequest")}


@pytest.fixture
def staff_client(client: Client) -> Client:
    client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    # One row of everything, so change lists render real rows.
    MembershipFactory.create()
    PlanDayFactory.create()
    PasskeyFactory.create()
    SignInRequestFactory.create()
    ReviewerAccountFactory.create()
    return client


def test_every_app_model_is_registered() -> None:
    assert len(MODELS) == 9


@pytest.mark.django_db
@pytest.mark.parametrize(("app_label", "model_name"), [m for m in MODELS if m not in READ_ONLY])
def test_admin_pages_render(staff_client: Client, app_label: str, model_name: str) -> None:
    for view in ("changelist", "add"):
        url = reverse(f"admin:{app_label}_{model_name}_{view}")
        assert staff_client.get(url).status_code == 200, url


@pytest.mark.django_db
def test_sign_in_requests_are_read_only(staff_client: Client) -> None:
    """Only the sign-in form makes requests; the admin shows them without the hashes."""
    request = SignInRequest.objects.get()
    assert staff_client.get(reverse("admin:accounts_signinrequest_add")).status_code == 403
    page = staff_client.get(reverse("admin:accounts_signinrequest_change", args=[request.pk]))
    assert page.status_code == 200
    assert request.token_hash not in page.content.decode()


@pytest.mark.django_db
def test_admin_carries_the_product_name(staff_client: Client) -> None:
    """The admin header names the product, not Django."""
    response = staff_client.get(reverse("admin:index"))
    assert "Gondola" in response.content.decode()
    assert "Django administration" not in response.content.decode()
