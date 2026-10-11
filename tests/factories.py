"""
tests/factories.py — FactoryBoy factories, one per concrete model.

Always call them with ``.create()`` so mypy infers the model type.
"""

from __future__ import annotations

import datetime

import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import Passkey, User
from apps.groups.models import Group, MeetUp, MeetUpParticipant, Membership, PlanDay
from apps.resorts.models import Pass, Resort


class UserFactory(DjangoModelFactory[User]):
    """Build a ``User``."""

    class Meta:
        """Factory metadata."""

        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"skier{n}@example.com")
    display_name = factory.Sequence(lambda n: f"Skier {n}")
    password = factory.django.Password("password")


class PasskeyFactory(DjangoModelFactory[Passkey]):
    """Build a ``Passkey`` with a made-up credential."""

    class Meta:
        """Factory metadata."""

        model = Passkey

    user = factory.SubFactory(UserFactory)
    credential_id = factory.Sequence(lambda n: f"credential-{n}")
    public_key = b"public-key"
    name = "Synced passkey"


class PassFactory(DjangoModelFactory[Pass]):
    """Build a ``Pass``."""

    class Meta:
        """Factory metadata."""

        model = Pass
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"pass-{n}")
    name = factory.Sequence(lambda n: f"Pass {n}")


class ResortFactory(DjangoModelFactory[Resort]):
    """Build a ``Resort`` with a coordinate and no code."""

    class Meta:
        """Factory metadata."""

        model = Resort

    name = factory.Sequence(lambda n: f"Resort {n}")
    canton = "VS"
    latitude = 46.1
    longitude = 7.2


class GroupFactory(DjangoModelFactory[Group]):
    """Build a ``Group``. Use ``MembershipFactory`` to add its owner row."""

    class Meta:
        """Factory metadata."""

        model = Group

    name = factory.Sequence(lambda n: f"Group {n}")
    owner = factory.SubFactory(UserFactory)


class MembershipFactory(DjangoModelFactory[Membership]):
    """Build a ``Membership`` as a plain member."""

    class Meta:
        """Factory metadata."""

        model = Membership

    group = factory.SubFactory(GroupFactory)
    user = factory.SubFactory(UserFactory)
    role = Membership.Role.MEMBER


class PlanDayFactory(DjangoModelFactory[PlanDay]):
    """Build a ``PlanDay`` at a resort."""

    class Meta:
        """Factory metadata."""

        model = PlanDay

    user = factory.SubFactory(UserFactory)
    date = factory.Sequence(lambda n: datetime.date(2027, 1, 1) + datetime.timedelta(n))
    skiing = PlanDay.Skiing.YES
    resort = factory.SubFactory(ResortFactory)


class MeetUpFactory(DjangoModelFactory[MeetUp]):
    """Build a ``MeetUp`` with no time or pin."""

    class Meta:
        """Factory metadata."""

        model = MeetUp

    group = factory.SubFactory(GroupFactory)
    organiser = factory.SelfAttribute("group.owner")
    date = datetime.date(2027, 1, 9)
    resort = factory.SubFactory(ResortFactory)


class MeetUpParticipantFactory(DjangoModelFactory[MeetUpParticipant]):
    """Build a ``MeetUpParticipant``."""

    class Meta:
        """Factory metadata."""

        model = MeetUpParticipant

    meetup = factory.SubFactory(MeetUpFactory)
    user = factory.SubFactory(UserFactory)
