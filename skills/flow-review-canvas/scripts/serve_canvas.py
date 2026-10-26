#!/usr/bin/env python3
"""Serve one canvas on loopback with explicit here.now snapshot publishing."""
import argparse
import hmac
import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

API = 'https://here.now/api/v1/publish'
CLIENT = 'flow-review/canvas'
MAX_BYTES = 64 * 1024 * 1024


class PublishError(Exception):
    def __init__(self, message, claim_url=None, status=None):
        super().__init__(message)
        self.claim_url = claim_url
        self.status = status


def request(url, data, method='POST', content_type='application/json', api_key=None):
    headers = {'Content-Type': content_type}
    if urlsplit(url).hostname == 'here.now':
        headers['X-HereNow-Client'] = CLIENT
    outgoing = Request(url, data=data, headers=headers, method=method)
    if api_key and urlsplit(url).hostname == 'here.now':
        # urllib must not forward a bearer key if the API redirects elsewhere.
        outgoing.add_unredirected_header('Authorization', f'Bearer {api_key}')
    try:
        with urlopen(outgoing, timeout=30) as response:
            body = response.read(1024 * 1024)
            return json.loads(body) if content_type == 'application/json' else None
    except HTTPError as exc:
        exc.close()
        raise PublishError(f'here.now returned HTTP {exc.code}. Check that the link still exists and its owner credentials are current. Your local review is unchanged.', status=exc.code) from exc
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        raise PublishError('Could not finish publishing to here.now. Your local review is unchanged.') from exc


def load_api_key():
    key = os.environ.get('HERENOW_API_KEY', '').strip()
    if not key:
        try:
            key = (Path.home() / '.herenow/credentials').read_text(encoding='utf-8').strip()
        except OSError:
            pass
    return key or None


def claim_token(owner_url, slug):
    if not isinstance(owner_url, str):
        raise ValueError('Invalid owner link')
    claim = urlsplit(owner_url)
    if claim.scheme != 'https' or claim.netloc != 'here.now' or claim.fragment:
        raise ValueError('Invalid owner link')
    if re.fullmatch(r'/c/[A-Za-z0-9_-]+', claim.path) and not claim.query:
        return claim.path[3:]
    query = parse_qs(claim.query)
    if claim.path == '/claim' and query.get('slug') == [slug] and len(query.get('token', [])) == 1:
        token = query['token'][0]
        if re.fullmatch(r'[A-Za-z0-9_-]+', token):
            return token
    raise ValueError('Invalid owner link')


def validate_publication(publication):
    try:
        site_url = publication['siteUrl']
        match = re.fullmatch(r'https://([a-z0-9]+(?:-[a-z0-9]+)*)\.here\.now/', site_url)
        if not match:
            raise ValueError('Invalid public URL')
        slug = match[1]
        owner_url = publication.get('claimUrl')
        token = claim_token(owner_url, slug) if owner_url is not None else None
        return slug, site_url, owner_url, token
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PublishError('Choose a valid existing here.now publication.') from exc


def publish_html(source, title, send=request, publication=None):
    content = source.encode('utf-8')
    claim_url = None
    expected_slug = None
    token = None
    api_key = None
    if publication is not None:
        expected_slug, _, claim_url, token = validate_publication(publication)
        if not token:
            api_key = load_api_key()
            if not api_key:
                raise PublishError('The owner link or a local here.now API key is required to update this publication.', claim_url)
    payload = {
        'files': [{'path': 'index.html', 'size': len(content), 'contentType': 'text/html; charset=utf-8'}],
        'displayName': title[:80],
    }
    if token:
        payload['claimToken'] = token
    endpoint = f'{API}/{expected_slug}' if expected_slug else API
    options = {'method': 'PUT'} if expected_slug else {}
    if api_key:
        options['api_key'] = api_key
    try:
        try:
            created = send(endpoint, json.dumps(payload).encode(), **options)
        except PublishError as exc:
            # A previously anonymous link may have been claimed since its last update.
            if not token or exc.status not in (401, 403):
                raise
            api_key = load_api_key()
            if not api_key:
                raise
            payload.pop('claimToken')
            created = send(endpoint, json.dumps(payload).encode(), method='PUT', api_key=api_key)
        slug = created['slug']
        if not isinstance(slug, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug) or (expected_slug and slug != expected_slug):
            raise ValueError('Invalid site name')
        site_url = f'https://{slug}.here.now/'
        if created['siteUrl'] != site_url:
            raise ValueError('Invalid public URL')
        if claim_url is None and (not expected_slug or created.get('claimUrl')):
            owner_url = created['claimUrl']
            claim_token(owner_url, slug)
            claim_url = owner_url
        uploads = created['upload']['uploads']
        if len(uploads) != 1 or uploads[0]['path'] != 'index.html' or uploads[0]['method'] != 'PUT':
            raise ValueError('Invalid upload')
        destination = urlsplit(uploads[0]['url'])
        if destination.scheme != 'https' or not (destination.hostname or '').endswith('.r2.cloudflarestorage.com') or destination.port not in (None, 443) or destination.username or destination.password:
            raise ValueError('Invalid storage destination')
        send(uploads[0]['url'], content, method='PUT', content_type='text/html; charset=utf-8')
        final_options = {'api_key': api_key} if api_key else {}
        final = send(f'{API}/{slug}/finalize', json.dumps({'versionId': created['upload']['versionId']}).encode(), **final_options)
        status = final.get('publishStatus', {})
        if final.get('success') is not True or final.get('siteUrl') != site_url or status.get('state') != 'live':
            raise ValueError('Publication was not confirmed')
        result = {'siteUrl': site_url, 'expiresAt': status.get('expiresAt') or created.get('expiresAt')}
        if claim_url:
            result['claimUrl'] = claim_url
        return result
    except PublishError as exc:
        raise PublishError(str(exc), claim_url, exc.status) from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise PublishError('here.now did not confirm a published link. Your local review is unchanged.', claim_url) from exc


