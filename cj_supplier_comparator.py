import streamlit as st
import requests
import json

# Your CJ Seller Credentials
CJ_EMAIL = "elgantoshop@gmail.com"
CJ_API_KEY = "057bacfa2f84484c8eac290987968153"

# Function to get access token
def get_cj_access_token():
    url = "https://developers.cjdropshipping.com/api2.0/v1/authentication/getAccessToken"
    headers = {'Content-Type': 'application/json'}
    data = {
        "email": CJ_EMAIL,
        "password": CJ_API_KEY
    }
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ token: {response_json.get('message', 'Unknown error')}")

    token = response_json['data']['accessToken']
    return token

# Streamlit UI
st.title("CJ API AUTH TEST")

if st.button("Test CJ API Connection"):
    try:
        token = get_cj_access_token()
        st.write("✅ Successfully obtained access token:")
        st.write(token)

        # Try simple store list query (safe test)
        url = "https://developers.cjdropshipping.com/api2.0/open/getStoreList"
        headers = {'CJ-Access-Token': token}
        data = {"page": 1, "pageSize": 10}

        response = requests.post(url, headers=headers, json=data)
        response_json = response.json()

        st.write("CJ API Response:")
        st.json(response_json)

    except Exception as e:
        st.write("❌ Failed to connect:")
        st.write(e)
