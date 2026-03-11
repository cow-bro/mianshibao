from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)


def ensure_bucket_exists(bucket_name: str) -> None:
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)


def upload_bytes(bucket_name: str, object_name: str, data: bytes, content_type: str) -> str:
    ensure_bucket_exists(bucket_name)
    minio_client.put_object(
        bucket_name,
        object_name,
        BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return f"{bucket_name}/{object_name}"


def download_bytes(bucket_name: str, object_name: str) -> bytes:
    response = None
    try:
        response = minio_client.get_object(bucket_name, object_name)
        return response.read()
    except S3Error as exc:
        raise FileNotFoundError(f"object not found: {bucket_name}/{object_name}") from exc
    finally:
        if response is not None:
            response.close()
            response.release_conn()
