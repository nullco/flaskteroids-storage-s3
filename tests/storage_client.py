"""In-memory SDK boundary for the reusable storage provider contract."""

import io

from botocore.exceptions import ClientError
from botocore.response import StreamingBody


class StorageClient:
    def __init__(self):
        self.files = {}

    def put_object(self, *, Bucket, Key, Body, **options):
        self.files[Bucket, Key] = Body if isinstance(Body, bytes) else Body.read()
        return {}

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.files:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def get_object(self, *, Bucket, Key, Range=None):
        try:
            data = self.files[Bucket, Key]
        except KeyError as error:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject") from error
        if Range is not None:
            start, end = Range.removeprefix("bytes=").split("-")
            data = data[int(start) : int(end) + 1 if end else None]
        return {"Body": StreamingBody(io.BytesIO(data), len(data))}

    def delete_object(self, *, Bucket, Key):
        self.files.pop((Bucket, Key), None)
        return {}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        return f"https://storage.example/{Params['Bucket']}/{Params['Key']}"
