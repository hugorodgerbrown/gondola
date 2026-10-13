"""Tests for the planning views: days, map, groups and the board."""

import datetime
import json
import re

import pytest
from django.test import Client
from django.urls import reverse
from freezegun import freeze_time

from apps.groups.models import Group, PlanDay
from apps.groups.services import plans
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.people import is_member
from tests.factories import PassFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
HTMX = {"HX-Request": "true"}


@pytest.fixture
def sam(client: Client, crew: Crew) -> Client:
    client.force_login(crew.sam)
    return client


# --- sign-in is required ---------------------------------------------------------


@pytest.mark.parametrize("name", ["planning:map", "planning:calendar", "planning:group_list"])
def test_screens_need_sign_in(client: Client, name: str) -> None:
    response = client.get(reverse(name))
    assert response["Location"].startswith(reverse("accounts:sign_in"))


# --- calendar ------------------------------------------------------------------------


def test_calendar_is_this_month(sam: Client, crew: Crew) -> None:
    today = plans.today()
    plans.set_plan(crew.sam, today, crew.verbier)
    plans.set_plan(crew.anna, today, crew.verbier)
    response = sam.get(reverse("planning:calendar"))
    cal = response.context["month"]
    assert cal.first == today.replace(day=1)
    assert cal.previous is None
    # The month is the title; today is selected, blue, and counts the one
    # friend with you.
    assert f'<h1 class="title title--large">{today:%B %Y}</h1>'.encode() in (response.content)
    assert response.context["selected"].date == today
    assert b"mday--in mday--selected" in response.content
    assert response.context["selected"].count == 1
    assert b'class="mday__friends"' in response.content
    # The panel: where you are, the one friend with you by name, and Edit
    # plans.
    assert b"In Verbier\n" in response.content
    assert b"<span>Anna</span>" in response.content
    assert b"with you</p>" not in response.content
    assert response.context["here"].resort == crew.verbier
    assert response.context["elsewhere"] == []
    assert b"Edit plans" in response.content
    label = (
        f"{today:%A} {today.day} {today:%B}, today, Verbier, friends at resorts: Anna, 1 with you"
    )
    assert label.encode() in response.content


def test_calendar_steps_a_month(sam: Client, crew: Crew) -> None:
    today = plans.today()
    later = (today.replace(day=1) + datetime.timedelta(days=62)).replace(day=1)
    response = sam.get(reverse("planning:calendar"), {"from": later.isoformat()})
    cal = response.context["month"]
    assert cal.first == later
    assert cal.previous is not None and cal.previous < later
    assert f'href="?from={cal.previous.isoformat()}"'.encode() in response.content
    assert response.context["window_from"] == later
    # Far past the horizon, the last plannable month, with no way on.
    end = sam.get(reverse("planning:calendar"), {"from": "2099-01-01"})
    assert end.context["month"].first == plans.last_plannable_day().replace(day=1)
    assert end.context["month"].next is None


def test_plain_forms_keep_the_month(sam: Client, crew: Crew) -> None:
    """Without JavaScript, saving or clearing a day returns to its month."""
    far = plans.today() + datetime.timedelta(days=60)
    first = far.replace(day=1)
    page = sam.get(reverse("planning:calendar"), {"day": far.isoformat()})
    day_url = reverse("planning:day", kwargs={"day": far})
    assert f'href="{day_url}?from={first.isoformat()}"'.encode() in page.content
    sheet = sam.get(day_url, {"from": first.isoformat()})
    assert f'name="from" value="{first.isoformat()}"'.encode() in sheet.content
    # Back to the month, with the day still selected in the panel.
    back = f"{reverse('planning:calendar')}?from={first.isoformat()}&day={far.isoformat()}"
    saved = sam.post(
        day_url,
        {"resort": str(crew.verbier.uuid), "from": first.isoformat()},
    )
    assert saved["Location"] == back
    cleared = sam.post(
        reverse("planning:day_clear", kwargs={"day": far}), {"from": first.isoformat()}
    )
    assert cleared["Location"] == back
    # This month needs nothing carried.
    assert sam.get(reverse("planning:calendar")).context["window_from"] is None


