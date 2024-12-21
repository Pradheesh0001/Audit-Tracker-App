import pandas as pd
import streamlit as st
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import openai
import json

# Retrieve secret keys from Streamlit secrets
service_account_key = st.secrets["google"]["service_account_key"]
openai_api_key = st.secrets["openai"]["openai_api_key"]
openai.api_key = openai_api_key
admin_password = st.secrets["general"]["ADMIN_PASSWORD"]
folder_id = st.secrets["general"]["folder_id"]

# Google Drive Authentication
credentials = service_account.Credentials.from_service_account_info(
    json.loads(service_account_key),
    scopes=["https://www.googleapis.com/auth/drive.file"]
)

drive_service = build('drive', 'v3', credentials=credentials)

# Function to load audit tracker data
def load_data(file_path):
    return pd.read_excel(file_path)

# Function to download file from Google Drive
def download_file_from_google_drive(file_id, destination):
    request = drive_service.files().get_media(fileId=file_id)
    with open(destination, 'wb') as f:
        f.write(request.execute())
    return destination

# Function to upload file to Google Drive
def upload_file_to_google_drive(file_path, folder_id):
    file_metadata = {
        'name': 'audit_data.xlsx',
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file['id']

# Streamlit Session State Initialization
if "file_uploaded" not in st.session_state:
    st.session_state["file_uploaded"] = False
if "file_id" not in st.session_state:
    st.session_state["file_id"] = None

# Role Selection
role = st.radio("Select your role:", ["Admin", "Auditor"])

# Admin Section
if role == "Admin":
    st.header("🔐 Admin Section: Upload Audit Data")
    password = st.text_input("Enter Admin Password:", type="password")

    if password == admin_password:
        uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])

        if uploaded_file:
            temp_file_path = "temp_audit_data.xlsx"
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(uploaded_file.getbuffer())

            # Upload the file to Google Drive
            file_id = upload_file_to_google_drive(temp_file_path, folder_id)
            st.session_state["file_uploaded"] = True
            st.session_state["file_id"] = file_id
            st.success("File uploaded successfully!")
    else:
        if password:
            st.error("Incorrect password. Please try again.")

# Auditor Section
elif role == "Auditor":
    st.header("📝 Auditor Section: View Audit Data")

    if st.session_state["file_uploaded"]:
        try:
            temp_file_path = "downloaded_audit_data.xlsx"
            
            # Display live updates
            progress_bar = st.progress(0)
            status_text = st.empty()

            for i in range(5):  # Simulate checking for updates
                status_text.text(f"Loading data... Attempt {i + 1}")
                progress_bar.progress((i + 1) * 20)
                time.sleep(1)  # Simulating a delay (adjust as needed)

            # Download and display the data
            download_file_from_google_drive(st.session_state["file_id"], temp_file_path)
            df = load_data(temp_file_path)
            st.success("Data loaded successfully!")
            st.write("### Audit Data:")
            st.dataframe(df)

        except Exception as e:
            st.error(f"Error loading data: {e}")
    else:
        st.warning("Admin has not uploaded any audit data yet.")
