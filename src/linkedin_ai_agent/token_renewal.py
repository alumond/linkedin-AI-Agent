"""Renew the existing member token without printing or persisting credentials."""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from .config import load_config
from .history import atomic_json

ROOT = Path(__file__).resolve().parents[2]
REPO = 'alumond/linkedin-AI-Agent'
SCOPES = {'openid', 'profile', 'w_member_social'}


def verified_metadata(inspection, identity, expected_owner, client_id, now=None):
    now = now or datetime.now(timezone.utc)
    scopes = set(filter(None, re.split(r'[,\s]+', inspection.get('scope', ''))))
    if not inspection.get('active') or inspection.get('client_id') != client_id:
        raise ValueError('LinkedIn did not validate this token for the existing app.')
    if not SCOPES.issubset(scopes):
        raise ValueError('The renewed token is missing a required existing permission.')
    if f"urn:li:person:{identity.get('sub', '')}" != expected_owner:
        raise ValueError('The authorized LinkedIn member does not match the configured publisher.')
    expiry = datetime.fromtimestamp(int(inspection['expires_at']), timezone.utc)
    if (expiry - now).total_seconds() < 7 * 86400:
        raise ValueError('LinkedIn did not issue a sufficiently extended token lifetime.')
    return {'expires_at': expiry.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'verified_at': now.isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'scopes': sorted(scopes), 'owner_urn': expected_owner, 'status': 'verified'}


class Renewal:
    def __init__(self, client_id, port=8080):
        self.client_id, self.port = client_id, port
        self.redirect = f'http://127.0.0.1:{port}/callback'
        self.csrf = secrets.token_urlsafe(32)
        self.oauth_state = secrets.token_urlsafe(32)
        self.client_secret = self.token = None
        self.metadata = None
        self.finished = False
        self.message = 'Ready to renew LinkedIn access.'
        self.gh = shutil.which('gh') or str(ROOT / '.tools/gh_2.94.0_macOS_arm64/bin/gh')
        self.config = load_config(ROOT / 'config/agent.yaml')
        self.callback_used = False

    def command(self, args, input_text=None, missing_ok=False):
        result = subprocess.run([self.gh, *args], input=input_text, text=True, capture_output=True,
                                cwd=ROOT, timeout=90)
        if result.returncode:
            if missing_ok and 'HTTP 404' in result.stderr:
                return 'null'
            raise RuntimeError('GitHub update failed. No credentials were printed; retry the save from this page.')
        return result.stdout

    def auth_url(self):
        return 'https://www.linkedin.com/oauth/v2/authorization?' + urlencode({
            'response_type':'code', 'client_id':self.client_id, 'redirect_uri':self.redirect,
            'state':self.oauth_state, 'scope':'w_member_social openid profile'})

    def exchange(self, code):
        response = requests.post('https://www.linkedin.com/oauth/v2/accessToken', data={
            'grant_type':'authorization_code', 'code':code, 'redirect_uri':self.redirect,
            'client_id':self.client_id, 'client_secret':self.client_secret}, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f'LinkedIn token exchange returned HTTP {response.status_code}. Restart renewal.')
        token = response.json().get('access_token')
        if not token:
            raise RuntimeError('LinkedIn returned no access token.')
        inspection = requests.post('https://www.linkedin.com/oauth/v2/introspectToken', data={
            'token':token, 'client_id':self.client_id, 'client_secret':self.client_secret}, timeout=30)
        identity = requests.get('https://api.linkedin.com/v2/userinfo',
                                headers={'Authorization':f'Bearer {token}'}, timeout=30)
        if inspection.status_code != 200 or identity.status_code != 200:
            raise RuntimeError('The new token failed LinkedIn verification. The saved publisher token was not replaced.')
        metadata = verified_metadata(inspection.json(), identity.json(), self.config.linkedin_owner_urn, self.client_id)
        self.token, self.metadata = token, metadata
        self.client_secret = None
        self.deploy()

    def deploy(self):
        if not self.token or not self.metadata:
            raise RuntimeError('Complete LinkedIn authorization first.')
        self.command(['secret','set','LINKEDIN_ACCESS_TOKEN','--repo',REPO], self.token)
        self.command(['variable','set','LINKEDIN_TOKEN_EXPIRES_AT','--repo',REPO,'--body',self.metadata['expires_at']])
        remote = json.loads(self.command(['api',f'repos/{REPO}/contents/.state/linkedin_token_metadata.json?ref=automation-state'], missing_ok=True))
        payload = {'message':'Renew verified LinkedIn token expiry', 'branch':'automation-state',
                   'content':base64.b64encode(json.dumps(self.metadata,indent=2).encode()).decode()}
        if remote:
            payload['sha'] = remote['sha']
        self.command(['api','--method','PUT',f'repos/{REPO}/contents/.state/linkedin_token_metadata.json','--input','-'],json.dumps(payload))
        expiry = self.command(['variable','get','LINKEDIN_TOKEN_EXPIRES_AT','--repo',REPO]).strip()
        if expiry != self.metadata['expires_at']:
            raise RuntimeError('GitHub expiry verification failed. Retry saving the verified token.')
        record = json.loads(self.command(['api',f'repos/{REPO}/contents/.state/linkedin_token_metadata.json?ref=automation-state']))
        if json.loads(base64.b64decode(record['content'])) != self.metadata:
            raise RuntimeError('Publisher metadata verification failed. Retry saving the verified token.')
        atomic_json(ROOT / self.config.state_dir / 'linkedin_token_metadata.json', self.metadata)
        atomic_json(ROOT / '.state/token_renewal_result.json', {'status':'renewed',**self.metadata,'published':False})
        self.token = self.client_secret = None
        self.message = f"LinkedIn access renewed and verified. New expiry: {expiry}. GitHub secret and publisher metadata updated. Nothing was published."
        self.finished = True
        print(json.dumps({'status':'renewed',**self.metadata,'published':False}),flush=True)


