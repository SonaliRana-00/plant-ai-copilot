import streamlit as st
from sentence_transformers import SentenceTransformer
from opcua import Client as OpcuaClient
from groq import Groq
import chromadb
import json
import time
import os
from logger import log_action, read_log
from users import verify_user

# ── PAGE CONFIG ────────────────────────────────────────────
st.set_page_config(
    page_title="Plant AI Co-pilot",
    page_icon="🏭",
    layout="wide"
)

# ── SESSION STATE INIT ─────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "role" not in st.session_state:
    st.session_state.role = None
if "full_name" not in st.session_state:
    st.session_state.full_name = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── CACHED RESOURCES ───────────────────────────────────────
def load_models():
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return embedding_model, groq_client

def load_sops_from_file(filepath):
    try:
        with open(filepath, "r") as f:
            content = f.read()
        chunks = [
            chunk.strip()
            for chunk in content.split("\n\n")
            if chunk.strip()
        ]
        return chunks
    except FileNotFoundError:
        return [
            "If TT-101 temperature exceeds 90°C reduce feed rate.",
            "If FT-101 flow drops below 30 m³/hr check CV-101.",
            "If PT-101 pressure exceeds 8 bar open bypass BV-101.",
        ]

@st.cache_resource
def load_knowledge_base():
    chroma_client = chromadb.PersistentClient(path="/app/data")
    try:
        chroma_client.delete_collection("plant_sops")
    except:
        pass
    collection = chroma_client.create_collection("plant_sops")
    sops = load_sops_from_file("/app/sops.txt")
    embedding_model, _ = load_models()
    vectors = embedding_model.encode(sops).tolist()
    ids = [f"SOP-{str(i+1).zfill(3)}" for i in range(len(sops))]
    collection.add(ids=ids, documents=sops, embeddings=vectors)
    return collection, ids, sops

# ── OPC-UA TOOL ────────────────────────────────────────────
def get_tag_value(tag_name):
    plc_address = os.getenv(
        "PLC_ADDRESS",
        "opc.tcp://172.20.0.10:4840/freeopcua/server/"
    )
    opcua_client = OpcuaClient(plc_address)
    tag_map = {
        "TT-101": "ns=2;i=2",
        "FT-101": "ns=2;i=3",
        "PT-101": "ns=2;i=4",
    }
    if tag_name not in tag_map:
        return f"{tag_name} not found"
    try:
        cert_path = "/app/certs/plant_app_cert.pem"
        key_path  = "/app/certs/plant_app_key.pem"
        if os.path.exists(cert_path) and os.path.exists(key_path):
            opcua_client.set_security_string(
                f"Basic256Sha256,SignAndEncrypt,{cert_path},{key_path}"
            )
            opcua_client.application_uri = "urn:plant:ai:copilot"
        opcua_client.connect()
        node = opcua_client.get_node(tag_map[tag_name])
        value = round(node.get_value(), 2)
        opcua_client.disconnect()
        return f"{tag_name} live value: {value}"
    except Exception as e:
        return f"Could not read {tag_name}: {str(e)}"

def update_setpoint(tag_name, value):
    plc_address = os.getenv(
        "PLC_ADDRESS",
        "opc.tcp://172.20.0.10:4840/freeopcua/server/"
    )
    opcua_client = OpcuaClient(plc_address)
    setpoint_map = {
        "SP_TEMP_HIGH":  "ns=2;i=8",
        "SP_FLOW_LOW":   "ns=2;i=9",
        "SP_PRESS_HIGH": "ns=2;i=10",
    }
    if tag_name not in setpoint_map:
        return f"{tag_name} not found"
    try:
        cert_path = "/app/certs/plant_app_cert.pem"
        key_path  = "/app/certs/plant_app_key.pem"
        if os.path.exists(cert_path):
            opcua_client.set_security_string(
                f"Basic256Sha256,SignAndEncrypt,{cert_path},{key_path}"
            )
        opcua_client.connect()
        node = opcua_client.get_node(setpoint_map[tag_name])
        node.set_value(float(value))
        opcua_client.disconnect()
        return f"{tag_name} updated to {value}"
    except Exception as e:
        return f"Failed to update {tag_name}: {str(e)}"

