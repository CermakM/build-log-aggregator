# Osiris: Build log aggregator.

"""Default API response specifications."""

import typing

from http import HTTPStatus
from marshmallow import MarshalResult

from osiris.schema.base import Base, BaseSchema


__schema__ = BaseSchema()


def status(http_status: HTTPStatus):
    """API response wrapper.

    This decorator can be used to assemble custom payloads
    with default keys common to all responses.
    """
    def wrapper(fun: typing.Callable[..., dict] = None):

        def inner(*args, **kwargs) -> typing.Tuple[dict, HTTPStatus]:
            base = Base(http_status)

            response = __schema__.dump(base)

            payload, errors, extras = fun(*args, **kwargs)

            response.data.update(extras or {})
            response.errors.update(errors or {})

            if isinstance(payload, MarshalResult):
                response.data.update({'payload': payload.data})
                response.errors.update(payload.errors)

            else:
                response.data.update({'payload': payload or {}})

            # noinspection PyProtectedMember
            return response._asdict(), http_status.value

        return inner

    return wrapper


# Syntactic sugar for some of common payloads follows

@status(HTTPStatus.OK)
def request_ok(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for status OK.

    Request fulfilled, document follows.
    """
    return payload, errors, kwargs


@status(HTTPStatus.ACCEPTED)
def request_accepted(payload=None, errors=None, **kwargs) -> tuple:
    """API response for accepted put_request.

    Request accepted, processing continues off-line.
    """
    return payload, errors, kwargs


@status(HTTPStatus.CREATED)
def request_created(payload=None, errors=None, **kwargs) -> tuple:
    """API response for created put_request.

    Document created, URL follows.
    """
    return payload, errors, kwargs


@status(HTTPStatus.UNAUTHORIZED)
def request_not_authorized(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for unauthorized put_request.

    No permission -- see authorization schemes.
    """
    return payload, errors, kwargs


@status(HTTPStatus.NETWORK_AUTHENTICATION_REQUIRED)
def request_not_authenticated(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for unauthenticated put_request.

    Network Authentication Required,
    The client needs to authenticate to gain network access
    """
    return payload, errors, kwargs


@status(HTTPStatus.FORBIDDEN)
def request_forbidden(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for forbidden put_request.

    Request forbidden -- authorization will not help.
    """
    return payload, errors, kwargs


@status(HTTPStatus.BAD_REQUEST)
def bad_request(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for bad put_request.

    Bad put_request syntax or unsupported method.
    """
    return payload, errors, kwargs


@status(HTTPStatus.SERVICE_UNAVAILABLE)
def request_unavailable(payload=None, errors=None, **kwargs) -> tuple:  # pragma: no cover
    """API response for bad put_request.

    The server cannot process the put_request at the moment.
    """
    return payload, errors, kwargs
