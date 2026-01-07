from agents import Agent, set_tracing_disabled, handoff
from agents.extensions.models.litellm_model import LitellmModel
from openai import AsyncOpenAI
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
import os
from prompt import career_assistant_prompt, analysis_agent_prompt
from tools import get_list_of_jobs, search_knowledge_base
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


def log_analyses_handoff(context):
    yield "```Delegating Analyses to Analysis Agent```\n\n"

custom_client = AsyncOpenAI(
    base_url=os.environ.get("LMAAS_URL"),
    api_key=os.environ.get("LMAAS_KEY"),
)

custom_model = OpenAIChatCompletionsModel(
    openai_client=custom_client,
    model=os.environ.get("LMAAS_MODEL"),
)

analysis_agent = Agent(
    name= "Analysis Agent",
    instructions= analysis_agent_prompt,
    handoff_description="Handles analysis of the uploaded text files for threats and provides recommendations",
    model = custom_model,
    tools = [search_knowledge_base]
)

career_assistant = Agent(
    name= "Gaurav",
    instructions= career_assistant_prompt,
    handoffs=[
        handoff(
            agent=analysis_agent,
            tool_name_override="analyze_text_file",
            on_handoff = log_analyses_handoff
        )
    ],
    model = custom_model,
    tools = [get_list_of_jobs, search_knowledge_base]
)