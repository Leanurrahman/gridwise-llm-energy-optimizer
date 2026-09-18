# GridWise — LLM-Assisted Energy Optimizer

Starter implementation for the BUP CSE Fest 2026 online preliminary.

## Architecture

1. FastAPI receives the 24-hour scenario.
2. The LLM interprets every `operator_notes` item.
3. Deterministic guardrails validate the structured directives.
4. PuLP/CBC builds the 24-hour minimum-cost schedule.
5. A deterministic replay validates energy balance, battery state, directives,
   totals, and end-of-day battery neutrality.
6. The API returns the required JSON response.

## Endpoints

### Health
`GET /health`

Expected response:

```json
{"status":"ok"}
```

### Optimization
`POST /optimize-energy`

Accepts the exact challenge request object.

## Local setup (Windows)

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from `.env.example`, then set:

- `LLM_API_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

Do not commit `.env`.

In PowerShell, export the variables for the current terminal, for example:

```powershell
$env:LLM_API_URL="YOUR_FULL_ENDPOINT"
$env:LLM_API_KEY="YOUR_KEY"
$env:LLM_MODEL="YOUR_MODEL"
```

Run:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Test health:

```powershell
curl.exe http://127.0.0.1:8000/health
```

Or use Postman.

## Public sample test

With the API running:

```powershell
python scripts/test_public_cases.py "PATH\TO\BUP_CSE_FEST_2026_Preli_Public_Sample_Cases.json"
```

The script compares the machine-checkable directive interpretation fields.
It does not require the hourly schedule to match the reference byte-for-byte.

## Docker

Build:

```bash
docker build -t gridwise .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e LLM_API_URL="YOUR_FULL_ENDPOINT" \
  -e LLM_API_KEY="YOUR_KEY" \
  -e LLM_MODEL="YOUR_MODEL" \
  gridwise
```

The container binds the API to `0.0.0.0:8000`.

## GitHub Actions / GHCR

`.github/workflows/docker.yml` builds the image in GitHub Actions, starts it,
checks `/health`, and then pushes:

`ghcr.io/<github-username>/gridwise:latest`

This lets the team build the fallback image without installing Docker Desktop
on the development PC.

After the workflow succeeds, ensure the package visibility and repository
submission settings satisfy the event instructions.

## LLM adapter

`app/llm.py` currently expects an OpenAI-compatible chat-completions style
HTTP response:

```text
choices[0].message.content
```

The full endpoint URL, API key, and model identifier are supplied by
environment variables.

If the organizer-provided Puku service uses a different request/response
format, replace only `app/llm.py`; the guardrails, optimizer, API schema, and
Docker workflow can remain unchanged.

## Important implementation note

The official material defines each `solar_reduction` as multiplying original
solar by a remaining fraction. It does not separately specify how two
overlapping solar-reduction notes should combine. This starter composes
overlapping reductions multiplicatively. Revisit this assumption if the
organizers publish a clarification.

## Security

- Never commit `.env`, keys, tokens, or passwords.
- Do not return provider errors, raw prompts containing secrets, or stack
  traces to API clients.
- Use only challenge synthetic data.

## Known remaining work before submission

- Configure and test a real LLM provider in `app/llm.py`.
- Run all organizer public sample cases.
- Deploy the API to a public HTTPS URL.
- Verify repeated requests and latency.
- Make the final repository visibility change at the required time.
- Verify the GHCR/Docker image is pullable by judges.
- Record the required <=3-minute architecture/solution video.
