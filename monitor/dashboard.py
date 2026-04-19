import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Security Monitor",
    page_icon="🔒",
    layout="wide"
)

st.title("Security Monitor — IEC 62443")
st.caption("Zone 3 — Operations level")

LOG_FILE = "/app/data/audit_log.jsonl"

def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        lines = f.readlines()
    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line.strip()))
        except:
            pass
    return list(reversed(entries))

# ── METRICS ───────────────────────────────────────────────
logs = read_log()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total interactions", len(logs))
with col2:
    tool_calls = sum(1 for l in logs if l.get("tool_used"))
    st.metric("OPC-UA reads", tool_calls)
with col3:
    today = datetime.now().strftime("%Y-%m-%d")
    today_logs = [l for l in logs if l.get("timestamp","").startswith(today)]
    st.metric("Today's activity", len(today_logs))
with col4:
    failed = sum(1 for l in logs if "unavailable" in str(l.get("live_data","")))
    st.metric("Failed reads", failed)

st.divider()

# ── AUDIT LOG TABLE ───────────────────────────────────────
st.subheader("Audit log")

if logs:
    df = pd.DataFrame(logs)
    df["timestamp"] = df["timestamp"].str[11:19]
    df["question"] = df["question"].str[:60]
    df["answer"] = df["answer"].str[:80]

    st.dataframe(
        df[["timestamp", "question", "tool_used", "live_data", "answer"]],
        use_container_width=True
    )
else:
    st.info("No activity logged yet")

st.divider()

# ── AUTO REFRESH ──────────────────────────────────────────
if st.button("Refresh"):
    st.rerun()

st.caption(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")