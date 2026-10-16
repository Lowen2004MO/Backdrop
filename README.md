# People Pulse Analytics

A local, server-rendered Django application for exploring employee pulse-survey views. Its standard question catalogue reflects the supplied Q4 FY25/26 survey structure and can be extended by importing additional CSV columns. It includes dashboard filtering, question and theme analysis, individual response history, adaptive survey imports, report configuration, local authentication, and role-based access.

Imported question definitions and parsed response values are persisted in SQLite locally or PostgreSQL in AWS. The original CSV file and raw email/ID identity values are not retained; identifiers are converted into keyed references for matching periods. Names and exact answer text remain sensitive and must be handled accordingly.

## AWS deployment

The [infrastructure guide](infra/README.md) uses a small CloudFormation bootstrap for the encrypted Terraform state bucket and account budget, followed by Terraform for the application resources. The current low-traffic cloud runtime is a Django container on Lambda with an HTTPS Function URL; the original App Runner implementation is retained under `infra/terraform/legacy/`. Separate `ci`, `dev`, `lmo`, and `prod` target directories provide explicit state and configuration boundaries.

```powershell
.\infra\scripts\bootstrap-account.ps1 -BudgetEmail you@example.com -Profile your-sandbox-profile
.\infra\scripts\terraform-validate.ps1
.\infra\scripts\terraform-plan.ps1 -EnvironmentName dev -BackendBucket your-bootstrap-output -Profile your-sandbox-profile
.\infra\scripts\deploy-environment.ps1 -EnvironmentName dev -BackendBucket your-bootstrap-output -Profile your-sandbox-profile
```

Local validation requires Terraform 1.11+ but no deployment permissions. Deployment additionally requires AWS CLI v2, Docker Desktop, and appropriate sandbox permissions. Review the infrastructure guide before deploying because the AWS resources can incur charges.

## Quick start on Windows PowerShell

This project requires Python 3.11 or newer.

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python manage.py migrate
$env:PEOPLE_PULSE_DEMO_PASSWORD = 'choose-a-local-password'
python manage.py create_demo_users
Remove-Item Env:PEOPLE_PULSE_DEMO_PASSWORD
python manage.py runserver
```

If activation is restricted by workstation policy, call the interpreter directly without changing that policy:

```powershell
.\venv\Scripts\python.exe -m pip install -e '.[dev]'
.\venv\Scripts\python.exe manage.py migrate
$env:PEOPLE_PULSE_DEMO_PASSWORD = 'choose-a-local-password'
.\venv\Scripts\python.exe manage.py create_demo_users
Remove-Item Env:PEOPLE_PULSE_DEMO_PASSWORD
.\venv\Scripts\python.exe manage.py runserver
```

Open <http://127.0.0.1:8000/accounts/login/>. Stop the server with `Ctrl+C`.

## Manual survey-upload test

1. Sign in as `analyst@example.test` or `admin@example.test`.
2. Open **Surveys**, then select **Download sample CSV**.
3. Open **Upload survey**, enter a demonstration survey name, choose the financial year and quarter, and select the downloaded file.
4. Select **Import and analyse**. The focused summary should report six rows, 18 confirmed mappings, six ignored metadata columns, and the additional collaboration column as a new question.
5. Follow **View its questions and analytics**, or return to **Surveys**. Use **Remove** and confirm to delete an incorrect survey together with its questions and responses.

The same demonstration file is available directly at [`samples/people-pulse-demo-upload.csv`](samples/people-pulse-demo-upload.csv). An additional [acquisition-status sample](samples/people-pulse-acquisition-demo.csv) demonstrates acquisition status as a configurable dimension, group comparisons, theme evidence and dissatisfaction associations. The import stores detected questions and parsed response values, but not the original file or raw identity fields. Reimporting the same survey name and period transactionally replaces its questions and responses. The eight built-in demonstration surveys cannot be removed.

## Local text analysis

Text analysis runs automatically after a successful upload. Open the imported
survey and select **View text analysis** to inspect reviewed themes, supporting
sentences, confidence, quantitative associations, dimension breakdowns,
suggested topics and period trends. Analysts can approve or reject suggested
topics and can enable any suitable choice or yes/no question as a respondent
filter from the survey detail page.

To refresh existing imported surveys from PowerShell:

    .\venv\Scripts\python.exe manage.py analyse_survey_text all

The current model is a dependency-free local hybrid sentence-vector and keyword
baseline. It provides deterministic, auditable results suitable for testing the
workflow, but it must be evaluated against a human-labelled dataset before real
employment data is interpreted. Set PEOPLE_PULSE_MIN_COHORT_SIZE to a larger
value such as 5 or 10 before production use.

## Quick start on Linux or macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -e '.[dev]'
python manage.py migrate
export PEOPLE_PULSE_DEMO_PASSWORD='choose-a-local-password'
python manage.py create_demo_users
unset PEOPLE_PULSE_DEMO_PASSWORD
python manage.py runserver
```

