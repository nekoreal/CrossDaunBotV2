import os , boto3
from typing import Optional
from botocore.exceptions import ClientError
from utils.logger import logger, make_log



class S3Client:
    def __init__(
            self,
            endpoint_url: str,
            access_key: str,
            secret_key: str,
            bucket_name: str
    ):
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name

        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key
        )

    @logger(
        txtfile="s3.txt",
        print_log=True,
        raise_exc=False,
        only_exc=True,
        time_log=True,
    )
    def upload_file(
            self, 
            file_bytes: str,
            file_path: str,
            content_type: str = "image/jpeg"
    ) -> bool:
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=file_bytes,
                ContentType=content_type,
            )
            return True
        except ClientError as e:
            make_log(txtfile="s3.txt", text=f"S3 Upload Error: {e}")
            return False


    @logger(
        txtfile="s3.txt",
        print_log=True,
        raise_exc=False,
        only_exc=True,
        time_log=True,
    )
    def download_file(
        self,
        file_path: str,
    ) -> Optional[bytes]:
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            return response['Body'].read()
        except ClientError as e:
            make_log(txtfile="s3.txt", text=f"S3 Download Error: {e}")
            return None


    @logger(
        txtfile="s3.txt",
        print_log=True,
        raise_exc=False,
        only_exc=True,
        time_log=True,
    )
    def delete_file(
        self,
        file_path: str,
    ) -> bool:
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            return True
        except ClientError as e:
            make_log(txtfile="s3.txt", text=f"S3 Delete Error: {e}")
            return False


    @logger(
        txtfile="s3.txt",
        print_log=True,
        raise_exc=False,
        only_exc=True,
        time_log=True,
    )
    def move_file(
        self,
        old_file_path: str,
        new_file_path: str,
    ) -> bool:
        try:
            copy_source = {'Bucket': self.bucket_name, 'Key': old_file_path}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=new_file_path)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=old_file_path)
            return True
        except ClientError as e:
            make_log(txtfile="s3.txt", text=f"S3 Move Error: {e}")
            return False