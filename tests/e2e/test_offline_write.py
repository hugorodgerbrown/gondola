"""A day saved with no signal waits on the phone and sends when signal returns.

Scenario: offline write (docs/testing.md, "Journeys").
"""

import datetime
import re
from typing import Any

from playwright.sync_api import Page, expect

from apps.accounts.models import User
from apps.groups.models import PlanDay
from apps.groups.services.memberships import create_group, join_group
from apps.groups.services.plans import set_plan, today
from tests.factories import ResortFactory, UserFactory


def test_a_day_saved_offline_sends_when_back_online(signed_in_page: Page, live_server: Any) -> None:
    """The sheet opens online; signal drops; Save draws the day waiting, then sends."""
    walker = User.objects.get(email="walker@example.com")
    friend = UserFactory.create(display_name="Anna")
    join_group(create_group(walker, "Crew"), friend)
    verbier = ResortFactory.create(name="Verbier", code="VERBIER")
    day = today() + datetime.timedelta(days=1)
    set_plan(friend, day, verbier)
    page = signed_in_page
    page.goto(f"{live_server.url}/app/days/?day={day.isoformat()}")
    page.get_by_role("link", name="Add plans").click()
    expect(page.get_by_role("radio", name="Verbier")).to_be_visible()

    page.context.set_offline(True)
    page.get_by_role("radio", name="Verbier").check()
    page.get_by_role("button", name="Save").click()
    cell = page.locator(f'.mday[data-date="{day.isoformat()}"]')
    expect(cell).to_have_class(re.compile(r"\bmday--pending\b.*\bmday--in\b"))
    expect(cell).to_contain_text("VER")
    expect(page.locator("[data-outbox-status]")).to_have_text("1 waiting to send")
    assert not PlanDay.objects.filter(user=walker).exists()

    page.context.set_offline(False)
    expect(cell).not_to_have_class(re.compile(r"\bmday--pending\b"), timeout=10_000)
    expect(cell).to_have_class(re.compile(r"\bmday--in\b"))
    assert PlanDay.objects.get(user=walker).resort == verbier
