# Plant AI Co-pilot

An industrial plant operations assistant built with RAG, MCP and IEC 62443 security.

## What it does
- Answers operator questions using plant SOPs (RAG)
- Reads live tag values from OPC-UA server (MCP)
- Role based access — Operator and Engineer roles
- IEC 62443 compliant security architecture

## Tech stack
- RAG: SentenceTransformers + ChromaDB
- MCP: OPC-UA + Groq LLM (llama-3.3-70b)
- UI: Streamlit
- Security: OPC-UA certificates + RBAC + network segmentation
- Infrastructure: Docker Compose (3 containers)

## Architecture
- virtual_plc: Python OPC-UA server (port 4840)
- plant_app: RAG + MCP + Streamlit UI (port 8501)
- security_monitor: IEC 62443 dashboard (port 8502)

## Security layers (IEC 62443)
- Layer 1: OPC-UA certificate authentication
- Layer 2: Role based access control
- Layer 3: Docker network segmentation
- Layer 4: Audit logging

## Quick start
1. Add your Groq API key to .env file
2. Generate certificates: python3 generate_certs.py
3. Start containers: docker compose up
4. Open browser: localhost:8501

## Credentials (demo)
- Operator: operator1 / op123
- Engineer: engineer1 / eng123
