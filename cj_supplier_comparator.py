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
# CJ API Order Fetch using correct GET method

def get_cj_orders(token, start_date, end_date):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    params = {
        "page": 1,
        "pageSize": 50,
        "startDate": start_date,
        "endDate": end_date
    }
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ orders: {response_json.get('message', 'Unknown error')}")

    return response_json['data']['list']

# ---------------------------
# Streamlit UI

st.title("CJ API - FINAL FULLY WORKING VERSION ✅")

# Allow selecting date range to pull orders:
st.write("Select time range to fetch orders:")

default_end_date = datetime.now()
default_start_date = default_end_date - timedelta(days=30)

start_date = st.date_input("Start date", default_start_date, key="start_date").strftime('%Y-%m-%d 00:00:00')
end_date = st.date_input("End date", default_end_date, key="end_date").strftime('%Y-%m-%d 23:59:59')

if st.button("Fetch Orders from CJ"):
    try:
        token = get_cj_access_token()
        st.success("✅ Successfully connected to CJ API.")

        cj_orders = get_cj_orders(token, start_date, end_date)
        st.write(f"✅ Found {len(cj_orders)} orders.")

        for idx, order in enumerate(cj_orders):
            st.write(f"--- ORDER {idx+1} ---")
            st.json(order)

    except Exception as e:
        st.error(f"❌ Failed: {e}")

