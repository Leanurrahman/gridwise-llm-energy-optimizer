# GridWise — LLM-Assisted Energy Optimizer

An LLM-assisted energy optimization system developed for the **BUP CSE Fest 2026 Hackathon Preliminary Round**.

GridWise receives a 24-hour campus energy scenario with natural-language operator instructions. The system uses an LLM to interpret operator notes, converts them into structured directives, validates them using deterministic guardrails, and generates a minimum-cost energy schedule using mathematical optimization.

---

# Live Deployment

## Base URL


https://gridwise-llm-energy-optimizer.onrender.com


## Health Endpoint


GET /health


Expected response:

```json
{
  "status": "ok"
}
Optimization Endpoint
POST /optimize-energy

The endpoint accepts the official GridWise request schema containing:

scenario_id
operator_notes
24-hour energy information
battery configuration

The response contains:

directive interpretation
optimized hourly schedule
total grid usage
total electricity cost
peak grid usage
plan summary
System Architecture
Input JSON
     |
     v
FastAPI Service
     |
     v
LLM Operator Note Interpreter
     |
     v
Deterministic Guardrail Validation
     |
     v
PuLP/CBC Optimization Solver
     |
     v
Final Schedule Replay Validation
     |
     v
JSON Response
System Components
1. FastAPI API Layer

Receives the 24-hour energy scenario and returns the final optimization result.

2. LLM Directive Interpreter

The LLM interprets each operator_notes item and converts natural-language instructions into structured directives.

Supported directives:

solar_reduction
minimum_battery_reserve
no_charge_window
no_discharge_window
max_grid_window
no_op
3. Deterministic Guardrails

The interpreted directives are validated before optimization.

Validation includes:

directive type checking
hour range validation
numeric value validation
structured adjustment validation
no_op consistency checking
4. Optimization Engine

PuLP/CBC is used to solve the 24-hour scheduling problem.

The optimizer considers:

grid electricity cost
solar availability
battery charging/discharging
battery capacity
charge/discharge limits
operator constraints
5. Final Replay Validation

The generated schedule is independently verified for:

hourly energy balance
battery state transition
battery limits
directive compliance
total cost calculation
end-of-day battery neutrality
Validation Results

The implementation was tested using the official public sample cases.

SAMPLE-01 PASS
SAMPLE-02 PASS
SAMPLE-03 PASS
SAMPLE-04 PASS
SAMPLE-05 PASS
SAMPLE-06 PASS
SAMPLE-07 PASS
SAMPLE-08 PASS
SAMPLE-09 PASS
SAMPLE-10 PASS

Result:

Passed directive interpretation: 10/10
Local Setup (Windows)
Create Virtual Environment
python --version

python -m venv .venv

.\.venv\Scripts\Activate.ps1
Install Dependencies
python -m pip install --upgrade pip

pip install -r requirements.txt
Configure Environment Variables

Create a .env file from .env.example.

Required variables:

LLM_API_URL
LLM_API_KEY
LLM_MODEL

Example:

$env:LLM_API_URL="YOUR_FULL_ENDPOINT"

$env:LLM_API_KEY="YOUR_API_KEY"

$env:LLM_MODEL="YOUR_MODEL"

Do not commit .env or any secret keys.

Run Locally

Start the API:

uvicorn app.main:app --host 0.0.0.0 --port 8000

Test health:

curl.exe http://127.0.0.1:8000/health

The API can also be tested using Postman.

Public Sample Testing

Run:

python scripts/test_public_cases.py "PATH_TO_PUBLIC_SAMPLE_CASES.json"

The script validates machine-checkable directive interpretation.

Equivalent optimal schedules are accepted; the hourly schedule does not need to match the reference output byte-for-byte.

Docker Image

The fallback Docker image is available through GitHub Container Registry (GHCR):

ghcr.io/leanurrrahman/gridwise:latest
Pull Image
docker pull ghcr.io/leanurrrahman/gridwise:latest
Run Container
docker run --rm -p 8000:8000 \
-e LLM_API_URL="YOUR_ENDPOINT" \
-e LLM_API_KEY="YOUR_KEY" \
-e LLM_MODEL="gemini-3.5-flash-lite" \
ghcr.io/leanurrrahman/gridwise:latest

The container runs the API on:

0.0.0.0:8000
GitHub Actions / Docker Workflow

Workflow file:

.github/workflows/docker.yml

The workflow:

builds the Docker image
starts the container
tests the /health endpoint
publishes the image to GitHub Container Registry

Docker image:

ghcr.io/leanurrrahman/gridwise:latest
Repository Structure
gridwise_starter/

├── app/
│   ├── main.py
│   ├── llm.py
│   ├── optimizer.py
│   ├── guardrails.py
│   ├── replay.py
│   └── schemas.py
│
├── scripts/
│   └── test_public_cases.py
│
├── .github/
│   └── workflows/
│       └── docker.yml
│
├── Dockerfile
├── requirements.txt
├── README.md
└── public_cases.json
LLM Configuration

The LLM provider configuration is controlled through environment variables:

LLM_API_URL
LLM_API_KEY
LLM_MODEL

The LLM integration is isolated inside:

app/llm.py

so the provider can be replaced without modifying the optimization pipeline.

Security
Never commit API keys, tokens, passwords, or .env files.
Do not expose secrets in logs or API responses.
Use only synthetic challenge data.
Project Status
