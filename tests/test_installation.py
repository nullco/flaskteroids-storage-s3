import io

from flaskteroids.application import Application
from flaskteroids.attachments import Blob, blob_path
from flaskteroids.attachments.schema import metadata
from flaskteroids.testing import TestDeliveryMethod, TestQueueAdapter

from tests.storage_client import StorageClient


class StorageApplication(Application):
    def configure(self, config):
        config.secret_key_base = "storage-installation-test"
        config.paths.routes = "tests.routes"
        config.attachments.service = "amazon"
        config.jobs.queue_adapter = TestQueueAdapter
        config.mailer.delivery_method = TestDeliveryMethod


def test_installed_package_registers_storage_without_application_imports(
    tmp_path, mocker
):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage.yml").write_text(
        "amazon:\n  service: S3\n  bucket: uploads\n"
    )
    (tmp_path / "config/database.yml").write_text(
        'test:\n  adapter: sqlite3\n  database: ":memory:"\n'
    )
    sdk = StorageClient()
    mocker.patch("boto3.client", return_value=sdk)
    app = StorageApplication.initialize(environment="test", root_path=tmp_path)
    try:
        storage = app.extensions["flaskteroids.attachments"]
        service = storage.service()
        assert type(service).__module__ == "flaskteroids_storage_s3"
        assert service.name == "amazon"
        with app.test_request_context():
            database = app.extensions["flaskteroids.db"]
            metadata.create_all(database.engine)
            blob = Blob.create_and_upload(
                io=io.BytesIO(b"report"), filename="report.txt", service_name="amazon"
            )
            assert blob.download() == b"report"
            url = blob_path(blob, route="proxy")
        response = app.test_client().get(url)
        assert response.status_code == 200
        assert response.data == b"report"
        response.close()
    finally:
        app.extensions["flaskteroids.db"].engine.dispose()
