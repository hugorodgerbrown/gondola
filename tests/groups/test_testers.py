"""Tests for the Testers auth group and the "UI test" planning group."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.groups.models import Group
from apps.groups.services.memberships import create_group
from apps.groups.services.people import is_member
from apps.groups.services.testers import (
    get_testers_group,
    set_testers,
    sync_tester,
    ui_test_group,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def ui_group() -> Group:
    """A seeded-looking "UI test" group owned by a made-up person."""
    owner = UserFactory.create(email="tess@ui-test.invalid")
    owner.groups.add(get_testers_group())
    return create_group(owner, "UI test")


def test_nothing_to_join_before_seeding() -> None:
    user = UserFactory.create()
    user.groups.add(get_testers_group())
    sync_tester(user)  # No group yet: does nothing, raises nothing.
    assert ui_test_group() is None


def test_a_group_of_that_name_owned_by_a_real_person_isnt_it() -> None:
    create_group(UserFactory.create(), "UI test")
    assert ui_test_group() is None


def test_set_testers_joins_and_leaves(ui_group: Group) -> None:
    me = UserFactory.create()
    set_testers([me], on=True)
    assert is_member(ui_group, me)
    set_testers([me], on=False)
    assert not is_member(ui_group, me)
    assert not me.groups.filter(name="Testers").exists()


def test_the_owner_never_leaves(ui_group: Group) -> None:
    set_testers([ui_group.owner], on=False)
    assert is_member(ui_group, ui_group.owner)
    assert ui_test_group() == ui_group


def test_admin_user_page_and_actions_follow_testers(client: Client, ui_group: Group) -> None:
    admin_user = UserFactory.create(is_staff=True, is_superuser=True)
    client.force_login(admin_user)
    me = UserFactory.create(email="me@example.com", display_name="Me")
    url = reverse("admin:accounts_user_change", args=[me.pk])
    form = {
        "email": me.email,
        "display_name": me.display_name,
        "is_active": "on",
        "groups": [get_testers_group().pk],
    }
    assert client.post(url, form).status_code == 302
    assert is_member(ui_group, me)
    del form["groups"]
    client.post(url, form)
    assert not is_member(ui_group, me)
    changelist = reverse("admin:accounts_user_changelist")
    client.post(changelist, {"action": "add_to_testers", "_selected_action": [me.pk]})
    assert is_member(ui_group, me)
    client.post(changelist, {"action": "remove_from_testers", "_selected_action": [me.pk]})
    assert not is_member(ui_group, me)
