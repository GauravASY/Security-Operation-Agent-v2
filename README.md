# Security Operations Agent v2

An intelligent AI-powered security operations assistant that helps analyze threat intelligence reports, extract indicators of compromise (IoCs), map tactics, techniques, and procedures (TTPs) to the MITRE ATT&CK framework, and integrates with Wazuh SIEM for real-time security event analysis. The system combines natural language processing with structured data storage to enable security analysts to query and analyze threat data through conversational interactions.

## Overview

Security Operations Agent v2 is a full-stack application consisting of a FastAPI backend with AI agent capabilities and a React-based chat interface. The system processes uploaded threat intelligence documents, extracts structured security information, and stores it in a PostgreSQL database for efficient querying. Additionally, it integrates with Wazuh SIEM to fetch, analyze, and provide actionable insights on security events in real-time. Users interact with the system through a chat interface powered by OpenAI's ChatKit, enabling natural language queries about threat reports, IoCs, victim sectors, attack techniques, and live security events.

## Architecture

The application follows a client-server architecture with the following components:

### Backend Architecture

- **FastAPI Server**: Handles HTTP requests, file uploads, and WebSocket connections for streaming responses
- **AI Agent System**: Multi-agent architecture using OpenAI Agents framework with tool-as-agent pattern and handoffs between specialized agents
- **Vector Database**: ChromaDB for semantic search over uploaded documents
- **Relational Database**: PostgreSQL for structured storage of threat intelligence data including reports, IoCs, and TTPs
- **File Storage**: AWS S3 integration for persistent document storage
- **Document Processing**: Unstructured library for extracting text from various document formats
- **Wazuh SIEM Integration**: Real-time security event fetching and analysis via Wazuh API

### Frontend Architecture

- **React 19**: Modern UI framework with latest features
- **OpenAI ChatKit**: Pre-built chat interface components with real-time streaming support
- **Vite**: Fast build tool and development server
- **TypeScript**: Type-safe development experience

### Data Flow

1. User uploads threat intelligence documents through the chat interface
2. Backend processes documents, extracts text, and uploads to S3
3. Content is ingested into ChromaDB vector store for semantic search
4. AI agent analyzes document and extracts structured data (IoCs, TTPs, victim info)
5. Structured data is stored in PostgreSQL for efficient querying
6. Users query the system through natural language, which is processed by specialized agents
7. Agents retrieve relevant information from vector store, SQL database, or Wazuh SIEM
8. Results are streamed back to the user interface in real-time


## Features

### Core Capabilities

- **Threat Intelligence Processing**: Upload and parse threat reports in TXT and PDF formats
- **Structured Data Extraction**: Automatically extract and categorize:
  - Indicators of Compromise (IP addresses, domains, hashes, URLs)
  - Tactics, Techniques, and Procedures mapped to MITRE ATT&CK
  - Victim sector information
  - Incident timelines and severity assessments
  
- **Natural Language Querying**: Conversational interface for:
  - Searching reports by victim sector
  - Finding IoCs associated with specific reports
  - Querying reports by MITRE ATT&CK technique
  - Retrieving full report content
  - Semantic search across uploaded documents

- **Wazuh SIEM Integration**: 
  - Real-time security event fetching from Wazuh
  - AI-powered analysis of security alerts
  - Domain-specific event filtering
  - Automated risk assessment and recommendations
  - Streaming analysis results directly to the UI

- **Multi-Agent System**: Specialized agents with distinct capabilities:
  - **Main Agent (Gaurav)**: Primary interface for user interactions and tool orchestration. Determines which tools or agents to invoke based on user queries.
  - **Extraction Agent**: Handles structured data extraction from threat intelligence documents with Pydantic schema validation for IoCs, TTPs, and report metadata.
  - **Wazuh Agent**: Dedicated agent for Wazuh SIEM operations. Fetches security events via the Wazuh API, performs analysis, and provides security recommendations with risk assessments.

### Technical Features

- **Real-time Streaming**: WebSocket-based streaming for agent responses with direct UI streaming for Wazuh analysis
- **Tool-as-Agent Pattern**: Wazuh agent is exposed as a tool to the main agent, enabling seamless delegation
- **ReAct Loop Architecture**: Multi-turn reasoning with tool execution for complex queries
- **File Upload with Two-Phase Strategy**: Efficient handling of large file uploads
- **Vector Similarity Search**: Semantic search capabilities using embeddings
- **Structured Database Queries**: SQL-based filtering and aggregation
- **CORS Support**: Configured for local development
- **Type Safety**: Full TypeScript support on frontend

## Prerequisites

### System Requirements

- **Python**: Version 3.13 or higher
- **Node.js**: Version 18 or higher
- **PostgreSQL**: Version 12 or higher
- **AWS Account**: For S3 bucket access (optional but recommended)

### External Services

- **LLM Provider**: Access to a language model API (OpenAI, Anthropic, or compatible endpoint)
- **PostgreSQL Database**: Local or remote PostgreSQL instance
- **AWS S3 Bucket**: For document storage (optional)
- **Wazuh SIEM**: Access to a Wazuh indexer endpoint for security event analysis (optional but required for Wazuh features)

## Environment Setup

### Backend Setup

1. **Navigate to the backend directory**
   ```bash
   cd Security-Operations-Agent
   ```

