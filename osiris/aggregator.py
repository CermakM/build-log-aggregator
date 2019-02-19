
"""Build aggregator."""

import hashlib

from boto3.resources.factory import ServiceResource
from botocore.paginate import Paginator

from typing import Tuple, Union

from thoth.storages.result_base import ResultStorageBase

from osiris import DEFAULT_OC_LOG_LEVEL
from osiris import get_oc_client

from osiris.schema.build import BuildLog
from osiris.schema.build import BuildInfo, BuildInfoSchema
from osiris.schema.build import BuildInfoPagination

# TODO: logging


class _BuildLogsAggregator(ResultStorageBase):

    RESULT_TYPE = 'build_aggregator'

    __PAGINATION_TOKEN__ = None
    __PAGINATION_COUNT__ = 0
    __COUNT__ = 0

    def __init__(self, *args, **kwargs):

        super(_BuildLogsAggregator, self).__init__(*args, **kwargs)

    def count(self):
        """Get total number of documents in the Ceph storage."""
        # noinspection PyProtectedMember
        return sum(
            1 for _ in
            self.ceph._s3.Bucket(self.ceph.bucket)  # pylint: disable=protected-access
                .objects
                .filter(Prefix=self.prefix)
                .all()
        )

    def connect(self):

        super().connect()

        _BuildLogsAggregator.__COUNT__ = self.count()

    def purge_build_data(self, prefix: str = None):
        """Purge build log documents stored in Ceph bucket.

        [WARNING] All data from the bucket will be LOST!
        """
        # noinspection PyProtectedMember
        bucket = self.ceph._s3.Bucket(self.ceph.bucket)
        # delete all objects in the bucket by the given prefix
        bucket.objects.filter(Prefix=prefix or self.prefix) \
                      .all() \
                      .delete()

        self.__COUNT__ = 0
        self.__PAGINATION_TOKEN__ = None

    def store_build_data(self, build_doc: dict):
        """Store the build log document in Ceph."""
        blob = self.ceph.dict2blob(build_doc)
        build_id: str = build_doc['build_id']

        document_id: str = hashlib.sha256(build_id.encode('utf-8')).hexdigest()

        self.ceph.store_blob(blob, document_id)

        _BuildLogsAggregator.__COUNT__ += 1

    def retrieve_build_data(
            self, build_id: str, log_only=False) -> Union[Tuple[BuildLog, ],
                                                          Tuple[BuildLog, BuildInfo]]:
        """Retrieve build log document from Ceph by its id."""
        document_id: str = hashlib.sha256(build_id.encode('utf-8')).hexdigest()

        build_doc: dict = self.ceph.retrieve_document(document_id)

        build_log_data = build_doc.pop('build_log')

        if isinstance(build_log_data, dict):
            build_log = BuildLog(**build_log_data)
        else:
            build_log = BuildLog(data=build_log_data)

        ret: tuple = (build_log, )

        if not log_only:
            build_info = BuildInfo(**BuildInfoSchema().load(build_doc).data)

            ret = build_log, build_info

        return ret

    def paginate_build_data(self, page: int) -> BuildInfoPagination:
        """Paginate build information stored in Ceph."""
        if page == 1:
            # reset pagination
            self.__COUNT__ = self.count()
            self.__PAGINATION_COUNT__ = 0

            _BuildLogsAggregator.__PAGINATION_TOKEN__ = None

        result_list = []

        if self.__COUNT__ > 0:

            # noinspection PyProtectedMember
            resource: ServiceResource = self.ceph._s3  # pylint: disable=protected-access

            s3_client = resource.meta.client

            paginator: Paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.ceph.bucket,
                Prefix=self.ceph.prefix,
                PaginationConfig={
                    'MaxItems': BuildInfoPagination.RESULTS_PER_PAGE,
                    'StartingToken': self.__PAGINATION_TOKEN__
                }
            )

            schema = BuildInfoSchema()
            for page_content in page_iterator:
                for obj in page_content['Contents']:
                    _, key = obj['Key'].rsplit('/', 1)

                    data = self.ceph.retrieve_document(key)
                    parsed_data, errors = schema.load(data)

                    result_list.append(
                        # ignore validation errors here
                        parsed_data
                    )

                    _BuildLogsAggregator.__PAGINATION_TOKEN__ = page_iterator.resume_token

            self.__PAGINATION_COUNT__ += len(result_list)

        build_info_pagination = BuildInfoPagination(
            result_list,
            total=self.__COUNT__,
            has_next=self.__PAGINATION_COUNT__ < self.__COUNT__,
            has_prev=page > 1  # assume that next pages wouldn't be shown otherwise
        )

        return build_info_pagination

    @staticmethod
    def get_build_log(build_id: str,
                      namespace: str,
                      log_level: int = DEFAULT_OC_LOG_LEVEL) -> str:
        """Curl OCP for build log for the given build.

        :raises OCError: In case of OC CLI failure.
        """
        client = get_oc_client()

        logs = client.get_build_log(  # TODO: can log level be modified?
            build_id=build_id,
            namespace=namespace
        )

        return logs


build_aggregator = _BuildLogsAggregator()
build_aggregator.connect()
