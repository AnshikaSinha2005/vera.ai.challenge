# Vera — Merchant Engagement Bot

This submission implements the magicpin AI Challenge contract with a deterministic, context-grounded composer plus a small multi-turn replay handler.

## What is included
- `bot.py` — `compose(category, merchant, trigger, customer=None) -> dict`
- `conversation_handlers.py` — auto-reply detection, intent transitions, graceful STOP
- `server.py` — `/v1/healthz`, `/v1/metadata`, `/v1/context`, `/v1/tick`, `/v1/reply`
- `submission.jsonl` — all 30 canonical test-pair outputs
- `dataset/` — expanded challenge dataset: 5 categories, 50 merchants, 200 customers, 100 triggers
- `test_smoke.py` — deterministic smoke tests
- `Dockerfile` / `requirements.txt` — container deployment

## Approach
Vera routes on `trigger.kind` and extracts the strongest verifiable fact from the supplied trigger/category/merchant/customer contexts. Messages then use category-specific voice, merchant state, real offers, dates, performance deltas, digest sources, and customer preferences when available. No external APIs or invented facts are used.

Customer-scope triggers are sent `merchant_on_behalf` and use consent-aware YES/STOP CTAs. Merchant action triggers use one binary commitment; information/research messages can use a low-friction open question. First-touch actions are wrapped in a pre-approved-style template object for the WhatsApp 24-hour rule.

The replay handler detects canned/automated replies, retries once, stops on repeated auto-replies, recognizes explicit action intent without re-qualifying, and exits cleanly on STOP.

## Run
```bash
python test_smoke.py
python server.py
```

Default port: `8080`. Docker:
```bash
docker build -t vera-bot .
docker run --rm -p 8080:8080 vera-bot
```

## Validation
- Python compilation: PASS
- Smoke tests: PASS
- Canonical submission generation: 30/30 valid outputs
- The provided LLM judge requires an external `LLM_API_KEY`, so its scoring engine cannot be run in this environment without credentials.
- The execution environment used for local checks does not permit loopback HTTP connections, so endpoint behavior is additionally validated through the handler implementation and static compilation rather than claiming a live local HTTP test.

## Tradeoff
The bot is deliberately deterministic and fast rather than dependent on an LLM at request time. This improves reproducibility and keeps `/v1/tick` and `/v1/reply` comfortably inside the challenge latency budget, at the cost of less linguistic variety than a tuned LLM.
