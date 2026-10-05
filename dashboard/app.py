from __future__ import annotations

import uuid

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="AuditPilot - JNMV Overseas", page_icon="🤖", layout="wide")
API = st.sidebar.text_input("Backend URL", "http://127.0.0.1:8000")
MODE = st.sidebar.selectbox("Agent mode", ["demo", "real"], index=0)
st.title("AuditPilot")
st.caption("JNMV Overseas Pvt. Ltd. - Enterprise Workflow & Data Agent")

if "token" not in st.session_state:
    st.session_state.token = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.write(f"Mode: **{MODE.title()}**")
    st.write("Demo mode needs no API key. Real mode uses the server-side `.env` key.")

if not st.session_state.token:
    st.subheader("Login")
    email = st.text_input("Email", value="analyst@jnmv.com")
    password = st.text_input("Password", value="Analyst@123", type="password")
    if st.button("Login"):
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
        if r.ok:
            data = r.json()
            st.session_state.token = data["access_token"]
            st.session_state.user = data["user"]
            st.rerun()
        st.error(r.text)
    st.stop()

user = st.session_state.user
st.sidebar.success(f"Logged in: {user['name']} ({user['role']})")
page = st.sidebar.radio("Page", ["Chat", "Approvals", "Audit", "Data", "Memory", "Evaluation"])
headers = {"Authorization": f"Bearer {st.session_state.token}"}

if page == "Chat":
    st.subheader("Chat")
    prompt = st.chat_input("Ask a JNMV business question...")
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            r = requests.post(f"{API}/chat", headers=headers, json={"session_id": st.session_state.session_id, "message": prompt, "mode": MODE}, timeout=90)
            if r.ok:
                data = r.json()
                st.markdown(data["answer"])
                with st.expander("How I got this"):
                    st.write("Intent:", data.get("intent"))
                    st.write("Plan:", data.get("plan"))
                    st.write("Confidence:", data.get("confidence"))
                    if data.get("sql"):
                        st.code(data["sql"], language="sql")
                    if data.get("rows"):
                        st.dataframe(pd.DataFrame(data["rows"]))
                    if data.get("policy_chunks"):
                        for c in data["policy_chunks"]:
                            st.write(f"**{c['doc']} / {c['section']}**")
                            st.caption(c["text"])
                    st.write("Risk:", data.get("risk"))
                    st.write("Guard events:", data.get("guard_events"))
                    st.write("Evidence:", data.get("evidence"))
                st.session_state.messages.append({"role": "assistant", "content": data["answer"]})
            else:
                st.error(r.text)

elif page == "Approvals":
    st.subheader("Approval Queue")
    r = requests.get(f"{API}/approvals", headers=headers, timeout=30)
    if not r.ok:
        st.warning("Manager/Admin access required.")
    else:
        pending = r.json()
        if not pending:
            st.info("No pending approvals.")
        for item in pending:
            with st.expander(f"#{item['id']} - {item['action_type']} - {item['risk_level']}"):
                st.json({"payload": item["payload"], "evidence": item["evidence"], "required_role": item["required_role"]})
                comment = st.text_input("Comment", key=f"comment-{item['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Approve", key=f"approve-{item['id']}"):
                    rr = requests.post(f"{API}/approvals/{item['id']}/approve", headers=headers, json={"comment": comment or "Approved"}, timeout=60)
                    if rr.ok:
                        data = rr.json()
                        st.success(f"Action #{item['id']} {data.get('status', 'completed')}. Verified={data.get('verified')}")
                        st.markdown("**Execution result**")
                        st.json(data)
                    else:
                        st.error(rr.text)
                    st.rerun()
                if c2.button("Reject", key=f"reject-{item['id']}"):
                    rr = requests.post(f"{API}/approvals/{item['id']}/reject", headers=headers, json={"comment": comment or "Rejected"}, timeout=60)
                    if rr.ok:
                        st.success(f"Action #{item['id']} rejected.")
                    else:
                        st.error(rr.text)
                    st.rerun()

        st.divider()
        st.subheader("Recent decisions")
        hr = requests.get(f"{API}/approvals/history", headers=headers, timeout=30)
        if hr.ok:
            history = hr.json()
            if history:
                hdf = pd.DataFrame([{
                    "id": x["id"],
                    "action": x["action_type"],
                    "risk": x["risk_level"],
                    "status": x["status"],
                    "decided_by": x["decided_by"],
                    "decided_at": x["decided_at"],
                } for x in history])
                st.dataframe(hdf, use_container_width=True)

elif page == "Audit":
    st.subheader("Audit Log")
    r = requests.get(f"{API}/audit", headers=headers, timeout=30)
    if r.ok:
        df = pd.DataFrame(r.json())
        st.dataframe(df, use_container_width=True)
        st.download_button("Export audit CSV", df.to_csv(index=False), "jnmv_audit_log.csv", "text/csv")
        if st.button("Verify hash chain"):
            rr = requests.get(f"{API}/audit/verify", headers=headers, timeout=30)
            st.json(rr.json())
        if st.button("Simulate tamper (demo)"):
            rr = requests.post(f"{API}/audit/simulate-tamper", headers=headers, timeout=30)
            st.json(rr.json())
            st.info("Run Verify again to demonstrate tamper detection.")
    else:
        st.warning("Admin access required.")

elif page == "Data":
    st.subheader("CSV Data")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file and st.button("Profile CSV"):
        r = requests.post(f"{API}/data/upload", headers=headers, files={"file": (file.name, file.getvalue(), "text/csv")}, timeout=60)
        st.json(r.json())

elif page == "Memory":
    st.subheader("Persistent Memory")
    r = requests.get(f"{API}/memory", headers=headers, timeout=30)
    if r.ok:
        for item in r.json():
            cols = st.columns([5, 1])
            cols[0].write(f"**{item['kind']}** - {item['content']}")
            if cols[1].button("Delete", key=f"mem-{item['id']}"):
                requests.delete(f"{API}/memory/{item['id']}", headers=headers, timeout=30)
                st.rerun()

elif page == "Evaluation":
    st.subheader("Evaluation Results")
    r = requests.get(f"{API}/eval/results", headers=headers, timeout=30)
    if r.ok:
        st.dataframe(pd.DataFrame(r.json()))
    else:
        st.warning("Admin access required. Run python eval_agent.py first.")
