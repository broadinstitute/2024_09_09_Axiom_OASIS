# ruff: noqa: CPY001, EM101, EM102, TC003, TRY003
"""Unsigned S3 access for the public Cell Painting Gallery."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

import boto3
from botocore import UNSIGNED
from botocore.config import Config


class StreamingBody(Protocol):
    """Narrow interface used from a botocore streaming response."""

    def read(self) -> bytes:
        """Read the complete response body."""
        ...

    def close(self) -> None:
        """Close the response body."""
        ...


class S3Client(Protocol):
    """Narrow low-level S3 client interface used by this workflow."""

    def get_object(self, **arguments: object) -> Mapping[str, object]:
        """Return one S3 object response."""
        ...


def public_s3_client(*, max_pool_connections: int = 64) -> S3Client:
    """Create a retrying unsigned S3 client suitable for shared worker threads."""
    if max_pool_connections < 1:
        raise ValueError("max_pool_connections must be positive")
    return cast(
        "S3Client",
        boto3.client(
            "s3",
            region_name="us-east-1",
            config=Config(
                signature_version=UNSIGNED,
                max_pool_connections=max_pool_connections,
                connect_timeout=15,
                read_timeout=120,
                retries={"max_attempts": 10, "mode": "adaptive"},
            ),
        ),
    )


def download_object(  # noqa: PLR0913
    client: S3Client,
    *,
    bucket: str,
    key: str,
    expected_size: int | None,
    expected_etag: str | None,
    version_id: str | None = None,
) -> tuple[bytes, str | None, str | None]:
    """Download one object and enforce the immutable metadata snapshot."""
    arguments = {"Bucket": bucket, "Key": key}
    if version_id:
        arguments["VersionId"] = version_id
    response = client.get_object(**arguments)
    body = cast("StreamingBody", response["Body"])
    try:
        payload = body.read()
    finally:
        body.close()

    raw_response_size = response.get("ContentLength", len(payload))
    if isinstance(raw_response_size, bool) or not isinstance(raw_response_size, int):
        raise S3ResponseError(
            f"invalid ContentLength for s3://{bucket}/{key}: {raw_response_size!r}",
        )
    response_size = raw_response_size
    if response_size != len(payload):
        raise ValueError(
            f"incomplete S3 response for s3://{bucket}/{key}: header={response_size}, received={len(payload)}",
        )
    if expected_size is not None and len(payload) != expected_size:
        raise ValueError(
            f"source size changed for s3://{bucket}/{key}: expected={expected_size}, received={len(payload)}",
        )

    response_etag = _normalize_etag(response.get("ETag"))
    normalized_expected_etag = _normalize_etag(expected_etag)
    if normalized_expected_etag is not None and response_etag != normalized_expected_etag:
        raise ValueError(
            f"source ETag changed for s3://{bucket}/{key}: "
            f"expected={normalized_expected_etag}, received={response_etag}",
        )
    response_version = _normalize_optional_text(response.get("VersionId"))
    if version_id is not None and response_version != version_id:
        raise ValueError(
            f"source version changed for s3://{bucket}/{key}: expected={version_id}, received={response_version}",
        )
    return payload, response_etag, response_version


def _normalize_etag(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().strip('"')
    return normalized or None


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise S3ResponseError(f"invalid optional S3 text value: {value!r}")
    return value


class S3ResponseError(RuntimeError):
    """Raised when a public S3 response violates the metadata contract."""
