import io

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from flaskteroids_storage_s3 import S3Service

KEY = "a" * 28


@pytest.fixture
def sdk():
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def test_storage_operations_match_the_botocore_request_contract(sdk):
    service = S3Service(bucket="uploads", client=sdk)
    with Stubber(sdk) as stubber:
        stubber.add_response(
            "put_object",
            {},
            {
                "Bucket": "uploads",
                "Key": KEY,
                "Body": b"report",
                "ContentType": "text/plain",
            },
        )
        stubber.add_response("head_object", {}, {"Bucket": "uploads", "Key": KEY})
        stubber.add_response(
            "get_object",
            {"Body": StreamingBody(io.BytesIO(b"report"), 6)},
            {"Bucket": "uploads", "Key": KEY},
        )
        stubber.add_response("delete_object", {}, {"Bucket": "uploads", "Key": KEY})
        service.upload(KEY, b"report", content_type="text/plain")
        assert service.exist(KEY)
        assert service.download(KEY) == b"report"
        service.delete(KEY)
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize(
    "start, end, expected",
    [(1, 3, "bytes=1-3"), (2, None, "bytes=2-"), (None, 2, "bytes=0-2")],
)
def test_open_requests_only_the_selected_range(sdk, start, end, expected):
    with Stubber(sdk) as stubber:
        raw = io.BytesIO(b"abc")
        body = StreamingBody(raw, 3)
        stubber.add_response(
            "get_object",
            {"Body": body},
            {"Bucket": "uploads", "Key": KEY, "Range": expected},
        )
        stream = S3Service(bucket="uploads", client=sdk).open(KEY, start=start, end=end)
        try:
            assert stream.read() == b"abc"
        finally:
            stream.close()
        assert raw.closed
        stubber.assert_no_pending_responses()


@pytest.mark.parametrize("operation", ["open", "exist"])
@pytest.mark.parametrize("code", ["404", "NoSuchKey", "NotFound", "AccessDenied"])
def test_storage_translates_only_missing_object_errors(sdk, operation, code):
    method = "get_object" if operation == "open" else "head_object"
    service = S3Service(bucket="uploads", client=sdk)
    with Stubber(sdk) as stubber:
        stubber.add_client_error(
            method,
            service_error_code=code,
            http_status_code=403 if code == "AccessDenied" else 404,
            expected_params={"Bucket": "uploads", "Key": KEY},
        )
        if code == "AccessDenied":
            with pytest.raises(ClientError):
                getattr(service, operation)(KEY)
        elif operation == "open":
            with pytest.raises(FileNotFoundError):
                service.open(KEY)
        else:
            assert not service.exist(KEY)
        stubber.assert_no_pending_responses()


def test_upload_uses_public_acl_and_safe_unicode_headers(mocker):
    client = mocker.Mock()
    service = S3Service(bucket="uploads", client=client, public=True)
    service.upload(
        KEY,
        b"report",
        filename="../résumé.txt",
        content_type="text/plain",
        disposition="attachment",
    )
    options = client.put_object.call_args.kwargs
    assert options["ACL"] == "public-read"
    assert "filename=resume.txt" in options["ContentDisposition"]
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9.txt" in options["ContentDisposition"]


def test_private_urls_presign_safe_response_headers(mocker):
    client = mocker.Mock()
    client.generate_presigned_url.return_value = "https://storage.example/signed"
    service = S3Service(bucket="uploads", client=client)
    url = service.url(
        KEY,
        expires_in=300,
        filename="../résumé.txt",
        content_type="text/plain",
        disposition="attachment",
    )
    assert url == "https://storage.example/signed"
    options = client.generate_presigned_url.call_args.kwargs
    assert options["ExpiresIn"] == 300
    assert options["Params"]["ResponseContentType"] == "text/plain"
    assert (
        "filename*=UTF-8''r%C3%A9sum%C3%A9.txt"
        in options["Params"]["ResponseContentDisposition"]
    )


@pytest.mark.parametrize(
    "path_style, expected",
    [
        (False, f"https://uploads.storage.example/{KEY}"),
        (True, f"https://storage.example/uploads/{KEY}"),
    ],
)
def test_public_urls_use_the_configured_addressing_style(mocker, path_style, expected):
    client = mocker.Mock()
    client.meta.endpoint_url = "https://storage.example"
    service = S3Service(
        bucket="uploads", client=client, public=True, force_path_style=path_style
    )
    assert (
        service.url(
            KEY,
            expires_in=300,
            filename="report.txt",
            content_type="text/plain",
            disposition="attachment",
        )
        == expected
    )
    client.generate_presigned_url.assert_not_called()
