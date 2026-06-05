from __future__ import annotations

from dataclasses import dataclass


EXIT_CODES = {
    "SUCCESS": 0,
    "INVALID_ARGS": 2,
    "AUTH_FAILED": 3,
    "FORBIDDEN": 4,
    "QUERY_SCHEMA_ERROR": 5,
    "UPSTREAM_OR_TIMEOUT": 6,
    "OUTPUT_IO_ERROR": 7,
    "CONFIG_ERROR": 8,
}


@dataclass
class TpCodexError(Exception):
    message: str
    exit_code: int

    def __str__(self) -> str:
        return self.message


class InvalidArgsError(TpCodexError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_CODES["INVALID_ARGS"])


class AuthFailedError(TpCodexError):
    def __init__(self, message: str = "authentication failed") -> None:
        super().__init__(message, EXIT_CODES["AUTH_FAILED"])


class ForbiddenError(TpCodexError):
    def __init__(self, message: str = "forbidden") -> None:
        super().__init__(message, EXIT_CODES["FORBIDDEN"])


class QuerySchemaError(TpCodexError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_CODES["QUERY_SCHEMA_ERROR"])


class UpstreamOrTimeoutError(TpCodexError):
    def __init__(self, message: str = "upstream request failed") -> None:
        super().__init__(message, EXIT_CODES["UPSTREAM_OR_TIMEOUT"])


class OutputIoError(TpCodexError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_CODES["OUTPUT_IO_ERROR"])


class ConfigError(TpCodexError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_CODES["CONFIG_ERROR"])
