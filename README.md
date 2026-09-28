# GitOps Automated Microservice with Observability Stack

A containerized FastAPI microservice with Redis caching, deployed and monitored
the way a small production service actually would be: automated tests and
image builds via GitHub Actions, multi-service orchestration via Docker
Compose, and live metrics via Prometheus + Grafana.

This isn't a toy CRUD app — the goal was to practice the full lifecycle a
backend service goes through: build -> test -> containerize -> publish -> observe.

## Architecture

```
                 +-------------+
   requests ---> |  FastAPI    |---> Redis (cache-aside)
                 |  app :8000  |
                 +------+------+
                        | /metrics
                        v
                 +-------------+        +-------------+
                 | Prometheus  |------->|   Grafana   |
                 |   :9090     |        |   :3000     |
                 +-------------+        +-------------+
```

On every push:
```
GitHub push -> pytest (against real Redis) -> Docker build -> push to Docker Hub
                                                                (tagged :latest and :<git-sha>)
```

## What's actually interesting here (not just "I used Docker")

- **Cache-aside pattern, not a raw key-value passthrough.** `GET /compute/{n}`
  simulates an expensive operation (1.5s). The first call misses the cache and
  computes it; every repeat call within the TTL hits Redis and returns in
  single-digit milliseconds. The response tells you which happened
  (`"source": "cache"` vs `"source": "computed"`) so it's easy to demo.
- **Structured JSON logs**, not free-text `print()` — every log line is a
  parseable JSON object, which is what you'd actually want if this shipped to
  something like Loki or CloudWatch.
- **Provisioned Grafana**, not a blank dashboard. Datasource and dashboard
  JSON are mounted in automatically on `docker compose up` — no manual
  clicking through the UI required.
- **CI gates the build on tests passing**, and tests run against a real Redis
  service container in GitHub Actions (not mocked), so a broken Redis
  interaction would actually fail CI.
- **Images are tagged with the git SHA**, not just `latest`, so you can trace
  exactly which commit produced any running container.
- **The deploy step is explicit and honest.** It's gated behind a
  `DEPLOY_ENABLED` repo variable and SSH secrets. Without a real target host
  configured, the pipeline correctly stops at "image published to Docker
  Hub" rather than silently pretending to deploy somewhere.

## Running it locally

```bash
docker compose up --build
```

This starts four containers:

| Service    | URL                     | What it's for                          |
|------------|-------------------------|------------------------------------------|
| app        | http://localhost:8000   | FastAPI service                         |
| redis      | localhost:6379          | Cache backend                           |
| prometheus | http://localhost:9090   | Metrics collection (check `/targets`)   |
| grafana    | http://localhost:3000   | Dashboards (admin / admin, or anonymous)|

Try it:

```bash
# health check
curl http://localhost:8000/

# cache-aside demo -- first call is slow (~1.5s), second call is fast
curl http://localhost:8000/compute/50
curl http://localhost:8000/compute/50

# raw key-value cache
curl -X POST http://localhost:8000/cache/foo/bar
curl http://localhost:8000/cache/foo
```

### Generating traffic for the dashboard

Dashboards look like nothing until there's traffic to graph:

```bash
pip install -r scripts/requirements.txt
python scripts/load_test.py --host http://localhost:8000 --duration 60
```

Then open Grafana at `http://localhost:3000` -> **GitOps Microservice
Overview** to see request rate, latency, and cache hit/miss ratio update live.

## Running tests

```bash
cd app
pip install -r requirements.txt
pytest -v
```

## CI/CD

- **On every push/PR:** runs the full test suite against a real Redis service
  container.
- **On push to `main`:** builds the Docker image and pushes it to Docker Hub,
  tagged both `:latest` and `:<git-sha>`.
- **Deploy (optional):** if a repo variable `DEPLOY_ENABLED=true` and the
  secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` are configured, a
  final job SSHs into the target host, pulls the new image, and restarts the
  service via Docker Compose, with a health-check curl after restart.

## What I'd add with more time

- Roll back the deploy automatically if the post-deploy health check fails
- Alerting rules in Prometheus (e.g. error-rate threshold) instead of just
  dashboards
- Centralized log aggregation (Loki or similar) instead of per-container logs
- Horizontal scaling test -- multiple app replicas behind a load balancer,
  sharing the same Redis cache

## Stack

FastAPI - Redis - Docker - Docker Compose - GitHub Actions - Prometheus - Grafana - pytest

<img width="725" height="476" alt="Screenshot 2026-09-28 234024" src="https://github.com/user-attachments/assets/4dd477c6-f4b9-4b91-950b-9853ff33a0d4" />
