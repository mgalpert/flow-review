import importlib.util
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
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


class ManagementTests(PublisherTests):
    def publication(self):
        return {'siteUrl': self.created()['siteUrl'], 'claimUrl': self.created()['claimUrl']}

    def sender(self, results, calls):
        results = iter(results)
        def send(url, data, **kwargs):
            calls.append((url, data, kwargs))
            result = next(results)
            if isinstance(result, Exception):
                raise result
            return result
        return send

    def test_update_keeps_same_url_and_claim_without_returned_claim_url(self):
        updated = self.created(); del updated['claimUrl']
        calls = []
        result = publisher.publish_html('<!doctype html><p>Updated</p>', 'Review',
            self.sender([updated, None, self.final()], calls), publication=self.publication())
        self.assertEqual(calls[0][0], publisher.API + '/review-example')
        self.assertEqual(calls[0][2]['method'], 'PUT')
        self.assertEqual(json.loads(calls[0][1])['claimToken'], 'private-owner-token')
        self.assertEqual(result['claimUrl'], self.publication()['claimUrl'])
        self.assertEqual(result['siteUrl'], self.publication()['siteUrl'])
        self.assertTrue(all('api_key' not in c[2] for c in calls))

    def test_legacy_claim_and_invalid_publication_never_create_new_site(self):
        publication = self.publication()
        publication['claimUrl'] = 'https://here.now/claim?slug=review-example&token=legacy-token'
        calls = []
        publisher.publish_html('<!doctype html>', 'Review', self.sender([self.created(), None, self.final()], calls), publication=publication)
        self.assertEqual(json.loads(calls[0][1])['claimToken'], 'legacy-token')
        for url in ['https://evil.example/', 'https://a.b.here.now/', 'https://review-example.here.now:443/',
                    'https://user@review-example.here.now/', 'https://review-example.here.now/?x=1']:
            calls = []
            with self.assertRaises(publisher.PublishError):
                publisher.publish_html('<!doctype html>', 'Review', self.sender([], calls), publication={'siteUrl': url})
            self.assertEqual(calls, [])

    def test_upstream_cannot_redirect_update_to_another_slug(self):
        changed = self.created(); changed['slug'] = 'other'; changed['siteUrl'] = 'https://other.here.now/'
        calls = []
        with self.assertRaises(publisher.PublishError) as failure:
            publisher.publish_html('<!doctype html>', 'Review', self.sender([changed], calls), publication=self.publication())
        self.assertEqual(len(calls), 1)
        self.assertEqual(failure.exception.claim_url, self.publication()['claimUrl'])

    @patch.object(publisher, 'load_api_key', return_value=None, create=True)
    def test_anonymous_removal_replaces_content_with_blank_page_and_confirms_live(self, _key):
        calls = []
        result = publisher.remove_publication(self.publication(), self.sender([self.created(), None, self.final()], calls))
        self.assertEqual(result['mode'], 'blanked')
        self.assertTrue(result['removed'])
        self.assertEqual(calls[0][0], publisher.API + '/review-example')
        self.assertGreaterEqual(len(json.loads(calls[0][1])['displayName']), 1)
        self.assertEqual(calls[1][1], b'<!doctype html><html><head><meta charset="utf-8"><title></title></head><body></body></html>')
        for final in [{'success': False}, {'success': True, 'siteUrl': self.created()['siteUrl'], 'publishStatus': {'state': 'pending'}}]:
            with self.assertRaises(publisher.PublishError):
                publisher.remove_publication(self.publication(), self.sender([self.created(), None, final], []))

    @patch.object(publisher, 'load_api_key', return_value='server-secret', create=True)
    def test_authenticated_delete_requires_explicit_success_and_does_not_leak_key(self, _key):
        calls = []
        result = publisher.remove_publication(self.publication(), self.sender([{'success': True}], calls))
        self.assertEqual(result['mode'], 'deleted')
        self.assertEqual(calls[0][2], {'method': 'DELETE', 'api_key': 'server-secret'})
        self.assertNotIn('server-secret', json.dumps(result))
        with self.assertRaises(publisher.PublishError):
            publisher.remove_publication(self.publication(), self.sender([{}], []))

    @patch.object(publisher, 'load_api_key', return_value='server-secret', create=True)
    def test_only_delete_auth_failure_can_fallback_to_blanking(self, _key):
        calls = []
        result = publisher.remove_publication(self.publication(), self.sender([
            publisher.PublishError('Not authorized', status=403), self.created(), None, self.final()], calls))
        self.assertEqual(result['mode'], 'blanked')
        self.assertNotIn('api_key', calls[1][2])
        for status in [404, 410, 409, 500]:
            calls = []
            with self.assertRaises(publisher.PublishError):
                publisher.remove_publication(self.publication(), self.sender([publisher.PublishError('Failed', status=status)], calls))
            self.assertEqual(len(calls), 1)

    @patch.object(publisher, 'load_api_key', return_value='server-secret', create=True)
    def test_claimed_update_falls_back_to_server_key_only_on_auth_failure(self, _key):
        calls = []
        result = publisher.publish_html('<!doctype html>', 'Review', self.sender([
            publisher.PublishError('Claimed', status=401), self.created(), None, self.final()], calls), publication=self.publication())
        self.assertEqual(result['siteUrl'], self.publication()['siteUrl'])
        self.assertNotIn('api_key', calls[0][2])
        self.assertEqual(calls[1][2]['api_key'], 'server-secret')
        self.assertNotIn('claimToken', json.loads(calls[1][1]))
        self.assertNotIn('api_key', calls[2][2])
        self.assertEqual(calls[3][2]['api_key'], 'server-secret')

    @patch.object(publisher, 'load_api_key', return_value='server-secret')
    def test_claimed_update_without_owner_link_uses_key_and_can_omit_claim_url(self, _key):
        updated = self.created(); del updated['claimUrl']
        calls = []
        result = publisher.publish_html('<!doctype html>', 'Review', self.sender([updated, None, self.final()], calls),
            publication={'siteUrl': self.created()['siteUrl']})
        self.assertEqual(result['siteUrl'], self.created()['siteUrl'])
        self.assertNotIn('claimUrl', result)
        self.assertEqual(calls[0][2]['api_key'], 'server-secret')

    def test_transport_keeps_bearer_key_off_storage_and_redirects(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"success":true}'
        with patch.object(publisher, 'urlopen', return_value=response) as network:
            publisher.request(publisher.API + '/review-example', None, method='DELETE', api_key='server-secret')
            outgoing = network.call_args.args[0]
            self.assertEqual(outgoing.unredirected_hdrs['Authorization'], 'Bearer server-secret')
            self.assertNotIn('Authorization', outgoing.headers)
            publisher.request('https://account.r2.cloudflarestorage.com/file', b'blank', method='PUT', content_type='text/html', api_key='server-secret')
            outgoing = network.call_args.args[0]
            self.assertIsNone(outgoing.get_header('Authorization'))

    def test_credentials_are_loaded_locally_with_environment_precedence(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(publisher.Path, 'home', return_value=Path(directory)):
            credential = Path(directory) / '.herenow/credentials'
            credential.parent.mkdir(); credential.write_text('  file-secret\n')
            with patch.dict(publisher.os.environ, {'HERENOW_API_KEY': ''}):
                self.assertEqual(publisher.load_api_key(), 'file-secret')
            with patch.dict(publisher.os.environ, {'HERENOW_API_KEY': 'env-secret'}):
                self.assertEqual(publisher.load_api_key(), 'env-secret')


class PreviewServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.canvas = Path(self.temp.name) / 'review.html'
        self.canvas.write_text('<!doctype html><html><head></head><body>Local canvas</body></html>')
        self.published = []
        self.removed = []
        self.blocked = threading.Event()
        self.release = threading.Event()
        def remove(publication):
            self.removed.append(publication)
            self.blocked.set()
            self.release.wait(3)
            return {'siteUrl': publication['siteUrl'], 'removed': True, 'mode': 'blanked'}
        def publish(source, title, publication=None):
            self.published.append((source, title) if publication is None else (source, title, publication))
            return {'siteUrl': 'https://review-example.here.now/'}
        self.server = publisher.make_server(self.canvas, publish=publish, remove=remove)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        with urlopen(self.origin) as response:
            self.source = response.read().decode()
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.token = json.loads(self.source.split('id="publisher-config">')[1].split('</script>')[0])['token']

    def tearDown(self):
        self.release.set()
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def post(self, headers=None, body=None, path='/__flow_review/publish'):
        values = {'Content-Type': 'application/json', 'Origin': self.origin, 'X-Flow-Review-Token': self.token}
        values.update(headers or {})
        return urlopen(Request(self.origin + path,
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

    def test_update_passes_validated_publication_and_remove_requires_same_guards(self):
        publication = {'siteUrl': 'https://review-example.here.now/', 'claimUrl': 'https://here.now/c/private-owner-token'}
        with self.post(body={'html': '<!doctype html>', 'title': 'Updated', 'publication': publication}) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self.published[-1][2], publication)
        for headers in [{'Origin': 'https://other.example'}, {'X-Flow-Review-Token': 'wrong'}, {'Host': 'other.example'}]:
            with self.assertRaises(HTTPError) as failure:
                self.post(headers, {'publication': publication}, '/__flow_review/remove')
            self.assertEqual(failure.exception.code, 403)
            failure.exception.close()
        with self.assertRaises(HTTPError) as failure:
            self.post(body={'publication': {'siteUrl': 'https://evil.example/'}}, path='/__flow_review/remove')
        self.assertEqual(failure.exception.code, 400)
        failure.exception.close()
        self.assertEqual(self.removed, [])

    def test_publish_and_remove_share_one_inflight_lock(self):
        publication = {'siteUrl': 'https://review-example.here.now/', 'claimUrl': 'https://here.now/c/private-owner-token'}
        outcomes = []
        def remove():
            with self.post(body={'publication': publication}, path='/__flow_review/remove') as response:
                outcomes.append(json.load(response))
        worker = threading.Thread(target=remove); worker.start()
        try:
            self.assertTrue(self.blocked.wait(2))
            for path, body in [('/__flow_review/publish', None), ('/__flow_review/remove', {'publication': publication})]:
                with self.assertRaises(HTTPError) as failure:
                    self.post(body=body, path=path)
                self.assertEqual(failure.exception.code, 409)
                failure.exception.close()
            self.assertEqual(self.published, [])
        finally:
            self.release.set(); worker.join(3)
        self.assertEqual(outcomes[0]['mode'], 'blanked')


if __name__ == '__main__':
    unittest.main()
