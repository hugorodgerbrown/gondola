"""Shared fixtures for the planning tests: a small group with resorts."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

import pytest

from apps.accounts.models import User
from apps.groups.models import Group
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import today
from apps.resorts.models import Resort
from tests.factories import ResortFactory, UserFactory


@dataclass
class Crew:
    """A group of three friends and an outsider, plus two resorts."""

    group: Group
    sam: User
    anna: User
    ben: User
    outsider: User
    verbier: Resort
    zermatt: Resort
    day: datetime.date


@pytest.fixture
def crew(db: None) -> Crew:
    sam = UserFactory.create(display_name="Sam")
    anna = UserFactory.create(display_name="Anna")
    ben = UserFactory.create(display_name="Ben")
    outsider = UserFactory.create(display_name="Olga")
    group = create_group(sam, "Thursday crew")
    join_group(group, anna)
    join_group(group, ben)
    return Crew(
        group=group,
        sam=sam,
        anna=anna,
        ben=ben,
        outsider=outsider,
        verbier=ResortFactory.create(
            name="Verbier", code="VERB", latitude=46.1, longitude=7.2
        ),
        zermatt=ResortFactory.create(
            name="Zermatt", code="ZERM", latitude=46.0, longitude=7.7
        ),
        day=today() + datetime.timedelta(days=2),
    )
