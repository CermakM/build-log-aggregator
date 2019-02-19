# Osiris: Build log aggregator.

"""Namespace: auth."""

from http import HTTPStatus
from pathlib import Path
from typing import Union

from flask_restplus import fields
from flask_restplus import Namespace
from flask_restplus import Resource

from marshmallow import ValidationError

from openshift.config import list_kube_config_contexts

from osiris import get_oc_client

from osiris.apis.model import response
from osiris.schema.config import ConfigSchema

from osiris.response import request_ok

from osiris.exceptions import OCError

from werkzeug.exceptions import HTTPException, InternalServerError


api = Namespace(name='config',
                description="Namespace for API configuration.",
                validate=True)


@api.errorhandler(ValidationError)
def propagate_validation_error(
        error: Union[OCError, ValidationError]):
    """Propagate login error to the global app error handler."""
    raise error  # re-raise


@api.errorhandler(HTTPException)
@api.errorhandler(InternalServerError)
def propagate_internal_server_error(
        error: Union[HTTPException, InternalServerError]):
    """Propagate internal server error to the global app error handler."""
    raise error  # re-raise


@api.errorhandler(Exception)
def propagate_unknown_exception(error: Exception):
    """Propagate unknown exception to the global app error handler."""
    raise error  # re-raise


config_fields = api.model('config_fields', {
    'api_key': fields.Raw(
        required=True,
        description="API authentication header.",
        example={"authorization": "<token>"}
    ),
    'context': fields.String(
        required=True,
        description="Current context",
        example="<namespace>/<cluster>/<username>"
    ),
    'host': fields.String(
        required=False,
        description="Host the user is currently logged into.",
        example="<host>:<port>"
    ),
    'namespace': fields.String(
        required=False,
        description="Current Namespace.",
        example="<namespace>"
    ),
    'verify_ssl': fields.Boolean(
        required=False,
        description="Whether to verify SSL",
        example=False
    ),
})

config_response = api.inherit('config_response', response, {
    'payload': fields.Nested(config_fields)
})


@api.route("/config")
class ConfigResource(Resource):
    """Authentication endpoint."""

    @api.marshal_with(config_response)
    @api.doc(responses={
        s.value: s.description for s in [
            HTTPStatus.OK,
        ]})
    def get(self):
        """Get current client configuration."""
        schema = ConfigSchema()

        client = get_oc_client()
        client_config = client.ocp_client.configuration
        client_config.token = client.token

        errors = dict()

        try:
            _, context = list_kube_config_contexts()

            client_config.context = context['name']
            client_config.cluster = context['context']['cluster']
            client_config.namespace = context['context']['namespace']
            client_config.username, _ = context['context']['user'].split('/')

        except (FileNotFoundError, KeyError) as exc:
            errors['context'] = str(exc)

            if client.in_cluster:
                client_config.namespace = Path(
                    "/run/secrets/kubernetes.io/serviceaccount/namespace"
                ).read_text()
            else:
                client_config.namespace = client.middletier_namespace

        return request_ok(
            payload=schema.dump(client_config.__dict__),
            errors=errors
        )
