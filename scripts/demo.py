import json
import tempfile
from pathlib import Path

from gitpulse.core import Person, Repository, Store


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as temporary:
        times = iter(["2026-10-02T12:00:00+00:00", "2026-10-04T12:00:00+00:00", "2026-10-06T12:00:00+00:00"])
        store = Store(Path(temporary) / "fixture.sqlite", "example-account", lambda: next(times))
        repos = [
            Repository(101, "signal-kit", "Python", 42, 8, 2),
            Repository(102, "dataset-audit", "TypeScript", 28, 5, 1),
            Repository(103, "notes-core", "Python", 16, 3, 0),
            Repository(104, "web-console", "TypeScript", 11, 2, 3),
        ]
        store.apply(
            [Person(1, "sample-analyst"), Person(2, "sample-builder"), Person(3, "sample-designer")],
            [Person(7, "sample-maintainer")],
            repos,
            0,
        )
        store.apply(
            [
                Person(1, "sample-analyst"),
                Person(3, "sample-designer"),
                Person(4, "sample-engineer"),
                Person(5, "sample-researcher"),
            ],
            [Person(7, "sample-maintainer"), Person(8, "sample-reviewer")],
            repos,
            1,
        )
        store.apply(
            [
                Person(1, "sample-analyst"),
                Person(4, "sample-engineer"),
                Person(5, "sample-researcher"),
                Person(6, "sample-contributor"),
            ],
            [Person(7, "sample-maintainer"), Person(8, "sample-reviewer")],
            repos,
            2,
        )
        report = store.report()
        report["source"] = "fixture"
        destination = root / "frontend" / "src" / "demo.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Built fictional demo data; no account or credential data exported")


if __name__ == "__main__":
    main()
