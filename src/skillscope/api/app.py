"""FastAPI driving adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse

from skillscope.api.schemas import (
    ConversationPageResponse,
    ConversationResponse,
    ErrorResponse,
    StoreMetadataResponse,
)
from skillscope.application.queries import (
    ConversationNotFoundError,
    GetConversation,
    GetStoreMetadata,
    InvalidPaginationError,
    ListConversations,
    PageRequest,
    StoreError,
)


def _error(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, details=None)
    return JSONResponse(status_code=status, content=body.model_dump())


def create_app(
    *,
    list_conversations: ListConversations,
    get_conversation: GetConversation,
    get_store_metadata: GetStoreMetadata,
    static_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Skillscope API", version="1.0.0")

    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found(
        _request: Request,
        _exc: ConversationNotFoundError,
    ) -> JSONResponse:
        return _error(404, "conversation_not_found", "Conversation not found.")

    @app.exception_handler(InvalidPaginationError)
    async def invalid_pagination(
        _request: Request,
        _exc: InvalidPaginationError,
    ) -> JSONResponse:
        return _error(
            400,
            "invalid_pagination",
            "The pagination parameters are invalid.",
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        return _error(
            400,
            "invalid_pagination",
            "The pagination parameters are invalid.",
        )

    @app.exception_handler(StoreError)
    async def store_error(_request: Request, exc: StoreError) -> JSONResponse:
        messages = {
            "store_missing": "The Skillscope snapshot store does not exist.",
            "store_incompatible": "The Skillscope snapshot store is incompatible.",
            "store_unreadable": "The Skillscope snapshot store cannot be read.",
        }
        return _error(503, exc.code, messages[exc.code])

    @app.get(
        "/api/v1/conversations",
        response_model=ConversationPageResponse,
        responses={
            400: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def list_route(
        cursor: str | None = Query(default=None, min_length=1),
        limit: int = Query(default=50),
    ) -> ConversationPageResponse:
        result = list_conversations(PageRequest(cursor=cursor, limit=limit))
        return ConversationPageResponse.model_validate(result)

    @app.get(
        "/api/v1/conversations/{conversation_id}",
        response_model=ConversationResponse,
        responses={
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    def detail_route(conversation_id: str) -> ConversationResponse:
        return ConversationResponse.model_validate(get_conversation(conversation_id))

    @app.get(
        "/api/v1/meta",
        response_model=StoreMetadataResponse,
        responses={503: {"model": ErrorResponse}},
    )
    def metadata_route() -> StoreMetadataResponse:
        return StoreMetadataResponse.model_validate(get_store_metadata())

    if static_dir and static_dir.is_dir():
        static_root = static_dir.resolve()
        index_path = static_root / "index.html"

        @app.api_route(
            "/{path:path}",
            methods=["GET"],
            include_in_schema=False,
        )
        async def spa_fallback(request: Request, path: str) -> Any:
            if path.startswith("api/"):
                return _error(404, "not_found", "API endpoint not found.")
            file_path = (static_root / path).resolve()
            if path and file_path.is_relative_to(static_root) and file_path.is_file():
                return FileResponse(file_path)
            if index_path.is_file():
                return FileResponse(index_path)
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

    def contract_openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            schema = get_openapi(
                title=app.title,
                version=app.version,
                routes=app.routes,
            )
            for path, operations in schema.get("paths", {}).items():
                if not path.startswith("/api/v1/"):
                    continue
                for operation in operations.values():
                    if isinstance(operation, dict):
                        operation.get("responses", {}).pop("422", None)
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = contract_openapi
    return app
