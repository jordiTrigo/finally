# FinAlly E2E

Playwright against the real container, with `LLM_MOCK=true` and no Massive key, so the
run is fast, free and deterministic.

## Run it

```bash
# App container + Playwright container, fresh database, from the project root
docker compose -f test/docker-compose.test.yml up --build \
    --abort-on-container-exit --exit-code-from playwright
docker compose -f test/docker-compose.test.yml down -v
```

Against an app you are already running:

```bash
cd test && npm install && npx playwright install chromium
BASE_URL=http://localhost:8001 npx playwright test
```

The app must be started on an empty database, or the fresh-start assertions ($10,000
cash, ten seeded tickers) will not hold:

```bash
docker run -d --name finally-e2e -p 8001:8001 \
    -e LLM_MOCK=true -e MASSIVE_API_KEY= -e OPENROUTER_API_KEY=unused finally:latest
```

## How it is put together

- One app instance, one SQLite file: state carries between specs, so files are numbered
  and run in order on a single worker. `01` asserts the seeded values before anything
  trades; later specs assert relative changes.
- Elements are selected only by `data-testid`.
- No fixed sleeps. Streamed values are waited on with `expect` / `expect.poll`, and the
  300ms flash class is captured by a `MutationObserver` installed before the app boots
  (`tests/helpers.ts`), since polling the DOM for it would be a race.
- The reconnection spec takes down a proxy it runs in front of the app
  (`tests/proxy.ts`). `context.setOffline` does not abort a response that is already
  streaming, so it cannot simulate a backend that went away mid-stream.
- The app service is called `finally-app`, not `app`: `.app` is an HSTS-preloaded gTLD
  and Chromium force-upgrades a host called `app` to HTTPS.
