"""apps/accounts/tasks.py — Background tasks for accounts: the sign-in email.

Views enqueue; they never send mail themselves, so a slow mail server
can't hold a request (settings.TASKS chooses where the task runs: on a
thread of its own, apps.core.task_backends.ThreadBackend).

The address is only this task's argument, so with the thread backend it
stays in memory. A queue-backed backend would store it until the email is
sent, and the privacy notice would have to say so.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.tasks import task
from django.template.loader import render_to_string


@task()
def send_sign_in_email(email: str, link: str, code: str) -> None:
    """Email ``email`` its sign-in link and code."""
    context = {
        "link": link,
        "code": code,
        "minutes": settings.SIGN_IN_MAX_AGE_SECONDS // 60,
        "SITE_NAME": settings.SITE_NAME,
    }
    send_mail(
        subject=render_to_string("accounts/email/sign_in_subject.txt", context).strip(),
        message=render_to_string("accounts/email/sign_in.txt", context),
        html_message=render_to_string("accounts/email/sign_in.html", context),
        from_email=None,
        recipient_list=[email],
    )
