#!/usr/bin/env python
"""Boot (or reuse) the bundled development PostgreSQL server.

Usage:
    python scripts/dev_pg.py [--data-dir .pgdata] [--create-db ecomind]

Prints ``POSTGRES_READY uri=postgresql://...`` once accepting connections.
The server keeps running for the lifetime of this process.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pgserver


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=".pgdata")
    parser.add_argument("--create-db", default="ecomind")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    server = pgserver.get_server(str(data_dir), cleanup_mode=None)

    dbs = server.psql("SELECT datname FROM pg_database;")[0]
    if args.create_db and args.create_db not in dbs.split():
        server.psql(f"CREATE DATABASE {args.create_db};")

    uri = server.get_uri()
    root = data_dir.as_posix()
    print(f"POSTGRES_READY uri={uri} socket_dir={root} pid=running", flush=True)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
