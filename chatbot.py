import json
import boto3
import streamlit as st
from PyPDF2 import PdfReader

REGION = "us-east-1"
MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
IDENTITY_POOL_ID = "us-east-1:7771aae7-be2c-4496-a582-615af64292cf"
USER_POOL_ID = "us-east-1_koPKi1lPU"
APP_CLIENT_ID = "3h7m15971bnfah362dldub1u2p"
USERNAME = "smityyt67@gmail.com"
PASSWORD = "jordanAir@3233"

def get_credentials(username, password):
    idp_client = boto3.client("cognito-idp", region_name=REGION)
    response = idp_client.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": username, "PASSWORD": password},
        ClientId=APP_CLIENT_ID,
    )
    id_token = response["AuthenticationResult"]["IdToken"]

    identity_client = boto3.client("cognito-identity", region_name=REGION)
    identity_response = identity_client.get_id(
        IdentityPoolId=IDENTITY_POOL_ID,
        Logins={f"cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}": id_token},
    )

    creds_response = identity_client.get_credentials_for_identity(
        IdentityId=identity_response["IdentityId"],
        Logins={f"cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}": id_token},
    )

    return creds_response["Credentials"]

def build_prompt(courses, question, structure, chat_history=None):
    if chat_history is None:
        chat_history = []
    prompt = "You are a helpful RMIT course advisor.\n\n"
    
    for msg in chat_history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        prompt += f"{role.capitalize()}: {content}\n"

    prompt += f"User: {question}\n\n"
    prompt += "Relevant course structure:\n" + json.dumps(structure, indent=2) + "\n\n"
    prompt += "Available courses:\n" + json.dumps(courses, indent=2) + "\n\n"
    prompt += "Based on the above, provide tailored course advice.\n"

    return prompt

def extract_text_from_pdfs(pdf_files):
    if not pdf_files:
        return "[No PDF files uploaded]"
    
    all_text = []
    for pdf_file in pdf_files:
        try:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text.strip())
        except Exception as e:
            all_text.append(f"[Error reading file {pdf_file.name}: {str(e)}]")
    combined_text = "\n\n".join(all_text)
    return combined_text if combined_text.strip() else "[No extractable text found in PDF files]"

def invoke_bedrock(prompt_text, max_tokens=640, temperature=0.3, top_p=0.9):
    credentials = get_credentials(USERNAME, PASSWORD)

    bedrock_runtime = boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretKey"],
        aws_session_token=credentials["SessionToken"],
    )

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "messages": [{"role": "user", "content": prompt_text}]
    }

    response = bedrock_runtime.invoke_model(
        body=json.dumps(payload),
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json"
    )

    result = json.loads(response["body"].read())
    return result["content"][0]["text"]

def format_chat_history(chat_history):
    lines = []
    for msg in chat_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['content']}\n")
    return "\n".join(lines)

st.set_page_config(page_title="RMIT Student Support", layout="centered")

with st.container():
    cols = st.columns([1, 6])
    with cols[0]:
        st.markdown(
            """
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 20px; width: 100px; height:100px">
                <img src="https://quangcaoviet.info/wp-content/uploads/2017/05/RMIT-LOGO-project.jpg"
                    style="width: 100px; height: 60px; object-fit: cover;">
            </div>
            """,
            unsafe_allow_html=True
        )
    with cols[1]:
        st.markdown(f"""
        <h1 style="color:#ED1C24; width:100% font-family: 'Arial Black', Gadget, sans-serif; margin-bottom: 0;">
            \U0001F393 RMIT Student Support
        </h1>
        <p style=" font-size:16px; margin-top: 0; ">
            This assistant helps students to solve their problems.
        </p>
        """, unsafe_allow_html=True)

st.markdown("---")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    
st.subheader("Step 1: Choose your data input format")
upload_mode = st.radio(
    "Select format:", 
    ["Structured JSON files", "Unstructured PDF files"],
    horizontal=True
)

if upload_mode == "Structured JSON files":
    uploaded_courses_json = st.file_uploader("\U0001F4C1 Upload `courses_data.json`", type=["json"], key="courses")
    uploaded_structure_json = st.file_uploader("\U0001F4C1 Upload `cyber_security_program_structure.json`", type=["json"], key="structure")
    uploaded_pdfs = None
else:
    uploaded_pdfs = st.file_uploader("\U0001F4C4 Upload one or more PDF files", type=["pdf"], accept_multiple_files=True)
    uploaded_courses_json = None
    uploaded_structure_json = None

st.subheader("Advanced Settings")
temperature = st.slider(
    "🎛️ Response Creativity (Temperature)",
    min_value=0.0,
    max_value=1.0,
    value=0.3,
    step=0.05,
    help="Higher = more creative, Lower = more focused and factual"
)

