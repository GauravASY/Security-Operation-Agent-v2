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
    """
    Runs the Wazuh agent and yields events directly to the UI for real-time streaming.
    Only the final response (after all tool calls complete) is yielded to the UI.
    """
    from llmAgent import wazuh_agent
    from chatkit.agents import stream_agent_response
    from tools import analyse_wazuh_data_raw
    from chatkit.types import ThreadItemAddedEvent, ThreadItemDoneEvent, AssistantMessageItem
    from datetime import datetime
    import uuid
    
    conversation_chain = [{"role": "user", "content": query}]
    print("Wazuh Agent: ", conversation_chain)
    
    max_turns = 5
    for turn in range(max_turns):
        full_turn_response = ""
        tool_calls_found = False
        buffered_events = []  # Buffer events for potential yielding

        streamed_result = Runner.run_streamed(wazuh_agent, conversation_chain)
        async for event in stream_agent_response(context, streamed_result):
            # Capture text from thread.item.done events
            if event.type == "thread.item.done" and hasattr(event, "item"):
                item_obj = event.item
                if hasattr(item_obj, "content") and item_obj.content:
                    for part in item_obj.content:
                        if hasattr(part, "text"):
                            print("Wazuh Agent Response: ", part.text[:100] if len(part.text) > 100 else part.text)
                            full_turn_response += part.text
            
            # Buffer events BUT skip thread.item.added to prevent duplicate display
            # thread.item.added contains full content, which would show before streaming
            if event.type != "thread.item.added":
                buffered_events.append(event)
        
        try:
            match = re.search(r'(\[\s*\{\s*"name"\s*:\s*"(?:analyse_wazuh_data|analyse_wazuh_data_raw)".*?\])', full_turn_response, re.DOTALL)
            
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
                            if name in ("analyse_wazuh_data_raw", "analyse_wazuh_data"):
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

        # Yield events to UI ONLY when no more tool calls (this is the final response)
        if not tool_calls_found:
            for event in buffered_events:
                yield event
            return  # Exit the generator
    
    # Max turns exceeded - yield error message to UI
    print("Wazuh Agent: Max turns exceeded, yielding error to UI")
    error_message = "**Max retries exceeded for Wazuh Endpoint**\n. The Wazuh API is not responding. Please check:\n- Wazuh server connectivity\n- Network configuration\n- API credentials\n\nTry again later or contact your administrator."
    
    error_item = AssistantMessageItem(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        thread_id=context.thread.id,
        created_at=datetime.utcnow(),
        content=[{"type": "output_text", "text": error_message}],
    )
    yield ThreadItemAddedEvent(item=error_item)
    yield ThreadItemDoneEvent(item=error_item)