from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from selfhost.app import create_app
from selfhost.auth import Visitors, VISITOR_COOKIE
from selfhost.tests.test_engine import fixture_engine


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.engine = fixture_engine(self.root)
        self.visitors = Visitors(self.engine.database, 'https://example.org', secret=b's' * 32)
        app = create_app(engine=self.engine, visitors=self.visitors, start_worker=False)
        self.client = TestClient(app, base_url='https://example.org', client=('203.0.113.9', 50000))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def initialize(self):
        response = self.client.get('/api/me')
        self.assertEqual(response.status_code,200)
        return response.json()

    def upload(self, session, data=b'synthetic-zip', name='My agent', extra_headers=None):
        return self.client.post('/api/evaluations', params={'display_name':name}, content=data,
            headers={'Content-Type':'application/zip','X-CSRF-Token':session['csrf'],
                     'Origin':self.visitors.origin, **(extra_headers or {})})

    def test_no_login_required_and_csrf_rejected(self):
        page = self.client.get('/evaluate/')
        self.assertEqual(page.status_code,200)
        self.assertNotIn('Sign in',page.text)
        self.assertNotIn('href="/oauth',page.text)
        self.assertEqual(self.client.post('/api/evaluations',content=b'zip').status_code,401)
        session = self.initialize()
        self.assertEqual(session['participant_kind'],'anonymous-session')
        self.assertEqual(self.client.post('/api/evaluations',content=b'zip').status_code,403)
        self.assertEqual(self.upload(session,extra_headers={'Origin':'https://attacker.example'}).status_code,403)
        self.assertEqual(self.upload(session).status_code,202)

    def test_self_reported_name_never_becomes_verified_participant(self):
        session = self.initialize()
        response = self.upload(session,name='Ray0311 <script>claimed identity</script>')
        self.assertEqual(response.status_code,202)
        job = response.json()['evaluation_id']
        self.engine.run_one()
        receipt = self.client.get('/api/evaluations/'+job+'/receipt').json()
        self.assertRegex(receipt['participant'],r'^anonymous-[0-9a-f]{32}$')
        self.assertEqual(receipt['participant_kind'],'anonymous-session')
        self.assertEqual(receipt['display_name'],'Ray0311 <script>claimed identity</script>')
        self.assertNotIn('ip_hash',receipt)
        self.assertNotIn('subject',receipt)
        self.assertNotIn('203.0.113.9',str(receipt))
        script = self.client.get('/evaluate-assets/app.js').text
        self.assertIn('td.textContent=value',script)
        self.assertNotIn('innerHTML',script)

    def test_receipt_ownership_and_same_visitor_across_trials(self):
        session = self.initialize()
        jobs, participants = [],[]
        for trial in range(3):
            response = self.upload(session,name='Trial '+str(trial))
            self.assertEqual(response.status_code,202)
            job = response.json()['evaluation_id']
            jobs.append(job)
            self.assertEqual(self.client.get('/api/evaluations/'+job+'/receipt').status_code,409)
            self.engine.run_one()
            receipt = self.client.get('/api/evaluations/'+job+'/receipt')
            self.assertEqual(receipt.status_code,200)
            participants.append(receipt.json()['participant'])
        self.assertEqual(len(set(participants)),1)
        self.client.cookies.clear()
        self.initialize()
        for job in jobs:
            self.assertEqual(self.client.get('/api/evaluations/'+job).status_code,404)
            self.assertEqual(self.client.get('/api/evaluations/'+job+'/receipt').status_code,404)

    def test_visitor_cookie_flags_and_no_public_admin(self):
        result = self.client.get('/api/me')
        cookie = result.headers['set-cookie']
        self.assertIn(VISITOR_COOKIE,cookie)
        for flag in ['HttpOnly','Secure','SameSite=lax','Path=/']: self.assertIn(flag,cookie)
        for path in ['/admin/','/api/admin/evaluations','/oauth/login','/.well-known/oauth-cimd']:
            self.assertEqual(self.client.get(path).status_code,404)

    def test_visitor_creation_limits_do_not_block_existing_cookie(self):
        from unittest.mock import patch
        with patch('selfhost.auth.MAX_ACTIVE_VISITORS',1):
            session = self.initialize()
            existing_cookie = self.client.cookies.get(VISITOR_COOKIE)
            self.client.cookies.clear()
            blocked = self.client.get('/api/me')
            self.assertEqual(blocked.status_code,429)
            self.assertNotIn('set-cookie',blocked.headers)
            self.client.cookies.set(VISITOR_COOKIE,existing_cookie)
            for _ in range(25):
                self.assertEqual(self.client.get('/api/me').status_code,200)
            result = self.upload(session)
            self.assertEqual(result.status_code,202)
            self.assertEqual(self.client.get('/api/evaluations').status_code,200)

    def test_visitor_database_failure_returns_generic_503(self):
        import sqlite3
        from unittest.mock import patch
        with patch.object(self.visitors,'new',side_effect=sqlite3.OperationalError('secret database path')):
            response = self.client.get('/api/me')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('secret',response.text)
        with patch.object(self.visitors,'session',side_effect=sqlite3.OperationalError('private file path')):
            response = self.client.get('/api/evaluations')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private',response.text)

    def test_names_content_type_size_and_private_paths(self):
        session = self.initialize()
        for name in ['', 'x'*81,'new\nline','name\x1b[31m']:
            self.assertEqual(self.upload(session,name=name).status_code,400)
        response = self.client.post('/api/evaluations?display_name=Agent',content=b'zip',headers={'X-CSRF-Token':session['csrf']})
        self.assertEqual(response.status_code,415)
        response = self.upload(session,data=b'x',extra_headers={'Content-Length':str(513*1024**2)})
        self.assertEqual(response.status_code,413)
        for path in ['/private/labels.npz','/state/autorse.sqlite3','/secrets/receipt.key','/evaluate-assets/../auth.py']:
            self.assertEqual(self.client.get(path).status_code,404)

    def test_streamed_oversize_upload_is_removed_and_counted(self):
        from unittest.mock import patch
        session = self.initialize()
        with patch('selfhost.app.MAX_BUNDLE_BYTES',16):
            result = self.upload(session,data=iter([b'x'*10,b'x'*10]))
        self.assertEqual(result.status_code,413)
        history = self.client.get('/api/evaluations').json()['evaluations']
        self.assertEqual(len(history),1)
        self.assertEqual(history[0]['status'],'failed')
        self.assertFalse(list(self.engine.uploads.glob('*/submission.zip')))

    def test_five_attempt_quota_and_ip_bound_ignore_spoofed_forwarded_headers(self):
        session = self.initialize()
        for _ in range(5):
            result = self.upload(session)
            self.assertEqual(result.status_code,202)
            self.engine.fail(result.json()['evaluation_id'])
        self.assertEqual(self.upload(session).status_code,429)
        # Different cookies cannot evade the network bound, even with forged headers.
        for number in range(15):
            self.client.cookies.clear()
            session = self.initialize()
            result = self.upload(session,extra_headers={'X-Forwarded-For':'198.51.100.'+str(number)})
            self.assertEqual(result.status_code,202)
            self.engine.fail(result.json()['evaluation_id'])
        self.client.cookies.clear()
        # A new hour permits creating a session, but the daily submission IP cap remains.
        import time
        self.visitors.clock = lambda:time.time()+3600
        session = self.initialize()
        result = self.upload(session,extra_headers={'X-Forwarded-For':'198.51.100.250'})
        self.assertEqual(result.status_code,429)
        self.assertIn('network',result.json()['detail'])


if __name__=='__main__': unittest.main()
