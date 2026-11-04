"""Publication hand-off tests use generated receipts and synthetic evidence only."""
from contextlib import redirect_stdout
import hashlib
import io
import stat
import unittest
from unittest.mock import patch
import zipfile

import test_cli
import test_review
from autorse_leaderboard import bootstrap_empty, cli, package_snapshot, receive, snapshot


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.workflow = test_cli.WorkflowTests()
        self.workflow.setUp()
        self.addCleanup(self.workflow.doCleanups)
        self.root = self.workflow.root
        self.source = self.root / "generated"
        with redirect_stdout(io.StringIO()), patch(
                "autorse_leaderboard.artifacts.PublicArtifactReader", return_value=self.workflow.reader):
            cli.publish(self.workflow.args)
        self.digest = hashlib.sha256((self.source / snapshot.MANIFEST_NAME).read_bytes()).hexdigest()
        self.published = self.root / "published"
        self.published.mkdir()

    def verify(self, **kwargs):
        return snapshot.verify_snapshot(self.source, self.workflow.fixture.keys, self.digest,
                                        artifact_reader=kwargs.get("reader", self.workflow.reader))

    def remanifest(self):
        self.digest = snapshot.write_manifest(self.source, ["synthetic-agent.json"], "f" * 40)

    def archive(self, transform=None):
        files = {p.relative_to(self.source).as_posix(): p.read_bytes()
                 for p in self.source.rglob("*") if p.is_file()}
        if transform:
            transform(files)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        return io.BytesIO(output.getvalue())

    def test_pinned_snapshot_rechecks_receipts_evidence_and_rebuilds_board(self):
        checked = self.verify()
        self.assertEqual(checked.audit["entry_count"], 1)
        self.assertEqual(checked.audit["receipt_signatures_verified"], 3)
        self.assertIs(checked.audit["snapshot_signed"], False)
        self.assertEqual(checked.board["rows"][0]["overall_rank"], 1)
        self.assertEqual(checked.files["community-leaderboard.json"],
                         (self.source / "community-leaderboard.json").read_bytes())

    def test_publisher_preserves_exact_reviewed_submission_bytes(self):
        original = self.workflow.path.read_bytes()
        compact = original.replace(b"\n", b" ")
        self.workflow.path.write_bytes(compact)
        ledger = cli.read_json(self.workflow.ledger_path)
        ledger["approvals"][0]["submission_sha256"] = hashlib.sha256(compact).hexdigest()
        cli.write_json(self.workflow.ledger_path, ledger)
        with redirect_stdout(io.StringIO()), patch(
                "autorse_leaderboard.artifacts.PublicArtifactReader", return_value=self.workflow.reader):
            cli.publish(self.workflow.args)
        self.digest = hashlib.sha256((self.source / snapshot.MANIFEST_NAME).read_bytes()).hexdigest()
        checked = self.verify()
        self.assertEqual(checked.files["submissions/synthetic-agent.json"], compact)

    def test_unknown_manifest_digest_and_changed_bytes_fail(self):
        self.digest = "0" * 64
        with self.assertRaises(ValueError):
            self.verify()
        self.remanifest()
        with (self.source / "community-leaderboard.json").open("ab") as stream:
            stream.write(b" ")
        with self.assertRaises(ValueError):
            self.verify()

    def test_rehashed_forged_ranking_or_review_ledger_is_not_accepted(self):
        board_path = self.source / "community-leaderboard.json"
        original = board_path.read_bytes()
        board = cli.read_json(board_path)
        board["rows"][0]["scores"][0] = 1.0
        cli.write_json(board_path, board)
        self.remanifest()
        with self.assertRaisesRegex(ValueError, "published_board_differs"):
            self.verify()
        board_path.write_bytes(original)
        ledger_path = self.source / "approval-ledger.json"
        ledger = cli.read_json(ledger_path)
        ledger["approvals"][0]["approved_reviews"][0]["reviewer"] = ledger["approvals"][0]["author"]
        cli.write_json(ledger_path, ledger)
        self.remanifest()
        with self.assertRaisesRegex(ValueError, "qualified_review_missing"):
            self.verify()

    def test_bad_evidence_or_demo_submission_cannot_enter_community(self):
        with self.assertRaisesRegex(ValueError, "snapshot_submission_validation_failed"):
            self.verify(reader=lambda _ref: b"altered evidence")
        submission_path = self.source / "submissions/synthetic-agent.json"
        submission = cli.read_json(submission_path)
        submission["kind"] = "test"
        cli.write_json(submission_path, submission)
        self.remanifest()
        with self.assertRaisesRegex(ValueError, "snapshot_submission_not_benchmark"):
            self.verify()

    def test_symlink_and_extra_manifest_paths_are_refused(self):
        path = self.source / "submissions/synthetic-agent.json"
        saved = self.root / "untrusted.json"
        saved.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, "snapshot_symlink_refused"):
            self.verify()

    def test_only_exact_forced_command_is_accepted(self):
        self.assertEqual(receive.command_digest("publish " + self.digest), self.digest)
        for command in (None, "", "sh", "publish " + self.digest + "; id",
                        "publish " + self.digest + "\n", "publish\t" + self.digest,
                        "publish " + self.digest + " /tmp/target", "publish " + "A" * 64):
            with self.subTest(command=command), self.assertRaises(ValueError):
                receive.command_digest(command)

    def test_receiver_installs_atomically_and_is_idempotent(self):
        args = ("publish " + self.digest, self.archive(), self.workflow.fixture.keys, self.published)
        result = receive.receive(*args, artifact_reader=self.workflow.reader)
        target = self.published / "current"
        self.assertTrue(target.is_symlink())
        self.assertEqual(target.resolve().parent, (self.published / "snapshots").resolve())
        expected = (self.source / "community-leaderboard.json").read_bytes()
        self.assertEqual((target / "community-leaderboard.json").read_bytes(), expected)
        self.assertIs(result["snapshot_signed"], False)
        receive.receive("publish " + self.digest, self.archive(), self.workflow.fixture.keys,
                        self.published, artifact_reader=self.workflow.reader)
        self.assertEqual((target / "community-leaderboard.json").read_bytes(), expected)
        self.assertFalse(list(self.published.glob(".incoming-*")))

    def test_authenticated_receiver_offline_mode_does_not_contact_evidence_host(self):
        with patch("autorse_leaderboard.artifacts.PublicArtifactReader", side_effect=AssertionError("network forbidden")):
            audit = receive.receive("publish " + self.digest, self.archive(),
                                    self.workflow.fixture.keys, self.published)
        self.assertIn("receiver did not independently fetch evidence", audit["evidence_verification"])
        with patch("autorse_leaderboard.artifacts.PublicArtifactReader", side_effect=ValueError("network unavailable")):
            with self.assertRaises(ValueError):
                snapshot.verify_snapshot(self.source, self.workflow.fixture.keys, self.digest)

    def test_offline_receiver_still_rejects_forged_receipts(self):
        submission_path = self.source / "submissions/synthetic-agent.json"
        submission = cli.read_json(submission_path)
        submission["receipts"][0]["signature"]["value"] = "invalid"
        cli.write_json(submission_path, submission)
        ledger_path = self.source / "approval-ledger.json"
        ledger = cli.read_json(ledger_path)
        ledger["approvals"][0]["submission_sha256"] = hashlib.sha256(submission_path.read_bytes()).hexdigest()
        cli.write_json(ledger_path, ledger)
        self.remanifest()
        with self.assertRaisesRegex(ValueError, "snapshot_submission_validation_failed"):
            receive.receive("publish " + self.digest, self.archive(), self.workflow.fixture.keys, self.published)
        self.assertFalse((self.published / "current").exists())

    def test_packager_binds_only_manifest_members_and_refuses_overwrite(self):
        output = self.root / "snapshot.zip"
        result = package_snapshot.package(self.source, output)
        self.assertEqual(result["manifest_sha256"], self.digest)
        self.assertEqual(result["file_count"], 4)
        with output.open("rb") as stream:
            receive.receive("publish " + self.digest, stream, self.workflow.fixture.keys, self.published)
        with self.assertRaises(FileExistsError):
            package_snapshot.package(self.source, output)

    def test_failed_update_preserves_previous_published_release(self):
        receive.receive("publish " + self.digest, self.archive(), self.workflow.fixture.keys,
                        self.published, artifact_reader=self.workflow.reader)
        target = self.published / "current"
        previous = target.resolve()
        original = (target / "community-leaderboard.json").read_bytes()
        archive = self.archive(lambda files: files.update({"community-leaderboard.json": b"{}"}))
        with self.assertRaises(ValueError):
            receive.receive("publish " + self.digest, archive, self.workflow.fixture.keys,
                            self.published, artifact_reader=self.workflow.reader)
        self.assertEqual(target.resolve(), previous)
        self.assertEqual((target / "community-leaderboard.json").read_bytes(), original)

    def test_frozen_checked_bytes_are_installed_after_source_changes(self):
        checked = self.verify()
        expected = checked.files["community-leaderboard.json"]
        (self.source / "community-leaderboard.json").write_bytes(b"{}")
        receive.install_snapshot(checked, self.published)
        self.assertEqual((self.published / "current/community-leaderboard.json").read_bytes(), expected)

    def test_archive_paths_symlinks_and_expansion_limits_are_refused(self):
        for name in ("../outside.json", "/tmp/outside.json", "submissions/../outside.json", "code.py"):
            archive = self.archive(lambda files: files.update({name: b"{}"}))
            with self.subTest(name=name), self.assertRaises(ValueError):
                receive.unpack_snapshot(archive, self.root / ("bad-" + hashlib.sha256(name.encode()).hexdigest()))
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            member = zipfile.ZipInfo(snapshot.MANIFEST_NAME)
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(member, "/tmp/elsewhere")
        with self.assertRaises(ValueError):
            receive.unpack_snapshot(io.BytesIO(output.getvalue()), self.root / "bad-symlink")
        with patch.object(receive, "MAX_SNAPSHOT_BYTES", 100), self.assertRaises(ValueError):
            receive.unpack_snapshot(self.archive(), self.root / "bad-size")
        archive = self.archive()
        compressed = len(archive.getvalue())
        with zipfile.ZipFile(archive) as opened:
            expanded = sum(item.file_size for item in opened.infolist())
        self.assertGreater(expanded, compressed)
        with patch.object(receive, "MAX_SNAPSHOT_BYTES", (compressed + expanded) // 2), self.assertRaises(ValueError):
            receive.unpack_snapshot(self.archive(), self.root / "bad-expanded-size")
        with patch.object(snapshot, "MAX_SNAPSHOT_FILES", 3), self.assertRaises(ValueError):
            self.verify()


class EmptyBootstrapTests(unittest.TestCase):
    def test_real_empty_git_tree_has_no_fabricated_reviews_or_results(self):
        with test_review.repository() as (root, _source, head, git):
            git("remote", "add", "origin", "https://github.com/Ray-Tiann/AutoRSE")
            git("update-ref", "refs/remotes/origin/main", head)
            result = bootstrap_empty.bootstrap(root, head, root / "initial-snapshot")
            self.assertEqual(result["entry_count"], 0)
            self.assertEqual(result["reviews_asserted"], 0)
            checked = snapshot.verify_snapshot(root / "initial-snapshot", {}, result["manifest_sha256"])
            self.assertEqual(checked.board["rows"], [])
            self.assertEqual(cli.read_json(root / "initial-snapshot/approval-ledger.json")["approvals"], [])
            self.assertIn("no human reviews are asserted", checked.audit["review_binding"])
            self.assertEqual(checked.audit["receipt_signatures_verified"], 0)
            manifest = cli.read_json(root / "initial-snapshot/snapshot-manifest.json")
            self.assertEqual(manifest["publication_kind"], "empty-source-bootstrap")
            self.assertEqual(manifest["publication_checks"], {})

    def test_nonempty_or_stale_source_cannot_be_bootstrapped(self):
        with test_review.repository(b'{"id":"example-agent"}') as (root, _source, head, git):
            git("remote", "add", "origin", "https://github.com/Ray-Tiann/AutoRSE")
            git("update-ref", "refs/remotes/origin/main", head)
            with self.assertRaisesRegex(ValueError, "bootstrap_requires_empty_submission_registry"):
                bootstrap_empty.bootstrap(root, head, root / "initial-snapshot")
            with self.assertRaisesRegex(ValueError, "bootstrap_requires_fetched_main_snapshot"):
                bootstrap_empty.bootstrap(root, "0" * 40, root / "stale-snapshot")
            self.assertFalse((root / "initial-snapshot").exists())


if __name__ == "__main__":
    unittest.main()
