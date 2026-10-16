import os
import re

# pytest-playwright owns an asyncio event loop while its session-scoped browser
# is running. Django's test database setup is intentionally synchronous, so
# allow that synchronous setup only inside this isolated browser-test process.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse


pytestmark = pytest.mark.django_db(transaction=True)
UI_PASSWORD = "ui-test-password-123"


@pytest.fixture
def viewer(django_user_model):
    return django_user_model.objects.create_user(
        username="viewer@example.test",
        email="viewer@example.test",
        password=UI_PASSWORD,
        first_name="Demo",
        last_name="Viewer",
    )


@pytest.fixture
def analyst(django_user_model):
    user = django_user_model.objects.create_user(
        username="analyst@example.test",
        email="analyst@example.test",
        password=UI_PASSWORD,
        first_name="Demo",
        last_name="Analyst",
    )
    group = Group.objects.create(name="People Pulse Analysts UI")
    group.permissions.add(
        Permission.objects.get(codename="add_surveyuploadpermission")
    )
    user.groups.add(group)
    return user


def sign_in(page, live_server, user):
    page.goto(f"{live_server.url}{reverse('accounts:login')}")
    page.get_by_label("Username or email").fill(user.username)
    page.get_by_label("Password").fill(UI_PASSWORD)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(re.compile(r"/dashboard/$"))


@pytest.fixture
def authenticated_page(page, live_server, viewer):
    sign_in(page, live_server, viewer)
    return page


@pytest.fixture
def analyst_page(page, live_server, analyst):
    sign_in(page, live_server, analyst)
    return page