def test_a_group_shows_its_people_on_days_you_have_not_said(sam: Client, crew: Crew) -> None:
    """My calendar hides pale days; a group shows its people there, pale."""
    far = plans.today() + datetime.timedelta(days=60)
    first = far.replace(day=1).isoformat()
    plans.set_plan(crew.anna, far, crew.verbier)
    plans.set_plan(crew.ben, far, crew.zermatt)
    url = reverse("planning:calendar")
    page = sam.get(url, {"day": far.isoformat()})
    assert page.context["group"] is None
    assert page.context["selected"].crowd is None
    assert b"mday--friends" not in page.content
    assert b">My calendar</a>" in page.content
    picked = f'href="?day={far.isoformat()}&group={crew.group.uuid}"'
    assert picked.encode() in page.content

    shown = sam.get(url, {"day": far.isoformat(), "group": str(crew.group.uuid)})
    assert shown.context["group"] == crew.group
    selected = shown.context["selected"]
    assert selected.crowd.resort == crew.verbier and selected.more == 1
    assert selected.count == 1
    assert b"mday--friends" in shown.content
    assert f"{crew.verbier.display_code} …".encode() in shown.content
    # The picked chip goes back to My calendar; the arrows, day links and
    # selection keep the group.
    current = f'aria-current="true" href="?day={far.isoformat()}"'
    assert current.encode() in shown.content
    back = f"from={first}&amp;group={crew.group.uuid}"
    assert f'data-select-back="{back}"'.encode() in shown.content
    day_url = reverse("planning:day", kwargs={"day": far})
    assert f'href="{day_url}?{back}"'.encode() in shown.content


def test_a_group_cuts_the_panel_to_its_people(sam: Client, crew: Crew) -> None:
    other = create_group(crew.sam, "Work")
    olga = crew.outsider
    join_group(other, olga)
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    plans.set_plan(olga, crew.day, crew.zermatt)
    url = reverse("planning:calendar")
    day = crew.day.isoformat()
    everyone = sam.get(url, {"day": day})
    assert len(everyone.context["elsewhere"]) == 2
    work = sam.get(url, {"day": day, "group": str(other.uuid)})
    assert [e.resort for e in work.context["elsewhere"]] == [crew.zermatt]
    assert work.context["selected"].crowd.names == "Olga"


@pytest.mark.parametrize("value", ["nope", "00000000-0000-0000-0000-000000000000"])
def test_a_group_you_are_not_in_is_ignored(sam: Client, crew: Crew, value: str) -> None:
    page = sam.get(reverse("planning:calendar"), {"group": value})
    assert page.status_code == 200
    assert page.context["group"] is None


def test_saving_a_day_keeps_the_group(sam: Client, crew: Crew) -> None:
    """The group rides through the sheet and back to the calendar."""
    picked = str(crew.group.uuid)
    day_url = reverse("planning:day", kwargs={"day": crew.day})
    sheet = sam.get(day_url, {"group": picked})
    hidden = f'type="hidden" name="group" value="{picked}"'
    assert hidden.encode() in sheet.content
    saved = sam.post(day_url, {"resort": str(crew.zermatt.uuid), "group": picked})
    assert saved["Location"] == (
        f"{reverse('planning:calendar')}?group={picked}&day={crew.day.isoformat()}"
    )
    plan = PlanDay.objects.get(user=crew.sam, date=crew.day)
    assert plan.resort == crew.zermatt


