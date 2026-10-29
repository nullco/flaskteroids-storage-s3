import pytest
from flaskteroids.testing import StorageServiceContract

from flaskteroids_storage_s3 import S3Service
from tests.storage_client import StorageClient


class TestS3Service(StorageServiceContract):
    @pytest.fixture
    def storage_service(self):
        return S3Service(bucket="uploads", client=StorageClient())