def remove_publication(publication, send=request):
    slug, site_url, owner_url, token = validate_publication(publication)
    api_key = load_api_key()
    if api_key:
        try:
            deleted = send(f'{API}/{slug}', None, method='DELETE', api_key=api_key)
            if not isinstance(deleted, dict) or deleted.get('success') is not True:
                raise PublishError('here.now did not confirm deletion. Your publication details are unchanged.', owner_url)
            return {'siteUrl': site_url, 'mode': 'deleted', 'removed': True}
        except PublishError as exc:
            if exc.status not in (401, 403, 405) or not token:
                raise PublishError(str(exc), owner_url, exc.status) from exc
    if not token:
        raise PublishError('The owner link or a local here.now API key is required to remove this publication.', owner_url)
    blank = '<!doctype html><html><head><meta charset="utf-8"><title></title></head><body></body></html>'
    result = publish_html(blank, 'Removed review', send, publication=publication)
    return {**result, 'mode': 'blanked', 'removed': True}


def make_server(canvas, port=0, publish=publish_html, remove=remove_publication):
    canvas = Path(canvas).resolve()
    # Fail before starting the server, rather than serving an empty/missing review.
    canvas.read_text(encoding='utf-8')
    token = secrets.token_urlsafe(32)
    publishing = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, body, content_type='application/json'):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            for key, value in {'Content-Type': content_type, 'Content-Length': str(len(data)),
                               'Cache-Control': 'no-store', 'X-Frame-Options': 'DENY',
                               'Referrer-Policy': 'no-referrer'}.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.valid_host():
                self.respond(403, {'error': 'Invalid host'})
                return
            if self.path not in ('/', '/canvas.html'):
                self.respond(404, {'error': 'Not found'})
                return
            try:
                config = json.dumps({'token': token}).replace('<', '\\u003c')
                source = canvas.read_text(encoding='utf-8')
                source = source.replace('</head>', f'<script type="application/json" id="publisher-config">{config}</script></head>', 1)
                self.respond(200, source, 'text/html; charset=utf-8')
            except OSError:
                self.respond(404, {'error': 'Canvas is unavailable'})

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.valid_host() or self.headers.get('Origin') != origin or not hmac.compare_digest(self.headers.get('X-Flow-Review-Token', ''), token):
                self.respond(403, {'error': 'Open the canvas in this publishing preview first.'})
                return
            if self.path not in ('/__flow_review/publish', '/__flow_review/remove'):
                self.respond(404, {'error': 'Not found'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_BYTES or self.headers.get_content_type() != 'application/json':
                    self.respond(413, {'error': 'Publish a canvas smaller than 64 MB.'})
                    return
                body = json.loads(self.rfile.read(length))
                publication = body.get('publication')
                if 'publication' in body:
                    validate_publication(publication)
                if self.path == '/__flow_review/remove':
                    if publication is None:
                        raise ValueError('Missing publication')
                else:
                    source, title = body['html'], body['title']
                    if not isinstance(source, str) or not isinstance(title, str) or '<!doctype html>' not in source[:100].lower():
                        raise ValueError('Invalid canvas')
            except (ValueError, KeyError, TypeError, UnicodeError, AttributeError, PublishError):
                self.respond(400, {'error': 'Choose a valid Flow Review canvas.'})
                return
            if not publishing.acquire(blocking=False):
                self.respond(409, {'error': 'A canvas is already publishing. Wait for its result.'})
                return
            try:
                if self.path == '/__flow_review/remove':
                    result = remove(publication)
                elif publication is not None:
                    result = publish(source, title, publication=publication)
                else:
                    result = publish(source, title)
                self.respond(200, result)
            except PublishError as exc:
                self.respond(502, {'error': str(exc), 'claimUrl': exc.claim_url, 'upstreamStatus': exc.status})
            finally:
                publishing.release()

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def serve(canvas, port=0):
    with make_server(canvas, port) as server:
        print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}/', 'publishing': 'here.now'}), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('canvas', type=Path)
    parser.add_argument('--port', type=int, default=0, help='Loopback port; default chooses an available port')
    args = parser.parse_args()
    try:
        serve(args.canvas, args.port)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
