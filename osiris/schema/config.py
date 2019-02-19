# Osiris: Build log aggregator.

"""Authentication API schema."""

from marshmallow import fields
from marshmallow import post_load
from marshmallow import Schema

from osiris import DEFAULT_OC_PROJECT


class Config(object):
    """Config model."""

    def __init__(self, api_key: str, token: str, context: str = None, cluster: str = None,
                 namespace: str = None, host: str = None, port: str = None, url: str = None,
                 username: str = None, password: str = None, verify_ssl: bool = None):
        """Initialize Config model."""
        self.api_key: str = api_key
        self.token: str = token

        self.context: str = context
        self.cluster: str = cluster
        self.namespace: str = namespace

        self.host: str = host
        self.port: str = port
        self.url: str = url

        self.username: str = username
        self.password: str = password

        self.verify_ssl: bool = verify_ssl


class ConfigSchema(Schema):
    """Config model schema."""

    api_key = fields.Raw(required=True)
    token = fields.String(required=True)

    context = fields.String(
        required=False)  # if not provided, use localhost
    cluster = fields.String(
        required=False)  # if not provided, use localhost
    namespace = fields.String(
        required=False, default=DEFAULT_OC_PROJECT, allow_none=True)

    host = fields.String(allow_none=True)
    port = fields.String(allow_none=True)
    url = fields.Url(allow_none=True)

    username = fields.String(allow_none=True)
    password = fields.String(allow_none=True)

    verify_ssl = fields.Bool(default=False)

    @post_load
    def make_config(self, data: dict) -> Config:
        """Make Config model from dictionary specification."""
        return Config(**data)