def test_the_panel_shows_the_picked_day(sam: Client, crew: Crew) -> None:
    """A tapped day fills the panel: Add plans, and where friends are."""
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    plans.set_plan(crew.ben, crew.day, crew.zermatt)
    url = reverse("planning:calendar")
    page = sam.get(url, {"day": crew.day.isoformat()})
    assert page.context["selected"].date == crew.day
    # Sam has no resort that day, so every friend is "out", none "with you".
    assert page.context["here"] is None
    assert [e.resort for e in page.context["elsewhere"]] == [
        crew.verbier,
        crew.zermatt,
    ]
    assert b"Friends out" in page.content
    assert b"Add plans" in page.content and b"Edit plans" not in page.content
    assert b"Meet-up" not in page.content
    # My calendar: no pale day, whatever friends do.
    assert page.context["selected"].crowd is None
    # A day with nothing on says so.
    empty = sam.get(url, {"day": (crew.day + datetime.timedelta(days=1)).isoformat()})
    assert b"No friends out this day." in empty.content


def test_the_panel_splits_with_you_from_elsewhere(sam: Client, crew: Crew) -> None:
    """The panel names the friends with you, then the rest."""
    plans.set_plan(crew.sam, crew.day, crew.verbier)
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    plans.set_plan(crew.ben, crew.day, crew.zermatt)
    url = reverse("planning:calendar")
    page = sam.get(url, {"day": crew.day.isoformat()})
    assert page.context["selected"].count == 1
    assert b"<span>Anna</span>" in page.content
    assert [e.resort for e in page.context["elsewhere"]] == [crew.zermatt]
    assert b"Elsewhere" in page.content
    assert b'<span class="muted">Ben</span>' in page.content
    # Your own day never shows the crowd.
    assert page.context["selected"].crowd is None


def test_the_panel_without_friends_out(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.sam, crew.day, crew.verbier)
    page = sam.get(reverse("planning:calendar"), {"day": crew.day.isoformat()})
    assert b"In Verbier" in page.content
    assert b"No friends out this day." in page.content


@pytest.mark.parametrize("value", ["nope", "2099-01-01"])
def test_an_unknown_day_selects_a_default(sam: Client, value: str) -> None:
    page = sam.get(reverse("planning:calendar"), {"day": value})
    selected = page.context["selected"]
    assert selected.in_month
    assert selected.date in (plans.today(), page.context["month"].first)


def test_a_later_month_selects_its_first(sam: Client, crew: Crew) -> None:
    later = (plans.today().replace(day=1) + datetime.timedelta(days=40)).replace(day=1)
    page = sam.get(reverse("planning:calendar"), {"from": later.isoformat()})
    assert page.context["selected"].date == later


@freeze_time("2026-10-12 09:00:00+02:00")
def test_a_past_day_has_no_plans_button(sam: Client, crew: Crew) -> None:
    page = sam.get(reverse("planning:calendar"), {"day": "2026-10-10"})
    assert page.context["selected"].date == datetime.date(2026, 10, 10)
    assert b"data-day-plan" not in page.content


def test_calendar_without_groups(client: Client, crew: Crew) -> None:
    client.force_login(crew.outsider)
    assert b"Nobody sees your days yet" in client.get(reverse("planning:calendar")).content


