from datetime import datetime, timezone
import base64
import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from linkedin_ai_agent import token_renewal
from linkedin_ai_agent.token_renewal import Renewal, verified_metadata


def fixtures():
    now=datetime(2026,9,26,tzinfo=timezone.utc)
    inspection={'active':True,'client_id':'existing-app','scope':'openid,profile,w_member_social',
                'expires_at':int(now.timestamp())+60*86400}
    return now,inspection,{'sub':'correct-member'}


def test_verified_metadata_contains_no_credentials():
    now,inspection,identity=fixtures()
    data=verified_metadata(inspection,identity,'urn:li:person:correct-member','existing-app',now)
    assert data['expires_at']=='2026-11-25T00:00:00Z'
    assert not any('token' in key or 'secret' in key for key in data)


@pytest.mark.parametrize('change',[{'active':False},{'client_id':'another-app'},{'scope':'openid profile'},{'expires_at':0}])
def test_invalid_token_is_not_accepted(change):
    now,inspection,identity=fixtures(); inspection.update(change)
    with pytest.raises(ValueError):
        verified_metadata(inspection,identity,'urn:li:person:correct-member','existing-app',now)


def test_wrong_linkedin_account_is_rejected():
    now,inspection,identity=fixtures()
    with pytest.raises(ValueError,match='does not match'):
        verified_metadata(inspection,identity,'urn:li:person:different-member','existing-app',now)


def renewal_for_test(monkeypatch, tmp_path):
    monkeypatch.setattr(token_renewal, 'ROOT', tmp_path)
    renewal = Renewal.__new__(Renewal)
    now, inspection, identity = fixtures()
    renewal.metadata = verified_metadata(inspection, identity, 'urn:li:person:correct-member', 'existing-app', now)
    renewal.token = 'test-only-token'
    renewal.client_secret = None
    renewal.config = SimpleNamespace(state_dir=tmp_path / '.state')
    renewal.finished = False
    return renewal


def test_deploy_creates_missing_metadata_and_keeps_credentials_private(monkeypatch, tmp_path, capsys):
    renewal = renewal_for_test(monkeypatch, tmp_path)
    remote_content = base64.b64encode(json.dumps(renewal.metadata).encode()).decode()
    renewal.command = Mock(side_effect=['', '', 'null', '{}', renewal.metadata['expires_at'],
                                      json.dumps({'content': remote_content})])
    renewal.deploy()

    calls = renewal.command.call_args_list
    assert calls[0].args[0][:3] == ['secret', 'set', 'LINKEDIN_ACCESS_TOKEN']
    assert calls[0].args[1] == 'test-only-token'  # stdin, never a command argument
    assert 'test-only-token' not in calls[0].args[0]
    assert calls[2].kwargs['missing_ok'] is True
    assert 'sha' not in json.loads(calls[3].args[1])
    assert renewal.finished and renewal.token is None
    result = (tmp_path / '.state/token_renewal_result.json').read_text()
    assert 'test-only-token' not in result + capsys.readouterr().out
    assert json.loads(result)['published'] is False


def test_failed_save_retains_verified_token_for_retry(monkeypatch, tmp_path):
    renewal = renewal_for_test(monkeypatch, tmp_path)
    renewal.command = Mock(side_effect=['', RuntimeError('GitHub update failed')])
    with pytest.raises(RuntimeError, match='GitHub update failed'):
        renewal.deploy()
    assert renewal.token == 'test-only-token'
    assert not renewal.finished
    assert not (tmp_path / '.state/token_renewal_result.json').exists()
