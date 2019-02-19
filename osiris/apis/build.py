# Osiris: Build log aggregator.

"""Namespace: build."""

from http import HTTPStatus
from typing import Union

from flask import request
from flask import url_for

from flask_restplus import fields
from flask_restplus import Namespace
from flask_restplus import Resource

from kubernetes.client import ApiClient
from kubernetes.client.models.v1_event import V1Event

from marshmallow import ValidationError

from osiris import DEFAULT_OC_LOG_LEVEL
from osiris.aggregator import build_aggregator
from osiris.apis.model import response
from osiris.response import request_accepted
from osiris.response import request_ok
from osiris.response import bad_request

from osiris.schema.build import BuildInfo, BuildInfoSchema, BuildLogSchema
from osiris.schema.build import BuildInfoPagination, BuildInfoPaginationSchema

from osiris.exceptions import OCError

from werkzeug.exceptions import HTTPException, InternalServerError


api = Namespace(name='build', description="Namespace for build triggers.")


@api.errorhandler(OCError)
@api.errorhandler(ValidationError)
def propagate_build_error(
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


build_fields = api.model('build_fields', {
    'build_id': fields.String(
        required=True,
        description="Unique build identification.",
        example="osiris-api-1"
    ),
    'build_status': fields.String(
        required=True,
        description="Status of the build.",
        example="BuildStarted"
    ),
    'build_url': fields.Url(
        required=False,
        description="URL to the OCP pod.",
    ),
    'build_log_url': fields.Url(
        required=False,
        description="URL to build logs.",
    ),
    'ocp_info': fields.Raw(
        required=False,
        description="OCP build-related information.",
    ),
})

build_response = api.inherit('build_response', response, {
    'payload': fields.Nested(build_fields)
})

build_log_fields = api.model('build_log_fields', {
    'data': fields.String(
        required=True,
        description="Build log data."
    ),
    'metadata': fields.Raw(
        required=False,
        description="Build log metadata."
    )
})

build_log_response = api.inherit('build_response', response, {
    'payload': fields.Nested(build_log_fields)
})


# status

@api.route('/status/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildStatusResource(Resource):
    """Build status endpoint."""

    # noinspection PyMethodMayBeStatic
    def get(self, build_id):
        """Return status of the given build."""
        _, build_info = build_aggregator.retrieve_build_data(build_id)

        return request_ok(payload={
            'build_status': build_info.build_status
        })


# info

@api.route('/info/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildInfoResource(Resource):
    """Build information endpoint."""

    # noinspection PyMethodMayBeStatic
    @api.marshal_with(build_response)
    @api.response(code=HTTPStatus.OK,
                  description="Retrieve stored information about build "
                              "specified by unique build id.",
                  model=build_response)
    def get(self, build_id):
        """Return complete information stored about given build."""
        schema = BuildInfoSchema()
        _, build_info = build_aggregator.retrieve_build_data(build_id)

        return request_ok(payload=schema.dump(build_info))


@api.route('/info/page', defaults={'page': 1})
@api.route('/info/page/<int:page>')
class BuildInfoListingResource(Resource):
    """Build information endpoint."""

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.OK,
                  description="Paginate build information documents."
                  )
    def get(self, page):
        """Paginate build information documents stored in Ceph."""
        schema = BuildInfoPaginationSchema()
        paginated_data: BuildInfoPagination = build_aggregator.paginate_build_data(page)

        return request_ok(payload=schema.dump(paginated_data))


# logs

@api.route('/logs/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildLogResource(Resource):
    """Build log endpoint."""

    # noinspection PyMethodMayBeStatic
    @api.marshal_with(response)
    @api.response(code=HTTPStatus.OK,
                  description="Retrieve stored build logs"
                              "for given build id.",
                  )
    @api.doc(responses={
        s.value: s.description for s in [
            HTTPStatus.OK,
            HTTPStatus.BAD_REQUEST
        ]})
    def get(self, build_id):
        """Return logs stored by the given build."""
        build_log, = build_aggregator.retrieve_build_data(build_id, log_only=True)

        # TODO: return the whole doc or just the build log?
        return request_ok(
            payload=build_log
        )

    @api.param(name='force', description="Overwrite existing logs (default 1).")
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    @api.expect(build_log_fields)
    def put(self, build_id):
        """Store logs for the given build in Ceph."""
        build_log, build_info = build_aggregator.retrieve_build_data(build_id)

        if build_log is not None and not int(request.args.get('force', 1)):

            return bad_request(
                errors={
                    'BuildLogExists': f"Build log `{build_id}` already exists"
                                      " and `force` is not specified."
                }
            )

        build_doc, _ = BuildInfoSchema().dump(build_info)

        build_log_schema = BuildLogSchema()
        build_log, validation_errors = build_log_schema.load(request.json)

        if not build_info.build_complete():
            resp = bad_request(
                errors={
                    'BuildNotCompleted': "Build has not been completed yet.",
                },
                validation_errors=validation_errors
            )

        else:
            if 'build_id' not in build_log['metadata']:
                build_log['metadata']['build_id'] = build_id

            build_doc['build_log'] = build_log

            build_aggregator.store_build_data(build_doc)

            resp = request_ok()

        return resp


# triggers

@api.route('/started/build_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildStartedResource(Resource):
    """Receiver hook for started builds.

    This endpoint expects data as BuildInfoSchema.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    @api.expect(build_fields)
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build start hook."""
        # TODO: run all of the following ops asynchronously
        errors = {}

        build_schema = BuildInfoSchema()
        build_data: dict = request.json

        if build_data['build_id'] != build_id:
            errors['build_data'] = "`build_id` field does not match given url."

        validation_errors = build_schema.validate(build_data)

        if not errors:  # validation errors other than build_id are permitted for now
            # store in Ceph
            build_data['build_log'] = None
            build_aggregator.store_build_data(build_data)

            return request_accepted(errors=validation_errors)

        else:
            errors.update(validation_errors)

            return bad_request(errors=errors)


@api.route('/started/event_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildStartedEventResource(Resource):
    """Receiver hook for started builds.

    This endpoint expects data as kubernetes V1Event.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build start hook."""
        build_schema = BuildInfoSchema()

        kube_client = ApiClient()

        event: V1Event = kube_client.deserialize(request, response_type='V1Event')
        build_data, validation_errors = build_schema.dump(
            BuildInfo.from_event(event, build_id)
        )

        # store in Ceph
        build_data['build_log'] = None
        build_aggregator.store_build_data(build_data)

        return request_accepted(errors=validation_errors)


@api.route('/started/<string:build_id>')
@api.route('/started/thoth_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildStartedEventResource(Resource):
    """Receiver hook for started builds.

    This endpoint expects data as returned by Thoth OpenShift API.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build start hook."""
        build_schema = BuildInfoSchema()

        build_data, validation_errors = build_schema.dump(
            BuildInfo.from_resource(request.json, build_id)
        )

        # store in Ceph
        build_data['build_log'] = None
        build_aggregator.store_build_data(build_data)

        return request_accepted(errors=validation_errors)


@api.route('/completed/build_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildCompletedResource(Resource):
    """Receiver hook for completed builds.

    When the build is marked completed and this endpoint
    is triggered, the aggregator will automatically gather
    logs for the given build.

    This endpoint expects data as BuildInfoSchema.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    @api.expect(build_fields)
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build completion hook."""
        log_level: int = request.args.get('log_level', DEFAULT_OC_LOG_LEVEL)

        build_data: dict = request.json
        validation_errors = _on_build_completed(
            build_id, build_data, get_build_log=request.args.get('mode', 'remote') == 'cluster', log_level=log_level)

        return request_accepted(errors=validation_errors)


@api.route('/completed/event_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildCompletedEventResource(Resource):
    """Receiver hook for completed builds.

    When the build is marked completed and this endpoint
    is triggered, the aggregator will automatically gather
    logs for the given build.

    This endpoint expects data as kubernetes V1Event.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build completion hook."""
        log_level: int = request.args.get('log_level', DEFAULT_OC_LOG_LEVEL)

        build_schema = BuildInfoSchema()

        kube_client = ApiClient()

        event: V1Event = kube_client.deserialize(request, response_type='V1Event')
        build_data, _ = build_schema.dump(
            BuildInfo.from_event(event, build_id)
        )

        # TODO: handle validation errors
        validation_errors = _on_build_completed(
            build_id, build_data, get_build_log=request.args.get('mode', 'remote') == 'cluster', log_level=log_level)

        return request_accepted(errors=validation_errors)


@api.route('/completed/<string:build_id>')
@api.route('/completed/thoth_schema/<string:build_id>')
@api.param('build_id', 'Unique build identification.')
class BuildCompletedThothResource(Resource):
    """Receiver hook for completed builds.

    When the build is marked completed and this endpoint
    is triggered, the aggregator will automatically gather
    logs for the given build.

    This endpoint expects data as returned by Thoth OpenShift API.
    """

    # noinspection PyMethodMayBeStatic
    @api.response(code=HTTPStatus.ACCEPTED,
                  description="Request has been accepted."
                              "Document will be stored in Ceph",
                  )
    @api.response(code=HTTPStatus.BAD_REQUEST,
                  description="Request could not be processed due to invalid data"
                              " or missing build identification."
                  )
    def put(self, build_id: str = None):  # pragma: no cover
        """Trigger build completion hook."""
        log_level: int = request.args.get('log_level', DEFAULT_OC_LOG_LEVEL)

        build_schema = BuildInfoSchema()

        build_data, _ = build_schema.dump(
            BuildInfo.from_resource(request.json, build_id)
        )

        # TODO: handle validation errors
        validation_errors = _on_build_completed(
            build_id, build_data, get_build_log=request.args.get('mode', 'remote') == 'cluster', log_level=log_level)

        return request_accepted(errors=validation_errors)


def _on_build_completed(build_id: str,
                        build_data: dict,
                        get_build_log=False,
                        log_level: int = DEFAULT_OC_LOG_LEVEL):
    """Update Ceph build data.

    :returns: validation errors produced by BuildInfoSchema schema validation.
    """
    # TODO: run all of the following ops asynchronously
    build_schema = BuildInfoSchema()

    build_info: BuildInfo
    _, build_info = build_aggregator.retrieve_build_data(build_id)

    build_info.build_status = build_data['build_status']
    build_info.build_log_url = url_for(
        'build_build_log_resource', build_id=build_id, _external=True)

    build_doc, validation_errors = build_schema.dump(build_info)

    if get_build_log:
        # get build log from relevant pod (requires OpenShift authentication)
        build_log: str = build_aggregator.get_build_log(
            build_id,
            namespace=build_info.ocp_info.namespace,
            log_level=log_level
        )

        build_doc['build_log'] = build_log

    # store in Ceph
    build_aggregator.store_build_data(build_doc)

    return validation_errors
