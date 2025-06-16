import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time

# ---------------------------
# Your CJ Seller Credentials
CJ_EMAIL = "elgantoshop@gmail.com"
CJ_API_KEY = "057bacfa2f84484c8eac290987968153"

# ---------------------------
# CJ API Authentication

@st.cache_data(ttl=60*60*24*15)  # Cache token for 15 days
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
# CJ API Order Fetch

def get_cj_order(order_id, token):
    url = "https://developers.cjdropshipping.com/api2.0/open/getOrderList"
    headers = {'CJ-Access-Token': token}
    data = {
        "page": 1,
        "pageSize": 50,
        "shopifyOrderId": order_id  # NO replacement, pass exactly
    }
    response = requests.post(url, headers=headers, json=data)
    response_json = response.json()

    if response_json['code'] != 200 or response_json['data'] is None or len(response_json['data']['list']) == 0:
        return None, None

    orders = response_json['data']['list']
    total_amount = float(orders[0]['orderAmount'])
    item_count = sum(item['orderQuantity'] for item in orders[0]['orderProductVos'])
    return total_amount, item_count

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool v4.0 (🔥 FINAL WORKING VERSION 🔥)")
st.write("Upload your Supplier CSV file to compare with CJ Dropshipping orders.")

uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

if uploaded_file:
    supplier_df = pd.read_excel(uploaded_file)

    # Clean and prepare supplier file
    supplier_df['Name'] = supplier_df['Name'].fillna(method='ffill')

    # Group per order
    orders = supplier_df.groupby('Name').agg({
        'Product fee': 'sum',
        'QTY': 'sum',
        'Total price': 'first'
    }).reset_index()

    orders.rename(columns={
        'Name': 'ShopifyOrderID',
        'Product fee': 'SupplierProductCost',
        'QTY': 'SupplierItemCount',
        'Total price': 'SupplierTotalPrice'
    }, inplace=True)

    st.write(f"Found {len(orders)} orders in your file.")

    st.write("Connecting to CJ API...")
    try:
        token = get_cj_access_token()
        st.success("✅ Successfully connected to CJ API.")
    except Exception as e:
        st.error(f"Failed to connect to CJ API: {e}")
        st.stop()

    report = []

    progress_bar = st.progress(0)
    for idx, row in orders.iterrows():
        shopify_order_id = row['ShopifyOrderID']
        supplier_total = row['SupplierTotalPrice']
        supplier_items = row['SupplierItemCount']

        cj_total, cj_items = get_cj_order(shopify_order_id, token)

        if cj_total is None:
            cj_total = np.nan
            cj_items = np.nan
            qty_match = 'NO DATA'
        else:
            qty_match = 'YES' if cj_items == supplier_items else 'NO'

        cost_diff = supplier_total - cj_total if cj_total is not np.nan else np.nan

        report.append({
            'ShopifyOrderID': shopify_order_id,
            'SupplierTotalPrice': supplier_total,
            'CJTotalPrice': cj_total,
            'CostDifference': cost_diff,
            'SupplierItemCount': supplier_items,
            'CJItemCount': cj_items,
            'QuantityMatch': qty_match
        })

        progress_bar.progress((idx+1) / len(orders))

    report_df = pd.DataFrame(report)

    # Calculate totals
    total_row = pd.DataFrame({
        'ShopifyOrderID': ['TOTAL'],
        'SupplierTotalPrice': [report_df['SupplierTotalPrice'].sum()],
        'CJTotalPrice': [report_df['CJTotalPrice'].sum()],
        'CostDifference': [report_df['CostDifference'].sum()],
        'SupplierItemCount': [report_df['SupplierItemCount'].sum()],
        'CJItemCount': [report_df['CJItemCount'].sum()],
        'QuantityMatch': ['-']
    })

    final_df = pd.concat([report_df, total_row], ignore_index=True)

    st.write(final_df)

    csv = final_df.to_csv(index=False)
    st.download_button("Download Full Report CSV", data=csv, file_name="eleganto_cog_audit.csv", mime='text/csv')
