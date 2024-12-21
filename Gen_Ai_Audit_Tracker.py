import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2.service_account import Credentials
import io

# Google Drive API Setup
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'  # Path to your service account key

def authenticate_gdrive():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

drive_service = authenticate_gdrive()
folder_id = "<YOUR_FOLDER_ID>"  # Replace with your Google Drive folder ID

# Helper Functions
def load_data(file_path):
    return pd.read_excel(file_path)

def preprocess_data(df):
    return df

def get_latest_file_in_folder(folder_id):
    try:
        results = drive_service.files().list(
            q=f"'{folder_id}' in parents",
            pageSize=1,
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc"
        ).execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching files from Google Drive: {e}")
        return None

def download_file_from_google_drive(file_id, destination):
    request = drive_service.files().get_media(fileId=file_id)
    with open(destination, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()

def upload_file_to_google_drive(file_path, folder_id):
    file_metadata = {'name': file_path, 'parents': [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def save_auditor_data(update_df, original_df):
    try:
        for idx, row in update_df.iterrows():
            audit_idx = original_df[original_df['audit_name'] == row['audit_name']].index[0]
            original_df.loc[audit_idx, ['auditor_name', 'mobile_number', 'remarks', 'status']] = \
                row[['auditor_name', 'mobile_number', 'remarks', 'status']]
        original_df.to_excel("audit_tracker_updated.xlsx", index=False)
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False

# Streamlit App
st.title("Audit Tracker App")
role = st.sidebar.radio("Select Role:", ("Admin", "Auditor"))

if "file_uploaded" not in st.session_state:
    st.session_state['file_uploaded'] = False

if "data" not in st.session_state:
    st.session_state['data'] = None

if role == "Admin":
    st.session_state['role'] = "Admin"
    st.header("📂 Admin Section: Upload Audit Data")

    uploaded_file = st.file_uploader("Upload the Audit Tracker Excel File", type=["xlsx"])

    if uploaded_file is not None:
        df = load_data(uploaded_file)
        st.session_state['data'] = preprocess_data(df)
        st.session_state['file_uploaded'] = True

        # Save and upload to Google Drive
        uploaded_file_path = "uploaded_audit_tracker.xlsx"
        df.to_excel(uploaded_file_path, index=False)
        upload_file_to_google_drive(uploaded_file_path, folder_id)

        st.success("File uploaded and shared successfully!")

elif role == "Auditor":
    st.session_state['role'] = "Auditor"
    st.header("📝 Auditor Section: Update Audit Data")

    latest_file_id = get_latest_file_in_folder(folder_id)
    if latest_file_id:
        temp_file_path = "downloaded_audit_tracker.xlsx"
        try:
            download_file_from_google_drive(latest_file_id, temp_file_path)
            st.session_state['data'] = load_data(temp_file_path)
            st.session_state['data'] = preprocess_data(st.session_state['data'])
            st.session_state['file_uploaded'] = True
        except Exception as e:
            st.error(f"Failed to fetch the latest audit data: {e}")

    if st.session_state['file_uploaded'] and st.session_state['data'] is not None:
        df = st.session_state['data']

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

                            if save_auditor_data(update, st.session_state['data']):
                                st.success("Audit data submitted successfully!")
                                upload_file_to_google_drive("audit_tracker_updated.xlsx", folder_id)
                                st.rerun()
                            else:
                                st.error("Failed to save auditor data. Please try again.")
    else:
        st.warning("Admin has not uploaded any audit data yet.")
