import streamlit as st
import requests
import json
from datetime import datetime, timedelta

# ---------------------------
# Your CJ Seller Credentials
CJ_EMAIL = "elgantoshop@gmail.com"
CJ_API_KEY = "7e07bce6c57b4d918da681a3d85d3bed"

# ---------------------------
# CJ API Authentication

@st.cache_data(ttl=60*60*24*15)
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
# CJ API Order Fetch using GET method

def get_cj_orders(token):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}

    # Automatically pull last 7 days (for faster debugging)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    params = {
        "page": 1,
        "pageSize": 10,  # just pull a few orders for debugging
        "startDate": start_date.strftime('%Y-%m-%d 00:00:00'),
        "endDate": end_date.strftime('%Y-%m-%d 23:59:59')
    }
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ orders: {response_json.get('message', 'Unknown error')}")

    return response_json['data']['list']

# ---------------------------
# Streamlit UI

st.title("CJ API Diagnostics Tool 🔬")

if st.button("Fetch and Inspect CJ Orders"):
    try:
        token = get_cj_access_token()
        st.success("✅ Connected to CJ API")

        cj_orders = get_cj_orders(token)
        st.write(f"✅ Fetched {len(cj_orders)} orders")

        # Show full JSON for first 3 orders:
        for i, order in enumerate(cj_orders[:3]):
            st.subheader(f"Order {i+1}:")
            st.json(order)

    except Exception as e:
        st.error(f"❌ Failed: {e}")
