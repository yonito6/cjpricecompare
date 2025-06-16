import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import time

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
# CJ API Order Fetch for Specific Order

def get_cj_order_by_number(token, order_num):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    params = {
        "orderIds": [order_num],
        "pageNum": 1,
        "pageSize": 10
    }
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()

    if response_json['code'] != 200 or not response_json['data']['list']:
        return None

    return response_json['data']['list'][0]

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅ (FINAL STABLE VERSION)")

# Supplier file uploader
uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx or .csv)", type=["xlsx", "csv"])

if uploaded_file and st.button("Run Full Comparison"):
    try:
        # Auto-detect file format
        if uploaded_file.name.endswith('.xlsx'):
            supplier_df = pd.read_excel(uploaded_file)
        else:
            supplier_df = pd.read_csv(uploaded_file)

        supplier_df['Name'] = supplier_df['Name'].fillna(method='ffill')

        supplier_orders = supplier_df.groupby('Name').agg({
            'Product fee': 'sum',
            'QTY': 'sum',
            'Total price': 'first'
        }).reset_index()

        supplier_orders.rename(columns={
            'Name': 'ShopifyOrderID',
            'Product fee': 'SupplierProductCost',
            'QTY': 'SupplierItemCount',
            'Total price': 'SupplierTotalPrice'
        }, inplace=True)

        st.write(f"✅ Loaded {len(supplier_orders)} supplier orders.")

        # Extract list of order numbers from supplier file
        order_nums = supplier_orders['ShopifyOrderID'].astype(str).str.replace('#', '').str.strip().tolist()

        token = get_cj_access_token()

        report = []
        more_expensive = []

        progress_bar = st.progress(0)
        for idx, row in enumerate(supplier_orders.itertuples(), 1):
            supplier_order_id = str(row.ShopifyOrderID).replace('#', '').strip()
            supplier_total = row.SupplierTotalPrice
            supplier_items = row.SupplierItemCount

            cj_order = get_cj_order_by_number(token, supplier_order_id)
            if cj_order:
                cj_total = float(cj_order.get('orderAmount', 0))

                if cj_total > supplier_total:
                    more_expensive.append({
                        "OrderID": supplier_order_id,
                        "Difference": round(cj_total - supplier_total, 2)
                    })
            else:
                cj_total = np.nan

            report.append({
                'OrderID': supplier_order_id,
                'Total': supplier_total
            })

            progress_bar.progress(idx / len(supplier_orders))

        report_df = pd.DataFrame(report)

        # Show CJ more expensive summary
        if more_expensive:
            st.write("⚠️ CJ more expensive orders:")
            st.write(pd.DataFrame(more_expensive))
        else:
            st.write("✅ All orders cheaper or equal on CJ.")

        # Export CSV in requested format
        csv = report_df.to_csv(index=False)
        st.download_button("Download Final Report CSV", data=csv, file_name="eleganto_cog_final.csv", mime='text/csv')

    except Exception as e:
        st.error(f"❌ Failed: {e}")