tool_map = {"get_tag_value": get_tag_value}
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_tag_value",
            "description": "Get live value for a plant instrument tag from OPC-UA",
            "parameters": {
                "type": "object",
                "properties": {
                    "tag_name": {
                        "type": "string",
                        "description": "Tag name e.g. TT-101, FT-101, PT-101"
                    }
                },
                "required": ["tag_name"]
            }
        }
    }
]

# ── RAG RETRIEVAL ──────────────────────────────────────────
def get_relevant_sop(question, collection):
    embedding_model, _ = load_models()
    query_vector = embedding_model.encode([question]).tolist()
    results = collection.query(
        query_embeddings=query_vector,
        n_results=2
    )
    return "\n".join(results["documents"][0])

# ── AGENT ──────────────────────────────────────────────────
def run_agent(question, collection):
    _, groq_client = load_models()
    messages = [{"role": "user", "content": question}]
    live_data = None
    tool_used = None

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        ai_message = response.choices[0].message
        if ai_message.tool_calls:
            tool_call = ai_message.tool_calls[0]
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            tool_used = f"{tool_name}({arguments})"
            live_data = tool_map[tool_name](arguments["tag_name"])
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": ai_message.tool_calls
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": live_data
            })
    except Exception as e:
        live_data = None
        tool_used = None

    relevant_sop = get_relevant_sop(question, collection)

    combined_prompt = f"""You are a plant operations assistant.

Live plant data:
{live_data if live_data else "Live data unavailable — answer from SOP only"}

Relevant SOP:
{relevant_sop}

Operator question:
{question}

Give a clear practical answer using the information above.
If live data is available be specific about the actual values."""

    try:
        final_response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": combined_prompt}]
        )
        answer = final_response.choices[0].message.content
    except Exception as e:
        time.sleep(5)
        try:
            final_response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": combined_prompt}]
            )
            answer = final_response.choices[0].message.content
        except Exception as e2:
            answer = "Could not generate answer. Please try again."

    log_action(
        question,
        tool_used,
        live_data,
        answer
    )
    return answer, live_data, relevant_sop, tool_used

# ── LOGIN PAGE ─────────────────────────────────────────────
def show_login_page():
    st.title("Plant AI Co-pilot")
    st.caption("Please login to continue")
    st.divider()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            user = verify_user(username, password)
            if user:
                st.session_state.logged_in = True
                st.session_state.username  = user["username"]
                st.session_state.role      = user["role"]
                st.session_state.full_name = user["full_name"]
                st.rerun()
            else:
                st.error("Invalid username or password")
                log_action(
                    question=f"LOGIN FAILED: {username}",
                    tool_used=None,
                    live_data=None,
                    answer="Authentication failed"
                )

        st.divider()
        st.caption("Demo credentials:")
        st.caption("Operator: operator1 / op123")
        st.caption("Engineer: engineer1 / eng123")

