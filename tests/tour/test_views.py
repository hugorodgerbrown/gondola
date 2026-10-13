"""Tests for the tour's views, middleware, session and context processor."""

from __future__ import annotations

import datetime
import json

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.groups.models import Group, PlanDay
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import today
from apps.resorts.models import Resort
from apps.tour.demo import DEMO_LIFETIME
from apps.tour.session import HANDOFF_KEY, OFFER_KEY, TOUR_KEY
from tests.factories import PlanDayFactory, ResortFactory, UserFactory

pytestmark = pytest.mark.django_db

HTMX = {"HX-Request": "true"}


def _demo(user: User) -> Group:
    """Return ``user``'s demo copy."""
    return Group.objects.demos().get(owner=user)


def _script(response: object) -> dict[str, object]:
    """Return the tour data a page carries."""
    data: dict[str, object] = response.context["tour"]["script"]  # type: ignore[attr-defined]
    return data


# --- The offer and the start ------------------------------------------------


def test_offer_welcomes_and_keeps_next(client: Client, tourist: User) -> None:
    client.force_login(tourist)
    response = client.get(reverse("tour:offer"), {"next": "/app/map/"})
    assert response.status_code == 200
    assert b"Welcome to Gondola!" in response.content
    assert b"Show me round" in response.content
    assert response.context["next_url"] == "/app/map/"


