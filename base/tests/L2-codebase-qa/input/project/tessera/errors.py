"""Exception types. API-facing errors carry the HTTP status and error code they map to."""


class TesseraError(Exception):
    status = 500
    code = "internal_error"

    def to_dict(self):
        return {"error": self.code, "message": str(self) or self.code}


class ValidationError(TesseraError):
    status = 400
    code = "invalid_request"


class JobNotFound(TesseraError):
    status = 404
    code = "job_not_found"


class RunNotFound(TesseraError):
    status = 404
    code = "run_not_found"


class RouteNotFound(TesseraError):
    status = 404
    code = "not_found"


class MethodNotAllowed(TesseraError):
    status = 405
    code = "method_not_allowed"


class InvalidTransition(TesseraError):
    status = 409
    code = "invalid_transition"

    def __init__(self, current, wanted):
        super().__init__("cannot move job from %s to %s" % (current, wanted))
        self.current = current
        self.wanted = wanted


class IdempotencyConflict(TesseraError):
    status = 409
    code = "idempotency_conflict"


class Busy(TesseraError):
    status = 409
    code = "busy"


class RequestTooLarge(TesseraError):
    status = 413
    code = "request_too_large"


class PayloadTooLarge(TesseraError):
    status = 413
    code = "payload_too_large"


class PermanentError(Exception):
    """Raise from a job handler to fail the job without further retries."""


class UnknownJobType(PermanentError):
    pass
