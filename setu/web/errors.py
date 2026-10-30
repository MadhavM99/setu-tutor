"""API errors: a fixed machine code plus a Hindi message key (api-and-tool-contracts.md Part B).

Learners never see the code; the UI renders the message key from the Hindi catalog (slice 1.6).
"""
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, status: int = 400):
        self.code, self.status = code, status


def body(code: str) -> dict:
    return {"error": code, "message_key": f"err.{code}"}


async def api_error_handler(_request: Request, exc: ApiError):
    return JSONResponse(body(exc.code), status_code=exc.status)


async def validation_error_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(body("validation"), status_code=400)
