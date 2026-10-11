"""Tests for the planning views: days, map, groups, board and meet-ups."""

import datetime
import json

import pytest
from django.test import Client
from django.urls import reverse

from apps.groups.models import Group, MeetUp, PlanDay
from apps.groups.services import meetups, plans
from apps.groups.services.people import is_member
from tests.factories import PassFactory
from tests.groups.conftest import Crew

pytestmark = pytest.mark.django_db
S = PlanDay.Status
HTMX = {"HX-Request": "true"}


@pytest.fixture
def sam(client: Client, crew: Crew) -> Client:
    client.force_login(crew.sam)
    return client


# --- sign-in is required ---------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["planning:map", "planning:my_days", "planning:group_list"]
)
def test_screens_need_sign_in(client: Client, name: str) -> None:
    response = client.get(reverse(name))
    assert response["Location"].startswith(reverse("accounts:sign_in"))


# --- my days ------------------------------------------------------------------------


def test_my_days_lists_fourteen_days(sam: Client, crew: Crew) -> None:
    plans.set_plan(
        crew.sam, plans.today(), S.RESORT, resort=crew.verbier, is_private=True
    )
    response = sam.get(reverse("planning:my_days"))
    assert len(response.context["rows"]) == 14
    assert b"Thursday crew sees these" in response.content
    assert b"Private" in response.content


def test_my_days_steps_a_fortnight_and_lists_other_plans(
    sam: Client, crew: Crew
) -> None:
    today = plans.today()
    far = today + datetime.timedelta(days=60)
    plans.set_plan(crew.sam, far, S.RESORT, resort=crew.verbier)
    response = sam.get(reverse("planning:my_days"))
    # The first fortnight starts today: no way back, a way on, and the
    # December day listed under it, and dotted on the calendar.
    assert response.context["previous_start"] is None
    assert response.context["next_start"] == today + datetime.timedelta(days=14)
    assert [plan.date for plan in response.context["elsewhere"]] == [far]
    assert response.context["marks"] == {far.isoformat(): "resort"}
    assert b"Your other plans" in response.content
    assert b'id="plan-marks"' in response.content
    assert b"js/calendar.js" in response.content

    later = sam.get(reverse("planning:my_days"), {"from": far.isoformat()})
    first_day, first_plan = later.context["rows"][0]
    assert first_day == far and first_plan.resort == crew.verbier
    assert later.context["elsewhere"] == []
    assert later.context["previous_start"] == far - datetime.timedelta(days=14)


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-5, 0), (1000, plans.PLAN_HORIZON_DAYS - plans.MY_DAYS_SPAN + 1)],
)
def test_my_days_window_stays_plannable(
    sam: Client, offset: int, expected: int
) -> None:
    today = plans.today()
    start = today + datetime.timedelta(days=offset)
    response = sam.get(reverse("planning:my_days"), {"from": start.isoformat()})
    assert response.context["start"] == today + datetime.timedelta(days=expected)
    if offset > 0:
        assert response.context["end"] == plans.last_plannable_day()
        assert response.context["next_start"] is None


def test_plain_forms_keep_the_fortnight(sam: Client, crew: Crew) -> None:
    """Without JavaScript, saving or clearing a day returns to its fortnight."""
    far = plans.today() + datetime.timedelta(days=60)
    page = sam.get(reverse("planning:my_days"), {"from": far.isoformat()})
    day_url = reverse("planning:day", kwargs={"day": far})
    assert f'href="{day_url}?from={far.isoformat()}"'.encode() in page.content
    sheet = sam.get(day_url, {"from": far.isoformat()})
    assert f'name="from" value="{far.isoformat()}"'.encode() in sheet.content
    back = f"{reverse('planning:my_days')}?from={far.isoformat()}"
    saved = sam.post(day_url, {"status": S.NOT_SURE, "from": far.isoformat()})
    assert saved["Location"] == back
    cleared = sam.post(
        reverse("planning:day_clear", kwargs={"day": far}), {"from": far.isoformat()}
    )
    assert cleared["Location"] == back
    # The first fortnight needs nothing carried.
    assert sam.get(reverse("planning:my_days")).context["window_from"] is None


