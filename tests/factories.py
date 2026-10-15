"""tests/factories.py — FactoryBoy factories, one per concrete model.

Always call them with ``.create()`` so mypy infers the model type.
"""

from __future__ import annotations

import datetime

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.accounts.models import Passkey, ReviewerAccount, SignInRequest, User
from apps.groups.models import Group, Membership, PlanDay
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


class SignInRequestFactory(DjangoModelFactory[SignInRequest]):
    """Build a live ``SignInRequest``. Use ``apps.accounts.sign_in.issue`` for a usable token."""

    class Meta:
        """Factory metadata."""

        model = SignInRequest

    email = factory.Sequence(lambda n: f"signin{n}@example.com")
    token_hash = factory.Sequence(lambda n: f"{n:064x}")
    code_hash = "0" * 64
    expires_at = factory.LazyFunction(lambda: timezone.now() + datetime.timedelta(minutes=30))


class PasskeyFactory(DjangoModelFactory[Passkey]):
    """Build a ``Passkey`` with a made-up credential."""

    class Meta:
        """Factory metadata."""

        model = Passkey

    user = factory.SubFactory(UserFactory)
    credential_id = factory.Sequence(lambda n: f"credential-{n}")
    public_key = b"public-key"
    name = "Synced passkey"


class ReviewerAccountFactory(DjangoModelFactory[ReviewerAccount]):
    """A reviewer account; its code is made on save."""

    class Meta:
        """Factory metadata."""

        model = ReviewerAccount

    email = factory.Sequence(lambda n: f"reviewer{n}@example.com")


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
    resort = factory.SubFactory(ResortFactory)
