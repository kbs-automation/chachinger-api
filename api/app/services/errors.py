from typing import Any


class DomainError(Exception):
    """Raised by services; rendered as {"detail": {"code", "message", ...extra}}."""

    def __init__(
        self, status_code: int, code: str, message: str, extra: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}

    def to_detail(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.extra}


def not_found(what: str) -> DomainError:
    return DomainError(404, f"{what}_not_found", f"{what.replace('_', ' ').capitalize()} not found")
