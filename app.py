from TeachingAgent import TeachingAgent, quick_delete
import streamlit as st
from openai import OpenAI
import tomllib
import io

with open("config.toml", "rb+") as f:
    config = tomllib.load(f)

secret = config["openai"]["secret"]
client = OpenAI(api_key=secret)

# Initialize state for the session
if "session" not in st.session_state:
    st.session_state["session"] = {"uploaded_files": {}, "files": [], "file_names": [], "history": [], "agent": None}

# Main app for managing the session
st.title("RAG Teaching Assistant")

def callback(future: tuple) -> None:
    _, revision, questions = future.result()
    st.session_state["session"]["callback_result"] = revision
    
    # add questions to main page

# Start a session
if st.session_state["session"]["agent"] is None:
    if st.button("Start Session"):
        st.session_state["session"]["agent"] = TeachingAgent(client)
        st.success("Session started!")

if st.session_state["session"]["agent"]:
    # End session
    if st.button("End Session"):
        st.session_state["session"]["agent"].close()
        st.session_state["session"] = {"uploaded_files": {}, "files": [], "file_names": [], "history": [], "agent": None}
        st.success("Session ended.")

    # File upload for the session in collapsible sidebar
    with st.sidebar:
        st.subheader("Upload Files for Current Session")
        uploaded_files = st.file_uploader("Drag and drop or upload files", accept_multiple_files=True, key="file_uploader")
        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.name not in st.session_state["session"]["uploaded_files"]:
                    file_like_object = io.BytesIO(uploaded_file.getvalue())
                    file_like_object.name = uploaded_file.name
                    st.session_state["session"]["uploaded_files"][uploaded_file.name] = file_like_object
            st.success("Files ready for upload.")

        if st.session_state["session"]["uploaded_files"]:
            st.subheader("Files Ready for Upload")
            file_names = list(st.session_state["session"]["uploaded_files"].keys())
            for file_name in file_names:
                col1, col2 = st.columns([8, 2])
                col1.write(file_name)
                if col2.button("Remove", key=file_name):
                    del st.session_state["session"]["uploaded_files"][file_name]

            if st.button("Upload Files"):
                new_files = list(st.session_state["session"]["uploaded_files"].values())
                st.session_state["session"]["files"].extend(new_files)
                st.session_state["session"]["file_names"].extend(file_names)
                st.session_state["session"]["agent"].add_files(new_files, binaries=True)
                st.session_state["session"]["uploaded_files"] = {}
                st.session_state["session"]["agent"].session_streamlit(callback)
                st.success("Files uploaded and processed successfully.")
                
        st.subheader("Uploaded Files")
        for i in st.session_state["session"]["file_names"]:
            st.write(i)

    # Display conversation history in a larger, fixed scrollable box
    st.subheader("Conversation History")
        
    for message in st.session_state["session"]["history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask a question..."):
        # Add user message to chat history
        st.session_state["session"]["history"].append({"role": "user", "content": prompt})
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
            
        resp = st.session_state["session"]["agent"].converse_streamlit(prompt)
        st.session_state["session"]["history"].append({"role": "AI", "content": resp})
        
        with st.chat_message("AI"):
            st.markdown(resp)
            
     # Add a separate tab for callback result
    if "callback_result" in st.session_state["session"] and st.session_state["session"]["callback_result"] is not None:
        with st.expander("Callback Result", expanded=False):
            st.write(st.session_state["session"]["callback_result"])
