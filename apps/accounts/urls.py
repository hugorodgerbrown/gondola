"""apps/accounts/urls.py — Sign-in and account URLs (namespace ``accounts``)."""

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-in/", views.sign_in, name="sign_in"),
    path("sign-in/check-email/", views.check_email, name="check_email"),
    path("sign-in/<str:token>/", views.verify, name="verify"),
    path("welcome/", views.welcome, name="welcome"),
    path("account/", views.account_settings, name="settings"),
    path("account/delete/", views.delete_account, name="delete"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("email/stop/<str:token>/", views.stop_evening_email, name="stop_email"),
]