# ── MAIN APP ───────────────────────────────────────────────
def show_main_app():
    collection, ids, sops = load_knowledge_base()

    # ── SIDEBAR ────────────────────────────────────────────
    with st.sidebar:
        st.title("Plant AI Co-pilot")
        st.caption("Powered by RAG + MCP")
        st.divider()

        st.markdown(f"**User:** {st.session_state.full_name}")
        if st.session_state.role == "engineer":
            st.success("Role: Engineer")
        else:
            st.info("Role: Operator")

        if st.button("Logout"):
            log_action(
                question=f"LOGOUT: {st.session_state.username}",
                tool_used=None,
                live_data=None,
                answer="User logged out"
            )
            st.session_state.logged_in = False
            st.session_state.username  = None
            st.session_state.role      = None
            st.session_state.full_name = None
            st.session_state.messages  = []
            st.rerun()

        st.divider()
        st.markdown("**Available tags**")
        st.markdown("""
        - `TT-101` — Temperature
        - `FT-101` — Flow rate
        - `PT-101` — Pressure
        """)
        st.divider()
        st.markdown("**Knowledge base**")
        st.success(f"{len(sops)} SOPs loaded")
        st.divider()

        if st.button("Show audit log"):
            st.session_state.show_log = not st.session_state.get("show_log", False)
        if st.session_state.get("show_log"):
            st.markdown("**Recent activity**")
            logs = read_log()
            if logs:
                for log in logs[:5]:
                    st.caption(
                        f"{log['timestamp'][11:19]} — "
                        f"{log['question'][:40]}..."
                    )
            else:
                st.caption("No activity yet")

    # ── MAIN AREA ──────────────────────────────────────────
    st.title("Plant operations assistant")
    st.caption("Ask about live tag values, alarms, or operating procedures")

    # Live metrics
    col1, col2, col3 = st.columns(3)
    try:
        tt_val = get_tag_value("TT-101").split(": ")[1]
        ft_val = get_tag_value("FT-101").split(": ")[1]
        pt_val = get_tag_value("PT-101").split(": ")[1]
    except:
        tt_val = ft_val = pt_val = "N/A"

    with col1:
        st.metric("TT-101 Temperature", tt_val)
    with col2:
        st.metric("FT-101 Flow", ft_val)
    with col3:
        st.metric("PT-101 Pressure", pt_val)

    st.divider()

    # ── ENGINEER ONLY — setpoint controls ──────────────────
    if st.session_state.role == "engineer":
        st.subheader("Setpoint controls")
        st.caption("Engineer access only")

        ecol1, ecol2, ecol3 = st.columns(3)
        with ecol1:
            sp_temp = st.number_input(
                "TT-101 high alarm (°C)",
                min_value=50.0, max_value=150.0,
                value=80.0, step=1.0
            )
            if st.button("Update TT-101 setpoint"):
                result = update_setpoint("SP_TEMP_HIGH", sp_temp)
                st.success(result)
                log_action(
                    question=f"Setpoint change: SP_TEMP_HIGH={sp_temp}",
                    tool_used="update_setpoint",
                    live_data=str(sp_temp),
                    answer=result
                )
        with ecol2:
            sp_flow = st.number_input(
                "FT-101 low alarm (m³/hr)",
                min_value=0.0, max_value=100.0,
                value=30.0, step=1.0
            )
            if st.button("Update FT-101 setpoint"):
                result = update_setpoint("SP_FLOW_LOW", sp_flow)
                st.success(result)
                log_action(
                    question=f"Setpoint change: SP_FLOW_LOW={sp_flow}",
                    tool_used="update_setpoint",
                    live_data=str(sp_flow),
                    answer=result
                )
        with ecol3:
            sp_press = st.number_input(
                "PT-101 high alarm (bar)",
                min_value=0.0, max_value=15.0,
                value=7.0, step=0.5
            )
            if st.button("Update PT-101 setpoint"):
                result = update_setpoint("SP_PRESS_HIGH", sp_press)
                st.success(result)
                log_action(
                    question=f"Setpoint change: SP_PRESS_HIGH={sp_press}",
                    tool_used="update_setpoint",
                    live_data=str(sp_press),
                    answer=result
                )
        st.divider()

    # ── CHAT ───────────────────────────────────────────────
    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        scol1, scol2, scol3 = st.columns(3)
        with scol1:
            if st.button("TT-101 temperature high — what do I do?"):
                st.session_state.starter = "TT-101 temperature high — what do I do?"
        with scol2:
            if st.button("Is FT-101 flow within normal range?"):
                st.session_state.starter = "Is FT-101 flow within normal range?"
        with scol3:
            if st.button("Check PT-101 pressure status"):
                st.session_state.starter = "Check PT-101 pressure status"

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if "starter" in st.session_state:
        question = st.session_state.starter
        del st.session_state.starter
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.messages.append(
            {"role": "user", "content": question}
        )
        with st.chat_message("assistant"):
            with st.spinner("Checking live data and SOPs..."):
                answer, live_data, sop, tool_used = run_agent(question, collection)
            st.markdown(answer)
            with st.expander("How I answered this"):
                if tool_used:
                    st.markdown(f"**MCP tool called:** `{tool_used}`")
                    st.markdown(f"**Live OPC-UA data:** {live_data}")
                st.markdown(f"**SOP retrieved:**\n\n{sop}")
        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )
        st.rerun()

    if question := st.chat_input("Ask about your plant..."):
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.messages.append(
            {"role": "user", "content": question}
        )
        with st.chat_message("assistant"):
            with st.spinner("Checking live data and SOPs..."):
                answer, live_data, sop, tool_used = run_agent(question, collection)
            st.markdown(answer)
            with st.expander("How I answered this"):
                if tool_used:
                    st.markdown(f"**MCP tool called:** `{tool_used}`")
                    st.markdown(f"**Live OPC-UA data:** {live_data}")
                st.markdown(f"**SOP retrieved:**\n\n{sop}")
        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )

# ── ENTRY POINT ────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login_page()
else:
    show_main_app()