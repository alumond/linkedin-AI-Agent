import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
from PIL import Image

from linkedin_ai_agent.agent import LinkedInAIAgent
from linkedin_ai_agent.codex_visuals import visual_signature
from linkedin_ai_agent.history import PublicationHistory
from linkedin_ai_agent.linkedin_client import LinkedInClient
from linkedin_ai_agent.portfolio import GitHubProjects, excluded_material
from tests.test_agent import FakeGemini
from tests.test_ranking import config, trend


def test_lifetime_history_never_ages_out(tmp_path):
    history = PublicationHistory(tmp_path / 'state')
    history.append({'created_at': '2020-01-01T00:00:00Z', 'topic': 'A reliable data pipeline',
                    'visual_sha256': 'old-image-hash'})
    assert history.is_duplicate('A reliable data pipeline!', 0)
    assert 'old-image-hash' in history.recent_visual_fingerprints(0)


def test_daily_limit_stops_before_any_generation(tmp_path, monkeypatch):
    agent = LinkedInAIAgent(config(tmp_path))
    agent.history.append({'created_at': datetime.now(timezone.utc).isoformat(), 'topic': 'Today',
                          'post_urn': 'urn:li:share:123'})
    monkeypatch.setattr(agent, '_select_draft', lambda: pytest.fail('Must not generate another live post today'))
    assert agent.run(dry_run=False).status == 'already_published'


def test_uncertain_publication_is_not_retried(tmp_path, monkeypatch):
    agent = LinkedInAIAgent(config(tmp_path))
    (agent.config.state_dir / 'publication_attempt.json').write_text(json.dumps({'status': 'publishing'}))
    monkeypatch.setattr(agent, '_select_draft', lambda: pytest.fail('Uncertain post must not be retried'))
    result = agent.run(dry_run=False)
    assert result.status == 'skipped'
    assert 'uncertain outcome' in result.skipped_reason


def test_project_draft_moves_past_duplicate_candidate_and_preserves_handoff(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    cfg.content_mode = 'portfolio'
    cfg.min_post_chars, cfg.max_post_chars = 700, 1300
    monkeypatch.setattr(GitHubProjects, 'collect', lambda *args: [{'name': 'Personal build'}])
    class PortfolioGemini(FakeGemini):
        def portfolio_candidates(self, cfg, projects, history):
            return [trend('Previous post'), trend('Fresh Gemini Trend')]
    agent = LinkedInAIAgent(cfg, gemini=PortfolioGemini())
    agent.history.append({'created_at': datetime.now(timezone.utc).isoformat(), 'topic': 'Previous post'})
    path = agent.prepare_post()
    assert path.exists()
    pending = json.loads((cfg.state_dir / 'pending_image_post.json').read_text())
    assert pending['draft']['topic'] == 'Fresh Gemini Trend'
    assert pending['citations']
    monkeypatch.setattr(agent, '_select_draft', lambda: pytest.fail('Pending draft must be preserved'))
    assert agent.prepare_post() == path


@pytest.mark.parametrize('text', ['StanforteEdge HR Dashboard', 'Stanforte-Edge', 'project-hr-analytics.jpg'])
def test_organisation_material_is_excluded(tmp_path, text):
    cfg = config(tmp_path)
    assert excluded_material(text, cfg.portfolio_excluded_terms)
    agent = LinkedInAIAgent(cfg)
    draft = FakeGemini().generate_post(cfg, trend('Personal project'))
    draft.body += '\n' + text
    with pytest.raises(RuntimeError, match='excluded organisation'):
        agent._ensure_original_draft(draft)


def test_recoloured_image_with_same_composition_is_rejected(tmp_path):
    cfg = config(tmp_path)
    agent = LinkedInAIAgent(cfg)
    asset = tmp_path / 'visual.png'
    image = Image.new('RGB', (64, 64))
    image.putdata([(x * 3, y * 3, 100) for y in range(64) for x in range(64)])
    image.save(asset)
    agent.history.append({'created_at': datetime.now(timezone.utc).isoformat(),
                          'visual_signature': visual_signature(asset)})
    # The bytes differ, but the composition is unchanged.
    image.putdata([(x * 2, y * 2, 50) for y in range(64) for x in range(64)])
    image.save(asset)
    with pytest.raises(RuntimeError, match='visually too similar'):
        agent._ensure_visual_not_reused(asset, agent._visual_sha256(asset))


def test_linkedin_create_post_never_retries_server_error(tmp_path):
    client = LinkedInClient('test-token', config(tmp_path))
    response = Mock(status_code=503)
    response.raise_for_status.side_effect = requests.HTTPError('unavailable')
    draft = FakeGemini().generate_post(client.config, trend('Personal build'))
    with patch('linkedin_ai_agent.linkedin_client.requests.request', return_value=response) as request:
        with pytest.raises(requests.HTTPError):
            client.publish_post(draft, 'urn:li:image:test')
    assert request.call_count == 1
