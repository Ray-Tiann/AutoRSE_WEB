import base64
import json
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption

from selfhost.engine import BACKEND, DEMO_PREDICTIONS, Engine, Rejected, TASK_ORDER


def fixture_engine(root, **kwargs):
    key = Ed25519PrivateKey.generate()
    path = root / "signing.key"
    path.write_bytes(base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())))
    path.chmod(0o600)
    runtime = root / "runtime"
    runtime.mkdir()
    engine = Engine(root / "state", runtime, root / "private", path, "a" * 64,
                    runner=kwargs.pop("runner", fake_runner), **kwargs)
    assert engine.initialize()
    return engine


def fake_runner(bundle, work):
    # Synthetic test data; this never qualifies as an actual research result.
    return {"data_revision": "test-fixture", "public_bundle_sha256": "b" * 64,
            "results": {task: {"task": task, "data_revision": "test-fixture",
                "public_bundle_sha256": "b" * 64, "submission_sha256": DEMO_PREDICTIONS[task],
                "backend": BACKEND, "metric": "auc", "metrics": {"auc": 0.5}} for task in TASK_ORDER}}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.engine = fixture_engine(self.root)
        self.addCleanup(self.engine.close)

    def queued(self, subject="visitor-1", username="anonymous-" + "1" * 32):
        job, path = self.engine.reserve(subject, username, display_name="Research agent", ip_hash="test-private-ip-hash")
        path.write_bytes(b"synthetic-test-zip")
        self.engine.uploaded(job)
        return job, path

    def test_complete_signature_ownership_and_cleanup(self):
        job, path = self.queued()
        self.assertTrue(self.engine.run_one())
        result = self.engine.get(job, "visitor-1")
        self.assertEqual(result["status"], "complete")
        receipt = result["receipt"]
        self.assertEqual(receipt["usage"], "demo")
        self.assertEqual(receipt["participant"], "anonymous-" + "1" * 32)
        self.assertEqual(receipt["backend"], BACKEND)
        self.assertFalse(path.exists())
        self.assertIsNone(self.engine.get(job, "other-user"))
        self.assertIsNotNone(self.engine.get(job, admin=True))
        payload = {key: value for key, value in receipt.items() if key != "signature"}
        canonical = b"AutoRSE evaluation receipt v1\x00" + json.dumps(payload,
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
        self.engine.key.public_key().verify(base64.b64decode(receipt["signature"]["value"]), canonical)

    def test_quota_invalid_attempts_and_durable_state(self):
        for _ in range(5):
            job, _ = self.engine.reserve("visitor-1", "anonymous-" + "1" * 32, display_name="Research agent")
            self.engine.fail(job)
        with self.assertRaises(Rejected):
            self.engine.reserve("visitor-1", "anonymous-" + "1" * 32, display_name="Renamed agent")
        engine2 = Engine(self.engine.state, self.engine.runtime, self.engine.private_root,
            self.engine.signing_key_file, self.engine.manifest_sha, runner=fake_runner)
        self.assertTrue(engine2.initialize())
        with self.assertRaises(Rejected):
            engine2.reserve("visitor-1", "anonymous-" + "1" * 32, display_name="Research agent")
        self.engine.reserve("another-visitor", "anonymous-" + "2" * 32, display_name="Another")

    def test_failed_scorer_sanitizes_error(self):
        def bad(*args):
            raise ValueError("private target value SECRET")
        self.engine.runner = bad
        job, path = self.queued()
        self.engine.run_one()
        result = self.engine.get(job, "visitor-1")
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("receipt", result)
        self.assertFalse(path.exists())

    def test_unready_and_excess_queue_fail_closed(self):
        self.engine.ready = False
        with self.assertRaises(Rejected):
            self.engine.reserve("visitor-1", "anonymous-" + "1" * 32, display_name="Research agent")
        self.engine.ready = True
        for number in range(16):
            self.engine.reserve("visitor-" + str(number), "anonymous-" + format(number,"032x"), display_name="Research agent")
        with self.assertRaises(Rejected):
            self.engine.reserve("visitor-over", "anonymous-" + "a" * 32, display_name="Research agent")

    def test_restart_does_not_retry_running_job(self):
        job, _ = self.queued()
        with self.engine.db() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (job,))
        self.engine.start()
        self.engine.close()
        self.assertEqual(self.engine.get(job, "visitor-1")["status"], "failed")

    def test_private_integrity_required_without_test_runner(self):
        self.engine.runner = None
        self.assertFalse(self.engine.initialize())
        self.assertIsNone(self.engine.key)


if __name__ == "__main__":
    unittest.main()
