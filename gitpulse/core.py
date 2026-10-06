import json
import re
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

Relation = Literal["followers", "following"]


def validate_login(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value)
        or "--" in value
    ):
        raise ValueError("Invalid GitHub login")
    return value


@dataclass(frozen=True)
class Person:
    id: int
    login: str

    def __post_init__(self) -> None:
        if type(self.id) is not int or not 0 < self.id < 2**63:
            raise ValueError("Invalid GitHub numeric ID")
        validate_login(self.login)


@dataclass(frozen=True)
class Repository:
    id: int
    name: str
    language: str | None
    stars: int
    forks: int
    issues: int

    def __post_init__(self) -> None:
        if type(self.id) is not int or not 0 < self.id < 2**63:
            raise ValueError("Invalid repository ID")
        if (
            not isinstance(self.name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", self.name)
            or self.name in (".", "..")
        ):
            raise ValueError("Invalid repository name")
        if self.language is not None and (not isinstance(self.language, str) or len(self.language) > 100):
            raise ValueError("Invalid language")
        if any(type(value) is not int or value < 0 for value in (self.stars, self.forks, self.issues)):
            raise ValueError("Invalid repository counters")


class AudienceClient(Protocol):
    def people(self, relation: Relation) -> list[Person]: ...
    def repositories(self) -> list[Repository]: ...


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path, username: str, clock: Callable[[], str] = now) -> None:
        self.path = path
        self.username = validate_login(username)
        self.clock = clock
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as database:
            database.executescript("""
                CREATE TABLE IF NOT EXISTS metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), username TEXT NOT NULL, revision INTEGER NOT NULL, last_sync TEXT);
                CREATE TABLE IF NOT EXISTS people (relation TEXT NOT NULL, github_id INTEGER NOT NULL, login TEXT NOT NULL, first_seen TEXT NOT NULL, PRIMARY KEY(relation, github_id));
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, revision INTEGER NOT NULL, relation TEXT NOT NULL, github_id INTEGER NOT NULL, login TEXT NOT NULL, kind TEXT NOT NULL, observed_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS repositories (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'append-only history'); END;
            """)
            database.execute("INSERT OR IGNORE INTO metadata VALUES (1, ?, 0, NULL)", (self.username,))
            owner = database.execute("SELECT username FROM metadata").fetchone()[0]
            if owner.lower() != self.username.lower():
                raise ValueError("Database belongs to a different account")
            if "position" not in {row["name"] for row in database.execute("PRAGMA table_info(people)")}:
                database.execute("ALTER TABLE people ADD COLUMN position INTEGER NOT NULL DEFAULT 0")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        database = sqlite3.connect(self.path, timeout=5)
        database.row_factory = sqlite3.Row
        try:
            with database:
                yield database
        finally:
            database.close()

    def revision(self) -> int:
        with self.connection() as database:
            return int(database.execute("SELECT revision FROM metadata").fetchone()[0])

    def sync(self, client: AudienceClient) -> dict[str, Any]:
        expected = self.revision()
        followers = client.people("followers")
        following = client.people("following")
        repositories = client.repositories()
        self.apply(followers, following, repositories, expected)
        return self.report()

    def apply(
        self,
        followers: Sequence[Person],
        following: Sequence[Person],
        repositories: Sequence[Repository],
        expected: int,
    ) -> None:
        for records in (followers, following, repositories):
            if len(records) > 5000 or len({record.id for record in records}) != len(records):
                raise ValueError("Snapshot is too large or contains duplicate IDs")
        observed_at = self.clock()
        with self.connection() as database:
            database.execute("BEGIN IMMEDIATE")
            revision = int(database.execute("SELECT revision FROM metadata").fetchone()[0])
            if revision != expected:
                raise ValueError("A newer sync has already committed; fetch again")
            for relation, incoming in (("followers", followers), ("following", following)):
                previous = {
                    int(row["github_id"]): dict(row)
                    for row in database.execute("SELECT * FROM people WHERE relation=?", (relation,))
                }
                current = {person.id: person for person in incoming}
                for identifier in previous.keys() - current.keys():
                    database.execute(
                        "INSERT INTO events(revision,relation,github_id,login,kind,observed_at) VALUES (?,?,?,?,?,?)",
                        (revision + 1, relation, identifier, previous[identifier]["login"], "removed", observed_at),
                    )
                for position, person in enumerate(incoming):
                    old = previous.get(person.id)
                    kind = (
                        ("baseline" if revision == 0 else "added")
                        if old is None
                        else ("renamed" if old["login"] != person.login else None)
                    )
                    if kind:
                        database.execute(
                            "INSERT INTO events(revision,relation,github_id,login,kind,observed_at) VALUES (?,?,?,?,?,?)",
                            (revision + 1, relation, person.id, person.login, kind, observed_at),
                        )
                    database.execute(
                        "INSERT OR REPLACE INTO people(relation,github_id,login,first_seen,position) VALUES (?,?,?,?,?)",
                        (relation, person.id, person.login, old["first_seen"] if old else observed_at, position),
                    )
                database.execute(
                    "DELETE FROM people WHERE relation=? AND github_id NOT IN (SELECT value FROM json_each(?))",
                    (relation, json.dumps(list(current))),
                )
            database.execute("DELETE FROM repositories")
            database.executemany(
                "INSERT INTO repositories VALUES (?,?)", ((repo.id, json.dumps(asdict(repo))) for repo in repositories)
            )
            database.execute("UPDATE metadata SET revision=?,last_sync=?", (revision + 1, observed_at))

    def report(self) -> dict[str, Any]:
        with self.connection() as database:
            metadata = dict(database.execute("SELECT username,revision,last_sync FROM metadata").fetchone())
            people = [
                dict(row)
                for row in database.execute(
                    "SELECT relation, github_id AS id, login, first_seen FROM people ORDER BY CASE WHEN relation='following' THEN position END,first_seen DESC,github_id"
                )
            ]
            events = [dict(row) for row in database.execute("SELECT * FROM events ORDER BY id DESC LIMIT 1000")]
            lost = [
                dict(row)
                for row in database.execute("""
                SELECT github_id AS id, login, MAX(observed_at) AS lost_at FROM events
                WHERE relation='followers' AND kind='removed' AND github_id NOT IN
                (SELECT github_id FROM people WHERE relation='followers') GROUP BY github_id ORDER BY lost_at DESC
            """)
            ]
            repos = [json.loads(row[0]) for row in database.execute("SELECT payload FROM repositories")]
        return {
            **metadata,
            "followers": [person for person in people if person["relation"] == "followers"],
            "following": [person for person in people if person["relation"] == "following"],
            "lost": lost,
            "events": events,
            "repositories": repos,
            "source": "github",
        }
