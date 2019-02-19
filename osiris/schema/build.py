# Osiris: Build log aggregator.

"""Build API schema."""

import re

from datetime import datetime
from typing import List, Union

from marshmallow import fields
from marshmallow import post_load
from marshmallow import Schema

from osiris import DEFAULT_OC_LOG_LEVEL
from osiris.schema.ocp import OCP, OCPSchema

from kubernetes.client.models.v1_event import V1Event as Event
from openshift.dynamic.client import ResourceInstance

from thoth.common.helpers import _DATETIME_FORMAT_STRING  # noqa


class BuildInfo(object):
    """BuildInfo model."""

    def __init__(self,
                 build_id: str = None,
                 build_status: str = None,
                 build_url: str = None,
                 build_log_url: str = None,
                 ocp_info: OCP = None,
                 first_timestamp: datetime = None,
                 last_timestamp: datetime = None,
                 log_level: int = None):
        """Initialize BuildInfo model."""
        self.build_id = build_id
        self.build_status = build_status

        self.build_url = build_url
        self.build_log_url = build_log_url

        self.ocp_info = ocp_info

        self.first_timestamp = first_timestamp
        self.last_timestamp = last_timestamp

        self.log_level = log_level or DEFAULT_OC_LOG_LEVEL

    @classmethod
    def from_event(cls, event: Event, build_id: str = None, **kwargs):
        """Create BuildInfo model from kubernetes event."""
        ocp = OCP.from_event(event)

        return cls(
            build_id=build_id or event.involved_object.name,
            build_status=event.reason,
            first_timestamp=event.first_timestamp,
            last_timestamp=event.last_timestamp,
            ocp_info=ocp,
            **kwargs
        )

    @classmethod
    def from_resource(cls, resource: Union[dict, ResourceInstance], build_id: str = None, **kwargs):
        """Create BuildInfo model from kubernetes event."""
        ocp = OCP.from_resource(resource)

        metadata = resource['metadata']
        status = resource['status']

        datetime_fmt = "%Y-%m-%dT%H:%M:%SZ"
        try:  # might be missing if build is in Pending state
            start_ts = datetime.strptime(status['startTimestamp'], datetime_fmt)
            end_ts = datetime.strptime(status['completionTimestamp'], datetime_fmt)
        except KeyError:
            start_ts = None
            end_ts = None

        return cls(
            build_id=build_id or metadata['name'],
            build_status=status['phase'],
            # TODO: use `format_datetime` from thoth.common when available in PyPI
            first_timestamp=start_ts,
            last_timestamp=end_ts,
            ocp_info=ocp,
            **kwargs
        )

    def build_complete(self) -> bool:
        """Return whether build has completed.

        Failed builds are considered completed, too.
        """
        return bool(re.match(r"complete|fail", self.build_status, re.IGNORECASE))


class BuildLog(object):
    """BuildLog model."""

    def __init__(self, data: str, metadata: dict = None):
        """Initialize BuildLog model."""
        self.data = data
        self.metadata = metadata


class BuildInfoSchema(Schema):
    """BuildInfo model schema."""

    build_id = fields.String(required=True)
    build_status = fields.String(required=True)

    build_url = fields.Url(required=False, allow_none=True)
    build_log_url = fields.Url(required=False, allow_none=True)

    ocp_info = fields.Nested(OCPSchema, required=False)

    first_timestamp = fields.DateTime(required=False, format=_DATETIME_FORMAT_STRING)
    last_timestamp = fields.DateTime(required=False, format=_DATETIME_FORMAT_STRING)

    log_level = fields.Integer(required=False)

    @post_load
    def make_build_info(self, data: dict) -> BuildInfo:
        """Make BuildInfo model from dictionary specification."""
        return BuildInfo(**data)


class BuildInfoPagination(object):
    """BuildInfoPagination model."""

    RESULTS_PER_PAGE = 20

    def __init__(self,
                 build_info_list: List[BuildInfo] = None,
                 total: int = None,
                 has_next: bool = None,
                 has_prev: bool = None):
        """Initialize BuildInfoPagination model."""
        self.build_info = build_info_list

        self.total = total
        self.has_next = has_next
        self.has_prev = has_prev


class BuildInfoPaginationSchema(Schema):
    """BuildInfoPagination model schema."""

    build_info = fields.Nested(BuildInfoSchema, many=True)

    total = fields.Integer(required=True)
    has_next = fields.Bool(required=False, default=False)
    has_prev = fields.Bool(required=False, default=False)


class BuildLogSchema(Schema):
    """BuildLog model schema."""

    data = fields.String(required=True)
    metadata = fields.Raw(required=False)
