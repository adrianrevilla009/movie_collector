"""Formato de error estandar RFC 7807 (Seccion 2.6): nunca {"error": "..."} ad-hoc."""

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger("api.errors")


def problem_response(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://cine-platform.local/errors/{status_code}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return problem_response(exc.status_code, exc.detail, exc.detail, str(request.url))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return problem_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Error de validacion",
            "El cuerpo o los parametros de la peticion no son validos",
            str(request.url),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        # Nunca se filtran detalles internos (rutas, stack traces) al cliente
        # (ver security-antipatterns); se loguea completo server-side.
        logger.error("unhandled_exception", path=str(request.url), error=str(exc))
        return problem_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Error interno",
            "Ha ocurrido un error inesperado",
            str(request.url),
        )