def test_my_days_without_groups(client: Client, crew: Crew) -> None:
    client.force_login(crew.outsider)
    assert b"Nobody sees these yet" in client.get(reverse("planning:my_days")).content


def test_day_sheet_shows_friends_first(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    plans.set_plan(crew.sam, crew.day, S.RESORT, resort=crew.zermatt)
    url = reverse("planning:day", kwargs={"day": crew.day})
    fragment = sam.get(url, headers=HTMX)
    assert b"<html" not in fragment.content
    assert b"Where friends are" in fragment.content
    assert fragment.context["elsewhere"] == crew.zermatt
    page = sam.get(url)
    assert b"<html" in page.content


def test_day_sheet_saves(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    response = sam.post(
        url,
        {
            "status": "resort",
            "resort": str(crew.verbier.uuid),
            "note": "first lift",
            "is_private": "on",
        },
        headers=HTMX,
    )
    assert response.status_code == 204 and response["HX-Refresh"] == "true"
    plan = PlanDay.objects.get(user=crew.sam, date=crew.day)
    assert (plan.resort, plan.note, plan.is_private) == (
        crew.verbier,
        "first lift",
        True,
    )


def test_day_sheet_needs_resort_when_skiing(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    response = sam.post(url, {"status": "resort"}, headers=HTMX)
    assert response.status_code == 200
    assert b"Pick a resort" in response.content
    bad = sam.post(
        url,
        {"status": "resort", "resort": "00000000-0000-0000-0000-000000000000"},
        headers=HTMX,
    )
    assert b"Pick a resort from the list" in bad.content


def test_day_sheet_not_sure_and_clear(sam: Client, crew: Crew) -> None:
    url = reverse("planning:day", kwargs={"day": crew.day})
    response = sam.post(url, {"status": "not_sure"})
    assert response["Location"] == reverse("planning:my_days")
    assert PlanDay.objects.get(user=crew.sam).status == S.NOT_SURE
    assert b"Clear this day" in sam.get(url).content
    sam.post(reverse("planning:day_clear", kwargs={"day": crew.day}), headers=HTMX)
    assert not PlanDay.objects.filter(user=crew.sam).exists()


def test_past_day_is_not_plannable(sam: Client) -> None:
    past = plans.today() - datetime.timedelta(days=1)
    assert sam.get(reverse("planning:day", kwargs={"day": past})).status_code == 404


def test_impossible_date_is_404(sam: Client) -> None:
    assert sam.get("/days/2027-02-30/").status_code == 404


def test_resort_search(sam: Client, crew: Crew) -> None:
    response = sam.get(reverse("planning:resort_search"), {"q": "verb"})
    assert b"Verbier" in response.content
    empty = sam.get(reverse("planning:resort_search"), {"q": "qqq"})
    assert b"No resort matches" in empty.content


# --- map -------------------------------------------------------------------------


def test_map_page(sam: Client, crew: Crew) -> None:
    PassFactory.create(slug="magic-pass", name="Magic Pass")
    response = sam.get(
        reverse("planning:map"), {"date": "2027-01-16", "pass": "magic-pass"}
    )
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


def test_map_page_bad_date_is_today(sam: Client) -> None:
    response = sam.get(reverse("planning:map"), {"date": "nope"})
    assert response.context["day"] == plans.today()


def test_map_pins_json(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    response = sam.get(reverse("planning:map_pins"), {"date": crew.day.isoformat()})
    data = json.loads(response.content)
    verbier = next(p for p in data["pins"] if p["name"] == "Verbier")
    assert verbier["friends"] == 1 and verbier["code"] == "VERB"


def test_resort_sheet_and_plan_here(sam: Client, crew: Crew) -> None:
    plans.set_plan(
        crew.anna, crew.day, S.RESORT, resort=crew.verbier, note="first lift"
    )
    url = reverse("planning:resort_sheet", kwargs={"resort_uuid": crew.verbier.uuid})
    sheet = sam.get(url, {"date": crew.day.isoformat()}, headers=HTMX)
    assert b"first lift" in sheet.content
    assert b"Plan my day here" in sheet.content
    assert b"Propose a meet-up here" in sheet.content
    plan_url = reverse("planning:plan_here", kwargs={"resort_uuid": crew.verbier.uuid})
    response = sam.post(plan_url, {"date": crew.day.isoformat()})
    assert response["Location"] == f"/map/?date={crew.day.isoformat()}"
    assert PlanDay.objects.get(user=crew.sam).resort == crew.verbier
    again = sam.get(url, {"date": crew.day.isoformat()}, headers=HTMX)
    assert b"Planned" in again.content and b"Plan my day here" not in again.content


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
    assert (
        client.get(reverse("planning:invite", kwargs={"token": old})).status_code == 404
    )
    client.force_login(crew.outsider)
    assert (
        client.post(reverse("planning:join", kwargs={"token": old})).status_code == 404
    )


# --- board ---------------------------------------------------------------------------


def test_board(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, plans.today(), S.RESORT, resort=crew.verbier)
    meetups.propose_meetup(crew.group, crew.anna, plans.today(), crew.zermatt)
    url = reverse("planning:board", kwargs={"group_uuid": crew.group.uuid})
    page = sam.get(url)
    assert b"VERB" in page.content and b"ZERM" in page.content
    week = sam.get(url, {"start": "2027-01-04"})
    assert week.context["board"].start == datetime.date(2027, 1, 4)


# --- meet-ups --------------------------------------------------------------------------


def test_propose_meetup_prefills_top_suggestion(sam: Client, crew: Crew) -> None:
    plans.set_plan(crew.anna, crew.day, S.RESORT, resort=crew.verbier)
    url = reverse("planning:meetup_new", kwargs={"group_uuid": crew.group.uuid})
    page = sam.get(url, {"date": crew.day.isoformat()})
    assert page.context["selected"] == str(crew.verbier.uuid)
    asked = sam.get(
        url, {"date": crew.day.isoformat(), "resort": str(crew.zermatt.uuid)}
    )
    assert asked.context["extra"] == crew.zermatt
    junk = sam.get(url, {"resort": "junk"})
    assert junk.context["extra"] is None


def test_propose_meetup_saves(sam: Client, crew: Crew) -> None:
    url = reverse("planning:meetup_new", kwargs={"group_uuid": crew.group.uuid})
    response = sam.post(
        url,
        {
            "date": crew.day.isoformat(),
            "resort": str(crew.verbier.uuid),
            "start_time": "09:00",
            "meeting_latitude": "46.1",
            "meeting_longitude": "",
        },
    )
    meetup = MeetUp.objects.get()
    assert response["Location"] == reverse(
        "planning:meetup", kwargs={"token": meetup.share_token}
    )
    assert meetup.start_time == datetime.time(9) and not meetup.has_meeting_pin


def test_propose_meetup_goes_to_the_existing_one(sam: Client, crew: Crew) -> None:
    meetup = meetups.propose_meetup(crew.group, crew.anna, crew.day, crew.verbier)
    url = reverse("planning:meetup_new", kwargs={"group_uuid": crew.group.uuid})
    response = sam.get(url, {"date": crew.day.isoformat()})
    assert response["Location"] == reverse(
        "planning:meetup", kwargs={"token": meetup.share_token}
    )


def test_propose_meetup_shows_a_lost_race(
    sam: Client, crew: Crew, monkeypatch: pytest.MonkeyPatch
) -> None:
    meetups.propose_meetup(crew.group, crew.anna, crew.day, crew.verbier)
    monkeypatch.setattr("apps.groups.views.meetups.meetup_on", lambda *a: None)
    url = reverse("planning:meetup_new", kwargs={"group_uuid": crew.group.uuid})
    response = sam.post(
        url, {"date": crew.day.isoformat(), "resort": str(crew.zermatt.uuid)}
    )
    assert b"already has a meet-up" in response.content
    assert MeetUp.objects.count() == 1


def test_propose_meetup_refuses_past_day(sam: Client, crew: Crew) -> None:
    url = reverse("planning:meetup_new", kwargs={"group_uuid": crew.group.uuid})
    past = plans.today() - datetime.timedelta(days=1)
    response = sam.post(
        url, {"date": past.isoformat(), "resort": str(crew.verbier.uuid)}
    )
    assert b"later day" in response.content
    assert not MeetUp.objects.exists()


def test_choose_group(client: Client, crew: Crew) -> None:
    url = reverse("planning:meetup_choose_group")
    client.force_login(crew.sam)
    one = client.get(url, {"date": "2027-01-16"})
    assert one["Location"].endswith(
        f"/groups/{crew.group.uuid}/meetups/new/?date=2027-01-16"
    )
    Group.objects.create(owner=crew.sam, name="Second").memberships.create(
        user=crew.sam, role="member"
    )
    assert b"Which group" in client.get(url).content


def test_meetup_page_public_and_member_views(client: Client, crew: Crew) -> None:
    meetup = meetups.propose_meetup(
        crew.group, crew.sam, crew.day, crew.verbier, latitude=46.1, longitude=7.2
    )
    url = reverse("planning:meetup", kwargs={"token": meetup.share_token})
    public = client.get(url)
    assert b"Sign in to join" in public.content
    assert b"og:title" in public.content
    assert public.context["show_names"] is False
    client.force_login(crew.anna)
    member = client.get(url)
    assert member.context["show_names"] is True
    assert "I'm going" in member.content.decode()
    client.force_login(crew.outsider)
    assert b"adds you to Thursday crew" in client.get(url).content


def test_meetup_join_leave_cancel(client: Client, crew: Crew) -> None:
    meetup = meetups.propose_meetup(crew.group, crew.sam, crew.day, crew.verbier)
    token = meetup.share_token
    client.force_login(crew.outsider)
    client.post(reverse("planning:meetup_join", kwargs={"token": token}))
    assert meetups.is_going(meetup, crew.outsider) and is_member(
        crew.group, crew.outsider
    )
    page = client.get(reverse("planning:meetup", kwargs={"token": token}))
    assert b"Share the meet-up link" in page.content
    client.post(reverse("planning:meetup_leave", kwargs={"token": token}))
    assert not meetups.is_going(meetup, crew.outsider)
    client.post(reverse("planning:meetup_cancel", kwargs={"token": token}))
    assert MeetUp.objects.exists()  # not theirs to cancel
    client.force_login(crew.sam)
    client.post(reverse("planning:meetup_leave", kwargs={"token": token}))
    assert meetups.is_going(meetup, crew.sam)  # organiser can't leave
    response = client.post(reverse("planning:meetup_cancel", kwargs={"token": token}))
    assert response["Location"] == reverse(
        "planning:board", kwargs={"group_uuid": crew.group.uuid}
    )
    assert not MeetUp.objects.exists()


def test_passed_meetup_cannot_be_joined(client: Client, crew: Crew) -> None:
    meetup = meetups.propose_meetup(crew.group, crew.sam, crew.day, crew.verbier)
    MeetUp.objects.filter(pk=meetup.pk).update(
        date=plans.today() - datetime.timedelta(days=1)
    )
    client.force_login(crew.anna)
    url = reverse("planning:meetup", kwargs={"token": meetup.share_token})
    assert b"has passed" in client.get(url).content
    client.post(reverse("planning:meetup_join", kwargs={"token": meetup.share_token}))
    assert not meetups.is_going(meetup, crew.anna)