def serve(client_id, port=8080):
    renewal = Renewal(client_id, port)
    stop = False
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{port}',f'localhost:{port}'}
        def respond(self, code, body='', location=None):
            data=body.encode()
            self.send_response(code)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','same-origin')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            if location:self.send_header('Location',location)
            self.send_header('Content-Length',str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def page(self):
            status=html.escape(renewal.message)
            if renewal.finished:
                content=f'<h1>LinkedIn renewed</h1><p>{status}</p>'
            elif renewal.token:
                content=f'<h1>Finish saving the verified token</h1><p>{status}</p><form method="post" action="/retry"><input type="hidden" name="csrf" value="{renewal.csrf}"><button>Retry save</button></form>'
            elif renewal.client_secret and not renewal.callback_used:
                content=f'<h1>Continue on LinkedIn</h1><p>The existing app credential is ready. Authorize the same posting and profile permissions on LinkedIn.</p><p><a href="{html.escape(renewal.auth_url(), quote=True)}" rel="noreferrer">Authorize on LinkedIn</a></p>'
            else:
                content=f'''<h1>Renew LinkedIn access</h1><p>Renew the existing Agent app for this publisher. Credentials stay in memory; the new token is saved directly to the existing GitHub secret.</p><p>{status}</p><form method="post" action="/start"><input type="hidden" name="csrf" value="{renewal.csrf}"><label>Client ID<input readonly value="{html.escape(client_id)}"></label><label for="client_secret">Existing client secret</label><input id="client_secret" name="client_secret" type="password" autocomplete="off" required><button>Continue to LinkedIn</button></form>'''
            return '<!doctype html><title>LinkedIn token renewal</title><style>body{font:17px system-ui;max-width:650px;margin:70px auto;padding:30px;background:#f6f8f5;color:#183d32}label,input,button{display:block;margin:18px 0}input{font:inherit;width:90%;padding:12px}button{font:inherit;padding:12px 20px;background:#195c47;color:white;border:0;border-radius:6px}p{line-height:1.6}</style>'+content
        def do_GET(self):
            nonlocal stop
            if not self.valid_host(): return self.respond(403,'Local access only')
            url=urlparse(self.path)
            if url.path=='/callback':
                args=parse_qs(url.query)
                if renewal.callback_used or not secrets.compare_digest(args.get('state',[''])[0],renewal.oauth_state):
                    return self.respond(400,'Invalid or already used authorization state.')
                renewal.callback_used=True
                if args.get('error') or not args.get('code'):
                    renewal.message='LinkedIn authorization did not complete. Restart renewal.'
                else:
                    try:renewal.exchange(args['code'][0])
                    except (RuntimeError,ValueError) as exc:renewal.message=str(exc)
                    except Exception:renewal.message='Renewal could not finish. Credentials were not printed. Restart or retry the save.'
                return self.respond(303,location='/complete')
            if url.path in {'/','/complete'}:
                self.respond(200,self.page())
                if renewal.finished:stop=True
                return
            return self.respond(404,'Not found')
        def do_POST(self):
            if not self.valid_host():return self.respond(403,'Local access only')
            origin=self.headers.get('Origin')
            # A privacy policy can serialize same-origin navigation origins as null.
            # The independent, unguessable form nonce remains mandatory below.
            if origin and origin not in {'null',f'http://127.0.0.1:{port}',f'http://localhost:{port}'}:
                return self.respond(403,'Use the local renewal form.')
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<8192:return self.respond(400,'Invalid request size.')
            args=parse_qs(self.rfile.read(length).decode())
            if not secrets.compare_digest(args.get('csrf',[''])[0],renewal.csrf):return self.respond(403,'Refresh the renewal form.')
            if self.path=='/start' and not renewal.callback_used:
                secret=args.get('client_secret',[''])[0].strip()
                if not secret:return self.respond(400,'Enter the existing client secret.')
                renewal.client_secret=secret
                # Keep the credential form same-origin. A separate navigation
                # link avoids browsers blocking OAuth under form-action self.
                return self.respond(303,location='/')
            if self.path=='/retry' and renewal.token:
                try:renewal.deploy()
                except RuntimeError as exc:renewal.message=str(exc)
                except Exception:renewal.message='Save failed. The verified token remains in memory for another retry.'
                return self.respond(303,location='/complete')
            return self.respond(400,'Start a new renewal session.')
    server=HTTPServer(('127.0.0.1',port),Handler)
    server.timeout=1
    print(f'LinkedIn renewal form: http://127.0.0.1:{port}',flush=True)
    deadline=time.monotonic()+1800
    try:
        while not stop and time.monotonic()<deadline:server.handle_request()
    finally:
        renewal.client_secret=renewal.token=None
        server.server_close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--client-id',required=True)
    parser.add_argument('--port',type=int,default=8080)
    args=parser.parse_args()
    serve(args.client_id,args.port)
