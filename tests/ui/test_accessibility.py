import pytest
from django.urls import reverse

pytest.importorskip("playwright.sync_api")
pytest.importorskip("axe_playwright_python.sync_playwright")
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import expect


pytestmark = [
    pytest.mark.ui,
    pytest.mark.django_db(transaction=True),
]

WCAG_22_AA = {
    "runOnly": {
        "type": "tag",
        "values": [
            "wcag2a",
            "wcag2aa",
            "wcag21a",
            "wcag21aa",
            "wcag22a",
            "wcag22aa",
        ],
    }
}


def assert_wcag_22_aa(page):
    results = Axe().run(page, options=WCAG_22_AA)
    violations = results.response["violations"]
    summary = "\n".join(
        f"{item['id']}: {item['help']} ({len(item['nodes'])} node(s)) - {item['helpUrl']}"
        for item in violations
    )
    assert not violations, summary


def test_login_page_has_no_automatically_detectable_wcag_22_aa_violations(
    page, live_server
):
    page.goto(f"{live_server.url}{reverse('accounts:login')}")
    assert_wcag_22_aa(page)


@pytest.mark.parametrize(
    "route_name",
    ["dashboard", "questions", "themes", "employees", "surveys", "reports"],
)
def test_primary_pages_have_no_automatically_detectable_wcag_22_aa_violations(
    authenticated_page, live_server, route_name
):
    authenticated_page.goto(f"{live_server.url}{reverse(f'pulse:{route_name}')}")
    assert_wcag_22_aa(authenticated_page)


def test_skip_link_moves_keyboard_focus_to_main(authenticated_page):
    page = authenticated_page
    page.keyboard.press("Tab")
    skip_link = page.get_by_role("link", name="Skip to main content")
    expect(skip_link).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()
