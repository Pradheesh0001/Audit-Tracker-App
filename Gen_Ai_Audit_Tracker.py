import openai
import pandas as pd
import streamlit as st

App_Developer = 'Pradheesh Selvan'
App_creater = 'Pradheesh Selvan'

# Set your OpenAI API key
openai.api_key = "OPENAI_API_KEY"  # Replace with a valid API key

# Password for Admin Access
ADMIN_PASSWORD = "ADMIN_PASSWORD"

# Function to load audit tracker data
def load_data(file_path):
    return pd.read_excel(file_path)

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
                {"role": "system", "content": "You are an expert assistant for audit data. Do not include any programming code in your responses."},
                {"role": "user", "content": f"Data Context: {context}\n\nQuestion: {query}"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        response_text = response['choices'][0]['message']['content'].strip()

        # Remove all code blocks from the response
        if "```" in response_text:  # Detect code blocks
            response_text = response_text.split("```")[0].strip()

        # Additional check for inline code (e.g., HTML, SQL)
        if "<" in response_text and ">" in response_text:  # Potential HTML or XML code
            response_text = "Response excluded due to programming code."

        return response_text
    except Exception as e:
        return f"An error occurred: {e}"

# Save auditor-submitted data
def save_auditor_data(data, admin_df, filename="auditor_updates.csv"):
    try:
        if 'auditor_name' not in admin_df.columns:
            admin_df['auditor_name'] = None
        if 'status' not in admin_df.columns:
            admin_df['status'] = None
        if 'remarks' not in admin_df.columns:
            admin_df['remarks'] = None
        if 'mobile_number' not in admin_df.columns:
            admin_df['mobile_number'] = None

        for index, row in data.iterrows():
            audit_name = row['audit_name']
            auditor_name = row['auditor_name']
            status = row['status']
            remarks = row['remarks']
            mobile_number = row['mobile_number']

            admin_df.loc[admin_df['audit_name'] == audit_name, 'auditor_name'] = auditor_name
            admin_df.loc[admin_df['audit_name'] == audit_name, 'status'] = status
            admin_df.loc[admin_df['audit_name'] == audit_name, 'remarks'] = remarks
            admin_df.loc[admin_df['audit_name'] == audit_name, 'mobile_number'] = mobile_number

        admin_df.to_csv(filename, index=False)
        st.session_state["auditor_data_saved"] = True
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
if 'file_uploaded' not in st.session_state:
    st.session_state['file_uploaded'] = False
if 'data' not in st.session_state:
    st.session_state['data'] = None

# Role Selection
role = st.radio("Select your role:", ["Admin", "Auditor"])

# Admin Section
if role == "Admin":
    st.session_state['role'] = "Admin"
    st.header("🔐 Admin Section: Upload, Query, and View Audit Updates")

    # Admin Password Validation
    password = st.text_input("Enter Admin Password:", type="password")
    if password == ADMIN_PASSWORD:
        st.success("Access granted!")

        # File upload
        uploaded_file = st.file_uploader("Upload an Audit Tracker Excel file", type=["xlsx"])

        if uploaded_file:
            st.session_state['data'] = load_data(uploaded_file)
            st.session_state['data'] = preprocess_data(st.session_state['data'])
            st.session_state['file_uploaded'] = True

            # Display data preview
            st.write("### Data Preview:")
            st.write(st.session_state['data'].head())

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

    if st.session_state['file_uploaded'] and st.session_state['data'] is not None:
        df = st.session_state['data']

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

                            if save_auditor_data(update, st.session_state['data']):
                                st.success("Audit data submitted successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to save auditor data. Please try again.")
    else:
        st.warning("Admin has not uploaded any audit data yet.")
