import boto3
from botocore.exceptions import ClientError


def upload_file_to_s3(file_name, bucket_name, object_name = None):
    """
    Uploads a file to an S3 bucket

    args:
        file_name (str): The path to the file to upload
        bucket_name (str): The name of the S3 bucket
        object_name (str, optional): The name of the object in the bucket. Defaults to None.
    """
    if object_name is None:
        object_name = file_name
    
    s3_client = boto3.client("s3")
    try:
        response = s3_client.upload_file(file_name, bucket_name, object_name)
        s3_url = f"https://{bucket_name}.s3.us-east-1.amazonaws.com/{object_name}"
        return s3_url
    except ClientError as e:
        print(e)
        return "Failed to upload file to S3"