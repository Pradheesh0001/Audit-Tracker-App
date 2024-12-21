import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import openai
import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError

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

# Function to upload file to Google Drive
def upload_file_to_google_drive(file_path, folder_id):
    try:
        file_metadata = {
            'name': 'audit_tracker_latest.xlsx',
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.success(f"File uploaded successfully with ID: {file['id']}")
    except HttpError as error:
        st.error(f"Google API Error: {error}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# Function to fetch the latest file from Google Drive
def fetch_latest_audit_data(folder_id, filename="audit_tracker_latest.xlsx"):
    try:
        query = f"'{folder_id}' in parents and name contains 'audit_tracker' and mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
        results = drive_service.files().list(q=query, pageSize=1, orderBy="modifiedTime desc", fields="files(id, name)").execute()
        files = results.get('files', [])
        if not files:
            st.warning("No audit tracker file found in Google Drive.")
            return None

        file_id = files[0]['id']
        request = drive_service.files().get_media(fileId=file_id)
        with open(filename, "wb") as f:
            request.execute()
        st.success(f"Latest audit tracker data fetched: {files[0]['name']}")
        return filename
    except HttpError as error:
        st.error(f"Error fetching audit tracker data: {error}")
        return None

# Preprocess the data
def preprocess_data(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    df['audit_date'] = pd.to_datetime(df['audit_date'], errors='coerce')
    return df

# Query OpenAI GPT for answers
def ask_gpt(query, context):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert assistant for audit data."},
                {"role": "user", "content": f"Data Context: {context}\n\nQuestion: {query}"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        return f"An error occurred: {e}"

# Save auditor-submitted data
def save_auditor_data(data, admin_df, filename="auditor_updates.csv"):
    try:
        admin_df.to_csv(filename, index=False)
        st.success("Audit data saved successfully!")
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# Merge Admin data and Auditor updates
def merge_data(admin_df, auditor_updates_path):
    try:
        auditor_df = pd.read_csv(auditor_updates_path)
        merged_df = pd.merge(admin_df, auditor_df, on="audit_name", how="left")
        return merged_df
    except Exception as e:
        st.error(f"Error merging data: {e}")
        return admin_df

# Streamlit UI setup
st.title('Audit Tracker GenAI App')

# Session state initialization
if 'role' not in st.session_state:
    st.session_state['role'] = None

# Role Selection
role = st.radio("Select your role:", ["Admin", "Auditor"])

# Admin Section
if role == "Admin":
    st.session_state['role'] = "Admin"
    st.header("🔐 Admin Section: Upload, Query, and View Audit Updates")

    password = st.text_input("Enter Admin Password:", type="password")
    if password == admin_password:
        st.success("Access granted!")

        # File upload
        uploaded_file = st.file_uploader("Upload an Audit Tracker Excel file", type=["xlsx"])
        if uploaded_file:
            temp_file_path = "uploaded_audit_tracker.xlsx"
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(uploaded_file.getbuffer())
            upload_file_to_google_drive(temp_file_path, folder_id)

            st.success("File uploaded and updated successfully!")
    else:
        if password:
            st.error("Invalid password! Please try again.")

# Auditor Section
elif role == "Auditor":
    st.session_state['role'] = "Auditor"
    st.header("📝 Auditor Section: Update Audit Data")

    latest_data_file = fetch_latest_audit_data(folder_id)
    if latest_data_file:
        df = load_data(latest_data_file)
        df = preprocess_data(df)

        available_audits = df[df['auditor_name'].isnull()]
        if available_audits.empty:
            st.warning("No audits are available for assignment at the moment.")
        else:
            st.write("### Filter by Region:")
            region_list = available_audits['region'].dropna().unique()
            selected_region = st.selectbox("Select Region:", options=region_list)

            region_based_audits = available_audits[available_audits['region'] == selected_region]
            if region_based_audits.empty:
                st.warning("No audits are available in this region.")
            else:
                audit_name = st.selectbox("Select Audit Name:", region_based_audits['audit_name'].unique())
                selected_audit = region_based_audits[region_based_audits['audit_name'] == audit_name].iloc[0]
                st.write("### Audit Details:")
                st.write(selected_audit)

                with st.form("auditor_form"):
                    st.write("### Auditor Inputs:")
                    auditor_name = st.text_input("Auditor Name:", placeholder="Enter your name")
                    remarks = st.text_area("Remarks (Optional):")
                    status = st.selectbox("Audit Status:", ["Pending", "In Progress", "Completed"])
                    submitted = st.form_submit_button("Submit")

                    if submitted:
                        update = pd.DataFrame([{
                            "audit_name": audit_name,
                            "auditor_name": auditor_name,
                            "remarks": remarks,
                            "status": status
                        }])
                        if save_auditor_data(update, df):
                            upload_file_to_google_drive("auditor_updates.csv", folder_id)
