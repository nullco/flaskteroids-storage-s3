# Flaskteroids Storage S3

S3-compatible attachment storage for Flaskteroids. This package owns the AWS SDK
integration; Flaskteroids owns attachment records, authorization, routes, and the
public `flaskteroids.storage.StorageService` contract.

## Install

```sh
uv add flaskteroids-storage-s3
```

Installation exposes the `S3` provider through the `flaskteroids.storage` entry
point group. No application import, initializer, or registration is needed.
Installing the package does not change the application's selected storage.

Configure `config/storage.yml`:

```yaml
amazon:
  service: S3
  bucket: {env: S3_BUCKET}
  region: {env: AWS_REGION}
```

Select it in environment configuration:

```python
config.attachments.service = "amazon"
```

AWS's normal credential chain, including IAM roles, is supported. Optional
`access_key_id` and `secret_access_key` values can use Flaskteroids credential
references. `endpoint` and `force_path_style: true` support S3-compatible providers.
`public: true` requests public-read objects; bucket policy and provider support
must permit this. Private objects use expiring signed URLs.

## Development

This is an unreleased package developed alongside the sibling Flaskteroids
checkout. That checkout must contain the new storage contract; the previously
published framework does not provide it. Set the published framework version
requirement to the release introducing that contract before publishing this package.

```sh
uv sync --locked --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The local uv source uses `../flaskteroids`. Tests require boto3 (a runtime
dependency), but no cloud credentials, network requests, or running S3 service.
Provider tests use botocore stubs and run the framework's shared storage contract.
