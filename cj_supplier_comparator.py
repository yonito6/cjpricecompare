import streamlit as st
import requests
import json

# Your existing CJ API token
CJ_API_TOKEN = "057bacfa2f84484c8eac290987968153"

# Streamlit UI
st.title("CJ API Connection Test")

if st.button("Test CJ API Connection"):
    url = "https://developers.cjdropshipping.com/api2.0/open/getStoreList"
    headers = {'CJ-Access-Token': CJ_API_TOKEN}
    data = {"page": 1, "pageSize": 10}

    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code == 200:
        response_json = response.json()
        st.write("✅ CJ API Connection Successful!")
        st.json(response_json)
    else:
        st.write("❌ Failed to connect to CJ API")
        st.write(f"Status Code: {response.status_code}")
        st.write(response.text)
