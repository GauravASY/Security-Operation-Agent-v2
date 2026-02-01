import boto3
from botocore.exceptions import ClientError
import os
import requests
from agents import Runner

import json
import re
import traceback


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

async def handling_wazuh_agent(query, context):
    print("Query inside handling_wazuh_agent: ", query)
    from llmAgent import wazuh_agent
    from chatkit.agents import stream_agent_response
    from tools import analyse_wazuh_data_raw
    
    conversation_chain = [{"role": "user", "content": query}]
    print("Conversation chain inside handling_wazuh_agent: ", conversation_chain)
    
    max_turns = 5
    for turn in range(max_turns):
        full_turn_response = ""
        tool_calls_found = False
        buffered_events = []  # Buffer events instead of yielding immediately

        streamed_result = Runner.run_streamed(wazuh_agent, conversation_chain)
        async for event in stream_agent_response(context, streamed_result):
            # Capture text from thread.item.done events
            if event.type == "thread.item.done" and hasattr(event, "item"):
                item_obj = event.item
                if hasattr(item_obj, "content") and item_obj.content:
                    for part in item_obj.content:
                        if hasattr(part, "text"):
                            print("Agent Response: ", part.text[:100] if len(part.text) > 100 else part.text)
                            full_turn_response += part.text

            # Buffer events instead of yielding immediately
            buffered_events.append(event)
        
        try:
            match = re.search(r'(\[.*"analyse_wazuh_data_raw".*\])', full_turn_response, re.DOTALL)
            
            if match:
                possible_json = match.group(1)
                tool_calls = json.loads(possible_json)
                if isinstance(tool_calls, list):
                    tool_calls_found = True
                    print(f"Tool call detected in turn {turn + 1}, executing...")

                    tool_outputs = []
                    for call in tool_calls:
                        res = "Error: Unknown tool"
                        name = call.get("name")
                        args = call.get("arguments", {})
                            
                        try:
                            if name == "analyse_wazuh_data_raw":
                                res = await analyse_wazuh_data_raw(**args)
                        except Exception as tool_err:
                            res = f"Tool Execution Error: {tool_err}"
                            
                        tool_outputs.append(res)
                        
                    # Update Chain for next iteration
                    conversation_chain.append({"role": "assistant", "content": full_turn_response})
                    conversation_chain.append({"role": "user", "content": f"Tool Output: {json.dumps(tool_outputs)}"})
                        
        except json.JSONDecodeError:
            pass
        except Exception as e:
            print(f"Error parsing tool call: {e}")
            traceback.print_exc()

        # Only yield events if NO tool call was found (this is the final response)
        if not tool_calls_found:
            print(f"Final response in turn {turn + 1}, yielding {len(buffered_events)} events to UI")
            for event in buffered_events:
                yield event
            break