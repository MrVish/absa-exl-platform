from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from mangum import Mangum

from .repository import RecordConflictError, RecordNotFoundError
from .routes import router
from .transitions import ApprovalPreconditionError, IllegalTransitionError


def _error(status: int, code: str, message: str, detail: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "detail": detail}},
    )


def create_app() -> FastAPI:
    app = FastAPI(title="ABSA x EXL Model & Pipeline Registry", version="1.0.0")
    app.include_router(router)

    @app.exception_handler(RecordNotFoundError)
    def _not_found(_: Request, exc: RecordNotFoundError) -> JSONResponse:
        return _error(404, "not_found", str(exc))

    @app.exception_handler(RecordConflictError)
    def _conflict(_: Request, exc: RecordConflictError) -> JSONResponse:
        return _error(409, "conflict", str(exc))

    @app.exception_handler(IllegalTransitionError)
    def _illegal(_: Request, exc: IllegalTransitionError) -> JSONResponse:
        return _error(409, "illegal_transition", str(exc))

    @app.exception_handler(ApprovalPreconditionError)
    def _precondition(_: Request, exc: ApprovalPreconditionError) -> JSONResponse:
        return _error(422, "approval_preconditions", str(exc), {"missing": exc.missing})

    @app.exception_handler(RequestValidationError)
    def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(
            422, "validation_error", "Request validation failed", jsonable_encoder(exc.errors())
        )

    return app


app = create_app()
handler = Mangum(app)
