from http import HTTPStatus

from fastapi import FastAPI
from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Body of every error raised by the application's own business rules.

    `detail` mirrors FastAPI's own error key, `code` is a stable machine-readable
    identifier clients can switch on. Request validation errors keep FastAPI's default
    422 format.
    """

    detail: str
    code: str


class DomainError(Exception):
    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "internal_error"
    message: str = "Internal error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class NotFoundError(DomainError):
    status_code = HTTPStatus.NOT_FOUND
    code = "not_found"
    message = "Resource not found"


class ConflictError(DomainError):
    status_code = HTTPStatus.CONFLICT
    code = "conflict"
    message = "Conflict"


class CustomerNotFoundError(NotFoundError):
    code = "customer_not_found"
    message = "Customer not found"


class DeviceNotFoundError(NotFoundError):
    code = "device_not_found"
    message = "Device not found"


class DuplicateEmailError(ConflictError):
    code = "duplicate_email"
    message = "A customer with this email already exists"


class DuplicateSerialNumberError(ConflictError):
    code = "duplicate_serial_number"
    message = "A device with this serial number already exists"


class CustomerDeletedError(ConflictError):
    code = "customer_deleted"
    message = "The owning customer has been deleted"


class DeviceNotActiveError(ConflictError):
    code = "device_not_active"
    message = "Measurements can only be ingested for ACTIVE devices"


class MeasurementConflictError(ConflictError):
    code = "measurement_conflict"
    message = (
        "A measurement with the same device, type and timestamp already exists "
        "with a different value or unit"
    )


class InvalidTimeRangeError(DomainError):
    status_code = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "invalid_time_range"
    message = "timestamp_after must not be later than timestamp_before"


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(detail=exc.message, code=exc.code).model_dump(),
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI's 422 response, minus the echoed `input`.

    FastAPI's default handler copies each error's `input` (the offending value) into the
    body. For `NaN`/`Infinity` that value is a non-finite float, which JSON cannot represent,
    so serialising the error itself crashed with a 500 instead of answering 422. Not echoing
    the caller's raw input back is also the safer default.
    """
    assert isinstance(exc, RequestValidationError)
    errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
