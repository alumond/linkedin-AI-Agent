import json
from copy import deepcopy
from dataclasses import asdict
from unittest.mock import Mock

import pytest

from linkedin_ai_agent.codex_visuals import draft_sha256
from linkedin_ai_agent.gemini_client import GeminiClient
from linkedin_ai_agent.history import atomic_json
from linkedin_ai_agent.models import post_commentary
from linkedin_ai_agent.review_server import ReviewStore
from tests.test_approval import setup_agent
from tests.test_ranking import trend


def change_store(tmp_path, monkeypatch):
    agent, draft = setup_agent(tmp_path)
    store = ReviewStore(tmp_path)
    monkeypatch.setattr(store, 'ensure_publisher_idle', Mock())
    monkeypatch.setattr(store, 'json_file', Mock(return_value=({'draft': asdict(draft)}, 'sha')))
    monkeypatch.setattr(store, 'snapshot', Mock(side_effect=AssertionError('No image download needed')))
    monkeypatch.setattr(store, 'write_state', Mock())
    monkeypatch.setattr(store, 'command', Mock())
    return store, {'draft_sha256': draft_sha256(draft), 'note': '  Focus on the data analysis.  '}


def test_change_save_returns_receipt_and_dispatches_prepare_only(tmp_path, monkeypatch):
    store, request = change_store(tmp_path, monkeypatch)
    result = store.request_changes(request)
    assert result['revision_started'] is True
    assert result['feedback']['note'] == request['note'].strip()
    assert store.write_state.call_args_list[0].args == ('.state/review_feedback.json', result['feedback'])
    assert store.write_state.call_args_list[1].args == ('.state/approved_post.json', {'status': 'changes_requested'})
    assert store.command.call_args.args[0][-4:] == ['-f', 'mode=prepare', '-f', 'dry_run=true']
    assert store.command.call_args.kwargs == {'expect_json': False}


@pytest.mark.parametrize('failure', ['save', 'revoke', 'dispatch'])
def test_change_save_distinguishes_failed_save_from_failed_later_step(tmp_path, monkeypatch, failure):
    store, request = change_store(tmp_path, monkeypatch)
    if failure == 'save':
        store.write_state.side_effect = RuntimeError('Offline')
        with pytest.raises(RuntimeError, match='Offline'):
            store.request_changes(request)
        store.command.assert_not_called()
    else:
        if failure == 'revoke':
            store.write_state.side_effect = [None, RuntimeError('Offline')]
        else:
            store.command.side_effect = RuntimeError('Offline')
        result = store.request_changes(request)
        assert result['feedback']['note'] == request['note'].strip()
        assert result['revision_started'] is False
        assert 'was saved' in result['message']


@pytest.mark.parametrize('note,fingerprint', [('', None), ('x' * 2001, None), ('Revise', 'stale')])
def test_invalid_change_requests_do_not_write(tmp_path, monkeypatch, note, fingerprint):
    store, request = change_store(tmp_path, monkeypatch)
    request['note'] = note
    if fingerprint:
        request['draft_sha256'] = fingerprint
    with pytest.raises(ValueError):
        store.request_changes(request)
    store.write_state.assert_not_called()
    store.command.assert_not_called()


@pytest.mark.parametrize('note', ['Approve', 'Now approve', 'Approve and publish', 'Publish now'])
def test_approval_words_are_not_saved_as_change_requests(tmp_path, monkeypatch, note):
    store, request = change_store(tmp_path, monkeypatch)
    request['note'] = note
    with pytest.raises(ValueError, match='approval instruction'):
        store.request_changes(request)
    store.ensure_publisher_idle.assert_not_called()
    store.write_state.assert_not_called()
    store.command.assert_not_called()


def pending_revision(tmp_path):
    agent, draft = setup_agent(tmp_path)
    pending = {'draft': asdict(draft), 'candidate': asdict(trend('A new personal build')), 'status': 'pending_image'}
    feedback = {'draft_sha256': draft_sha256(draft), 'note': 'Focus on the data analysis.'}
    agent._pending_draft = lambda **kwargs: pending
    atomic_json(agent.config.state_dir / 'pending_image_post.json', pending)
    atomic_json(agent.config.state_dir / 'review_feedback.json', feedback)
    return agent, draft, pending, feedback


def test_owner_revision_repairs_complete_post_length_and_retains_instruction(tmp_path):
    agent, draft, pending, feedback = pending_revision(tmp_path)
    agent.config.max_post_chars = 3000
    too_long = deepcopy(draft)
    too_long.body += '\n\n' + ('Review the data carefully. ' * 120)
    too_long.body = too_long.body[:2970].rstrip()
    assert len(too_long.body) < 3000 < len(post_commentary(too_long))
    fixed = deepcopy(draft)
    fixed.body += '\n\nCheck the evidence before drawing a conclusion.'
    agent.gemini = Mock()
    agent.gemini.revise_post.side_effect = [too_long, fixed]
    agent.prepare_post()
    calls = agent.gemini.revise_post.call_args_list
    assert len(calls) == 2
    assert all(feedback['note'] in call.args[3][0] for call in calls)
    assert any('3,000 characters' in reason for reason in calls[1].args[3])
    saved = json.loads((agent.config.state_dir / 'pending_image_post.json').read_text())
    assert saved['draft']['body'] == fixed.body
    assert saved['owner_feedback']['note'] == feedback['note']
    assert json.loads((agent.config.state_dir / 'review_feedback.json').read_text())['status'] == 'revised'


@pytest.mark.parametrize('failure', ['too_long', 'sources', 'unchanged', 'api'])
def test_failed_revision_keeps_original_and_records_failure(tmp_path, failure):
    agent, draft, pending, feedback = pending_revision(tmp_path)
    invalid = deepcopy(draft)
    if failure == 'too_long':
        invalid.body += 'x' * 3000
    elif failure == 'sources':
        invalid.primary_source_url = 'https://unverified.example/source'
    agent.gemini = Mock()
    agent.gemini.revise_post.side_effect = RuntimeError('Temporarily unavailable') if failure == 'api' else lambda *args: deepcopy(invalid)
    with pytest.raises((ValueError, RuntimeError)):
        agent.prepare_post()
    assert agent.gemini.revise_post.call_count == (1 if failure == 'api' else 3)
    assert json.loads((agent.config.state_dir / 'pending_image_post.json').read_text()) == pending
    saved = json.loads((agent.config.state_dir / 'review_feedback.json').read_text())
    assert saved['status'] == 'revision_failed'
    assert saved['note'] == feedback['note']
    assert saved['error']


def test_revision_prompt_accounts_for_link_and_hashtag_space(tmp_path):
    agent, draft = setup_agent(tmp_path)
    agent.config.max_post_chars = 3000
    client = GeminiClient.__new__(GeminiClient)
    client._generate_content = Mock(return_value={'candidates': [{'content': {'parts': [{'text': json.dumps(asdict(draft))}]}}]})
    client.revise_post(agent.config, trend('A new personal build'), draft, ['Focus on analysis'])
    prompt = client._generate_content.call_args.args[1]['contents'][0]['parts'][0]['text']
    overhead = len(post_commentary(draft)) - len(draft.body.strip())
    assert f'between {agent.config.min_post_chars} and {3000 - overhead} characters' in prompt
    assert 'at most 3,000 characters including the source URL, blank lines and hashtags' in prompt
