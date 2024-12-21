import pandas as pd
import streamlit as st
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
import io
import json

# Streamlit Secrets for Credentials
service_account_key = st.secrets["google"]["service_account_key"]
openai_api_key = st.secrets["openai"]["openai_api_key"]
admin_password = st.secrets["general"]["ADMIN_PASSWORD"]
folder_id = st.secrets["general"]["folder_id"]

# Authenticate with Google Drive API
credentials = service_account.Credentials.from_service_account_info(
    json.loads(service_account_key),
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build("drive", "v3", credentials=credentials)

# Streamlit Session State
if "file_uploaded" not in st.session_state:
    st.session_state["file_uploaded"] = False
if "file_id" not in st.session_state:
    st.session_state["file_id"] = None


def upload_file_to_google_drive(file_path, folder_id):
    """Upload file to Google Drive and return file ID."""
    try:
        file_metadata = {"name": "audit_data.xlsx", "parents": [folder_id]}
        media = MediaFileUpload(file_path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        return uploaded_file.get("id")
    except Exception as e:
        st.error(f"Error during file upload: {e}")
        return None


def download_file_from_google_drive(file_id):
    """Download file from Google Drive using file ID."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"Error during file download: {e}")
        return None


def load_data_from_excel(buffer):
    """Load data from Excel file buffer."""
    try:
        return pd.read_excel(buffer)
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return None


# Main App
st.title("📋 Audit Tracker App")

role = st.radio("Select your role:", ["Admin", "Auditor"])

if role == "Admin":
    st.header("🔐 Admin Section: Upload Audit Data")
    password = st.text_input("Enter Admin Password:", type="password")

    if password == admin_password:
        uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx"])
        if uploaded_file:
            temp_file_path = "temp_audit_data.xlsx"
            with open(temp_file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            try:
                file_id = upload_file_to_google_drive(temp_file_path, folder_id)
                if file_id:
                    st.session_state["file_uploaded"] = True
                    st.session_state["file_id"] = file_id
                    st.success("File uploaded successfully!")
                else:
                    st.error("Failed to upload file to Google Drive.")
            except Exception as e:
                st.error(f"Unexpected error: {e}")
    elif password:
        st.error("Incorrect password. Please try again.")

elif role == "Auditor":
    st.header("📝 Auditor Section: View Audit Data")

    if st.session_state["file_uploaded"] and st.session_state["file_id"]:
        try:
            with st.spinner("Fetching the latest data..."):
                buffer = download_file_from_google_drive(st.session_state["file_id"])
                if buffer:
                    df = load_data_from_excel(buffer)
                    if df is not None:
                        st.success("Data loaded successfully!")
                        st.write("### Audit Data:")
                        st.dataframe(df)
                    else:
                        st.error("Failed to process the uploaded data.")
        except Exception as e:
            st.error(f"Unexpected error while fetching data: {e}")
    else:
        st.warning("Admin has not uploaded any audit data yet.")
