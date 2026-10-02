import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from linkedin_ai_agent.codex_visuals import draft_sha256, reviewed_visual
from linkedin_ai_agent.history import atomic_json
from linkedin_ai_agent.validators import validate_visual
from tests.test_approval import setup_agent
from tests.test_ranking import trend


def screenshot_fixture(tmp_path):
    agent, draft = setup_agent(tmp_path)
    agent.config.visual_provider = 'codex_manual'
    draft.category = 'portfolio'
    draft.visual_style = 'project_screenshot'
    draft.primary_source_url = 'https://github.com/example/dashboard'
    draft.alt_text = 'Original dashboard screenshot, with demonstration data.'
    asset = agent._codex_manual_visual_path(draft)
    asset.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (1440, 1100), 'white').save(asset)
    data = asset.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    review = {
        'provider': 'project_screenshot', 'review_status': 'passed',
        'topic': draft.topic, 'draft_sha256': draft_sha256(draft), 'asset_sha256': digest,
        'reviewed_at': '2026-09-29T22:00:00Z', 'review_notes': ['Inspected fixture.'],
        'alt_text': draft.alt_text, 'capture_method': 'repository_asset',
        'source_repository': draft.primary_source_url,
        'source_url': draft.primary_source_url + '/blob/main/assets/dashboard.png',
        'source_sha256': digest,
        'source_blob_sha': hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest(),
    }
    asset.with_suffix('.json').write_text(json.dumps(review))
    return agent, draft, asset, review


def test_original_screenshot_keeps_its_dimensions_and_truthful_provider(tmp_path):
    agent, draft, asset, review = screenshot_fixture(tmp_path)
    visual = reviewed_visual(draft, asset)
    assert (visual.width, visual.height) == (1440, 1100)
    assert asset.name.startswith('project_screenshot_')
    assert 'prompt' not in review
    # A generated image cannot use the screenshot size exception.
    with pytest.raises(ValueError):
        validate_visual(asset, draft.alt_text, allow_landscape=True)


@pytest.mark.parametrize('field,value', [
    ('source_repository', 'https://github.com/other/project'),
    ('source_url', 'https://example.org/fake.png'),
    ('capture_method', 'generated'),
    ('source_sha256', 'wrong'),
    ('source_blob_sha', 'wrong'),
    ('asset_sha256', 'wrong'),
    ('draft_sha256', 'wrong'),
    ('review_status', 'failed'),
    ('review_notes', []),
    ('provider', 'codex_imagegen'),
])
def test_screenshot_rejects_missing_or_mismatched_provenance(tmp_path, field, value):
    _, draft, asset, review = screenshot_fixture(tmp_path)
    review[field] = value
    asset.with_suffix('.json').write_text(json.dumps(review))
    with pytest.raises(RuntimeError):
        reviewed_visual(draft, asset)


def test_screenshot_rejects_edited_bytes_even_with_updated_final_digest(tmp_path):
    _, draft, asset, review = screenshot_fixture(tmp_path)
    Image.new('RGB', (1440, 1100), 'blue').save(asset)
    review['asset_sha256'] = hashlib.sha256(asset.read_bytes()).hexdigest()
    asset.with_suffix('.json').write_text(json.dumps(review))
    with pytest.raises(RuntimeError, match='unchanged original'):
        reviewed_visual(draft, asset)


def test_screenshot_dry_run_reports_source_and_still_requires_approval(tmp_path):
    agent, draft, asset, review = screenshot_fixture(tmp_path)
    atomic_json(agent.config.state_dir / 'pending_image_post.json', {
        'draft': asdict(draft), 'candidate': asdict(trend(draft.topic)), 'citations': [],
    })
    agent.linkedin = Mock()
    result = agent.run(dry_run=True)
    assert result.status == 'dry_run_ok'
    report = json.loads(Path(result.report_path).read_text())
    assert report['visual_generation']['provider'] == 'project_screenshot'
    assert report['visual_generation']['review']['source_sha256'] == review['source_sha256']
    assert agent.run(dry_run=False).status == 'awaiting_approval'
    assert not agent.linkedin.mock_calls


def test_previous_image_approval_does_not_approve_screenshot(tmp_path):
    agent, draft, asset, review = screenshot_fixture(tmp_path)
    atomic_json(agent.config.state_dir / 'approved_post.json', {
        'draft_sha256': draft_sha256(draft), 'asset_sha256': 'previous-generated-image',
        'approved_at': '2026-09-29T21:00:00Z', 'approved_by': 'owner_local_review',
    })
    assert agent._approval_reason(draft, review['asset_sha256'])


def running_app_fixture(tmp_path):
    agent, draft, asset, review = screenshot_fixture(tmp_path)
    commit = 'a' * 40
    review.update({
        'capture_method': 'running_app',
        'source_commit_sha': commit,
        'source_url': draft.primary_source_url + '/commit/' + commit,
        'source_worktree_clean': True,
        'capture_url': 'http://127.0.0.1:8511/',
        'captured_at': '2026-10-02T05:00:00Z',
    })
    del review['source_blob_sha']
    asset.with_suffix('.json').write_text(json.dumps(review))
    return agent, draft, asset, review


def test_running_app_screenshot_keeps_original_bytes_and_needs_owner_approval(tmp_path):
    agent, draft, asset, review = running_app_fixture(tmp_path)
    before = asset.read_bytes()
    visual = reviewed_visual(draft, asset)
    assert (visual.width, visual.height) == (1440, 1100)
    assert asset.read_bytes() == before
    assert agent._approval_reason(draft, review['asset_sha256'])


@pytest.mark.parametrize('field,value', [
    ('source_commit_sha', 'main'),
    ('source_url', 'https://github.com/other/project/commit/' + 'a' * 40),
    ('source_worktree_clean', False),
    ('source_worktree_clean', 'true'),
    ('captured_at', ''),
    ('capture_url', ''),
    ('capture_url', 'file:///tmp/mockup.html'),
    ('capture_url', 'http://example.com/'),
    ('capture_url', 'https://secret@example.com/'),
    ('source_sha256', 'wrong'),
    ('draft_sha256', 'wrong'),
])
def test_running_app_capture_rejects_incomplete_or_changed_provenance(tmp_path, field, value):
    _, draft, asset, review = running_app_fixture(tmp_path)
    review[field] = value
    asset.with_suffix('.json').write_text(json.dumps(review))
    with pytest.raises(RuntimeError):
        reviewed_visual(draft, asset)
