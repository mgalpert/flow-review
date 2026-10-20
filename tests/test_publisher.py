import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('publisher', ROOT / 'skills/flow-review-canvas/scripts/serve_canvas.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherTests(unittest.TestCase):
    def created(self):
        return {'slug': 'review-example', 'siteUrl': 'https://review-example.here.now/',
                'claimUrl': 'https://here.now/c/private-owner-token', 'expiresAt': '2026-10-22T00:00:00Z',
                'upload': {'versionId': 'version-1', 'uploads': [{'path': 'index.html', 'method': 'PUT',
                           'url': 'https://account.r2.cloudflarestorage.com/bucket/index.html?signature=example'}]}}

    def final(self):
        return {'success': True, 'siteUrl': 'https://review-example.here.now/',
                'publishStatus': {'state': 'live', 'expiresAt': '2026-10-22T00:00:00Z'}}

    def test_publish_uploads_exact_utf8_snapshot_and_requires_final_live_confirmation(self):
        calls = []
        def send(url, data, **kwargs):
            calls.append((url, data, kwargs))
            return self.created() if len(calls) == 1 else self.final() if len(calls) == 3 else None
        source = '<!doctype html><p>Notes: café; comments: 你好</p>'
        result = publisher.publish_html(source, 'My canvas', send)
        self.assertEqual(json.loads(calls[0][1])['files'][0]['size'], len(source.encode()))
        self.assertEqual(calls[1][1], source.encode())
        self.assertEqual(calls[1][2]['method'], 'PUT')
        self.assertEqual(calls[2][0], publisher.API + '/review-example/finalize')
        self.assertEqual(json.loads(calls[2][1]), {'versionId': 'version-1'})
        self.assertEqual(result['claimUrl'], 'https://here.now/c/private-owner-token')
        self.assertEqual(result['siteUrl'], 'https://review-example.here.now/')

    def test_failed_upload_keeps_claim_link_and_does_not_finalize(self):
        calls = []
        def send(url, _data, **_kwargs):
            calls.append(url)
            if len(calls) == 1:
                return self.created()
            raise publisher.PublishError('Upload failed')
        with self.assertRaises(publisher.PublishError) as failure:
            publisher.publish_html('<!doctype html>', 'Review', send)
        self.assertEqual(len(calls), 2)
        self.assertEqual(failure.exception.claim_url, 'https://here.now/c/private-owner-token')

    def test_unexpected_upload_destinations_and_unconfirmed_finalization_are_refused(self):
        for bad in ['http://127.0.0.1/private', 'https://account.r2.cloudflarestorage.com.evil.example/upload']:
            created = self.created(); created['upload']['uploads'][0]['url'] = bad
            calls = []
            def send(url, _data, **_kwargs):
                calls.append(url)
                return created
            with self.assertRaises(publisher.PublishError):
                publisher.publish_html('<!doctype html>', 'Review', send)
            self.assertEqual(calls, [publisher.API])
        for final in [{'success': True}, {'success': False, 'siteUrl': 'https://review-example.here.now/'},
                      {'success': True, 'siteUrl': 'https://review-example.here.now/', 'publishStatus': {'state': 'pending'}}]:
            results = iter([self.created(), None, final])
            with self.assertRaises(publisher.PublishError):
                publisher.publish_html('<!doctype html>', 'Review', lambda *_args, **_kwargs: next(results))


class PreviewServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.canvas = Path(self.temp.name) / 'review.html'
        self.canvas.write_text('<!doctype html><html><head></head><body>Local canvas</body></html>')
        self.published = []
        def publish(source, title):
            self.published.append((source, title))
            return {'siteUrl': 'https://review-example.here.now/'}
        self.server = publisher.make_server(self.canvas, publish=publish)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        with urlopen(self.origin) as response:
            self.source = response.read().decode()
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.token = json.loads(self.source.split('id="publisher-config">')[1].split('</script>')[0])['token']

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def post(self, headers=None, body=None):
        values = {'Content-Type': 'application/json', 'Origin': self.origin, 'X-Flow-Review-Token': self.token}
        values.update(headers or {})
        return urlopen(Request(self.origin + '/__flow_review/publish',
                              data=json.dumps(body or {'html': '<!doctype html><p>Feedback</p>', 'title': 'Review'}).encode(), headers=values))

    def test_explicit_same_origin_request_publishes_the_supplied_snapshot(self):
        self.assertEqual(self.published, [])
        with self.post() as response:
            self.assertEqual(json.load(response)['siteUrl'], 'https://review-example.here.now/')
        self.assertEqual(self.published, [('<!doctype html><p>Feedback</p>', 'Review')])

    def test_other_websites_invalid_tokens_and_rebinding_hosts_cannot_publish(self):
        for headers in [{'Origin': 'https://other.example'}, {'X-Flow-Review-Token': 'wrong'}, {'Host': 'other.example'}]:
            with self.assertRaises(HTTPError) as failure:
                self.post(headers)
            self.assertEqual(failure.exception.code, 403)
            failure.exception.close()
        self.assertEqual(self.published, [])

    def test_only_the_selected_canvas_is_served_and_invalid_payloads_do_not_publish(self):
        for path in ['/../review.html', '/.herenow/credentials', '/anything.html']:
            with self.assertRaises(HTTPError) as failure:
                urlopen(self.origin + path)
            self.assertEqual(failure.exception.code, 404)
            failure.exception.close()
        with self.assertRaises(HTTPError) as failure:
            self.post(body={'html': 'not a canvas', 'title': 'Review'})
        self.assertEqual(failure.exception.code, 400)
        failure.exception.close()
        self.assertEqual(self.published, [])


if __name__ == '__main__':
    unittest.main()
