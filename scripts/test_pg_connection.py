#!/usr/bin/env python3
"""Quick test for psycopg2 connection to local PostgreSQL Docker container."""
import psycopg2
import time
import sys

sys.stdout.write("Starting psycopg2 connection test...\n")
sys.stdout.flush()

start = time.time()
try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5433,
        dbname="database_test",
        user="postgres",
        password="postgres",
        connect_timeout=5,
    )
    elapsed = time.time() - start
    sys.stdout.write(f"Connected in {elapsed:.3f}s\n")
    sys.stdout.flush()

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orderhistoryline")
    count = cur.fetchone()[0]
    sys.stdout.write(f"Row count: {count} ({time.time()-start:.3f}s)\n")
    sys.stdout.flush()

    cur.execute("SELECT * FROM orderhistoryline LIMIT 2")
    rows = cur.fetchall()
    sys.stdout.write(f"Sample: {len(rows)} rows fetched\n")
    sys.stdout.flush()

    conn.close()
    sys.stdout.write("SUCCESS\n")
except Exception as e:
    sys.stdout.write(f"ERROR: {type(e).__name__}: {e}\n")

sys.stdout.flush()
