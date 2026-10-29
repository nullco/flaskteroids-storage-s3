"""S3-compatible attachment storage for Flaskteroids."""

from urllib.parse import quote, urlsplit, urlunsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from flaskteroids.storage import (
    StorageService,
    content_disposition,
    validate_key,
    validate_range,
    verify_checksum,
)


class S3Service(StorageService):
    def __init__(
        self,
        *,
        bucket,
        client=None,
        region=None,
        access_key_id=None,
        secret_access_key=None,
        endpoint=None,
        force_path_style=False,
        public=False,
    ):
        if client is None:
            options = {
                "region_name": region,
                "aws_access_key_id": access_key_id,
                "aws_secret_access_key": secret_access_key,
                "endpoint_url": endpoint,
            }
            client = boto3.client(
                "s3",
                config=Config(
                    s3={"addressing_style": "path" if force_path_style else "auto"}
                ),
                **{key: value for key, value in options.items() if value is not None},
            )
        self.bucket = bucket
        self.client = client
        super().__init__(public=public)
        self.force_path_style = force_path_style

    def upload(
        self,
        key,
        data,
        *,
        checksum=None,
        content_type=None,
        filename=None,
        disposition=None,
    ):
        validate_key(key)
        if checksum is not None:
            verify_checksum(data, checksum)
        options = {"Bucket": self.bucket, "Key": key, "Body": data}
        if checksum is not None:
            options["ContentMD5"] = checksum
        if content_type is not None:
            options["ContentType"] = content_type
        if filename is not None and disposition is not None:
            options["ContentDisposition"] = content_disposition(filename, disposition)
        if self.public:
            options["ACL"] = "public-read"
        self.client.put_object(**options)

    def open(self, key, *, start=None, end=None):
        validate_key(key)
        validate_range(start, end)
        options = {"Bucket": self.bucket, "Key": key}
        if start is not None or end is not None:
            options["Range"] = f"bytes={start or 0}-{end if end is not None else ''}"
        try:
            response = self.client.get_object(**options)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from error
            raise
        return response["Body"]

    def delete(self, key):
        validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exist(self, key):
        validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def url(self, key, *, expires_in, filename, content_type, disposition):
        validate_key(key)
        if self.public:
            parts = urlsplit(self.client.meta.endpoint_url)
            if self.force_path_style:
                path = f"{parts.path.rstrip('/')}/{quote(self.bucket)}/{key}"
                return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
            return urlunsplit(
                (parts.scheme, f"{self.bucket}.{parts.netloc}", f"/{key}", "", "")
            )
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": content_disposition(
                    filename, disposition
                ),
            },
            ExpiresIn=expires_in,
        )
