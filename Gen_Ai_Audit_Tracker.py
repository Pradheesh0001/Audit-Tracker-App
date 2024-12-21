import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai
import pandas as pd
import streamlit as st
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

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
    try:
        return pd.read_excel(file_path, engine="openpyxl")
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Function to upload file to Google Drive
def upload_file_to_google_drive(file_path, folder_id):
    try:
        file_metadata = {
            'name': 'audit_data.xlsx',
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        st.success(f"File uploaded successfully with ID: {file['id']}")
        return file['id']
    except HttpError as error:
        st.error(f"Google API Error: {error}")
        return None

# Function to download file from Google Drive
def download_file_from_google_drive(file_id, destination):
    request = drive_service.files().get_media(fileId=file_id)
    try:
        with open(destination, 'wb') as f:
            request.execute()
        st.success(f"File downloaded to {destination}")
    except Exception as e:
        st.error(f"Error downloading file: {e}")

# Preprocess the data
def preprocess_data(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    df['audit_date'] = pd.to_datetime(df['audit_date'], errors='coerce')
    return df

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
if 'file_uploaded' not in st.session_state:
    st.session_state['file_uploaded'] = False
if 'data' not in st.session_state:
    st.session_state['data'] = None
if 'file_id' not in st.session_state:
    st.session_state['file_id'] = None

# Role Selection
role = st.radio("Select your role:", ["Admin", "Auditor"])

# Admin Section
if role == "Admin":
    st.session_state['role'] = "Admin"
    st.header("🔐 Admin Section: Upload, Query, and View Audit Updates")

    # Admin Password Validation
    password = st.text_input("Enter Admin Password:", type="password")
    if password == admin_password:
        st.success("Access granted!")

        # File upload
        uploaded_file = st.file_uploader("Upload an Audit Tracker Excel file", type=["xlsx"])

        if uploaded_file:
            # Save the uploaded file temporarily
            temp_file_path = "uploaded_audit_tracker.xlsx"
            with open(temp_file_path, "wb") as temp_file:
                temp_file.write(uploaded_file.getbuffer())

            # Upload the file to Google Drive
            file_id = upload_file_to_google_drive(temp_file_path, folder_id)

            if file_id:
                # Save the file ID in session state for retrieval by auditor
                st.session_state['file_id'] = file_id

                # Load the data from the temporary file
                st.session_state['data'] = load_data(temp_file_path)
                st.session_state['data'] = preprocess_data(st.session_state['data'])
                st.session_state['file_uploaded'] = True

                # Merge with Auditor Updates
                merged_data = merge_data(st.session_state['data'], "auditor_updates.csv")
                st.write("### Merged Data with Auditor Inputs:")
                st.write(merged_data)

                # Query GPT
                st.write("### Ask Questions About the Data:")
                question = st.text_input("Enter your query:")

                if question:
                    data_context = merged_data.to_json()
                    response = ask_gpt(question, data_context)
                    st.write("### Query Response:")
                    st.write(response)
    else:
        if password:
            st.error("Invalid password! Please try again.")

# Auditor Section
elif role == "Auditor":
    st.session_state['role'] = "Auditor"
    st.header("📝 Auditor Section: Update Audit Data")

    if st.session_state['file_uploaded'] and st.session_state['file_id'] is not None:
        # Download the file from Google Drive for the Auditor to access
        temp_file_path = "downloaded_audit_data.xlsx"
        download_file_from_google_drive(st.session_state['file_id'], temp_file_path)

        # Load and preprocess the data
        df = load_data(temp_file_path)
        if df is not None:
            df = preprocess_data(df)

            # Filter out audits that have already been assigned to an auditor
            available_audits = df[df['auditor_name'].isnull()]

            if available_audits.empty:
                st.warning("No audits are available for assignment at the moment.")
            else:
                # REGION FILTER
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
                        accept_terms = st.checkbox("Accept Terms and Conditions (Mandatory)", value=False)
                        auditor_name = st.text_input("Auditor Name:", placeholder="Enter your name")
                        mobile_number = st.text_input("Mobile Number:", placeholder="Enter your mobile number")
                        remarks = st.text_area("Remarks (Optional):")
                        status = st.selectbox("Audit Status:", ["Pending", "In Progress", "Completed"])

                        submitted = st.form_submit_button("Submit")

                        if submitted:
                            if not accept_terms:
                                st.warning("You must accept the Terms and Conditions to proceed.")
                            elif not auditor_name or not mobile_number:
                                st.warning("Auditor Name and Mobile Number are mandatory fields.")
                            else:
                                update = pd.DataFrame([{
                                    "audit_name": audit_name,
                                    "auditor_name": auditor_name,
                                    "mobile_number": mobile_number,
                                    "remarks": remarks,
                                    "status": status
                                }])

                                try:
                                    # Save and upload the auditor data
                                    if save_auditor_data(update, df):
                                        st.success("Audit data submitted successfully!")
                                        upload_file_to_google_drive("auditor_updates.csv", folder_id)
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"An error occurred during rerun: {e}")

    else:
        st.warning("Admin has not uploaded any audit data yet.")