if st.button("📄 Summarize Uploaded Data", use_container_width=True):
    try:
        summary_prompt = None
        if upload_mode == "Structured JSON files":
            if uploaded_courses_json and uploaded_structure_json:
                try:
                    courses = json.load(uploaded_courses_json)
                    structure = json.load(uploaded_structure_json)
                    summary_prompt = (
                        "You are a course advisor. Summarize the following:\n\n"
                        f"Program Structure:\n{json.dumps(structure, indent=2)}\n\n"
                        f"Courses Offered:\n{json.dumps(courses, indent=2)}"
                    )
                except json.JSONDecodeError:
                    st.error("One or both JSON files are invalid. Please upload valid JSON files.")
                    summary_prompt = None
            else:
                st.warning("Please upload both JSON files to summarize.")
                summary_prompt = None

        elif upload_mode == "Unstructured PDF files":
            if uploaded_pdfs:
                extracted_text = extract_text_from_pdfs(uploaded_pdfs)
                if extracted_text.startswith("[No"):
                    st.warning("No extractable text found in uploaded PDFs for summarization.")
                    summary_prompt = None
                else:
                    summary_prompt = (
                        "You are a course advisor. Summarize the following course and program document text:\n\n"
                        + extracted_text
                    )
            else:
                st.warning("Please upload at least one PDF file to summarize.")
                summary_prompt = None

        if summary_prompt:
            with st.spinner("🔎 Summarizing..."):
                summary = invoke_bedrock(summary_prompt, temperature=temperature)
                st.text_area("📄 Claude's Summary", summary, height=300)
                st.download_button("💾 Download Summary", summary, file_name="summary.txt")

    except Exception as e:
        st.error(f"❌ Error during summarization: {str(e)}")

st.subheader("Step 2: Ask a question")
user_question = st.text_input(
    "\U0001F4AC What would you like to ask?",
    placeholder="e.g., I'm a second-year student interested in digital forensics and blockchain."
)

if st.button("\U0001F4A1 Get Advice", use_container_width=True):
    if not user_question:
        st.warning("Please enter a question.")
    elif upload_mode == "Structured JSON files" and (not uploaded_courses_json or not uploaded_structure_json):
        st.warning("Please upload both JSON files.")
    elif upload_mode == "Unstructured PDF files" and not uploaded_pdfs:
        st.warning("Please upload at least one PDF file.")
    else:
        try:
            if upload_mode == "Structured JSON files":
                try:
                    courses = json.load(uploaded_courses_json)
                    structure = json.load(uploaded_structure_json)
                except json.JSONDecodeError:
                    st.error("One or both JSON files are invalid. Please upload valid JSON files.")
                    courses, structure = None, None
                if courses is None or structure is None:
                    st.stop()
                prompt = build_prompt(courses, user_question, structure, st.session_state.chat_history)
            else:
                extracted_text = extract_text_from_pdfs(uploaded_pdfs)
                if extracted_text.startswith("[No"):
                    extracted_text = "No course documents available to reference."
                prompt = (
                    "You are a course advisor. The following is extracted from official course documents:\n\n"
                    + extracted_text +
                    "\n\nPlease answer the following question based on this information:\n"
                    + user_question
                )

            with st.spinner("\U0001F50D Generating advice..."):
                answer = invoke_bedrock(prompt, temperature=temperature)
                
            st.session_state.chat_history.append({"role": "user", "content": user_question})
            st.session_state.chat_history.append({"role": "assistant", "content": answer})

            st.success("\u2705 Response received")
            st.text_area("\U0001F916 Claude's Answer", answer, height=300)
            st.download_button(
                label="📥 Download Advice",
                data=answer,
                file_name="rmit_course_advice.txt",
                mime="text/plain"
            )

        except Exception as e:
            st.error(f"\u274C Error: {str(e)}")

if "reset_flag" not in st.session_state:
    st.session_state.reset_flag = False

if st.button("🔄 Reset Chat History"):
    st.session_state.chat_history = []
    st.session_state.reset_flag = True
    st.success("Chat history cleared!")

if st.checkbox("📜 Show full chat history"):
    if st.session_state.reset_flag:
        st.info("Chat history was just cleared.")
        st.session_state.reset_flag = False
    else:
        for msg in st.session_state.chat_history:
            role_icon = "🧑" if msg["role"] == "user" else "🤖"
            st.markdown(f"**{role_icon} {msg['role'].capitalize()}:** {msg['content']}")
            
if st.session_state.chat_history:
    chat_text = format_chat_history(st.session_state.chat_history)
    st.download_button(
        label="💾 Download Chat History",
        data=chat_text,
        file_name="rmit_course_advice_chat.txt",
        mime="text/plain"
    )
    
st.markdown(f"""
<style>
    .footer {{
        visibility: visible;
        text-align: center;
        padding: 10px 20px;
        background-color: #ED1C24;
        color: white !important;
        font-weight: bold;
        font-size: 14px;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        max-width: 100vw;
        box-sizing: border-box;
        z-index: 1000;
        box-shadow: 0 -2px 5px rgba(0,0,0,0.3);
        overflow-wrap: break-word;
        word-wrap: break-word;
        hyphens: auto;
    }}
    /* Make sure main app content doesn’t get hidden under the footer */
    .stApp {{
        padding-bottom: 50px;  /* footer height + some padding */
        max-width: 100vw;
        overflow-x: hidden;
    }}
</style>
<div class="footer">
    © 2025 RMIT University - Cyber Security Department
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    /* Hide Streamlit default menu (top-right hamburger) */
    #MainMenu {visibility: hidden;}
    /* Hide Streamlit footer */
    footer {visibility: hidden;}
    /* Also remove the default top padding so no black space */
    /* Remove extra padding from header */
    .css-1d391kg { background-color: white !important; }
</style>
""", unsafe_allow_html=True)
