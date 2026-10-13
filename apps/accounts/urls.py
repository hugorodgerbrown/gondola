"""apps/accounts/urls.py — Sign-in and account URLs (namespace ``accounts``)."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-in/check-email/", views.check_email, name="check_email"),
    path(
        "sign-in/passkey/options/",
        views.passkey_sign_in_options,
        name="passkey_sign_in_options",
    ),
    path("sign-in/passkey/", views.passkey_sign_in, name="passkey_sign_in"),
    path("sign-in/<str:token>/", views.verify, name="verify"),
    path("app/welcome/", views.welcome, name="welcome"),
    path("app/welcome/passkey/", views.passkey_welcome, name="passkey_welcome"),
    path("app/account/", views.account_settings, name="settings"),
    path("app/account/delete/", views.delete_account, name="delete"),
    path(
        "app/account/passkeys/options/",
        views.passkey_register_options,
        name="passkey_register_options",
    ),
    path("app/account/passkeys/", views.passkey_register, name="passkey_register"),
    path(
        "app/account/passkeys/<uuid:passkey_uuid>/delete/",
        views.passkey_delete,
        name="passkey_delete",
    ),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("email/stop/<str:token>/", views.stop_evening_email, name="stop_email"),
]
