"""apps/groups/urls.py — Planning URLs (namespace ``planning``).

Everything is under /app/, the installed app, except the invite link.
"""

from django.urls import path, register_converter

from .converters import DateConverter
from .views import board, days, groups, resort_map

register_converter(DateConverter, "date")

app_name = "planning"

urlpatterns = [
    # A · the map
    path("app/map/", resort_map.map_page, name="map"),
    path("app/map/pins.json", resort_map.pins, name="map_pins"),
    path("app/map/resort/<uuid:resort_uuid>/", resort_map.resort_sheet, name="resort_sheet"),
    path("app/map/resort/<uuid:resort_uuid>/plan/", resort_map.plan_here, name="plan_here"),
    # B · the calendar
    path("app/days/", days.calendar, name="calendar"),
    path("app/days/<date:day>/", days.day, name="day"),
    path("app/days/<date:day>/clear/", days.day_clear, name="day_clear"),
    path("app/days/several/", days.several_days, name="several_days"),
    path("app/days/several/clear/", days.several_days_clear, name="several_days_clear"),
    # The outbox's save and clear (JSON), for any of the sheets above.
    path("app/days/plans/", days.plans_write, name="plans_write"),
    path("app/resorts/search/", days.resort_search, name="resort_search"),
    # Groups and the board
    path("app/groups/", groups.group_list, name="group_list"),
    path("app/groups/<uuid:group_uuid>/", groups.group_detail, name="group_detail"),
    path("app/groups/<uuid:group_uuid>/board/", board.board, name="board"),
    path(
        "app/groups/<uuid:group_uuid>/reset-link/",
        groups.reset_invite,
        name="reset_invite",
    ),
    path("app/groups/<uuid:group_uuid>/leave/", groups.leave, name="leave_group"),
    path("app/groups/<uuid:group_uuid>/delete/", groups.delete, name="delete_group"),
    path(
        "app/groups/<uuid:group_uuid>/members/<uuid:user_uuid>/remove/",
        groups.remove,
        name="remove_member",
    ),
    # Public: an invite link opens without an account, outside the app.
    path("i/<str:token>/", groups.invite, name="invite"),
    path("i/<str:token>/join/", groups.join, name="join"),
]
