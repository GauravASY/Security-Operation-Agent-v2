from agents import Agent, set_tracing_disabled, handoff
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
import os
from prompt import career_assistant_prompt, extraction_agent_prompt, wazuh_agent_prompt
from tools import search_indicators_by_report, search_by_victim, get_file_content, get_reportsID_by_technique, get_reports_by_reportID, analyse_wazuh_data
from typing import List, Optional
from pydantic import BaseModel, Field

set_tracing_disabled(True)

# --- 1. Define the "Digital Form" the LLM must fill ---
class Indicator(BaseModel):
    value: str = Field(..., description="The IoC value (e.g., 185.199.110.153)")
    type: str = Field(..., description="Type of IoC: IP, Domain, Hash, URL")

class TTP(BaseModel):
    technique_id: str = Field(..., description="MITRE ATT&CK ID (e.g., T1059)")
    name: str = Field(..., description="Technique name (e.g., PowerShell)")

class ReportExtraction(BaseModel):
    summary: str = Field(..., description="Brief summary of the incident")
    severity: str = Field(..., description="High, Medium, or Low")
    victim_sector: str = Field(..., description="e.g. Finance, Healthcare")
    timeline_start: Optional[str] = Field(description="ISO timestamp of start")
    timeline_end: Optional[str] = Field(description="ISO timestamp of end")
    iocs: List[Indicator]
    ttps: List[TTP]

class ReportAnalysis(BaseModel):
    summary: str = Field(..., description="Brief summary of the events")
    severity: str = Field(..., description="High, Medium, or Low")
    victim_sector: List[str] = Field(..., description="e.g. Finance, Healthcare")
    iocs: List[Indicator] = Field(..., description="List of indicators of compromise")
    top_attackers: List[str] = Field(..., description="List of top attacker IPs")
    recommendations: List[str] = Field(..., description="Actionable steps for the security team")


def log_analyses_handoff(context):
    yield "```Delegating Extraction to Extraction Agent```\n"

custom_client = AsyncOpenAI(
    base_url=os.environ.get("LMAAS_URL"),
    api_key=os.environ.get("LMAAS_KEY"),
)

custom_model = OpenAIChatCompletionsModel(
    openai_client=custom_client,
    model=os.environ.get("LMAAS_MODEL"),
)

extraction_assistant = Agent(
    name= "Extraction Agent",
    instructions= extraction_agent_prompt,
    handoff_description="Handles extraction of the uploaded text files for threats and provides recommendations",
    model = custom_model,
    output_type=ReportExtraction,
)

wazuh_agent = Agent(
    name= "wazuh_agent",
    instructions= wazuh_agent_prompt,
    model= custom_model,
    tools = [
        analyse_wazuh_data
    ],
    output_type=ReportAnalysis,
)

career_assistant = Agent(
    name= "Gaurav",
    instructions= career_assistant_prompt,
    handoffs=[
        handoff(
            agent=extraction_assistant,
            tool_name_override="analyze_text_file",
            on_handoff = log_analyses_handoff
        )
    ],
    model = custom_model,
    tools = [
        search_indicators_by_report, 
        search_by_victim, 
        get_file_content, 
        get_reportsID_by_technique, 
        get_reports_by_reportID,
        wazuh_agent.as_tool(
            tool_name="wazuh_agent",
            tool_description="Handles all the tasks related to Wazuh. Performs Wazuh analysis, provides recommendations, and performs Wazuh operations"
        )
    ]
)