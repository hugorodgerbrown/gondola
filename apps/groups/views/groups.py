"""apps/groups/views/groups.py — Groups, their invite links and members.

* ``group_list`` lists your groups and makes a new one.
* ``group_detail`` is a group's page: who's in it and its invite link.
* ``invite`` is what an invite link opens. It needs no account to read,
  and never joins by itself: the Join button does.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.shortcuts import render
from apps.public.views import DEMO_MONTH, demo_weeks
from apps.tour.session import after_join

from ..forms import GroupForm
from ..models import Group
from ..services.memberships import (
    MembershipError,
    create_group,
    join_group,
    leave_group,
    remove_member,
)
from ..services.people import is_member, members_of
from .helpers import current_user, member_group


@login_required
def group_list(request: HttpRequest) -> HttpResponse:
    """List the person's groups, and make a new one."""
    user = current_user(request)
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = create_group(user, form.cleaned_data["name"])
        messages.success(request, "Group made. Send the invite link to your friends.")
        return redirect("planning:group_detail", group_uuid=group.uuid)
    # Count before filtering: filtering on memberships first would count
    # only the viewer's own row.
    groups = (
        Group.objects.annotate(member_count=Count("memberships"))
        .filter(pk__in=Group.objects.for_user(user).values("pk"))
        .order_by("name")
    )
    return render(request, "groups/group_list.html", {"groups": groups, "form": form})


def invite_url(request: HttpRequest, group: Group) -> str:
    """Return the absolute invite link for ``group``."""
    path = reverse("planning:invite", kwargs={"token": group.invite_token})
    return request.build_absolute_uri(path)


@login_required
def group_detail(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Show a group: its members, its invite link and its actions."""
    group = member_group(request, group_uuid)
    user = current_user(request)
    memberships = {m.user_id: m for m in group.memberships.all()}
    members = [(person, memberships[person.pk]) for person in members_of(group)]
    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "members": members,
            "is_owner": group.owner_id == user.pk,
            "invite_link": invite_url(request, group),
        },
    )


@login_required
@require_POST
def reset_invite(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Replace the invite link (owner only), so the old one stops working."""
    group = member_group(request, group_uuid)
    if group.owner_id == current_user(request).pk:
        group.reset_invite_token()
        messages.success(request, "New invite link made. The old one no longer works.")
    return redirect("planning:group_detail", group_uuid=group.uuid)


@login_required
@require_POST
def leave(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Leave a group."""
    group = member_group(request, group_uuid)
    try:
        leave_group(group, current_user(request))
    except MembershipError as exc:
        messages.error(request, str(exc))
        return redirect("planning:group_detail", group_uuid=group.uuid)
    messages.success(request, f"You left {group.name}.")
    return redirect("planning:group_list")


@login_required
def delete(request: HttpRequest, group_uuid: str) -> HttpResponse:
    """Confirm, then delete a group (owner only)."""
    group = member_group(request, group_uuid)
    if group.owner_id != current_user(request).pk:
        return redirect("planning:group_detail", group_uuid=group.uuid)
    if request.method == "POST":
        name = group.name
        group.delete()
        messages.success(request, f"{name} is deleted.")
        return redirect("planning:group_list")
    return render(request, "groups/group_delete.html", {"group": group})


@login_required
@require_POST
def remove(request: HttpRequest, group_uuid: str, user_uuid: str) -> HttpResponse:
    """Remove someone from the group (owner only)."""
    group = member_group(request, group_uuid)
    member = get_object_or_404(User, uuid=user_uuid)
    try:
        remove_member(group, current_user(request), member)
    except MembershipError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{member} is out of {group.name}.")
    return redirect("planning:group_detail", group_uuid=group.uuid)


def invite(request: HttpRequest, token: str) -> HttpResponse:
    """Show an invite: the front page's story of Gondola, around a Join button."""
    group = Group.objects.real().select_related("owner").filter(invite_token=token).first()
    if group is None:
        return render(request, "groups/invite_invalid.html", status=404)
    user = request.user
    if isinstance(user, User) and is_member(group, user):
        return redirect("planning:group_detail", group_uuid=group.uuid)
    member_count = group.memberships.count()
    return render(
        request,
        "groups/invite.html",
        {
            "group": group,
            "member_count": member_count,
            "others": member_count - 1,
            "demo_month": DEMO_MONTH,
            "demo_weeks": demo_weeks(),
        },
    )


@login_required
@require_POST
def join(request: HttpRequest, token: str) -> HttpResponse:
    """Join the group an invite link names."""
    group = Group.objects.real().filter(invite_token=token).first()
    if group is None:
        return render(request, "groups/invite_invalid.html", status=404)
    _, created = join_group(group, current_user(request))
    if created:
        messages.success(request, f"You're in {group.name}. Add your days next.")
    group_url = reverse("planning:group_detail", kwargs={"group_uuid": group.uuid})
    # A new account that signed up through this link is offered the tour now.
    return redirect(after_join(request, group_url))
