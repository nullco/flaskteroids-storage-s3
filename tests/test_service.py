import base64
import hashlib
import io

import pytest
from botocore.exceptions import ClientError
from flaskteroids.storage import IntegrityError, StorageError

from flaskteroids_storage_s3 import S3Service

KEY = "a" * 28
DATA = b"file contents"
CHECKSUM = base64.b64encode(hashlib.md5(DATA, usedforsecurity=False).digest()).decode()


def test_s3_service_supports_upload_download_and_idempotent_delete(mocker):
    client = mocker.Mock()
    client.get_object.return_value = {"Body": io.BytesIO(DATA)}
    service = S3Service(bucket="uploads", client=client)
    service.upload(KEY, DATA, checksum=CHECKSUM, content_type="text/plain")
    client.put_object.assert_called_once_with(
        Bucket="uploads",
        Key=KEY,
        Body=DATA,
        ContentMD5=CHECKSUM,
        ContentType="text/plain",
    )
    assert service.download(KEY) == DATA
    service.delete(KEY)
    client.delete_object.assert_called_once_with(Bucket="uploads", Key=KEY)


def test_s3_rejects_bad_checksum_and_keys_before_contacting_service(mocker):
    client = mocker.Mock()
    service = S3Service(bucket="uploads", client=client)
    with pytest.raises(IntegrityError):
        service.upload(KEY, DATA, checksum="incorrect", content_type="text/plain")
    with pytest.raises(StorageError):
        service.delete("../secret")
    client.put_object.assert_not_called()
    client.delete_object.assert_not_called()


def test_s3_configuration_maps_to_sdk_options(mocker):
    client = mocker.patch("boto3.client")
    S3Service(
        bucket="uploads",
        region="test-region",
        endpoint="https://s3.example.com",
        access_key_id="key",
        secret_access_key="secret",
        force_path_style=True,
    )
    assert client.call_args.args == ("s3",)
    options = client.call_args.kwargs
    assert options["region_name"] == "test-region"
    assert options["aws_access_key_id"] == "key"
    assert options["aws_secret_access_key"] == "secret"
    assert options["endpoint_url"] == "https://s3.example.com"
    assert options["config"].s3["addressing_style"] == "path"


def test_s3_existence_propagates_permission_errors(mocker):
    client = mocker.Mock()
    service = S3Service(bucket="uploads", client=client)
    client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadObject"
    )
    assert not service.exist(KEY)
    client.head_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "HeadObject"
    )
    with pytest.raises(ClientError):
        service.exist(KEY)
