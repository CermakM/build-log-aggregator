# Osiris: Build log aggregator.

"""OCP API schema."""

from marshmallow import fields
from marshmallow import post_load
from marshmallow import Schema


class OCP(object):
    """OCP model."""

    def __init__(self,
                 kind: str = None,
                 name: str = None,
                 namespace: str = None,
                 self_link: str = None):
        """Initialize OCP model."""
        self.kind = kind

        self.name = name
        self.namespace = namespace

        self.self_link = self_link

    @classmethod
    def from_event(cls, event: "V1Event"):
        """Construct class from Kubernetes V1Event."""
        kind = event.involved_object.kind
        name = event.involved_object.name
        namespace = event.involved_object.namespace

        self_link = event.metadata.self_link

        return cls(
            kind=kind,
            name=name,
            namespace=namespace,
            self_link=self_link
        )

    @classmethod
    def from_resource(cls, resource: "ResourceInstance"):
        """Construct class from OpenShift ResourceInstance."""
        metadata = resource['metadata']

        kind = resource['kind']
        name = metadata['name']
        namespace = metadata['namespace']

        self_link = metadata['selfLink']

        return cls(
            kind=kind,
            name=name,
            namespace=namespace,
            self_link=self_link
        )


class OCPSchema(Schema):
    """OCP model schema."""

    kind = fields.String(required=True)

    name = fields.String(required=True)
    namespace = fields.String(required=True)

    self_link = fields.String(required=False, allow_none=True)

    @post_load
    def make_ocp(self, data: dict) -> OCP:
        """Make OCP model from dictionary specification."""
        return OCP(**data)