def test_day_sheet_shows_friends_first(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    plans.set_plan(crew.sam, crew.day, crew.zermatt)
    url = reverse("planning:day", kwargs={"day": crew.day})
    fragment = sam.get(url, headers=HTMX)
    assert b"<html" not in fragment.content
    assert b"Where will you be?" in fragment.content
    assert fragment.context["elsewhere"] == [crew.zermatt]
    page = sam.get(url)
    assert b"<html" in page.content


def test_day_sheet_saves(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    response = sam.post(
        url,
        {"resort": str(crew.verbier.uuid)},
        headers=HTMX,
    )
    assert response.status_code == 204 and response["HX-Refresh"] == "true"
    plan = PlanDay.objects.get(user=crew.sam, date=crew.day)
    assert plan.resort == crew.verbier
    # The sheet asks only where: no skiing switch.
    sheet = sam.get(url, headers=HTMX).content
    assert b"day-skiing" not in sheet and b'name="skiing"' not in sheet
    bad = sam.post(
        url,
        {"resort": "00000000-0000-0000-0000-000000000000"},
        headers=HTMX,
    )
    assert b"Pick a resort from the list" in bad.content


def test_day_sheet_needs_a_resort(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    sheet = sam.get(url, headers=HTMX).content
    assert b"Not at a resort" not in sheet and b"data-clearable" not in sheet
    assert b"(optional)" not in sheet
    missing = sam.post(url, {}, headers=HTMX)
    assert b"Pick a resort." in missing.content
    assert not PlanDay.objects.filter(user=crew.sam).exists()
    sam.post(url, {"resort": str(crew.verbier.uuid)}, headers=HTMX)
    assert PlanDay.objects.get(user=crew.sam).resort == crew.verbier


def test_day_sheet_save_and_clear(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    response = sam.post(url, {"resort": str(crew.verbier.uuid)})
    # Back to the calendar with the day still in the panel.
    assert response["Location"] == (f"{reverse('planning:calendar')}?day={crew.day.isoformat()}")
    assert PlanDay.objects.get(user=crew.sam).resort == crew.verbier
    assert b"Not sure" not in sam.get(url).content
    assert b"Clear this day" in sam.get(url).content
    sam.post(reverse("planning:day_clear", kwargs={"day": crew.day}), headers=HTMX)
    assert not PlanDay.objects.filter(user=crew.sam).exists()


def test_past_day_is_not_plannable(sam: Client) -> None:
    past = plans.today() - datetime.timedelta(days=1)
    assert sam.get(reverse("planning:day", kwargs={"day": past})).status_code == 404


def test_impossible_date_is_404(sam: Client) -> None:
    assert sam.get("/days/2027-02-30/").status_code == 404


def several(*days: str) -> str:
    """Return the several-days sheet's URL for ISO dates."""
    return reverse("planning:several_days") + "?days=" + ",".join(days)


@freeze_time("2026-10-11 09:00:00+02:00")
def test_several_days_sheet(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, datetime.date(2026, 12, 14), crew.verbier)
    plans.set_plan(crew.anna, datetime.date(2026, 12, 15), crew.verbier)
    plans.set_plan(crew.sam, datetime.date(2026, 12, 15), crew.zermatt)
    days = [f"2026-12-{day}" for day in range(14, 21)]
    fragment = sam.get(several(*reversed(days)), headers=HTMX)
    assert fragment.status_code == 200
    context = fragment.context
    assert context["title"] == "Mon 14 – Sun 20 December"
    assert context["eyebrow"] == "Calendar · 7 days"
    assert context["save_label"] == "Save 7 days"
    assert [e.names for e in context["friends"]] == ["Anna"]  # once, not twice
    # Sam is in Zermatt one day and has said nothing about the rest.
    assert context["mixed"]
    assert b"Pick a resort to put them all there." in fragment.content
    assert b"Leave as it is" not in fragment.content
    plans.update_plans(crew.sam, [datetime.date.fromisoformat(day) for day in days], crew.verbier)
    alike = sam.get(several(*days), headers=HTMX)
    assert not alike.context["mixed"]
    assert alike.context["selected"] == str(crew.verbier.uuid)
    assert b"Clear these days" in fragment.content
    assert context["form_url"].endswith("?days=" + ",".join(days))


@freeze_time("2026-10-11 09:00:00+02:00")
@pytest.mark.parametrize(
    ("days", "title"),
    [
        (["2026-12-14"], "Monday 14 December"),
        (["2026-12-30", "2027-01-02"], "Wed 30 December and Sat 2 January"),
        (
            ["2026-12-05", "2026-12-12", "2026-12-19"],
            "Sat 5, Sat 12 and Sat 19 December",
        ),
        (["2026-12-31", "2027-01-01"], "Thu 31 December – Fri 1 January"),
        ([f"2026-12-{d:02}" for d in (1, 3, 5, 7, 9)], "5 days, 1 – 9 December"),
        (
            ["2026-11-28", "2026-11-30", "2026-12-02", "2026-12-04", "2026-12-06"],
            "5 days, 28 November – 6 December",
        ),
    ],
)
def test_several_days_titles(sam: Client, crew: Crew, days: list[str], title: str) -> None:
    assert sam.get(several(*days), headers=HTMX).context["title"] == title


@freeze_time("2026-10-11 09:00:00+02:00")
def test_several_days_in_different_resorts(sam: Client, crew: Crew) -> None:
    days = [datetime.date(2026, 12, d) for d in (19, 20)]
    plans.set_plan(crew.sam, days[0], crew.verbier)
    plans.set_plan(crew.sam, days[1], crew.zermatt)
    url = several(*(d.isoformat() for d in days))
    sheet = sam.get(url, headers=HTMX)
    # Nothing is picked, so saving needs a resort.
    assert sheet.context["mixed"] and sheet.context["selected"] == ""
    refused = sam.post(url, {}, headers=HTMX)
    assert b"Pick a resort." in refused.content
    sam.post(url, {"resort": str(crew.verbier.uuid)}, headers=HTMX)
    assert {p.resort for p in PlanDay.objects.filter(user=crew.sam)} == {crew.verbier}


@freeze_time("2026-10-11 09:00:00+02:00")
def test_several_days_save_and_clear(sam: Client, crew: Crew) -> None:
    days = ["2026-12-05", "2026-12-12", "2026-12-19"]
    url = several(*days)
    response = sam.post(
        url,
        {"resort": str(crew.verbier.uuid), "from": "2026-12-01"},
    )
    assert response["Location"] == reverse("planning:calendar") + "?from=2026-12-01"
    saved = PlanDay.objects.filter(user=crew.sam).order_by("date")
    assert [p.date.isoformat() for p in saved] == days
    assert {p.resort for p in saved} == {crew.verbier}
    # Picking up the first day's plan as the starting point.
    assert sam.get(url, headers=HTMX).context["selected"] == str(crew.verbier.uuid)
    clear = reverse("planning:several_days_clear") + "?days=" + ",".join(days[:2])
    response = sam.post(clear, headers=HTMX)
    assert response["HX-Refresh"] == "true"
    assert [p.date.isoformat() for p in PlanDay.objects.filter(user=crew.sam)] == [days[2]]


@freeze_time("2026-10-11 09:00:00+02:00")
@pytest.mark.parametrize(
    "query",
    [
        "",
        "?days=",
        "?days=2026-12-01,nope",
        "?days=2026-10-10,2026-12-01",  # yesterday
        "?days="
        + ",".join(
            (datetime.date(2026, 11, 1) + datetime.timedelta(days=n)).isoformat() for n in range(63)
        ),
    ],
)
def test_several_days_refuses_bad_selections(sam: Client, crew: Crew, query: str) -> None:
    assert sam.get(reverse("planning:several_days") + query).status_code == 404


def test_calendar_can_select(sam: Client, crew: Crew) -> None:
    page = sam.get(reverse("planning:calendar"))
    assert b"data-select-bar" in page.content
    assert b'data-select-days="/days/several/"' in page.content
    assert b"js/day_select.js" in page.content
    assert b'data-select-max="62"' in page.content
    assert f'data-select-owner="{crew.sam.uuid}"'.encode() in page.content


def test_resort_search(sam: Client, crew: Crew) -> None:
    response = sam.get(reverse("planning:resort_search"), {"q": "verb"})
    assert b"Verbier" in response.content
    empty = sam.get(reverse("planning:resort_search"), {"q": "qqq"})
    assert b"No resort matches" in empty.content


# --- map -------------------------------------------------------------------------


def test_map_page(sam: Client, crew: Crew) -> None:
    PassFactory.create(slug="magic-pass", name="Magic Pass")
    response = sam.get(reverse("planning:map"), {"date": "2027-01-16", "pass": "magic-pass"})
    assert response.context["day"] == datetime.date(2027, 1, 16)
    assert b"Magic Pass" in response.content
    assert b"map/resort/RESORT/" in response.content
    assert b"Friends show up here" not in response.content
    # The pass chips swap pins in place, the day arrows keep the pass, and
    # the search box has every resort to match against.
    assert b'data-pass-chip="magic-pass"' in response.content
    assert response.content.count(b"data-day-link") == 2
    assert b'id="resort-index"' in response.content
    assert b"Verbier" in response.content
    # The day label opens a calendar that reaches the end of the horizon.
    assert b"data-calendar" in response.content
    assert response.context["last_day"] == plans.last_plannable_day()
    assert b'id="plan-marks"' in response.content
    # The site's top bar, with the one account link, sits above the map.
    assert b'class="topbar"' in response.content
    assert response.content.count(b'aria-label="Your account"') == 1


def test_map_page_bad_date_is_today(sam: Client) -> None:
    response = sam.get(reverse("planning:map"), {"date": "nope"})
    assert response.context["day"] == plans.today()


def test_map_pins_json(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    response = sam.get(reverse("planning:map_pins"), {"date": crew.day.isoformat()})
    data = json.loads(response.content)
    verbier = next(p for p in data["pins"] if p["name"] == "Verbier")
    assert verbier["friends"] == 1 and verbier["code"] == "VER"


def test_resort_sheet_and_plan_here(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, crew.verbier)
    url = reverse("planning:resort_sheet", kwargs={"resort_uuid": crew.verbier.uuid})
    sheet = sam.get(url, {"date": crew.day.isoformat()}, headers=HTMX)
    assert b"Anna" in sheet.content
    assert b"I'll be here" in sheet.content
    plans.set_plan(crew.ben, crew.day, crew.verbier)
    assert b"Around" not in (sam.get(url, {"date": crew.day.isoformat()}, headers=HTMX).content)
    assert b"meet-up" not in sheet.content
    plan_url = reverse("planning:plan_here", kwargs={"resort_uuid": crew.verbier.uuid})
    response = sam.post(plan_url, {"date": crew.day.isoformat()})
    assert response["Location"] == f"/map/?date={crew.day.isoformat()}"
    assert PlanDay.objects.get(user=crew.sam).resort == crew.verbier
    again = sam.get(url, {"date": crew.day.isoformat()}, headers=HTMX)
    assert b"Planned" in again.content and b"ll be here" not in again.content


def test_plan_here_ignores_past_days(sam: Client, crew: Crew) -> None:
    past = plans.today() - datetime.timedelta(days=3)
    url = reverse("planning:plan_here", kwargs={"resort_uuid": crew.verbier.uuid})
    sam.post(url, {"date": past.isoformat()}, headers=HTMX)
    assert not PlanDay.objects.exists()


# --- groups ------------------------------------------------------------------------


def test_group_list_and_create(sam: Client, crew: Crew) -> None:
    listing = sam.get(reverse("planning:group_list"))
    assert listing.context["groups"][0].member_count == 3
    response = sam.post(reverse("planning:group_list"), {"name": "Uni friends"})
    group = Group.objects.get(name="Uni friends")
    assert response["Location"] == reverse(
        "planning:group_detail", kwargs={"group_uuid": group.uuid}
    )
    assert is_member(group, crew.sam)


def test_group_detail_is_members_only(client: Client, crew: Crew) -> None:
    url = reverse("planning:group_detail", kwargs={"group_uuid": crew.group.uuid})
    client.force_login(crew.outsider)
    assert client.get(url).status_code == 404
    client.force_login(crew.anna)
    page = client.get(url)
    assert crew.group.invite_token.encode() in page.content
    assert b"Reset link" not in page.content  # owner only
    assert b"Leave this group" in page.content


def test_group_detail_owner_removes_members_from_a_menu(client: Client, crew: Crew) -> None:
    """Remove sits behind each member's "…" menu, never on the row itself."""
    url = reverse("planning:group_detail", kwargs={"group_uuid": crew.group.uuid})
    client.force_login(crew.sam)
    html = client.get(url).content.decode()
    assert html.count('<details class="row-menu">') == crew.group.memberships.count() - 1
    assert f"Remove {crew.anna}</button>" in html


def test_reset_invite(client: Client, crew: Crew) -> None:
    url = reverse("planning:reset_invite", kwargs={"group_uuid": crew.group.uuid})
    old = crew.group.invite_token
    client.force_login(crew.anna)
    client.post(url)
    crew.group.refresh_from_db()
    assert crew.group.invite_token == old  # not the owner
    client.force_login(crew.sam)
    client.post(url)
    crew.group.refresh_from_db()
    assert crew.group.invite_token != old


def test_leave_group(client: Client, crew: Crew) -> None:
    url = reverse("planning:leave_group", kwargs={"group_uuid": crew.group.uuid})
    client.force_login(crew.sam)
    assert client.post(url)["Location"].endswith(f"{crew.group.uuid}/")  # owner refused
    client.force_login(crew.anna)
    assert client.post(url)["Location"] == reverse("planning:group_list")
    assert not is_member(crew.group, crew.anna)


def test_delete_group(client: Client, crew: Crew) -> None:
    url = reverse("planning:delete_group", kwargs={"group_uuid": crew.group.uuid})
    client.force_login(crew.anna)
    assert client.get(url).status_code == 302  # not the owner
    client.force_login(crew.sam)
    assert b"Delete Thursday crew?" in client.get(url).content
    client.post(url)
    assert not Group.objects.exists()


def test_remove_member(client: Client, crew: Crew) -> None:
    url = reverse(
        "planning:remove_member",
        kwargs={"group_uuid": crew.group.uuid, "user_uuid": crew.ben.uuid},
    )
    client.force_login(crew.anna)
    client.post(url)
    assert is_member(crew.group, crew.ben)
    client.force_login(crew.sam)
    client.post(url)
    assert not is_member(crew.group, crew.ben)


def test_invite_flow(client: Client, crew: Crew) -> None:
    url = reverse("planning:invite", kwargs={"token": crew.group.invite_token})
    anonymous = client.get(url)
    assert b"Sign in to join" in anonymous.content
    assert b"og:title" in anonymous.content
    client.force_login(crew.outsider)
    page = client.get(url)
    assert b"Join Thursday crew" in page.content
    assert not is_member(crew.group, crew.outsider)  # opening never joins
    join = reverse("planning:join", kwargs={"token": crew.group.invite_token})
    client.post(join)
    assert is_member(crew.group, crew.outsider)
    assert client.get(url).status_code == 302  # members go to the group


def test_reset_invite_kills_old_link(client: Client, crew: Crew) -> None:
    old = crew.group.invite_token
    crew.group.reset_invite_token()
    assert client.get(reverse("planning:invite", kwargs={"token": old})).status_code == 404
    client.force_login(crew.outsider)
    assert client.post(reverse("planning:join", kwargs={"token": old})).status_code == 404


# --- board ---------------------------------------------------------------------------


def test_board(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, plans.today(), crew.verbier)
    plans.set_plan(crew.ben, plans.today(), crew.zermatt)
    url = reverse("planning:board", kwargs={"group_uuid": crew.group.uuid})
    page = sam.get(url)
    assert b"VER" in page.content and b"ZER" in page.content
    week = sam.get(url, {"start": "2027-01-04"})
    assert week.context["board"].start == datetime.date(2027, 1, 4)


@freeze_time("2026-10-11 09:00:00+02:00")
def test_calendar_marks_one_friend_or_several(sam: Client, crew: Crew) -> None:
    one, two = datetime.date(2026, 12, 5), datetime.date(2026, 12, 6)
    for day in (one, two):
        plans.set_plan(crew.sam, day, crew.verbier)
        plans.set_plan(crew.anna, day, crew.verbier)
    plans.set_plan(crew.ben, two, crew.verbier)
    page = sam.get(reverse("planning:calendar") + "?from=2026-12-01").content.decode()
    marks = re.findall(r'class="mday__friends"><svg[^>]*>(.*?)</svg>', page)
    single, double = '<circle cx="12"', '<circle cx="9"'
    assert len(marks) == 2
    assert marks[0].startswith(single) and marks[1].startswith(double)
