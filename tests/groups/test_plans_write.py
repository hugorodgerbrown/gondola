"""Tests for apps/groups/views/days.py: plans_write, the outbox's save and clear."""

import datetime
import json
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import User
from apps.groups.models import PlanDay
from apps.groups.services import plans
from tests.factories import PlanDayFactory, ResortFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("frozen")]

URL = reverse("planning:plans_write")
DAY = datetime.date(2026, 12, 14)
NEXT = datetime.date(2026, 12, 15)


@pytest.fixture
def frozen() -> Any:
    """A morning in October, with the season ahead plannable."""
    with freeze_time("2026-10-13 09:00:00+02:00") as frozen_time:
        yield frozen_time


def write(client: Client, body: Any, key: str = "") -> Any:
    """POST a plan write as the outbox does."""
    headers = {"Idempotency-Key": key} if key else {}
    payload = body if isinstance(body, str) else json.dumps(body)
    return client.post(URL, payload, content_type="application/json", headers=headers)


def test_saves_days_in_a_resort(signed_in: Client, user: User) -> None:
    resort = ResortFactory.create()
    response = write(signed_in, {"days": [str(NEXT), str(DAY)], "resort": str(resort.uuid)})
    assert response.status_code == 200
    assert response.json() == {"saved": [str(DAY), str(NEXT)], "skipped": []}
    assert set(PlanDay.objects.filter(user=user).values_list("date", "resort")) == {
        (DAY, resort.pk),
        (NEXT, resort.pk),
    }


def test_a_null_resort_clears_the_days(signed_in: Client, user: User) -> None:
    PlanDayFactory.create(user=user, date=DAY)
    response = write(signed_in, {"days": [str(DAY)], "resort": None})
    assert response.json()["saved"] == [str(DAY)]
    assert not PlanDay.objects.filter(user=user).exists()


def test_a_day_gone_by_is_skipped(signed_in: Client, user: User) -> None:
    """A write that waited past its day doesn't fail: the day is skipped."""
    resort = ResortFactory.create()
    yesterday = plans.today() - datetime.timedelta(days=1)
    response = write(signed_in, {"days": [str(yesterday), str(DAY)], "resort": str(resort.uuid)})
    assert response.json() == {"saved": [str(DAY)], "skipped": [str(yesterday)]}


def test_a_day_changed_since_the_write_is_kept(signed_in: Client, user: User) -> None:
    """A queued write never overwrites a newer answer for the same day."""
    newer = PlanDayFactory.create(user=user, date=DAY)
    resort = ResortFactory.create()
    an_hour_ago = (timezone.now() - datetime.timedelta(hours=1)).isoformat()
    response = write(
        signed_in,
        {"days": [str(DAY), str(NEXT)], "resort": str(resort.uuid), "written_at": an_hour_ago},
    )
    assert response.json() == {"saved": [str(NEXT)], "skipped": [str(DAY)]}
    newer.refresh_from_db()
    assert newer.resort != resort


def test_writes_queued_for_one_day_land_in_order(
    signed_in: Client, user: User, frozen: Any
) -> None:
    """Two edits made offline, sent later, leave the second one standing."""
    verbier, zermatt = ResortFactory.create_batch(2)
    first = (timezone.now() - datetime.timedelta(minutes=20)).isoformat()
    second = (timezone.now() - datetime.timedelta(minutes=10)).isoformat()
    write(signed_in, {"days": [str(DAY)], "resort": str(verbier.uuid), "written_at": first})
    frozen.tick(datetime.timedelta(seconds=5))
    response = write(
        signed_in, {"days": [str(DAY)], "resort": str(zermatt.uuid), "written_at": second}
    )
    assert response.json()["saved"] == [str(DAY)]
    plan = PlanDay.objects.get(user=user, date=DAY)
    assert plan.resort == zermatt
    assert plan.said_at.isoformat() == second


def test_a_queued_clear_follows_a_queued_save(signed_in: Client, user: User) -> None:
    resort = ResortFactory.create()
    first = (timezone.now() - datetime.timedelta(minutes=20)).isoformat()
    second = (timezone.now() - datetime.timedelta(minutes=10)).isoformat()
    write(signed_in, {"days": [str(DAY)], "resort": str(resort.uuid), "written_at": first})
    response = write(signed_in, {"days": [str(DAY)], "resort": None, "written_at": second})
    assert response.json()["saved"] == [str(DAY)]
    assert not PlanDay.objects.filter(user=user).exists()


def test_a_write_from_the_future_counts_as_now(signed_in: Client, user: User) -> None:
    """A phone clock running fast can't claim a later time than the server's."""
    PlanDayFactory.create(user=user, date=DAY)
    tomorrow = (timezone.now() + datetime.timedelta(days=1)).isoformat()
    response = write(signed_in, {"days": [str(DAY)], "resort": None, "written_at": tomorrow})
    assert response.json()["saved"] == [str(DAY)]


@pytest.mark.parametrize("written_at", ["not a time", "2026-10-13T08:00:00", None])
def test_an_unreadable_time_counts_as_now(
    signed_in: Client, user: User, written_at: str | None
) -> None:
    resort = ResortFactory.create()
    response = write(
        signed_in, {"days": [str(DAY)], "resort": str(resort.uuid), "written_at": written_at}
    )
    assert response.json()["saved"] == [str(DAY)]


@pytest.mark.parametrize(
    ("body", "error"),
    [
        ("not json", "days"),
        ({"resort": None}, "days"),
        ({"days": "2026-12-14", "resort": None}, "days"),
        ({"days": ["14 December"], "resort": None}, "days"),
        ({"days": [], "resort": None}, "days"),
        ({"days": [str(DAY + datetime.timedelta(days=n)) for n in range(63)]}, "days"),
        ({"days": [str(DAY)], "resort": "not-a-uuid"}, "resort"),
        ({"days": [str(DAY)], "resort": "00000000-0000-0000-0000-000000000000"}, "resort"),
    ],
)
def test_a_bad_write_is_refused(signed_in: Client, body: Any, error: str) -> None:
    """400s are final: the outbox shows them as not sent, with Retry and Discard."""
    response = write(signed_in, body)
    assert response.status_code == 400
    assert response.json() == {"error": error}


def test_signed_out_is_401_not_a_redirect(client: Client) -> None:
    """The outbox keeps the write and waits for sign-in."""
    response = write(client, {"days": [str(DAY)], "resort": None})
    assert response.status_code == 401


def test_a_repeated_write_runs_once(signed_in: Client, user: User) -> None:
    """The outbox resends with the same key; the second answer is a replay."""
    resort = ResortFactory.create()
    body = {"days": [str(DAY)], "resort": str(resort.uuid)}
    first = write(signed_in, body, key="k1")
    PlanDay.objects.filter(user=user).delete()
    second = write(signed_in, body, key="k1")
    assert second["Idempotent-Replayed"] == "true"
    assert second.json() == first.json()
    assert not PlanDay.objects.filter(user=user).exists()


def test_the_sheets_send_through_the_outbox(signed_in: Client) -> None:
    """Outside the tour, the day sheet's forms carry what plans.js needs."""
    sheet = signed_in.get(
        reverse("planning:several_days") + f"?days={DAY},{NEXT}", headers={"HX-Request": "true"}
    )
    content = sheet.content.decode()
    assert 'data-plan-write="set"' in content
    assert f'data-days="{DAY},{NEXT}"' in content
    assert f'data-plans-url="{URL}"' in content
    page = signed_in.get(reverse("planning:calendar"))
    assert f'data-plans-url="{URL}"' in page.content.decode()
