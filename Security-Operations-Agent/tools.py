from agents import function_tool
from vectorstore import collection
import psycopg2
import json
import chromadb
from database import DB_CONFIG, TARGET_DB
from utils import checkEnvVariable
import requests

# Connect to DBs
chroma_client = chromadb.PersistentClient(path="./my_local_db")
collection = chroma_client.get_or_create_collection(name="pdf_knowledge_base_v2")


def get_db_connection():
    return psycopg2.connect(dbname=TARGET_DB, **DB_CONFIG)


def search_knowledge_base_raw(query: str, filename: str) -> str:
    """
    Search the local knowledge base for information about a specific file.
    Use this tool when the user asks questions about the uploaded text file.
    """
    print("Filename : ", filename)
    # Query ChromaDB
    results = collection.query(
        query_texts=[query],
        where={"filename": {"$eq": filename}},
        n_results=5  # Return top 5 matches
    )
    # Combine the IDs and Documents into a readable string for the LLM
    print("Results : \n", results)
    # Format results as a single string for the Agent
    found_text = "\n\n".join(results['documents'][0])
    print("Found Text : \n", found_text)
    return found_text


async def search_indicators_by_report_raw(report_id: int):
    """
    Fetches all Indicators of Compromise (IoCs) associated with a specific report.
    
    Args:
        report_id (int): The unique identifier for the report.
    
    Returns:
        str: JSON string containing a list of IoCs with their types and values,
             or an error message if no indicators are found.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT type, value FROM iocs WHERE report_id = %s", (report_id,))
        results = cur.fetchall()
        if not results:
            return "No indicators found for this report."
        print("Inside search_indicators_by_report:\n")
        for r in results:
            print("type : ", r[0])
            print("    value : \n", r[1])
        return json.dumps([{"type": r[0], "value": r[1]} for r in results])
    finally:
        conn.close()


async def search_by_victim_raw(sector: str):
    """
    Finds all reports targeting a specific victim sector.
    
    Args:
        sector (str): The industry sector name (e.g., 'BFSI', 'Finance', 'Healthcare').
    
    Returns:
        str: String representation of a list of tuples containing (report_id, filename, summary, created_at),
             or an empty list if no matching reports are found.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT report_id, filename, summary, created_at FROM reports WHERE victim_sector ILIKE %s", (f"%{sector}%",))
        results = cur.fetchall()
        print("Inside search_by_victim. Results:\n", results)
        return str(results)
    finally:
        conn.close()


async def get_file_content_raw(filename: str):
    """
    Fetches the raw content, summary, and report ID of a specific file.
    
    Args:
        filename (str): The name of the file to retrieve (can include path, will extract basename).
    
    Returns:
        tuple: A tuple containing (raw_content, summary, report_id),
               or an error message if the file is not found.
    """
    name = filename.split("\\")[-1]
    print("Filename : ", name)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT raw_content, summary, report_id FROM reports WHERE filename = %s", (name,))
        result = cur.fetchone()
        if not result:
            return "File not found."
        print("Inside get_file_content. Result:\n", result)
        return result
    finally:
        conn.close()


async def get_reportsID_by_technique_raw(technique: str):
    """
    Fetches all report IDs associated with a specific MITRE ATT&CK technique.
    
    Args:
        technique (str): The MITRE ATT&CK technique ID (e.g., 'T1090', 'T1566') or technique name to search for.
    
    Returns:
        str: A string representation of a list of tuples containing (report_id, technique_name) pairs,
             or an error message if no reports are found.
    """
    print("Technique : ", technique)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT report_id, technique_name FROM ttps WHERE technique_id ILIKE %s", (f"%{technique}%",))
        results = cur.fetchall()
        print("Results from get_reportsID_by_technique : \n", results)
        if not results:
            return "No reports found for this technique."
        return str(results)
    finally:
        conn.close()


async def get_reports_by_reportID_raw(report_id: int):
    """
    Fetches complete report details for a specific report ID.
    
    Args:
        report_id (int): The unique identifier for the report.
    
    Returns:
        tuple: A tuple containing all report fields from the database,
               or an error message if the report is not found.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(" SELECT * from reports WHERE report_id = %s", (report_id,))
        result = cur.fetchone()
        if not result:
            return "Report not found."
        print("Inside get_reports_by_reportID. Result:\n", result)
        return result
    finally:
        conn.close()


async def analyse_wazuh_data_raw(size: int = 20, domain: str = "*"):
    """
    Fetches security events from the WAZUH
    Args:
        size (int, optional): Number of events to fetch. Defaults to 20.
        domain (str, optional): Domain to filter events by. Defaults to "*".
    """
    WAZUH_URL = checkEnvVariable("WAZUH_URL")
    WAZUH_USER = checkEnvVariable("WAZUH_USER")
    WAZUH_PASS = checkEnvVariable("WAZUH_PASS")

    # checkEnvVariable returns "Missing the environment variable: X" on failure
    if "Missing" in WAZUH_URL or "Missing" in WAZUH_USER or "Missing" in WAZUH_PASS:
        missing_vars = [v for v in [WAZUH_URL, WAZUH_USER, WAZUH_PASS] if "Missing" in v]
        return f"Error: {'; '.join(missing_vars)}"
    
    # fetch Wazuh alerts
    body = {
        "size": int(size),
        "sort": [
            {"@timestamp": {"order": "desc"}}
        ],
        "query": {
            "query_string": {
                "query": domain or "*"
            }
        }
    }

    try:
        resp = requests.post(
            WAZUH_URL,
            auth=(WAZUH_USER, WAZUH_PASS),
            headers={"Content-Type": "application/json"},
            json=body,
            verify=False
        )
        resp.raise_for_status()  # Raise exception for 4xx/5xx responses
    except requests.RequestException as e:
        print(f"Wazuh API request failed: {e}")
        return f"Error connecting to Wazuh API: {str(e)}"

    try:
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])
        events = [hit["_source"] for hit in hits]
    except (KeyError, ValueError) as e:
        print(f"Error parsing Wazuh response: {e}")
        return f"Error parsing Wazuh response: {str(e)}"
    
    if not events:
        return "No events found in Wazuh"
    
    return json.dumps(events, indent=2)


# TOOL WRAPPERS (for use in Agent definitions)
# These are FunctionTool objects for registering with agents


search_knowledge_base = function_tool(search_knowledge_base_raw)
search_indicators_by_report = function_tool(search_indicators_by_report_raw)
search_by_victim = function_tool(search_by_victim_raw)
get_file_content = function_tool(get_file_content_raw)
get_reportsID_by_technique = function_tool(get_reportsID_by_technique_raw)
get_reports_by_reportID = function_tool(get_reports_by_reportID_raw)
analyse_wazuh_data = function_tool(analyse_wazuh_data_raw)