def test_offer_needs_sign_in(client: Client) -> None:
    response = client.get(reverse("tour:offer"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response["Location"]


def test_start_makes_the_copy_and_opens_the_calendar(
    client: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    client.force_login(tourist)
    response = client.post(reverse("tour:start"), {"next": "/app/map/"})
    assert response["Location"] == reverse("planning:calendar")
    group = _demo(tourist)
    assert client.session[TOUR_KEY] == {"group": str(group.uuid), "next": "/app/map/"}


def test_start_without_resorts_goes_on(client: Client, tourist: User) -> None:
    client.force_login(tourist)
    response = client.post(reverse("tour:start"), {"next": "/app/map/"})
    assert response["Location"] == "/app/map/"
    assert not Group.objects.demos().exists()


def test_account_page_offers_the_tour(client: Client, tourist: User) -> None:
    client.force_login(tourist)
    response = client.get(reverse("accounts:settings"))
    assert b"Take the tour" in response.content


# --- Touring: the demo, and only the demo -----------------------------------


def test_touring_pages_show_the_demo_and_the_bar(touring: Client, tourist: User) -> None:
    response = touring.get(reverse("planning:calendar"))
    assert b"Demo</strong> \xc2\xb7 nothing is saved" in response.content
    assert b'id="tour-script"' in response.content
    script = _script(response)
    assert script["page"] == "calendar"
    assert [c["number"] for c in script["chapters"]] == [1, 2]  # type: ignore[attr-defined]
    assert [g.name for g in response.context["groups"]] == ["Thursday crew"]


def test_touring_hides_real_groups(
    touring: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    real = create_group(tourist, "Real friends")
    friend = UserFactory.create(display_name="Rita")
    join_group(real, friend)
    PlanDayFactory.create(user=friend, date=today(), resort=resorts["VERB"])
    groups = touring.get(reverse("planning:group_list")).context["groups"]
    assert [g.name for g in groups] == ["Thursday crew"]
    real_page = reverse("planning:group_detail", kwargs={"group_uuid": real.uuid})
    assert touring.get(real_page).status_code == 404
    pins = touring.get(reverse("planning:map_pins"), {"date": today().isoformat()}).json()
    verbier = next(p for p in pins["pins"] if p["id"] == str(resorts["VERB"].uuid))
    assert verbier["friends"] == 3  # Sam, Anna and Chloé, not Rita


def test_outside_the_tour_demo_groups_never_show(
    client: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    from apps.tour.demo import create_demo

    create_demo(tourist)
    assert not Group.objects.for_user(tourist).exists()
    client.force_login(tourist)
    # A page load with no tour in the session deletes the leftover copy.
    response = client.get(reverse("planning:calendar"))
    assert response.context["tour"]["script"] is None
    assert not Group.objects.demos().exists()


def test_a_stale_tour_ends_on_the_next_request(touring: Client, tourist: User) -> None:
    Group.objects.filter(pk=_demo(tourist).pk).update(created_at=timezone.now() - DEMO_LIFETIME * 2)
    response = touring.get(reverse("planning:calendar"))
    assert response.context["tour"]["script"] is None
    assert TOUR_KEY not in touring.session
    assert not Group.objects.demos().exists()


def test_the_demo_invite_link_is_dead(touring: Client, tourist: User) -> None:
    token = _demo(tourist).invite_token
    outsider = Client()
    outsider.force_login(UserFactory.create())
    assert outsider.get(reverse("planning:invite", args=[token])).status_code == 404
    assert outsider.post(reverse("planning:join", args=[token])).status_code == 404


def test_the_demo_share_button_is_not_counted(touring: Client, tourist: User) -> None:
    url = reverse("planning:group_detail", kwargs={"group_uuid": _demo(tourist).uuid})
    assert b"data-tally" not in touring.get(url).content


# --- Nothing is saved -------------------------------------------------------


def test_saving_a_day_moves_on_to_the_group(touring: Client, tourist: User) -> None:
    url = reverse("planning:day", kwargs={"day": today()})
    response = touring.post(url, {"resort": ""}, headers=HTMX)
    group_url = reverse("planning:group_detail", kwargs={"group_uuid": _demo(tourist).uuid})
    assert response.status_code == 204
    assert response["HX-Redirect"] == group_url
    plain = touring.post(url, {"resort": ""})
    assert plain["Location"] == group_url
    assert not PlanDay.objects.filter(user=tourist).exists()


def test_any_other_post_stays_put_and_says_so(
    touring: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    url = reverse("planning:plan_here", kwargs={"resort_uuid": resorts["VERB"].uuid})
    response = touring.post(url, {"date": today().isoformat()}, headers=HTMX)
    assert response["HX-Refresh"] == "true"
    back = touring.post(
        reverse("planning:group_list"),
        {"name": "New"},
        HTTP_REFERER="http://testserver/groups/",
    )
    assert back["Location"] == "http://testserver/groups/"
    elsewhere = touring.post(
        reverse("planning:group_list"), {"name": "New"}, HTTP_REFERER="https://evil/"
    )
    assert elsewhere["Location"] == reverse("planning:calendar")
    page = touring.get(reverse("planning:calendar"))
    assert b"nothing was saved" in page.content
    assert not PlanDay.objects.filter(user=tourist).exists()
    assert not Group.objects.filter(name="New").exists()


# --- Ending and finishing ---------------------------------------------------


def test_end_tour_deletes_the_copy(touring: Client, tourist: User) -> None:
    response = touring.post(reverse("tour:end"), {"chapter": "3"})
    assert response["Location"] == reverse("planning:calendar")
    assert not Group.objects.demos().exists()
    assert TOUR_KEY not in touring.session
    page = touring.get(response["Location"])
    assert b"The demo group is gone" in page.content
    assert page.context["tour"]["script"] is None


def test_finish_hands_over_once(touring: Client, tourist: User) -> None:
    response = touring.post(reverse("tour:finish"))
    assert response["Location"] == reverse("planning:calendar")
    tourist.refresh_from_db()
    assert tourist.toured_at is not None
    assert not Group.objects.demos().exists()
    page = touring.get(reverse("planning:calendar"))
    assert b"This is your real calendar" in page.content
    # No group yet: Let's go starts one.
    assert reverse("planning:group_list").encode() in page.content
    assert b"Tell the group" not in page.content
    assert b"This is your real calendar" not in touring.get(reverse("planning:calendar")).content


def test_the_handoff_waits_for_the_calendar(touring: Client) -> None:
    touring.post(reverse("tour:finish"))
    touring.get(reverse("planning:group_list"))
    assert b"This is your real calendar" in touring.get(reverse("planning:calendar")).content


def test_a_quiet_group_gets_tell_the_group(touring: Client, tourist: User) -> None:
    real = create_group(tourist, "Real friends")
    touring.post(reverse("tour:finish"))
    page = touring.get(reverse("planning:calendar"))
    assert b"Tell the group" in page.content
    assert real.invite_token.encode() in page.content
    assert b"My ski days are on Gondola, add yours" in page.content
    assert b'data-tally-from="tour"' in page.content


def test_a_busy_group_just_closes(
    touring: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    real = create_group(tourist, "Real friends")
    friend = UserFactory.create()
    join_group(real, friend)
    PlanDayFactory.create(
        user=friend, date=today() + datetime.timedelta(days=3), resort=resorts["CRA"]
    )
    touring.post(reverse("tour:finish"))
    assert touring.session[HANDOFF_KEY]["group"] == "busy"
    page = touring.get(reverse("planning:calendar"))
    assert b"Tell the group" not in page.content
    assert page.context["handoff"]["go_url"] == ""


def test_from_an_invite_lets_go_back_to_it(
    client: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    invite = reverse("planning:invite", args=["abc"])
    client.force_login(tourist)
    client.post(reverse("tour:start"), {"next": invite})
    client.post(reverse("tour:finish"))
    page = client.get(reverse("planning:calendar"))
    assert page.context["handoff"]["go_url"] == invite


# --- Offered once, after the welcome or after joining ------------------------


def test_new_account_from_an_invite_is_offered_after_joining(
    client: Client,
) -> None:
    owner = UserFactory.create()
    group = create_group(owner, "Crew")
    invite = reverse("planning:invite", args=[group.invite_token])
    newcomer = UserFactory.create(display_name="")
    client.force_login(newcomer)
    done = client.post(reverse("accounts:welcome"), {"display_name": "N", "next": invite})
    assert "%2Ftour%2F" not in done["Location"]
    assert client.session[OFFER_KEY] is True
    joined = client.post(reverse("planning:join", args=[group.invite_token]))
    group_url = reverse("planning:group_detail", kwargs={"group_uuid": group.uuid})
    assert joined["Location"].startswith(reverse("tour:offer"))
    assert client.get(joined["Location"]).context["next_url"] == group_url
    again = client.post(reverse("planning:join", args=[group.invite_token]))
    assert again["Location"] == group_url


def test_unknown_next_is_not_an_invite(client: Client) -> None:
    from apps.tour.session import is_invite

    assert not is_invite("/no/such/page/")
    assert is_invite(reverse("planning:invite", args=["x"]) + "?a=1")


# --- fivebar events ---------------------------------------------------------


def _events(client: Client) -> list[list[object]]:
    """Return the events the next full page would send."""
    page = client.get(reverse("accounts:settings"))
    content = page.content.decode()
    marker = '<script id="analytics-events" type="application/json">'
    if marker not in content:
        return []
    start = content.index(marker) + len(marker)
    events: list[list[object]] = json.loads(content[start : content.index("</script>", start)])
    return events


@pytest.fixture
def fivebar(settings: object) -> None:
    settings.FIVEBAR_DOMAIN = "gondola.ultraniche.ai"  # type: ignore[attr-defined]


@pytest.mark.usefixtures("fivebar")
def test_the_offer_is_counted_and_not_now_is_tagged(client: Client, tourist: User) -> None:
    client.force_login(tourist)
    page = client.get(reverse("tour:offer"))
    assert b'"Tour offered"' in page.content
    assert b'data-tally="Tour skipped"' in page.content
    assert _events(client) == []


@pytest.mark.usefixtures("fivebar")
def test_tour_events_are_counted(client: Client, tourist: User, resorts: dict[str, Resort]) -> None:
    client.force_login(tourist)
    client.post(reverse("tour:start"))
    assert _events(client) == [["Tour started", {"replay": False}]]
    client.post(reverse("tour:end"), {"chapter": "4"})
    assert _events(client) == [["Tour ended", {"chapter": 4}]]
    client.post(reverse("tour:start"))
    client.post(reverse("tour:finish"))
    assert _events(client) == [
        ["Tour started", {"replay": False}],
        ["Tour finished", {"group": "none"}],
    ]
    client.post(reverse("tour:start"))
    client.post(reverse("tour:end"), {"chapter": "x"})
    assert _events(client) == [
        ["Tour started", {"replay": True}],
        ["Tour ended", {"chapter": 0}],
    ]


@pytest.mark.usefixtures("fivebar")
def test_real_days_are_counted(client: Client, tourist: User) -> None:
    resort = ResortFactory.create()
    create_group(tourist, "Crew")
    client.force_login(tourist)
    day = today() + datetime.timedelta(days=1)
    client.post(
        reverse("planning:day", kwargs={"day": day}),
        {"resort": resort.uuid},
    )
    client.post(
        reverse("planning:plan_here", kwargs={"resort_uuid": resort.uuid}),
        {"date": day.isoformat()},
    )
    assert _events(client) == [
        ["Day planned", {"first": True, "after_tour": False}],
        ["Day planned", {"first": False, "after_tour": False}],
    ]


def test_no_events_are_queued_while_fivebar_is_off(
    client: Client, tourist: User, resorts: dict[str, Resort]
) -> None:
    client.force_login(tourist)
    client.post(reverse("tour:start"))
    assert "analytics_events" not in client.session