2. **Create Python virtual environment**
   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate  # On Windows
   ```

3. **Install uv package manager (recommended)**
   ```bash
   pip install uv
   ```

4. **Install dependencies**
   ```bash
   uv pip install -e .
   # or using pip
   pip install -e .
   ```

5. **Set up PostgreSQL database**
   
   Install PostgreSQL if not already installed:
   ```bash
   # macOS
   brew install postgresql
   brew services start postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   sudo systemctl start postgresql
   ```

   Create a database user (optional):
   ```bash
   psql postgres
   CREATE USER your_username WITH PASSWORD 'your_password';
   ALTER USER your_username WITH SUPERUSER;
   \q
   ```

6. **Configure environment variables**
   
   Create a `.env` file in the `Security-Operations-Agent` directory:
   ```bash
   # LLM Configuration
   LMAAS_URL=https://api.openai.com/v1  # Your LLM provider endpoint
   LMAAS_KEY=your_api_key_here
   LMAAS_MODEL=gpt-4  # Model name

   # PostgreSQL Configuration
   POSTGRES_USER=your_username
   POSTGRES_PASSWORD=your_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   TARGET_DB=siem_db

   # AWS S3 Configuration (Optional)
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   S3_BUCKET_NAME=your_bucket_name
   AWS_REGION=us-east-1

   # Wazuh SIEM Configuration (Required for Wazuh integration)
   WAZUH_URL=https://your-wazuh-server:9200/_search  # Wazuh indexer endpoint
   WAZUH_USER=your_wazuh_username
   WAZUH_PASS=your_wazuh_password
   ```

7. **Initialize the database**
   
   The database tables will be created automatically on first run, but you can verify:
   ```bash
   uv run python -c "from database import init_db; init_db()"
   ```

### Frontend Setup

1. **Navigate to the frontend directory**
   ```bash
   cd Client-UI
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

## Running the Application

### Start the Backend Server

From the `Security-Operations-Agent` directory:

```bash
uv run main.py
```

The backend server will start on `http://localhost:8000`

You should see output similar to:
```
Database siem_db already exists.
Schema initialized successfully (Tables created/verified).
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Start the Frontend Development Server

From the `Client-UI` directory:

```bash
npm run dev
```

The frontend will start on `http://localhost:5173`

You should see output similar to:
```
VITE v7.2.4  ready in 500 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### Access the Application

Open your browser and navigate to `http://localhost:5173`

## Usage

### Uploading Threat Reports

1. Click the attachment icon in the chat interface
2. Select a `.txt` or `.pdf` file containing threat intelligence
3. Wait for the upload and processing confirmation
4. The document will be analyzed and stored in both the vector database and PostgreSQL

### Querying the System

**Threat Intelligence Queries:**

- "Show me all reports targeting the healthcare sector"
- "What are the IoCs for report ID 5?"
- "Find all reports using technique T1566"
- "Show me the content of file threat_report.txt"
- "Search for information about ransomware attacks"
- "What techniques are associated with report 3?"

**Wazuh SIEM Queries:**

- "Start Wazuh analysis"
- "Analyze the last 50 security events from Wazuh"
- "Show me Wazuh alerts for domain example.com"
- "What security events occurred in the last hour?"
- "Analyze Wazuh data and provide recommendations"

### Agent Delegation

The system uses a multi-agent architecture with intelligent delegation:

**Extraction Agent:**
When you upload a threat report, you may see:
```
Delegating Extraction to Extraction Agent
```
This indicates the main agent is delegating structured data extraction to the specialized Extraction Agent.

**Wazuh Agent:**
When you request Wazuh analysis, the main agent automatically invokes the Wazuh Agent as a tool. The Wazuh Agent:
1. Fetches security events from your Wazuh SIEM
2. Analyzes the events using AI
3. Streams the analysis results directly to your interface in real-time
4. Provides risk assessments and actionable recommendations

### Building for Production

**Frontend:**
```bash
cd Client-UI
npm run build
```

The production build will be in the `dist` directory.

**Backend:**
No build step required for Python. Deploy using a production ASGI server like Gunicorn:
```bash
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Troubleshooting

### Backend Issues

**Database connection errors:**
- Verify PostgreSQL is running: `pg_isready`
- Check credentials in `.env` file
- Ensure database user has necessary permissions

**ChromaDB errors:**
- Check that `./my_local_db` directory is writable
- Clear the ChromaDB directory if corrupted: `rm -rf my_local_db`

**S3 upload failures:**
- Verify AWS credentials are correct
- Check S3 bucket permissions
- Ensure bucket exists in the specified region

**LLM API errors:**
- Verify API key is valid
- Check endpoint URL is correct
- Ensure model name is supported by your provider

**Wazuh SIEM connection errors:**
- Verify Wazuh indexer is accessible from your network
- Check `WAZUH_URL`, `WAZUH_USER`, and `WAZUH_PASS` in `.env` file
- Ensure the Wazuh user has permissions to query the security events index
- If using self-signed certificates, note that SSL verification is disabled by default
- Check Wazuh server logs for authentication failures

### Frontend Issues

**Vite command not found:**
```bash
npm install
```

**CORS errors:**
- Ensure backend is running on port 8000
- Check CORS configuration in `main.py`

**WebSocket connection failures:**
- Verify backend server is running
- Check browser console for specific error messages

## License

This project is provided as-is for educational and internal use.

## Contributing

This is an internal project. For questions or issues, contact the development team.
