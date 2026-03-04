#!/usr/bin/env python3
"""Test raw TCP connection to PostgreSQL"""
import socket
import sys
import time

# Force unbuffered output
sys.stdout = open(sys.stdout.fileno(), 'w', buffering=1)

host = "127.0.0.1"
port = 5433

print(f"Testing raw TCP to {host}:{port}")
s = time.time()
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)
try:
    result = sock.connect_ex((host, port))
    elapsed = time.time() - s
    if result == 0:
        print(f"TCP connected in {elapsed:.3f}s!")
        # Try to read PostgreSQL greeting
        data = sock.recv(1024)
        print(f"Received {len(data)} bytes: {data[:50]}")
    else:
        print(f"TCP connect failed with code {result} in {elapsed:.3f}s")
except Exception as e:
    print(f"Error: {e} in {time.time()-s:.3f}s")
finally:
    sock.close()

# Now try psycopg2 with explicit settings
print("\nTesting psycopg2...")
import psycopg2
s = time.time()
try:
    c = psycopg2.connect(
        host=host, port=port, dbname='database_test',
        user='postgres', password='postgres',
        connect_timeout=5
    )
    print(f"psycopg2 connected in {time.time()-s:.3f}s")
    cur = c.cursor()
    cur.execute('SELECT COUNT(*) FROM orderhistoryline')
    print(f"Count: {cur.fetchone()[0]}, total: {time.time()-s:.3f}s")
    c.close()
except Exception as e:
    print(f"psycopg2 error: {e} after {time.time()-s:.3f}s")
