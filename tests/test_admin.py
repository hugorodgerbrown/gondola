"""Smoke tests: every registered admin's list and add pages render."""

import pytest
from django.contrib import admin
from django.test import Client
from django.urls import reverse

from tests.factories import (
    MeetUpParticipantFactory,
    MembershipFactory,
    PasskeyFactory,
    PlanDayFactory,
    UserFactory,
)

MODELS = [
    (model._meta.app_label, model._meta.model_name)
    for model in admin.site._registry
    if model._meta.app_label in {"accounts", "resorts", "groups"}
]


@pytest.fixture
def staff_client(client: Client) -> Client:
    client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    # One row of everything, so change lists render real rows.
    MembershipFactory.create()
    PlanDayFactory.create()
    MeetUpParticipantFactory.create()
    PasskeyFactory.create()
    return client


def test_every_app_model_is_registered() -> None:
    assert len(MODELS) == 9


@pytest.mark.django_db
@pytest.mark.parametrize(("app_label", "model_name"), MODELS)
def test_admin_pages_render(
    staff_client: Client, app_label: str, model_name: str
) -> None:
    for view in ("changelist", "add"):
        url = reverse(f"admin:{app_label}_{model_name}_{view}")
        assert staff_client.get(url).status_code == 200, url


@pytest.mark.django_db
def test_admin_carries_the_product_name(staff_client: Client) -> None:
    """The admin header names the product, not Django."""
    response = staff_client.get(reverse("admin:index"))
    assert "Gondola" in response.content.decode()
    assert "Django administration" not in response.content.decode()
