"""Tests for the page frame: the website's footer, the app's links and the logo."""

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

LINKS = ["public:help", "public:terms", "public:privacy"]


@pytest.mark.parametrize("name", ["public:home", "public:help", "public:terms"])
def test_public_pages_end_with_the_footer(client: Client, name: str) -> None:
    """A public page ends with the footer: its links and the copyright, nothing else."""
    content = client.get(reverse(name)).content.decode()
    footer = content[content.index('<footer class="site-footer"') : content.index("</footer>")]
    for link in LINKS:
        assert f'href="{reverse(link)}"' in footer
    assert f"© {timezone.localdate().year} ultraniche.ai" in footer
    assert "<img" not in footer


def test_the_account_page_lists_the_links(signed_in: Client) -> None:
    """The app has no footer, so its links and the copyright are on the account page."""
    content = signed_in.get(reverse("accounts:settings")).content.decode()
    assert 'class="site-links"' in content
    for link in LINKS:
        assert f'href="{reverse(link)}"' in content
    assert f"© {timezone.localdate().year} ultraniche.ai" in content
