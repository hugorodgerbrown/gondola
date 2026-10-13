"""Tests for apps/mcp/tools.py: each tool, called as a user."""

import datetime
from typing import Any

import pytest
from freezegun import freeze_time

from apps.groups.models import PlanDay
from apps.mcp.tools import (
    ToolError,
    clear_days,
    find_resort,
    my_days,
    my_groups,
    set_days,
    where_is,
    whos_where,
)
from tests.factories import (
    GroupFactory,
    MembershipFactory,
    PassFactory,
    PlanDayFactory,
    ResortFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def frozen() -> Any:
    """Every test runs on 1 December 2026, Swiss time."""
    with freeze_time("2026-12-01 09:00:00+01:00"):
        yield


DAY = datetime.date(2026, 12, 20)


@pytest.fixture
def world() -> Any:
    """Anna (the caller) and Ben share a group; Cara is in no group of Anna's."""
    anna = UserFactory.create(display_name="Anna")
    ben = UserFactory.create(display_name="Ben Smith")
    cara = UserFactory.create(display_name="Cara")
    group = GroupFactory.create(name="Thursday crew", owner=anna)
    MembershipFactory.create(group=group, user=anna)
    MembershipFactory.create(group=group, user=ben)
    verbier = ResortFactory.create(name="Verbier", code="VER")
    verbier.passes.add(PassFactory.create(name="Magic Pass"))
    zermatt = ResortFactory.create(name="Zermatt", code="ZER")
    return {
        "anna": anna,
        "ben": ben,
        "cara": cara,
        "group": group,
        "verbier": verbier,
        "zermatt": zermatt,
    }


def test_find_resort(world: Any) -> None:
    (found,) = find_resort(world["anna"], {"query": "verb"})["resorts"]
    assert found == {
        "name": "Verbier",
        "code": "VER",
        "canton": "VS",
        "passes": ["Magic Pass"],
    }


def test_set_then_read_my_days(world: Any) -> None:
    result = set_days(
        world["anna"], {"from": "2026-12-20", "to": "2026-12-21", "resort": "verbier"}
    )
    assert result["saved"] == ["2026-12-20", "2026-12-21"]
    days = my_days(world["anna"], {})["days"]
    assert days[0] == {
        "date": "2026-12-20",
        "weekday": "Sunday",
        "resort": "Verbier",
        "code": "VER",
    }
    assert len(days) == 2


def test_set_days_moves_a_day_to_another_resort(world: Any) -> None:
    PlanDayFactory.create(user=world["anna"], date=DAY, resort=world["verbier"])
    set_days(world["anna"], {"dates": ["2026-12-20"], "resort": "ZER"})
    assert PlanDay.objects.get(user=world["anna"], date=DAY).resort == world["zermatt"]


def test_set_days_saves_nothing_when_a_day_is_past(world: Any) -> None:
    with pytest.raises(ToolError, match="nothing was saved"):
        set_days(
            world["anna"],
            {"dates": ["2026-11-30", "2026-12-20"], "resort": "Verbier"},
        )
    assert not PlanDay.objects.exists()


@pytest.mark.parametrize(
    ("resort", "message"),
    [("Nowhere", "No resort matches"), ("er", "could be")],
)
def test_set_days_needs_one_resort(world: Any, resort: str, message: str) -> None:
    with pytest.raises(ToolError, match=message):
        set_days(world["anna"], {"dates": ["2026-12-20"], "resort": resort})


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"resort": "Verbier"}, "Say which days"),
        ({"dates": [], "resort": "Verbier"}, "non-empty list"),
        ({"dates": ["20/12/2026"], "resort": "Verbier"}, "YYYY-MM-DD"),
        ({"dates": [20261220], "resort": "Verbier"}, "YYYY-MM-DD"),
        ({"from": "2026-12-21", "to": "2026-12-20", "resort": "V"}, "on or after"),
        ({"from": "2026-12-01", "to": "2028-12-01", "resort": "V"}, "at most"),
        ({"dates": ["2026-12-20"] * 400, "resort": "V"}, "at most"),
        ({"dates": ["2026-12-20"], "resort": " "}, "resort is required"),
    ],
)
def test_bad_days_are_explained(world: Any, args: dict[str, Any], message: str) -> None:
    with pytest.raises(ToolError, match=message):
        set_days(world["anna"], args)


