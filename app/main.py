
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .guardrails import validate_llm_directives
from .llm import interpret_notes_with_llm
from .optimizer import optimize_schedule
from .replay import replay_and_validate
from .schemas import OptimizeRequest, OptimizeResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gridwise")

app = FastAPI(
    title="GridWise LLM-Assisted Energy Optimizer",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    # Problem Statement: malformed JSON -> 400; semantic/structural invalidity
    # may use 422.
    errors = exc.errors()
    if any(e.get("type") == "json_invalid" for e in errors):
        return JSONResponse(
            status_code=400,
            content={"detail": "Malformed JSON request"},
        )
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request structure or values"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizeResponse)
async def optimize_energy(req: OptimizeRequest):
    try:
        raw_directives = await interpret_notes_with_llm(req)
        directives = validate_llm_directives(req, raw_directives)
        response = optimize_schedule(req, directives)
        replay_and_validate(req, response)
        return response

    except ValueError as exc:
        logger.warning("Controlled interpretation/validation failure: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Controlled interpretation or validation failure",
        ) from exc

    except RuntimeError as exc:
        logger.warning("Controlled service failure: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Controlled internal service failure",
        ) from exc

    except Exception:
        logger.exception("Unexpected internal failure")
        raise HTTPException(
            status_code=500,
            detail="Controlled internal service failure",
        )
