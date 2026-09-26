"""Loopback-only review UI. GitHub remains the publisher's source of truth."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

from .agent import LinkedInAIAgent
from .codex_visuals import draft_sha256, reviewed_visual
from .config import load_config
from .models import draft_from_dict, post_commentary
from .validators import validate_draft

ROOT = Path(__file__).resolve().parents[2]
REPO = 'alumond/linkedin-AI-Agent'


class ReviewStore:
    def __init__(self, root: Path = ROOT):
        self.root = root
        self.cache = root / '.review_cache'
        self.cache.mkdir(exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.gh = shutil.which('gh') or str(root / '.tools/gh_2.94.0_macOS_arm64/bin/gh')
        self.last_image = None
        self.lock = threading.RLock()

    def command(self, args: list[str], payload: dict | None = None):
        result = subprocess.run([self.gh, *args], input=json.dumps(payload) if payload is not None else None,
                                text=True, capture_output=True, timeout=90, cwd=self.root)
        if result.returncode:
            # Do not reflect raw subprocess output or credentials into the browser.
            raise RuntimeError('GitHub could not complete the request. Check connectivity and gh authentication.')
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def read_file(self, path: str, branch: str, optional: bool = False):
        result = subprocess.run([self.gh, 'api', f'repos/{REPO}/contents/{quote(path, safe="/")}?ref={branch}'],
                                text=True, capture_output=True, timeout=60, cwd=self.root)
        if result.returncode:
            if optional and '404' in result.stderr:
                return None, None
            raise RuntimeError('Unable to read the current GitHub state. Nothing has been approved or published.')
        envelope = json.loads(result.stdout)
        if envelope.get('encoding') == 'none':
            # GitHub Contents omits large files. The blob endpoint transports
            # PNG bytes as base64 JSON, avoiding CLI binary decoding failures.
            blob_cache = self.cache / 'blobs' / envelope['sha']
            if blob_cache.exists():
                return blob_cache.read_bytes(), envelope['sha']
            blob = self.command(['api', f'repos/{REPO}/git/blobs/{envelope["sha"]}'])
            data = base64.b64decode(blob['content'])
            actual = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
            if actual != envelope['sha']:
                raise RuntimeError('Image download did not match its GitHub fingerprint.')
            blob_cache.parent.mkdir(exist_ok=True)
            blob_cache.write_bytes(data)
            return data, envelope['sha']
        return base64.b64decode(envelope['content']), envelope['sha']

    def json_file(self, path, branch='automation-state', optional=False):
        data, sha = self.read_file(path, branch, optional)
        return (json.loads(data) if data else None), sha

    def snapshot(self):
        cfg = load_config(self.root / 'config/agent.yaml')
        history, _ = self.json_file('.state/publication_history.json')
        pending, _ = self.json_file('.state/pending_image_post.json', optional=True)
        approval, _ = self.json_file('.state/approved_post.json', optional=True)
        feedback, _ = self.json_file('.state/review_feedback.json', optional=True)
        state = {'token': self.token, 'history_count': len(history), 'history': sorted(history, key=lambda h: h.get('created_at', ''), reverse=True)[:8],
                 'pending': pending, 'approval': approval, 'feedback': feedback,
                 'schedule': 'Weekdays · 09:17 Lagos', 'require_approval': getattr(cfg, 'require_post_approval', False),
                 'image_ready': False, 'checks': [], 'image_url': None}
        self.last_image = None
        if not pending:
            return state
        draft = draft_from_dict(pending['draft'])
        state['draft_sha256'] = draft_sha256(draft)
        state['commentary'] = post_commentary(draft)
        cfg.state_dir = self.cache / 'state'
        cfg.assets_dir = self.cache / 'assets'
        cfg.reports_dir = self.cache / 'reports'
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        cfg.reports_dir.mkdir(parents=True, exist_ok=True)
        (cfg.state_dir / 'publication_history.json').write_text(json.dumps(history))
        # Legacy audit reports contain bodies that early history records omitted.
        for item in history:
            if not item.get('body') and item.get('report_path'):
                target = cfg.reports_dir / Path(item['report_path']).name
                if not target.exists():
                    data, _ = self.read_file(item['report_path'], 'automation-state')
                    target.write_bytes(data)
        agent = LinkedInAIAgent(cfg)
        try:
            agent._ensure_original_draft(draft)
            validation = validate_draft(draft, cfg)
            if not validation.passed:
                raise ValueError('; '.join(validation.reasons))
            state['checks'].append({'ok': True, 'label': 'Original copy and organisation exclusions checked'})
        except Exception as exc:
            state['checks'].append({'ok': False, 'label': str(exc)})
        asset = agent._codex_manual_visual_path(draft)
        remote_asset = 'assets/' + asset.name
        data, _ = self.read_file(remote_asset, 'main', optional=True)
        review, _ = self.json_file(remote_asset[:-4] + '.json', 'main', optional=True)
        if data and review:
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(data)
            asset.with_suffix('.json').write_text(json.dumps(review))
            try:
                reviewed_visual(draft, asset)
                agent._ensure_visual_not_reused(asset, hashlib.sha256(data).hexdigest())
                state['image_ready'] = True
                state['asset_sha256'] = hashlib.sha256(data).hexdigest()
                state['image_url'] = '/api/image?v=' + state['asset_sha256']
                state['review'] = review
                self.last_image = asset
                state['checks'].append({'ok': True, 'label': 'Codex image reviewed and reuse checks passed'})
            except Exception as exc:
                state['checks'].append({'ok': False, 'label': str(exc)})
        else:
            state['checks'].append({'ok': False, 'label': 'Waiting for the Codex image and its review'})
        state['approved'] = bool(approval and approval.get('draft_sha256') == state['draft_sha256']
                                 and approval.get('asset_sha256') == state.get('asset_sha256')
                                 and not agent._approval_reason(draft, state.get('asset_sha256', '')))
        return state

    def write_state(self, path, value):
        _, sha = self.read_file(path, 'automation-state', optional=True)
        payload = {'message': 'Update LinkedIn post review', 'branch': 'automation-state',
                   'content': base64.b64encode(json.dumps(value, indent=2).encode()).decode()}
        if sha:
            payload['sha'] = sha
        return self.command(['api', '--method', 'PUT', f'repos/{REPO}/contents/{path}', '--input', '-'], payload)

    def ensure_publisher_idle(self):
        runs = self.command(['run', 'list', '--repo', REPO, '--workflow', 'weekday-linkedin-post.yml',
                             '--limit', '20', '--json', 'status'])
        if any(run['status'] in {'queued', 'in_progress', 'waiting', 'pending', 'requested'} for run in runs):
            raise ValueError('The publisher is preparing or processing a post. Wait for it to finish, then refresh before reviewing.')

    def approve(self, request):
        from datetime import datetime, timezone
        self.ensure_publisher_idle()
        state = self.snapshot()
        if not state.get('image_ready') or not all(check['ok'] for check in state['checks']):
            raise ValueError('The draft and image must pass their checks before approval.')
        for key in ('draft_sha256', 'asset_sha256'):
            if request.get(key) != state.get(key):
                raise ValueError('The preview changed. Refresh and review the current version.')
        self.write_state('.state/approved_post.json', {
            'draft_sha256': state['draft_sha256'], 'asset_sha256': state['asset_sha256'],
            'approved_at': datetime.now(timezone.utc).isoformat(), 'approved_by': 'owner_local_review',
        })

    def request_changes(self, request):
        from datetime import datetime, timezone
        self.ensure_publisher_idle()
        state = self.snapshot()
        if not state.get('pending') or request.get('draft_sha256') != state.get('draft_sha256'):
            raise ValueError('The preview changed. Refresh before requesting changes.')
        note = str(request.get('note', '')).strip()
        if not note or len(note) > 2000:
            raise ValueError('Enter a specific change request, up to 2,000 characters.')
        self.write_state('.state/review_feedback.json', {
            'draft_sha256': state['draft_sha256'], 'note': note,
            'requested_at': datetime.now(timezone.utc).isoformat(),
        })
        # Approval is revoked even when the same bytes remain on screen.
        self.write_state('.state/approved_post.json', {'status': 'changes_requested'})
        self.command(['workflow', 'run', 'weekday-linkedin-post.yml', '--repo', REPO,
                      '-f', 'mode=prepare', '-f', 'dry_run=true'])


class Handler(BaseHTTPRequestHandler):
    store: ReviewStore

    def log_message(self, *_):
        pass

    def respond(self, code, data, content_type='application/json'):
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
        elif isinstance(data, str):
            data = data.encode()
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def allowed_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed_host():
            return self.respond(403, {'error': 'Local access only.'})
        path = urlparse(self.path).path
        try:
            if path == '/':
                return self.respond(200, (ROOT / 'web/review.html').read_bytes(), 'text/html; charset=utf-8')
            if path == '/api/state':
                with self.store.lock:
                    return self.respond(200, self.store.snapshot())
            if path == '/api/image' and self.store.last_image:
                return self.respond(200, self.store.last_image.read_bytes(), 'image/png')
            return self.respond(404, {'error': 'Not found'})
        except Exception as exc:
            return self.respond(502, {'error': str(exc)})

    def do_POST(self):
        if not self.allowed_host() or self.headers.get('X-Review-Token') != self.store.token:
            return self.respond(403, {'error': 'Refresh the local review page before making changes.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 10000:
                return self.respond(413, {'error': 'Request is too large.'})
            request = json.loads(self.rfile.read(length) or '{}')
            if self.path == '/api/approve':
                with self.store.lock:
                    self.store.approve(request)
                return self.respond(200, {'message': 'Approved for the next scheduled publication.'})
            if self.path == '/api/changes':
                with self.store.lock:
                    self.store.request_changes(request)
                return self.respond(200, {'message': 'Approval removed and revision started. The revised image still needs Codex generation.'})
            if self.path == '/api/prepare':
                self.store.command(['workflow', 'run', 'weekday-linkedin-post.yml', '--repo', REPO,
                                    '-f', 'mode=prepare', '-f', 'dry_run=true'])
                return self.respond(200, {'message': 'Draft preparation started. Refresh after the GitHub run finishes.'})
            return self.respond(404, {'error': 'Not found'})
        except Exception as exc:
            return self.respond(400, {'error': str(exc)})


def popup_key(state):
    if (not state.get('image_ready') or state.get('approved')
            or not state.get('checks') or not all(check['ok'] for check in state['checks'])):
        return None
    if (state.get('feedback') or {}).get('draft_sha256') == state.get('draft_sha256'):
        return None
    return ':'.join([state['draft_sha256'], state['asset_sha256'], datetime.now().date().isoformat()])


def show_approval_popup(port):
    # A native dialog is visible even when browser notifications are disabled.
    # No approval action is possible from the popup itself.
    script = ('display dialog "A new LinkedIn post and Codex image are ready. Review both before approving." '
              'with title "LinkedIn Studio — approval needed" buttons {"Later", "Review post"} '
              'default button "Review post" giving up after 120')
    result = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, text=True, timeout=130)
    if result.returncode == 0 and 'gave up:true' not in result.stdout and 'button returned:Review post' in result.stdout:
        app = Path.home() / 'Applications/LinkedIn Studio.app'
        destination = str(app) if port == 8765 and app.exists() else f'http://127.0.0.1:{port}'
        subprocess.run(['/usr/bin/open', destination], check=False)
    return result.returncode == 0


def watch_approvals(store, port):
    import time
    path = store.cache / 'last_notification.json'
    try:
        last = json.loads(path.read_text()).get('key')
    except (OSError, ValueError):
        last = None
    while True:
        try:
            with store.lock:
                key = popup_key(store.snapshot())
            if key and key != last and show_approval_popup(port):
                last = key
                path.write_text(json.dumps({'key': key}))
        except Exception as exc:
            print(f'Approval notification check: {type(exc).__name__}', flush=True)
        time.sleep(120)


def serve(port=8765):
    Handler.store = ReviewStore()
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    if os.environ.get('LINKEDIN_REVIEW_NOTIFICATIONS', '1') == '1':
        threading.Thread(target=watch_approvals, args=(Handler.store, port), daemon=True).start()
    print(f'LinkedIn Review: http://127.0.0.1:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    serve(int(os.environ.get('LINKEDIN_REVIEW_PORT', '8765')))
