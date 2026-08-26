from .client import S3Client
import os


s3_client = S3Client(
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    access_key=os.getenv("MINIO_ROOT_USER"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD"),
    bucket_name=os.getenv("S3_BUCKET_NAME")
)
