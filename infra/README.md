# People Pulse infrastructure

The active infrastructure keeps one personal sandbox, `lmo`, and the resources
needed to run the existing Django application: Lambda with an HTTPS Function
URL, ECR, private PostgreSQL, networking, IAM, Secrets Manager, and logs.
CloudFormation bootstraps the encrypted, versioned Terraform state bucket and
account budget.

```text
infra/
  bootstrap/template.yaml
  scripts/
  terraform/
    modules/people_pulse/
    target_env/lmo/
```

The complete previous folder is preserved at [`../infra-backup/`](../infra-backup/README.md).
It includes `ci`, `dev`, `prod`, the older App Runner implementation, and local
tools/caches. The active folder omits these and the unused App Runner scaling
variables. Terraform resource addresses, physical names, the `lmo` backend key,
and provider lockfile are retained. Some network resource names still mention
App Runner to preserve their existing Terraform identities.

## Validate

Install Terraform 1.11 or later, then run from the project root:

```powershell
terraform fmt -recursive -check .\infra\terraform
.\infra\scripts\terraform-validate.ps1
```

Validation downloads providers into a temporary directory and does not deploy.
The previous locally downloaded Terraform executable is preserved at
`infra-backup/.tools/terraform/terraform.exe` if needed.

## Bootstrap and deploy

Deployment requires AWS CLI v2, Docker Desktop, and an AWS profile with deployment
permissions. Bootstrap once per account/region, or reuse the existing state bucket:

```powershell
.\infra\scripts\bootstrap-account.ps1 -BudgetEmail you@example.com -Profile your-sandbox-profile
.\infra\scripts\terraform-plan.ps1 -BackendBucket your-existing-state-bucket -Profile your-sandbox-profile
.\infra\scripts\deploy-environment.ps1 -BackendBucket your-existing-state-bucket -Profile your-sandbox-profile
.\infra\scripts\show-environment-access.ps1 -BackendBucket your-existing-state-bucket -Profile your-sandbox-profile
```

Environment helpers default to `lmo`; `-EnvironmentName lmo` remains supported.
The region defaults to `eu-west-2`. Use the existing state bucket: initialization
reconnects to `people-pulse/lmo/terraform.tfstate`. Local `.terraform` directories
are archived; the helpers initialize the active working directory as needed.

The `lmo` IAM role prefix and permissions boundary retain their existing sandbox
account settings. Review these before using a different account.

Deployment first creates ECR, builds and pushes a timestamped container image,
then presents the full Terraform apply for approval. Review plans before applying.
Demo credentials are generated in Secrets Manager; the access helper prints them.

## Teardown

```powershell
.\infra\scripts\destroy-environment.ps1 -BackendBucket your-existing-state-bucket -Profile your-sandbox-profile
```

Review the destroy plan. The sandbox retains a final RDS snapshot; state objects,
retained backups, bootstrap bucket, and budget are not removed by this helper.

This remains a demonstration: Lambda concurrency is capped at one because
migrations run at container startup. AWS resources incur charges, and production
identity, audit, retention, and migration controls still need separate work.
