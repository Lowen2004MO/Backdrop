import re
from pathlib import Path

import pytest
from django.urls import reverse

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect


pytestmark = [
    pytest.mark.ui,
    pytest.mark.django_db(transaction=True),
]


def test_sign_in_navigation_and_logout(authenticated_page):
    page = authenticated_page

    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()
    page.get_by_role("link", name="Questions", exact=True).click()
    expect(page.get_by_role("heading", name="Questions", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Questions", exact=True)).to_have_attribute(
        "aria-current", "page"
    )

    page.get_by_role("button", name="Log out").click()
    expect(page.get_by_role("heading", name="Sign in")).to_be_visible()


def test_period_shortcuts_and_custom_selection(authenticated_page):
    page = authenticated_page
    recent = page.get_by_label("Most recent only")
    all_periods = page.get_by_label("All periods")

    recent.check()
    expect(all_periods).not_to_be_checked()
    expect(page.locator("input[name='period']:checked")).to_have_count(1)

    with page.expect_request(re.compile(r"/dashboard/\?.*most_recent=1")):
        page.get_by_role("button", name="Apply filters").click()
    expect(page.get_by_text("1 selected", exact=True)).to_be_visible()

    page.get_by_text("Select survey periods").click()
    first_period = page.locator("input[name='period']").first
    first_period.check()
    expect(recent).not_to_be_checked()
    expect(all_periods).not_to_be_checked()


def test_employee_search_updates_results(authenticated_page, live_server):
    page = authenticated_page
    page.goto(f"{live_server.url}{reverse('pulse:employees')}")

    page.get_by_label("Search by name").fill("Avery")
    page.get_by_role("button", name="Apply").click()

    expect(page.get_by_text("Avery North")).to_be_visible()
    expect(page.get_by_text("Blair Rowan")).not_to_be_visible()


def test_dashboard_filters_work_areas_and_wraps_long_questions(authenticated_page, live_server):
    page = authenticated_page
    page.goto(
        f"{live_server.url}{reverse('pulse:dashboard')}?question=tools-and-resources"
    )

    picker = page.locator('.question-picker > summary')
    expect(picker).to_have_text('I have access to the tools and resources I need to do my job well')
    expect(page.get_by_role('heading', name='Associated themes')).to_have_count(0)
    page.get_by_text('Select groups', exact=False).click()
    page.get_by_label('Critical National Infrastructure', exact=True).check()
    group_dropdown = page.locator('details').filter(has=page.locator('[aria-label="Available respondent groups"]'))
    group_dropdown.get_by_role('button', name='OK', exact=True).click()
    expect(group_dropdown).not_to_have_attribute('open', '')
    expect(page.get_by_label('Critical National Infrastructure', exact=True)).to_be_checked()
    page.get_by_text('Select groups', exact=False).click()
    page.get_by_role('heading', name='Dashboard', exact=True).click()
    expect(group_dropdown).not_to_have_attribute('open', '')
    page.get_by_text('Select survey periods', exact=False).click()
    page.get_by_text('Select groups', exact=False).click()
    expect(page.locator('.period-dropdown[open]')).to_have_count(1)
    page.keyboard.press('Escape')
    expect(page.locator('.period-dropdown[open]')).to_have_count(0)
    page.get_by_role('button', name='Apply filters').click()
    expect(group_dropdown).not_to_have_attribute('open', '')
    expect(page.get_by_label('Critical National Infrastructure', exact=True)).to_be_checked()
    expect(page.locator('#dashboard-results')).to_contain_text('Critical National Infrastructure')
    expect(page.locator('#dashboard-results')).not_to_contain_text('All work areas')
    # The period shortcuts still work after the form has been replaced by HTMX.
    page.get_by_label('Most recent only').check()
    page.get_by_role('button', name='Apply filters').click()
    expect(page.locator('input[name=period]:checked')).to_have_count(1)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert picker.evaluate('(element) => element.scrollWidth <= element.clientWidth')
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    picker.click()
    page.get_by_label('I feel supported at work', exact=False).check()
    expect(page.locator('.question-picker > summary')).to_have_text('I feel supported at work')
    expect(page.get_by_label('Critical National Infrastructure', exact=True)).to_be_checked()
    expect(
        page.get_by_text(
            "Demonstration environment — not for employment decisions",
            exact=True,
        )
    ).to_be_visible()


def test_upload_and_remove_survey_through_ui(analyst_page, live_server):
    page = analyst_page
    sample = Path(__file__).resolve().parents[2] / "samples" / "people-pulse-demo-upload.csv"
    page.goto(f"{live_server.url}{reverse('pulse:upload')}")

    page.get_by_label("Survey name").fill("Playwright upload")
    page.get_by_label("Financial year").select_option("FY2025")
    page.get_by_label("Quarter").select_option("Q4")
    page.get_by_label("Csv file").set_input_files(sample)
    page.get_by_role("button", name="Import and analyse").click()

    expect(page.get_by_role("heading", name="Import summary")).to_be_visible()
    page.get_by_role("link", name="Surveys", exact=True).first.click()
    row = page.get_by_role("row").filter(has_text="Playwright upload")
    expect(row).to_be_visible()
    row.get_by_role("link", name="Remove").click()
    expect(
        page.get_by_role("heading", name=re.compile(r"Remove Playwright upload\?"))
    ).to_be_visible()
    page.get_by_role("button", name="Remove survey").click()
    expect(page.get_by_text(re.compile("Removed survey, questions and responses"))).to_be_visible()


def test_uploaded_question_and_exact_employee_response(analyst_page, live_server):
    page = analyst_page
    upload = Path(__file__).resolve().parents[2] / "samples" / "people-pulse-demo-upload.csv"
    page.goto(f"{live_server.url}{reverse('pulse:upload')}")
    page.get_by_label("Survey name").fill("Flexible questions")
    page.get_by_label("Financial year").select_option("FY2026")
    page.get_by_label("Quarter").select_option("Q3")
    page.get_by_label("Csv file").set_input_files(upload)
    page.get_by_role("button", name="Import and analyse").click()
    page.get_by_role("link", name="View its questions and analytics").click()
    page.get_by_role("link", name="What would improve collaboration across teams?").click()
    page.get_by_text("Select groups").click()
    page.get_by_label("Digital delivery", exact=True).check()
    page.get_by_label("Consulting", exact=True).check()
    page.get_by_role("button", name="Apply group filter").click()
    expect(page.get_by_text("Difference between selected groups")).to_be_visible()
    page.get_by_role("link", name="Sample Respondent 01").click()
    expect(
        page.get_by_role(
            "heading",
            name="Written responses",
        )
    ).to_be_visible()
    expect(page.get_by_text("More shared planning sessions.", exact=True)).to_be_visible()


def test_employee_selects_multiple_periods(authenticated_page, live_server):
    page = authenticated_page
    page.goto(f'{live_server.url}/employees/00000000-0000-0000-0000-000000000001/')
    page.get_by_text('Select survey periods', exact=False).click()
    for checkbox in page.locator('input[name=period]').all():
        checkbox.uncheck()
    for period in ['FY2024 Q3', 'FY2025 Q1', 'FY2025 Q4']:
        page.get_by_label(period, exact=True).check()
    page.get_by_role('button', name='OK', exact=True).click()
    page.get_by_role('button', name='Compare periods', exact=True).click()
    expect(page.locator('.employee-period-answers thead th')).to_have_count(4)
    expect(page.locator('.written-comparison').first.locator('.written-response-table tbody tr')).to_have_count(3)
    expect(page.locator('input[name=period]:checked')).to_have_count(3)
    expect(page.locator('.period-dropdown[open]')).to_have_count(0)
    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_mobile_menu_exposes_navigation(authenticated_page):
    page = authenticated_page
    page.set_viewport_size({"width": 390, "height": 844})

    menu = page.get_by_role("button", name="Menu")
    expect(menu).to_be_visible()
    menu.click()
    expect(menu).to_have_attribute("aria-expanded", "true")
    expect(page.get_by_role("navigation", name="Primary")).to_have_class(
        re.compile(r"\bopen\b")
    )
