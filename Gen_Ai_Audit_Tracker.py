import json
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import openai
import pandas as pd
import streamlit as st
from io import BytesIO

# Retrieve secret keys from Streamlit secrets
service_account_key = st.secrets["google"]["service_account_key"]
openai_api_key = st.secrets["openai"]["openai_api_key"]
admin_password = st.secrets["general"]["ADMIN_PASSWORD"]
folder_id = st.secrets["general"]["folder_id"]

openai.api_key = openai_api_key

# Google Drive Authentication
credentials = service_account.Credentials.from_service_account_info(
    json.loads(service_account_key),
    scopes=["https://www.googleapis.com/auth/drive"]
)
drive_service = build('drive', 'v3', credentials=credentials)

# Function to upload file to Google Drive
def upload_file_to_google_drive(file_path, folder_id, file_name):
    try:
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file['id']
    except Exception as e:
        st.error(f"An error occurred while uploading the file: {e}")
        return None

# Function to download file from Google Drive
def download_file_from_google_drive(file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file_data = BytesIO()
        downloader = MediaIoBaseDownload(file_data, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        file_data.seek(0)
        return file_data
    except Exception as e:
        st.error(f"An error occurred while downloading the file: {e}")
        return None

# Function to load audit tracker data
def load_data(file):
    return pd.read_excel(file)

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

# Streamlit UI setup
st.title('Audit Tracker GenAI App')

# Role Selection
role = st.radio("Select your role:", ["Admin", "Auditor"])

# Admin Section
if role == "Admin":
    st.header("\U0001F512 Admin Section: Upload and Query Audit Data")

    password = st.text_input("Enter Admin Password:", type="password")

    if password == admin_password:
        st.success("Access granted!")

        uploaded_file = st.file_uploader("Upload an Audit Tracker Excel file", type=["xlsx"])

        if uploaded_file:
            data = load_data(uploaded_file)
            data = preprocess_data(data)

            # Save file to Google Drive
            file_id = upload_file_to_google_drive(uploaded_file, folder_id, "audit_tracker.xlsx")
            if file_id:
                st.success("File uploaded successfully and available for auditors.")

            st.write("### Uploaded Data:")
            st.write(data)

            # Query GPT
            question = st.text_input("Ask a question about the data:")

            if question:
                response = ask_gpt(question, data.to_json())
                st.write("### GPT Response:")
                st.write(response)
    else:
        if password:
            st.error("Invalid password! Please try again.")

# Auditor Section
elif role == "Auditor":
    st.header("\U0001F4DD Auditor Section: View and Update Audit Data")

    # Fetch the audit tracker file from Google Drive
    search_query = f"name='audit_tracker.xlsx' and '{folder_id}' in parents"
    results = drive_service.files().list(q=search_query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if files:
        file_id = files[0]['id']
        file_data = download_file_from_google_drive(file_id)

        if file_data:
            data = load_data(file_data)
            data = preprocess_data(data)

            st.write("### Available Audit Data:")
            st.write(data)

            st.write("### Update Audit Data:")
            selected_audit = st.selectbox("Select Audit Name:", data['audit_name'].unique())

            with st.form("update_form"):
                auditor_name = st.text_input("Auditor Name:")
                status = st.selectbox("Status:", ["Pending", "In Progress", "Completed"])
                remarks = st.text_area("Remarks:")

                submitted = st.form_submit_button("Submit")

                if submitted:
                    data.loc[data['audit_name'] == selected_audit, ['auditor_name', 'status', 'remarks']] = [
                        auditor_name, status, remarks
                    ]

                    # Save updated data to Google Drive
                    updated_file = BytesIO()
                    data.to_excel(updated_file, index=False)
                    updated_file.seek(0)

                    upload_file_to_google_drive(updated_file, folder_id, "audit_tracker.xlsx")
                    st.success("Audit data updated successfully!")
    else:
        st.warning("No audit data available. Please check with the admin.")
