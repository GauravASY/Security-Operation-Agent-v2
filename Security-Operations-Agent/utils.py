import boto3
from botocore.exceptions import ClientError
import os
import requests
from agents import Runner
from llmAgent import wazuh_agent


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


def get_token(WAZUH_API_URL, WAZUH_API_USER, WAZUH_API_PASS):
    """
    Authenticates Wazuh API and returns the JWT token.
    
    args:
        WAZUH_API_URL (str): The URL of the Wazuh API
        WAZUH_API_USER (str): The username for Wazuh API authentication
        WAZUH_API_PASS (str): The password for Wazuh API authentication
    """

    url = f"{WAZUH_API_URL}/security/user/authenticate"
    response = requests.post(url, auth=(WAZUH_API_USER, WAZUH_API_PASS), verify=False)
    if response.status_code == 200:
        return response.json()['data']['token']
    else:
        raise Exception(f"Authentication Failed: {response.text}")

def checkEnvVariable(var_name):
    """Check if an environment variable is set and return its value."""
    env_var  = os.environ.get(var_name)
    if not env_var: 
        return "Missing the environment variable: " + var_name
    return env_var

def handling_wazuh_agent(query):
    streamed_result = Runner.run_streamed(wazuh_agent, f"{query}")
    async for _ in streamed_result.stream_events():
        pass  
    print("Wazuh Agent Output: ", streamed_result.final_output)
    return streamed_result.final_output  