The command creates or refreshes these development-only accounts:

| Username | Role | Upload | Admin site |
| --- | --- | --- | --- |
| `admin@example.test` | Administrator | Yes | Yes |
| `analyst@example.test` | Analyst | Yes | No |
| `stakeholder@example.test` | Stakeholder | No | No |

Passwords are not stored in source control. Pass one interactively, through the temporary development environment variable above, or with `--password` for disposable local use. Rerun the command to reset all three passwords.

Use the password you supplied through `PEOPLE_PULSE_DEMO_PASSWORD`. Choose a different local password whenever the workspace or database is shared.

## Tests and checks

```powershell
.\venv\Scripts\python.exe -m pytest
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

### Browser and accessibility tests

Install the optional UI dependencies and the managed Chromium browser once:

```powershell
.\venv\Scripts\python.exe -m pip install -e '.[dev,ui]'
.\venv\Scripts\python.exe -m playwright install chromium
```

Then run the Playwright journeys and axe WCAG 2.2 A/AA checks:

```powershell
.\venv\Scripts\python.exe -m pytest tests\ui -m ui --browser chromium
```

The automated checks cover detectable issues on login and the primary
authenticated pages, plus keyboard, responsive-menu, filtering, search, upload,
and removal journeys. Automated accessibility testing is not a WCAG
certification; complement it with keyboard-only, screen-reader, zoom/reflow,
contrast, and usability testing by people with disabilities.

## Development notes

- Django is constrained to `Django>=5.2.17,<5.3`, selecting the 5.2 LTS line. Django 6.1 was considered; an upgrade should happen at a planned dependency review rather than during this first vertical slice.
- Templates are server rendered. The pinned HTMX 2.0.8 asset is stored locally at `static/js/htmx.min.js`; there is no Node or frontend build step.
- Dashboard, question, theme, employee-search, and upload interactions have normal form fallbacks and focused HTMX responses.
- Period comparisons use two shortcut checkboxes (`Most recent only` and `All periods`) plus a compact dropdown containing the ticked quarters for custom, non-consecutive comparisons.
- Built-in demonstration analytics come from typed repository objects, while imported survey questions and answers use normalized Django models. Prepared metrics live in service modules rather than templates or chart JavaScript.
- Additional non-metadata CSV columns are inferred as agreement, yes/no, numeric, written, or choice questions. Choice and yes/no fields such as acquisition status can be enabled as reusable respondent filters.
- Uploaded written answers are processed by a versioned, local, explainable theme classifier. It stores confidence and exact evidence, proposes recurring unmatched topics for human review, calculates descriptive links with negative quantitative answers, and reports trends across matching survey names.
- Individual response pages show complete written answers and matched prior-period wording. Imported email/ID values are not displayed or stored directly.
- Charts are CSS/HTML representations supplied with captioned tables, keeping data usable without JavaScript, colour, or a visual chart.
- Local authentication is deliberately replaceable: application views use `request.user` and Django permissions without embedding password assumptions.

See [docs/architecture.md](docs/architecture.md) for boundaries and future replacement points.

See [docs/adaptive-questions.md](docs/adaptive-questions.md) for the implemented question-mapping states and the proposed versioning, lineage, review, and response-schema approach for future surveys.

See [docs/data-and-infrastructure-roadmap.md](docs/data-and-infrastructure-roadmap.md) for a prioritised review of data opportunities, application gaps, privacy safeguards, and AWS work needed before real survey data is used.

## Current demonstration limitations

Response-level CSV import and database-backed analytics are implemented for uploaded surveys. Response-type inference, approximate question matches, and proposed text themes should still receive human review. The local explainable classifier is an auditable baseline, not a validated production language model. There is no completed report generation, corporate SSO, audit logging, configurable retention schedule, or field-level encryption for response text. The AWS targets are a demonstration starting point rather than a completed production security design.
