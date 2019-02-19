# Osiris: Build log aggregator.

"""Base API schema."""

from http import HTTPStatus

from marshmallow import fields
from marshmallow import Schema

from osiris import ABOUT
from osiris.utils import format_status_message


# Model: Status

class AppData(object):
    """AppData model."""

    def __init__(self):
        """Initialize AppData model."""
        self.name = ABOUT['__title__']
        self.version = ABOUT['__version__']


class AppDataSchema(Schema):
    """AppData model schema."""

    name = fields.String(required=True)
    version = fields.String(required=True)


class Status(object):
    """Status model."""

    def __init__(self, status: HTTPStatus):
        """Initialize Status model."""
        self.code = status.value
        self.phrase = status.phrase
        self.description = status.description
        self.message = format_status_message(status)


class StatusSchema(Schema):
    """Status model schema."""

    code = fields.Integer(required=True)
    phrase = fields.String()
    description = fields.String()
    message = fields.String()


# Model: Base

class Base(object):
    """Base model."""

    def __init__(self, status: HTTPStatus):
        """Initialize Base model."""
        self.app_data = AppData()
        self.status = Status(status)

        self.output = None
        self.errors = None

        self.payload = None


class BaseSchema(Schema):
    """Base model schema.

    This schema is inhereted and marshalled by all schemas
    and used for each API payload.
    """

    app_data = fields.Nested(AppDataSchema)
    status = fields.Nested(StatusSchema)

    output = fields.Raw()  # oc-client output
    errors = fields.Raw()  # cli, parsing or other types of errors

    payload = fields.Raw()
