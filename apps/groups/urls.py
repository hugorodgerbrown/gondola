"""apps/groups/urls.py — Planning URLs (namespace ``planning``)."""

from django.urls import path, register_converter

from .converters import DateConverter
from .views import board, days, groups, meetups, resort_map

register_converter(DateConverter, "date")

app_name = "planning"

urlpatterns = [
    # A · the map
    path("map/", resort_map.map_page, name="map"),
    path("map/pins.json", resort_map.pins, name="map_pins"),
    path(
        "map/resort/<uuid:resort_uuid>/", resort_map.resort_sheet, name="resort_sheet"
    ),
    path("map/resort/<uuid:resort_uuid>/plan/", resort_map.plan_here, name="plan_here"),
    # B · my days
    path("days/", days.my_days, name="my_days"),
    path("days/<date:day>/", days.day, name="day"),
    path("days/<date:day>/clear/", days.day_clear, name="day_clear"),
    path("days/several/", days.several_days, name="several_days"),
    path("days/several/clear/", days.several_days_clear, name="several_days_clear"),
    path("resorts/search/", days.resort_search, name="resort_search"),
    # Groups and the board
    path("groups/", groups.group_list, name="group_list"),
    path("groups/<uuid:group_uuid>/", groups.group_detail, name="group_detail"),
    path("groups/<uuid:group_uuid>/board/", board.board, name="board"),
    path(
        "groups/<uuid:group_uuid>/reset-link/",
        groups.reset_invite,
        name="reset_invite",
    ),
    path("groups/<uuid:group_uuid>/leave/", groups.leave, name="leave_group"),
    path("groups/<uuid:group_uuid>/delete/", groups.delete, name="delete_group"),
    path(
        "groups/<uuid:group_uuid>/members/<uuid:user_uuid>/remove/",
        groups.remove,
        name="remove_member",
    ),
    path("i/<str:token>/", groups.invite, name="invite"),
    path("i/<str:token>/join/", groups.join, name="join"),
    # C · meet-ups
    path("meetups/new/", meetups.meetup_choose_group, name="meetup_choose_group"),
    path(
        "groups/<uuid:group_uuid>/meetups/new/",
        meetups.meetup_new,
        name="meetup_new",
    ),
    path("m/<str:token>/", meetups.meetup, name="meetup"),
    path("m/<str:token>/join/", meetups.meetup_join, name="meetup_join"),
    path("m/<str:token>/leave/", meetups.meetup_leave, name="meetup_leave"),
    path("m/<str:token>/cancel/", meetups.meetup_cancel, name="meetup_cancel"),
]
