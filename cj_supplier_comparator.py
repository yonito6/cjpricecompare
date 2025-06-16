import streamlit as st
import requests
import json

# ---------------------------
# Your CJ Seller Credentials
CJ_EMAIL = "elgantoshop@gmail.com"
CJ_API_KEY = "7e07bce6c57b4d918da681a3d85d3bed"

# ---------------------------
# CJ API Authentication

@st.cache_data(ttl=60*60*24*15)  # Cache token for 15 days (CJ token lifetime)
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

# ---------------------------
# CJ API Test Call

def get_cj_orders(token):
    url = "https://developers.cjdropshipping.com/api2.0/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    data = {
        "page": 1,
        "pageSize": 50
    }
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ orders: {response_json.get('message', 'Unknown error')}")

    return response_json['data']['list']

# ---------------------------
# Streamlit UI

st.title("CJ API DEBUG TOOL 🔬")
st.write("We will test your CJ order data to verify ID structure.")

if st.button("Run Debug Test"):
    try:
        token = get_cj_access_token()
        st.success("✅ Successfully connected to CJ API.")

        cj_orders = get_cj_orders(token)
        st.write(f"✅ Found {len(cj_orders)} orders.")

        for idx, order in enumerate(cj_orders):
            st.write(f"--- ORDER {idx+1} ---")
            st.json(order)

    except Exception as e:
        st.error(f"❌ Failed: {e}")
