# Security Operations Chatbot

**Security Operations Chatbot** is a Proof of Concept demonstrating a multi-agent AI system designed for security operations. It combines a conversational interface with specialized agents capable of analyzing unstructured security logs, extracting threat intelligence, and mapping behaviors to MITRE ATT&CK TTPs.

## 🚀 Key Features

- **Multi-Agent Architecture**: 
  - **Primary Agent ("Gaurav")**: A conversational assistant serving as the user entry point.
  - **Extraction Agent**: A specialized sub-agent that automatically ingests text files, extracts structured data (IoCs, TTPs), and generates incident summaries.
- **Automated Threat Analysis**: 
  - Extracts **Indicators of Compromise (IoCs)** (IPs, Domains, Hashes).
  - Maps activities to **MITRE ATT&CK TTPs**.
  - Determines incident severity and victim sector.
- **RAG (Retrieval-Augmented Generation)**: Ingests uploaded documents into a Vector Store (ChromaDB) to answer user queries with context.
- **Structured Storage**: Automatically initializes and populates a **PostgreSQL** database with analyzed reports.
- **S3 Integration**: securely uploads and manages files via AWS S3.
- **Interactive UI**: Built with **Gradio** for a seamless chat and file upload experience.

## 🛠️ Technology Stack

- **Language**: Python 3.13+
- **Frameworks**: `gradio`, `openai-agents`
- **Database**: PostgreSQL (Metadata & Reports), ChromaDB (Vector Store)
- **Cloud Storage**: AWS S3
- **LLM Provider**: OpenAI / LiteLLM (via LM-as-a-Service integration)

## ⚙️ Prerequisites

Ensure you have the following installed:
- **Python 3.13+**
- **PostgreSQL** (running and accessible)
- **AWS** Credentials (with S3 access)
- **UV** (Recommended for dependency management) or `pip`

## 🔧 Setup & Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd Cert-SIEM-POC-v2
    ```

2.  **Install Dependencies**:
    Using `uv` (recommended):
    ```bash
    uv sync
    ```
    Or using `pip`:
    ```bash
    pip install .
    ```

3.  **Environment Configuration**:
    Create a `.env` file in the root directory with the following variables:

    ```ini
    # OpenAI / LLM Configuration
    OPENAI_API_KEY=sk-...
    LMAAS_URL=...
    LMAAS_KEY=...
    LMAAS_MODEL=...

    # Database Configuration
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=yourpassword
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    TARGET_DB=siem_db

    # AWS S3 Configuration
    S3_BUCKET_NAME=your-bucket-name
    # Ensure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set in your environment or ~/.aws/credentials
    ```

## ▶️ Usage

1.  **Start the Application**:
    ```bash
    python main.py
    ```

2.  **Access the Interface**:
    Open your browser and navigate to the local URL provided by Gradio (typically `http://127.0.0.1:7860`).

3.  **Interact**:
    - **Chat**: Converse with the agent.
    - **Upload Logs**: Upload `.txt` log files. The system will automatically:
        - Upload them to S3.
        - Ingest them into the vector store.
        - Trigger the **Extraction Agent** to analyze the file and generate a structured report.
