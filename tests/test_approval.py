import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from linkedin_ai_agent.agent import LinkedInAIAgent
from linkedin_ai_agent.codex_visuals import draft_sha256
from linkedin_ai_agent.history import atomic_json
from linkedin_ai_agent.review_server import ReviewStore
from tests.test_agent import FakeGemini
from tests.test_ranking import config, trend


def setup_agent(tmp_path):
    cfg = config(tmp_path)
    cfg.require_post_approval = True
    cfg.min_post_chars, cfg.max_post_chars = 700, 1300
    agent = LinkedInAIAgent(cfg, gemini=FakeGemini(), linkedin=Mock())
    candidate = trend('A new personal build')
    draft = agent.generate_draft(candidate)
    agent._select_draft = lambda: (candidate, draft, [])
    return agent, draft


def test_unapproved_post_never_contacts_linkedin(tmp_path):
    agent, draft = setup_agent(tmp_path)
    result = agent.run(dry_run=False)
    assert result.status == 'awaiting_approval'
    assert not agent.linkedin.mock_calls
    assert (agent.config.state_dir / 'pending_image_post.json').exists()
    assert not agent.history.load()
    # A full dry run remains possible without approving or publishing.
    assert agent.run(dry_run=True).status == 'dry_run_ok'
    assert not agent.linkedin.mock_calls


def test_approval_is_bound_to_text_and_image(tmp_path):
    agent, draft = setup_agent(tmp_path)
    atomic_json(agent.config.state_dir / 'approved_post.json', {
        'draft_sha256': draft_sha256(draft), 'asset_sha256': 'image-v1',
        'approved_at': datetime.now(timezone.utc).isoformat(), 'approved_by': 'owner_local_review'})
    assert agent._approval_reason(draft, 'image-v1') is None
    assert agent._approval_reason(draft, 'image-v2')
    draft.body += '\nAn edit after approval.'
    assert agent._approval_reason(draft, 'image-v1')


def test_requested_changes_revoke_approval(tmp_path):
    agent, draft = setup_agent(tmp_path)
    atomic_json(agent.config.state_dir / 'approved_post.json', {
        'draft_sha256': draft_sha256(draft), 'asset_sha256': 'image',
        'approved_at': '2026-09-25T08:00:00+00:00', 'approved_by': 'owner_local_review'})
    atomic_json(agent.config.state_dir / 'review_feedback.json', {
        'draft_sha256': draft_sha256(draft), 'requested_at': '2026-09-25T08:01:00+00:00',
        'note': 'Revise the image'})
    assert 'Changes were requested' in agent._approval_reason(draft, 'image')


def test_legacy_publish_commands_cannot_bypass_review(tmp_path):
    agent, _ = setup_agent(tmp_path)
    with pytest.raises(RuntimeError, match='local review dashboard'):
        agent.publish_staged()
    assert agent.publish_featured_dashboard(dry_run=False).status == 'awaiting_approval'
    assert not agent.linkedin.mock_calls


def test_stale_browser_cannot_approve_new_preview(tmp_path, monkeypatch):
    store = ReviewStore(tmp_path)
    monkeypatch.setattr(store, 'ensure_publisher_idle', lambda: None)
    monkeypatch.setattr(store, 'snapshot', lambda: {'image_ready': True, 'checks': [{'ok': True}],
                                                  'draft_sha256': 'current', 'asset_sha256': 'image'})
    writer = Mock()
    monkeypatch.setattr(store, 'write_state', writer)
    with pytest.raises(ValueError, match='preview changed'):
        store.approve({'draft_sha256': 'old', 'asset_sha256': 'image'})
    writer.assert_not_called()


def test_review_cannot_race_running_publisher(tmp_path, monkeypatch):
    store = ReviewStore(tmp_path)
    monkeypatch.setattr(store, 'command', lambda *args: [{'status': 'in_progress'}])
    with pytest.raises(ValueError, match='publisher is preparing'):
        store.ensure_publisher_idle()


def test_popup_only_for_complete_unapproved_version():
    from linkedin_ai_agent.review_server import popup_key
    state = {'image_ready': True, 'approved': False, 'checks': [{'ok': True}],
             'draft_sha256': 'draft', 'asset_sha256': 'image', 'feedback': None}
    key = popup_key(state)
    assert key
    assert popup_key(state) == key
    state['asset_sha256'] = 'new-image'
    assert popup_key(state) != key
    state['approved'] = True
    assert popup_key(state) is None
    state['approved'] = False
    state['image_ready'] = False
    assert popup_key(state) is None


def test_mixed_mode_alternates_and_can_use_fresh_research(tmp_path, monkeypatch):
    agent, draft = setup_agent(tmp_path)
    agent.config.content_mode = 'mixed'
    agent.history.append({'category': 'portfolio', 'created_at': '2026-01-01T00:00:00Z', 'topic': 'Old build'})
    actual = LinkedInAIAgent._select_draft
    calls = []
    def select(self):
        if self.config.content_mode == 'mixed':
            return actual(self)
        calls.append(self.config.content_mode)
        return trend('Fresh research'), draft, [{'url': 'https://example.com/source'}]
    monkeypatch.setattr(LinkedInAIAgent, '_select_draft', select)
    result = actual(agent)
    assert calls == ['researched']
    assert result[2]
