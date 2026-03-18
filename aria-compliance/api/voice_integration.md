# ARIA Voice Integration

## Overview

ARIA's voice integration is a stateless contract. The existing voice module handles all speech I/O. ARIA handles only the compliance reasoning.

## Integration Contract

```
┌─────────────────┐    transcript     ┌──────────────────┐
│  Voice Module   │ ─────────────────▶│  POST /ask-voice  │
│ (speech-to-text)│                   │  ARIA FastAPI     │
│                 │ ◀─────────────────│                   │
│ (text-to-speech)│   {answer, id}    └──────────────────┘
└─────────────────┘
```

## Endpoint

```
POST /ask-voice
Content-Type: application/json

{
  "transcript": "What are the CET1 capital requirements under Basel III?"
}
```

### Response

```json
{
  "answer": "Under Basel III (12 CFR Part 3)...",
  "query_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

## Steps for the Voice Module

1. **Speech-to-text** — transcribe user audio using your existing module
2. **POST to ARIA** — send transcript to `POST /ask-voice`
3. **Receive answer** — ARIA returns compliance answer with citations
4. **Text-to-speech** — pass `answer` field to your existing TTS module
5. **Log** — `query_id` can be used for audit lookups via `GET /query-log`

## No changes required to the existing voice module.

## Authentication (Phase E production hardening)

Add an `X-API-Key` header to all voice requests:

```
X-API-Key: <ARIA_API_KEY>
```

Set `ARIA_API_KEY` as an environment variable. ARIA will validate it on `/ask-voice`.
This header is not yet enforced — add enforcement before public deployment.

## Error Handling

| HTTP Status | Meaning | Voice Module Action |
|-------------|---------|---------------------|
| 200 | Success | Read answer aloud |
| 400 | Empty transcript | Prompt user to repeat |
| 500 | ARIA internal error | Say "I couldn't retrieve an answer, please try again" |

## Latency

Typical response time: 10–50 seconds (LLM + graph + vector search in parallel).
Voice module should play a hold message if latency exceeds 5 seconds.
