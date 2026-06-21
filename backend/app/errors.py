from __future__ import annotations


class BackendError(Exception):
    status_code = 500


class BadRequestError(BackendError):
    status_code = 400


class ValidationError(BackendError):
    status_code = 422


class ProviderError(BackendError):
    status_code = 502


class NotFoundError(BackendError):
    status_code = 404
