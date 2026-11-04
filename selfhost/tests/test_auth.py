import ipaddress
from pathlib import Path
import tempfile
import unittest

from selfhost.auth import Visitors, VisitorLimit, validate_origin, SESSION_SECONDS


class VisitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.now = 1000000
        self.visitors = Visitors(self.root / 'state.db', 'https://example.org', secret=b's' * 32,
                                 clock=lambda:self.now)

    def test_opaque_identity_is_generated_and_stable(self):
        token, session = self.visitors.new('203.0.113.1')
        self.assertRegex(session['participant'], r'^anonymous-[0-9a-f]{32}$')
        self.assertEqual(self.visitors.session(token), session)
        self.assertNotEqual(token, session['participant'])
        self.assertNotIn(token.encode(), (self.root / 'state.db').read_bytes())
        _, other = self.visitors.new('203.0.113.1')
        self.assertNotEqual(other['participant'], session['participant'])
        self.assertNotEqual(other['csrf'], session['csrf'])
        self.assertIsNone(self.visitors.session('made-up-cookie'))

    def test_expiry_and_invalid_origins(self):
        token, session = self.visitors.new('203.0.113.1')
        self.now += SESSION_SECONDS + 1
        self.assertIsNone(self.visitors.session(token))
        for origin in ['http://example.org','https://u:p@example.org','https://example.org/path','https://example.org/?x=1']:
            with self.assertRaises(ValueError): validate_origin(origin)

    def test_ip_quota_hash_is_canonical_private_and_keyed(self):
        hashed = self.visitors.ip_hash('2001:db8::1')
        self.assertEqual(hashed, self.visitors.ip_hash('2001:0db8:0000:0::1'))
        self.assertNotIn('2001', hashed)
        other = Visitors(self.root / 'other.db', 'https://example.org', secret=b'z' * 32)
        self.assertNotEqual(hashed, other.ip_hash('2001:db8::1'))
        with self.assertRaises(ValueError): self.visitors.ip_hash('forwarded-spoof-value')

    def test_hourly_creation_cap_is_atomic_and_existing_visitors_work(self):
        from concurrent.futures import ThreadPoolExecutor
        def attempt(_):
            try:
                return self.visitors.new('203.0.113.9')[0]
            except VisitorLimit:
                return None
        with ThreadPoolExecutor(max_workers=12) as pool:
            tokens = list(pool.map(attempt, range(40)))
        tokens = [token for token in tokens if token]
        self.assertEqual(len(tokens),20)
        with self.visitors.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM anonymous_visitors').fetchone()[0],20)
            self.assertEqual(db.execute('SELECT SUM(count) FROM visitor_creation_limits').fetchone()[0],20)
        self.assertIsNotNone(self.visitors.session(tokens[0]))
        self.now += 3600
        self.visitors.new('203.0.113.9')
        with self.visitors.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visitor_creation_limits').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT SUM(count) FROM visitor_creation_limits').fetchone()[0],1)

    def test_global_creation_cap_and_expired_cleanup(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        def attempt(number):
            try:
                return self.visitors.new('203.0.113.'+str(number+1))[0]
            except VisitorLimit:
                return None
        with patch('selfhost.auth.MAX_ACTIVE_VISITORS',10):
            with ThreadPoolExecutor(max_workers=8) as pool:
                tokens = [token for token in pool.map(attempt,range(30)) if token]
            self.assertEqual(len(tokens),10)
            self.assertIsNotNone(self.visitors.session(tokens[0]))
            self.now += SESSION_SECONDS+1
            self.visitors.new('198.51.100.1')
        with self.visitors.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM anonymous_visitors').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visitor_creation_limits').fetchone()[0],1)


if __name__ == '__main__': unittest.main()
