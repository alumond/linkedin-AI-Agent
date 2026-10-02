from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from linkedin_ai_agent.review_server import ReviewStore, REPO


def review_store():
    store = ReviewStore.__new__(ReviewStore)
    store.ensure_publisher_idle = Mock()
    store.snapshot = Mock(return_value={
        'image_ready': True, 'checks': [{'ok': True}],
        'draft_sha256': 'current-draft', 'asset_sha256': 'current-image',
    })
    store.command = Mock(return_value={})
    store.saved = []
    store.write_state = Mock(side_effect=lambda path, value: store.saved.append((path, deepcopy(value))))
    return store


def test_approval_dispatches_real_publisher_after_persisting_exact_approval():
    store = review_store()

    def dispatched(args, *, expect_json):
        assert expect_json is False
        assert store.saved[0][1]['draft_sha256'] == 'current-draft'
        assert store.saved[0][1]['asset_sha256'] == 'current-image'
        assert args == ['workflow', 'run', 'weekday-linkedin-post.yml', '--repo', REPO,
                        '-f', 'mode=publish', '-f', 'dry_run=false']
        return {}

    store.command.side_effect = dispatched
    store.approve({'draft_sha256': 'current-draft', 'asset_sha256': 'current-image'})
    store.command.assert_called_once()
    assert store.saved[0][1]['publication_status'] == 'queued'


@pytest.mark.parametrize('change', ['image_changed', 'draft_changed', 'failed_check', 'image_missing'])
def test_unreviewed_or_failed_preview_does_not_dispatch(change):
    store = review_store()
    state = store.snapshot.return_value
    request = {'draft_sha256': 'current-draft', 'asset_sha256': 'current-image'}
    if change == 'image_changed':
        request['asset_sha256'] = 'old-image'
    elif change == 'draft_changed':
        request['draft_sha256'] = 'old-draft'
    elif change == 'failed_check':
        state['checks'] = [{'ok': False}]
    else:
        state['image_ready'] = False
    with pytest.raises(ValueError):
        store.approve(request)
    store.write_state.assert_not_called()
    store.command.assert_not_called()


def test_dispatch_failure_preserves_approval_and_allows_a_visible_retry():
    store = review_store()
    store.command.side_effect = RuntimeError('network error')
    request = {'draft_sha256': 'current-draft', 'asset_sha256': 'current-image'}
    with pytest.raises(ValueError, match='Retry publication'):
        store.approve(request)
    assert store.saved[-1][1]['publication_status'] == 'dispatch_failed'
    store.command.side_effect = None
    store.approve(request)
    assert store.saved[-1][1]['publication_status'] == 'queued'


def test_active_publisher_blocks_duplicate_dispatch():
    store = review_store()
    store.ensure_publisher_idle.side_effect = ValueError('Publisher is active')
    with pytest.raises(ValueError, match='active'):
        store.approve({'draft_sha256': 'current-draft', 'asset_sha256': 'current-image'})
    store.write_state.assert_not_called()
    store.command.assert_not_called()


def test_workflow_dispatch_accepts_plain_text_cli_response(tmp_path):
    store = ReviewStore.__new__(ReviewStore)
    store.gh = 'gh'
    store.root = tmp_path
    with patch('linkedin_ai_agent.review_server.subprocess.run', return_value=SimpleNamespace(
            returncode=0, stdout='Created workflow_dispatch event\n', stderr='')):
        assert store.command(['workflow', 'run', 'weekday-linkedin-post.yml'], expect_json=False).strip() == 'Created workflow_dispatch event'