def test_clear_days(world: Any) -> None:
    PlanDayFactory.create(user=world["anna"], date=DAY, resort=world["verbier"])
    PlanDayFactory.create(user=world["ben"], date=DAY, resort=world["verbier"])
    result = clear_days(world["anna"], {"from": "2026-12-19", "to": "2026-12-21"})
    assert result == {"cleared": ["2026-12-20"]}
    assert list(PlanDay.objects.values_list("user", flat=True)) == [world["ben"].pk]


def test_clear_days_never_touches_the_past(world: Any) -> None:
    past = datetime.date(2025, 12, 20)
    PlanDayFactory.create(user=world["anna"], date=past, resort=world["verbier"])
    PlanDayFactory.create(user=world["anna"], date=DAY, resort=world["verbier"])
    with pytest.raises(ToolError, match="nothing was cleared"):
        clear_days(world["anna"], {"dates": ["2025-12-20", "2026-12-20"]})
    assert PlanDay.objects.filter(user=world["anna"]).count() == 2


def test_my_days_takes_a_range_and_skips_the_past(world: Any) -> None:
    PlanDayFactory.create(user=world["anna"], date=datetime.date(2026, 11, 1))
    PlanDayFactory.create(user=world["anna"], date=DAY)
    assert len(my_days(world["anna"], {})["days"]) == 1
    past = my_days(world["anna"], {"from": "2026-11-01"})["days"]
    assert [d["date"] for d in past] == ["2026-11-01"]


def test_my_groups_hides_demo_groups(world: Any) -> None:
    demo = GroupFactory.create(name="Demo", is_demo=True)
    MembershipFactory.create(group=demo, user=world["anna"])
    (group,) = my_groups(world["anna"], {})["groups"]
    assert group["name"] == "Thursday crew"
    assert group["owner"] == "Anna"
    assert group["members"] == ["Anna", "Ben Smith"]


def test_whos_where_shows_friends_and_you_but_no_strangers(world: Any) -> None:
    PlanDayFactory.create(user=world["anna"], date=DAY, resort=world["verbier"])
    PlanDayFactory.create(user=world["ben"], date=DAY, resort=world["verbier"])
    PlanDayFactory.create(user=world["cara"], date=DAY, resort=world["verbier"])
    (day,) = whos_where(world["anna"], {"dates": ["2026-12-20"]})["days"]
    assert day["weekday"] == "Sunday"
    assert day["resorts"] == [
        {"resort": "Verbier", "code": "VER", "people": ["you", "Ben Smith"]}
    ]


def test_whos_where_defaults_to_today_and_narrows(world: Any) -> None:
    today = datetime.date(2026, 12, 1)
    PlanDayFactory.create(user=world["ben"], date=today, resort=world["zermatt"])
    assert whos_where(world["anna"], {})["days"][0]["date"] == "2026-12-01"
    args = {"from": "2026-12-01", "to": "2026-12-03", "group": "thursday"}
    assert len(whos_where(world["anna"], args)["days"]) == 1
    assert whos_where(world["anna"], {**args, "resort": "Verbier"}) == {"days": []}


@pytest.mark.parametrize(
    ("group", "message"), [("Nope", "no group called"), ("r", "could be")]
)
def test_whos_where_needs_one_of_your_groups(
    world: Any, group: str, message: str
) -> None:
    other = GroupFactory.create(name="Friday crew")
    MembershipFactory.create(group=other, user=world["anna"])
    with pytest.raises(ToolError, match=message):
        whos_where(world["anna"], {"group": group})


def test_whos_where_is_capped(world: Any) -> None:
    with pytest.raises(ToolError, match="at most 31"):
        whos_where(world["anna"], {"from": "2026-12-01", "to": "2027-01-31"})


def test_where_is(world: Any) -> None:
    PlanDayFactory.create(user=world["ben"], date=DAY, resort=world["zermatt"])
    result = where_is(world["anna"], {"person": "ben"})
    assert result["person"] == "Ben Smith"
    assert [d["resort"] for d in result["days"]] == ["Zermatt"]


@pytest.mark.parametrize("person", ["Cara", "Zed"])
def test_where_is_only_finds_your_groups(world: Any, person: str) -> None:
    with pytest.raises(ToolError, match="No one in your groups"):
        where_is(world["anna"], {"person": person})


def test_where_is_asks_which_when_two_match(world: Any) -> None:
    other = UserFactory.create(display_name="Ben Jones")
    MembershipFactory.create(group=world["group"], user=other)
    with pytest.raises(ToolError, match="could be"):
        where_is(world["anna"], {"person": "Ben"})
    assert where_is(world["anna"], {"person": "Ben Jones"})["person"] == "Ben Jones"
