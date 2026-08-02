import base64
import json

from linkedin_ai_agent.oauth_server import owner_urn_from_id_token


def test_owner_urn_from_id_token():
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "abc123"}).encode()).decode().rstrip("=")
    assert owner_urn_from_id_token(f"{header}.{payload}.") == "urn:li:person:abc123"
