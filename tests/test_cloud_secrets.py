import json

from people_pulse import cloud_secrets


class FakeSecretsManager:
    def __init__(self):
        self.calls = 0

    def get_secret_value(self, *, SecretId):
        self.calls += 1
        return {
            "ARN": SecretId,
            "SecretString": json.dumps(
                {"username": "database-user", "password": "database-password"}
            ),
        }


def test_secret_values_are_decoded_and_cached(monkeypatch):
    client = FakeSecretsManager()
    cloud_secrets.get_secret_string.cache_clear()
    monkeypatch.setattr(cloud_secrets.boto3, "client", lambda service: client)

    secret = cloud_secrets.get_secret_json("arn:aws:secretsmanager:test")
    repeated = cloud_secrets.get_secret_json("arn:aws:secretsmanager:test")

    assert secret == {
        "username": "database-user",
        "password": "database-password",
    }
    assert repeated == secret
    assert client.calls == 1
