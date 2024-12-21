import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_account.json'  # Replace with your service account JSON file

credentials = service_account.Credentials.from_service_account_info(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

# Function to upload file to Google Drive
def upload_file_to_google_drive(file_name, folder_id):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(file_name, resumable=True)
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# Function to download file from Google Drive
def download_file_from_google_drive(file_id, destination):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(destination, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()

# Function to load data
def load_data(file_path):
    return pd.read_excel(file_path)

# Function to preprocess data
def preprocess_data(df):
    return df

# Function to save auditor data
def save_auditor_data(update, df):
    try:
        df.update(update)
        df.to_excel('updated_audit_tracker.xlsx', index=False)
        upload_file_to_google_drive('updated_audit_tracker.xlsx', folder_id)
        return True
    except Exception as e:
        st.error(f"Error: {e}")
        return False

# Streamlit app setup
st.title("Audit Tracker App")

# Sidebar for role selection
role = st.sidebar.selectbox("Select your role:", ["Admin", "Auditor"])
folder_id = "your_google_drive_folder_id"  # Replace with your Google Drive folder ID

if role == "Admin":
    st.session_state['role'] = "Admin"
    st.header("📂 Admin Section: Upload Audit Data")

    uploaded_file = st.file_uploader("Upload Audit Tracker File", type=['xlsx'])
    if uploaded_file:
        with open("audit_tracker.xlsx", "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Upload the file to Google Drive
        upload_file_to_google_drive("audit_tracker.xlsx", folder_id)
        st.success("File uploaded successfully!")

elif role == "Auditor":
    st.session_state['role'] = "Auditor"
    st.header("📝 Auditor Section: Update Audit Data")

    # Load the latest file from Google Drive
    try:
        st.write("Fetching the latest audit data...")
        query = f"'{folder_id}' in parents and name = 'audit_tracker.xlsx' and mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])

        if not files:
            st.warning("Admin has not uploaded any audit data yet.")
        else:
            # Get the file ID of the latest audit_tracker.xlsx
            file_id = files[0]["id"]

            # Download the latest audit file
            download_file_from_google_drive(file_id, "latest_audit_tracker.xlsx")

            # Load the data
            df = load_data("latest_audit_tracker.xlsx")
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

                                if save_auditor_data(update, df):
                                    st.success("Audit data submitted successfully!")
                                    upload_file_to_google_drive("auditor_updates.csv", folder_id)
                                    st.rerun()
                                else:
                                    st.error("Failed to save auditor data. Please try again.")
    except HttpError as error:
        st.error(f"Google Drive API Error: {error}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
