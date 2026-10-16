import json
from functools import cache
from typing import Any

import boto3


@cache
def get_secret_string(secret_arn: str) -> str:
    """Return and cache one Secrets Manager value for this process."""
    response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_arn)
    value = response.get("SecretString")
    if not value:
        raise RuntimeError(f"Secret {secret_arn} does not contain a string value.")
    return value


def get_secret_json(secret_arn: str) -> dict[str, Any]:
    """Decode a JSON Secrets Manager value."""
    value = json.loads(get_secret_string(secret_arn))
    if not isinstance(value, dict):
        raise RuntimeError(f"Secret {secret_arn} does not contain a JSON object.")
    return value
