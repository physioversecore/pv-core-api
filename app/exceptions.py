import logging
import traceback
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from prisma.errors import PrismaError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.logging_config import logger
from app.middleware import request_id_var


def _error_response(status: int, message: str, errors: list | None = None, exc: Exception | None = None) -> JSONResponse:
    body: dict = {
        "success": False,
        "message": message,
        "requestId": request_id_var.get(""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_response(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for err in exc.errors():
            loc = " → ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Invalid value")
            errors.append({"field": loc, "message": msg})
        return _error_response(422, "Validation error", errors=errors)

    @app.exception_handler(JWTError)
    async def jwt_exception_handler(request: Request, exc: JWTError) -> JSONResponse:
        return _error_response(401, "Invalid or expired token")

    @app.exception_handler(PrismaError)
    async def prisma_exception_handler(request: Request, exc: PrismaError) -> JSONResponse:
        logger.error("database error", exc_info=exc, extra={"request_id": request_id_var.get("")})
        return _error_response(500, "A database error occurred")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unhandled exception",
            exc_info=exc,
            extra={"request_id": request_id_var.get("")},
        )
        return _error_response(500, "An internal server error occurred")
