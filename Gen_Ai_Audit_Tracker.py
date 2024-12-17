import openai
import pandas as pd
import streamlit as st

# Set your OpenAI API key
openai.api_key = "your-openai-api-key-here"  # Make sure to replace this with a valid OpenAI key

# Get Admin Password from Streamlit secrets
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

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
        if "```" in response_text:
            response_text = response_text.split("```")[0].strip()

        # Additional check for inline code (e.g., HTML, SQL)
        if "<" in response_text and ">" in response_text:
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
