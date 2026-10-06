import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from gitpulse.core import Person, Repository, Store


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "state.sqlite", "example", lambda: "2026-10-06T12:00:00+00:00")

    def test_partial_network_failure_preserves_snapshot(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        before = self.store.report()
        client = Mock()
        client.people.side_effect = [[], RuntimeError("network failure")]
        with self.assertRaises(RuntimeError):
            self.store.sync(client)
        self.assertEqual(before, self.store.report())

    def test_renamed_user_is_not_lost(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        self.store.apply([Person(1, "alice-renamed")], [], [], 1)
        report = self.store.report()
        self.assertEqual(report["lost"], [])
        self.assertEqual(report["events"][0]["kind"], "renamed")

    def test_refollow_excluded_from_lost(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        self.store.apply([], [], [], 1)
        self.assertEqual(len(self.store.report()["lost"]), 1)
        self.store.apply([Person(1, "alice")], [], [], 2)
        self.assertEqual(self.store.report()["lost"], [])

    def test_no_changes_do_not_duplicate_events(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        self.store.apply([Person(1, "alice")], [], [], 1)
        self.assertEqual(len(self.store.report()["events"]), 1)

    def test_duplicate_ids_rejected_before_write(self) -> None:
        with self.assertRaises(ValueError):
            self.store.apply([Person(1, "alice"), Person(1, "other")], [], [], 0)
        self.assertEqual(self.store.revision(), 0)

    def test_stale_writer_rejected(self) -> None:
        self.store.apply([], [], [], 0)
        with self.assertRaises(ValueError):
            self.store.apply([Person(1, "alice")], [], [], 0)
        self.assertEqual(self.store.report()["followers"], [])

    def test_invalid_identifiers_and_counters(self) -> None:
        with self.assertRaises(ValueError):
            Person(True, "alice")
        with self.assertRaises(ValueError):
            Person(1, "../private")
        with self.assertRaises(ValueError):
            Repository(1, "valid", None, -1, 0, 0)

    def test_history_is_append_only(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        with self.store.connection() as database, self.assertRaises(sqlite3.IntegrityError):
            database.execute("DELETE FROM events")

    def test_database_owner_and_persistence(self) -> None:
        self.store.apply([Person(1, "alice")], [], [], 0)
        self.assertEqual(Store(self.store.path, "example").revision(), 1)
        with self.assertRaises(ValueError):
            Store(self.store.path, "another")

    def test_following_preserves_provider_order(self) -> None:
        self.store.apply([], [Person(2, "second"), Person(1, "first")], [], 0)
        self.assertEqual([person["id"] for person in self.store.report()["following"]], [2, 1])


if __name__ == "__main__":
    unittest.main()
