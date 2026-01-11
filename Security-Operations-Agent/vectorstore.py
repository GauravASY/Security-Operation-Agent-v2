import chromadb
import os
import psycopg2
from agents import Runner
from database import DB_CONFIG, TARGET_DB
from chromadb.utils.embedding_functions.ollama_embedding_function import (
    OllamaEmbeddingFunction,
)
from unstructured.partition.text import partition_text
import uuid
client = chromadb.PersistentClient(path="./my_local_db")
emb_fn = OllamaEmbeddingFunction(
    url = "http://localhost:11434",
    model_name="mxbai-embed-large:335m"
)
collection = client.get_or_create_collection(name="pdf_knowledge_base_v2", embedding_function=emb_fn)

async def ingest_txt(file_path, s3_url):
    
    from llmAgent import extraction_assistant
    try:
        document = partition_text(filename=file_path)
        content = ""
        text=[]
        for doc in document:
            content += doc.text
            text.append(doc.text)        
        print("Text : \n", text)
        extracted_data = await Runner.run(extraction_assistant, content)
        data = extracted_data.final_output
        
        file_path = file_path.split("\\")[-1]
        
        conn = psycopg2.connect(dbname=TARGET_DB, **DB_CONFIG)
        cur = conn.cursor()
        if len(text) > 0:
            #check whether the file is already ingested
            cur.execute("SELECT * FROM reports WHERE filename = %s", (file_path,))
            if cur.fetchone():
                return {"success" : True, "message" : "File already ingested"}
            
            cur.execute("""
                INSERT INTO reports (filename, summary, severity, victim_sector, timeline_start, timeline_end, raw_content)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING report_id;
            """, (file_path, data.summary, data.severity, data.victim_sector, data.timeline_start, data.timeline_end, content))
            
            report_id = cur.fetchone()[0]
            
            # Inserting IoCs
            for ioc in data.iocs:
                cur.execute("INSERT INTO iocs (report_id, value, type) VALUES (%s, %s, %s)", 
                            (report_id, ioc.value, ioc.type))
                
            # Inserting TTPs
            for ttp in data.ttps:
                cur.execute("INSERT INTO ttps (report_id, technique_id, technique_name) VALUES (%s, %s, %s)", 
                            (report_id, ttp.technique_id, ttp.name))
            
            conn.commit()
            
            # Storing in ChromaDB (Vector Store)
            text.append(f"Summary: {data.summary}")
            collection.add(
                documents=text,
                metadatas=[{"report_id": report_id, "severity": data.severity, "s3_url": s3_url, "filename": file_path} for _ in range(len(text))],
                ids=[str(uuid.uuid4()) for _ in range(len(text))]
            )
            print(f"--> Successfully ingested Report ID: {report_id}")
            return {"success" : True, "message" : "File processed successfully"}
        
    except Exception as e:
        print(f"Error ingesting {file_path}: {e}")
        conn.rollback()
        return {"success" : False, "message" : "File processing failed"}
    finally:
        conn.close()
    