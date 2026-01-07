import psycopg2
import os
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configuration
DB_CONFIG = {
    "user": os.environ.get("POSTGRES_USER"),
    "password": os.environ.get("POSTGRES_PASSWORD"),
    "host": os.environ.get("POSTGRES_HOST"),
    "port": os.environ.get("POSTGRES_PORT")
}
TARGET_DB = os.environ.get("TARGET_DB")

def init_db():
    """
    1. Checks if the database 'siem_db' exists; creates it if not.
    2. Connects to 'siem_db' and creates the required tables.
    """
    
    conn = psycopg2.connect(dbname="postgres", **DB_CONFIG)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    # Check if DB exists
    cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{TARGET_DB}'")
    exists = cur.fetchone()
    
    if not exists:
        print(f"Creating database {TARGET_DB}...")
        cur.execute(f"CREATE DATABASE {TARGET_DB}")
    else:
        print(f"Database {TARGET_DB} already exists.")
    
    cur.close()
    conn.close()

    # --- Step B: Create the Tables ---
    # Now connect to the specific SIEM database
    conn = psycopg2.connect(dbname=TARGET_DB, **DB_CONFIG)
    cur = conn.cursor()
    
    # Define the Schema (Using IF NOT EXISTS for safety)
    # Remove the raw_content column. No need to store the raw content in the database as report is stored in S3.
    table_schema = """
    -- 1. Reports Table
    CREATE TABLE IF NOT EXISTS reports (
        report_id SERIAL PRIMARY KEY,
        filename VARCHAR(255),
        summary TEXT,
        severity VARCHAR(50),
        victim_sector VARCHAR(100),
        timeline_start VARCHAR(100),
        timeline_end VARCHAR(100),
        raw_content TEXT,   
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 2. Indicators (IoCs)
    CREATE TABLE IF NOT EXISTS iocs (
        ioc_id SERIAL PRIMARY KEY,
        report_id INT REFERENCES reports(report_id) ON DELETE CASCADE,
        value VARCHAR(255),
        type VARCHAR(50)
    );

    -- 3. TTPs (MITRE)
    CREATE TABLE IF NOT EXISTS ttps (
        ttp_id SERIAL PRIMARY KEY,
        report_id INT REFERENCES reports(report_id) ON DELETE CASCADE,
        technique_id VARCHAR(50),
        technique_name VARCHAR(100)
    );
    """
    
    try:
        cur.execute(table_schema)
        conn.commit()
        print("Schema initialized successfully (Tables created/verified).")
    except Exception as e:
        print(f"Error creating schema: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

