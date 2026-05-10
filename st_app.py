import streamlit as st
import json, argparse, uvicorn, threading, requests
from api.main import app
import streamlit.components.v1 as components

def start_server(host, port):
    uvicorn.run(app, host=host, port=port, log_level="error")

if "server_started" not in st.session_state:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args, _ = parser.parse_known_args()

    thread = threading.Thread(target=start_server, args=(args.host, args.port), daemon=True)
    thread.start()
    st.session_state.server_started = True
    st.session_state.api_url = f"http://{args.host}:{args.port}"

st.title("Knowledge Graph Builder")

mode = st.selectbox("Choose input method", options=["Enter Text", "Upload file (pdf/.txt)"])
raw_text = ""
uploaded_file = None
file_bytes = None

if mode == "Enter Text":
    raw_text = st.text_area("Input Text")
elif mode == "Upload file (pdf/.txt)":
    uploaded_file = st.file_uploader("Upload", type=["txt", "pdf"])
    file_bytes = uploaded_file.read() if uploaded_file else None
else:
    st.warning("Please enter text or upload a file.")
    
if st.button("Build Graph"):
    with st.spinner("Extracting triples..."):
        try:
            if uploaded_file and file_bytes:
                response = requests.post(
                    f"{st.session_state.api_url}/build-graph", 
                    files={"file": ("filename.txt", file_bytes, "text/plain")}
                )
            elif raw_text:
                response = requests.post(
                    f"{st.session_state.api_url}/build-graph", 
                    data={"text": raw_text} 
                )
            if response.status_code == 200:
                st.session_state.triples = response.json()["triples"]
                st.session_state.graph_html = response.json()["graph"]
                st.success("Graph Built successfully!")
            else:
                st.error(f"API Error: {response.text}")
        except Exception as e:
            st.error(f"Connection failed: {e}")
    

if "triples" in st.session_state:
    st.subheader("Interactive Knowledge Graph")
    components.html(st.session_state.graph_html, height=550)
    st.download_button(
        label="Download Triples",
        data=json.dumps(st.session_state.triples, indent=2),
        file_name="triples.json",
        mime="application/json"
    )
