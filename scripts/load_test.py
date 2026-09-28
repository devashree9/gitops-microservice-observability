"""
Simple load generator for demoing the observability stack.

Hits a mix of endpoints so the Grafana dashboard shows realistic patterns:
request rate, latency spread, and cache hit/miss ratio, instead of a flat line.

Usage:
    python scripts/load_test.py
    python scripts/load_test.py --host http://localhost:8000 --duration 120
"""
import argparse
import random
import time
import requests


def run(host: str, duration: int):
    end_time = time.time() + duration
    request_count = 0

    print(f"Sending traffic to {host} for {duration}s ... (Ctrl+C to stop early)")

    while time.time() < end_time:
        choice = random.random()
        try:
            if choice < 0.5:
                # repeated compute calls on a small set of n values -> lots of cache hits
                n = random.choice([10, 50, 100, 250])
                requests.get(f"{host}/compute/{n}", timeout=5)
            elif choice < 0.8:
                key = f"demo-key-{random.randint(1, 5)}"
                requests.post(f"{host}/cache/{key}/value-{random.randint(1, 1000)}", timeout=5)
            else:
                requests.get(f"{host}/", timeout=5)
        except requests.RequestException as e:
            print(f"request failed: {e}")

        request_count += 1
        time.sleep(random.uniform(0.05, 0.3))

    print(f"Done. Sent {request_count} requests.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8000")
    parser.add_argument("--duration", type=int, default=60, help="seconds to run for")
    args = parser.parse_args()
    run(args.host, args.duration)
