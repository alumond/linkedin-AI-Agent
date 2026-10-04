import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from linkedin_ai_agent.review_server import ReviewStore


@pytest.mark.parametrize('output', ['', '\n', 'https://github.com/alumond/linkedin-AI-Agent/actions/runs/123\n'])
def test_prepare_accepts_successful_cli_output(tmp_path, monkeypatch, output):
    store = ReviewStore(tmp_path)
    run = Mock(side_effect=[
        SimpleNamespace(returncode=0, stdout='[]'),
        SimpleNamespace(returncode=0, stdout=output),
    ])
    monkeypatch.setattr('linkedin_ai_agent.review_server.subprocess.run', run)
    result = store.prepare()
    assert result['preparing'] is True
    assert 'started' in result['message']
    assert run.call_args.args[0][-4:] == ['-f', 'mode=prepare', '-f', 'dry_run=true']


@pytest.mark.parametrize('status', ['queued', 'in_progress', 'pending', 'waiting', 'requested'])
def test_prepare_does_not_duplicate_active_run(tmp_path, monkeypatch, status):
    store = ReviewStore(tmp_path)
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout=json.dumps([{'status': status}])))
    monkeypatch.setattr('linkedin_ai_agent.review_server.subprocess.run', run)
    assert 'already' in store.prepare()['message']
    assert run.call_count == 1
    assert run.call_args.args[0][1:3] == ['run', 'list']


def test_prepare_reports_real_dispatch_failure_without_exposing_output(tmp_path, monkeypatch):
    store = ReviewStore(tmp_path)
    run = Mock(side_effect=[
        SimpleNamespace(returncode=0, stdout='[]'),
        SimpleNamespace(returncode=1, stdout='private diagnostic', stderr='private credential'),
    ])
    monkeypatch.setattr('linkedin_ai_agent.review_server.subprocess.run', run)
    with pytest.raises(RuntimeError, match='GitHub could not complete') as exc:
        store.prepare()
    assert 'private' not in str(exc.value)


def test_invalid_json_is_not_treated_as_success(tmp_path, monkeypatch):
    store = ReviewStore(tmp_path)
    run = Mock(return_value=SimpleNamespace(returncode=0, stdout='invalid response'))
    monkeypatch.setattr('linkedin_ai_agent.review_server.subprocess.run', run)
    with pytest.raises(RuntimeError, match='unreadable response'):
        store.prepare()
    assert run.call_count == 1


@pytest.mark.parametrize('busy', [True, False])
def test_empty_desk_includes_preparation_status(tmp_path, monkeypatch, busy):
    store = ReviewStore(tmp_path)
    monkeypatch.setattr('linkedin_ai_agent.review_server.load_config', lambda _: SimpleNamespace())
    monkeypatch.setattr(store, 'json_file', lambda path, **kw: ([] if 'history' in path else None, None))
    monkeypatch.setattr(store, 'publisher_busy', lambda: busy)
    state = store.snapshot()
    assert state['preparing'] is busy
    assert state['pending'] is None
    assert state['approved'] is False
