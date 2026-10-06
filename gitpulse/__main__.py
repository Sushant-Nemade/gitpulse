import argparse
import json
import os
from pathlib import Path

from gitpulse.core import Store
from gitpulse.github import GitHubClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Explicit single-account GitHub audience sync")
    parser.add_argument("command", choices=["sync", "report"])
    parser.add_argument("--username", default=os.getenv("GITHUB_USERNAME", "Sushant-Nemade"))
    parser.add_argument("--database", type=Path, default=Path("data/gitpulse.sqlite"))
    args = parser.parse_args()
    store = Store(args.database, args.username)
    if args.command == "sync":
        client = GitHubClient(args.username, os.getenv("GITHUB_TOKEN", ""))
        try:
            store.sync(client)
        except (RuntimeError, ValueError):
            parser.exit(1, "Sync failed; previous snapshot preserved. Check account, limits and credentials locally.\n")
        finally:
            client.close()
    print(json.dumps(store.report(), indent=2))


if __name__ == "__main__":
    main()
