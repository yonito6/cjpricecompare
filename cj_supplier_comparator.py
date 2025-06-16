import streamlit as st
import pandas as pd
import numpy as np
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
        "pageSize": 100,  # You can increase for bigger datasets
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

st.title("Eleganto Full COG Audit Tool ✅")

# Supplier file uploader
uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

# Allow selecting date range to pull CJ orders:
st.write("Select time range to fetch CJ orders:")

default_end_date = datetime.now()
default_start_date = default_end_date - timedelta(days=30)

start_date = st.date_input("Start date", default_start_date, key="start_date").strftime('%Y-%m-%d 00:00:00')
end_date = st.date_input("End date", default_end_date, key="end_date").strftime('%Y-%m-%d 23:59:59')

if uploaded_file and st.button("Run Full Comparison"):
    try:
        supplier_df = pd.read_excel(uploaded_file)
        supplier_df['Name'] = supplier_df['Name'].fillna(method='ffill')

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

        st.write(f"✅ Found {len(orders)} supplier orders.")

        # Get CJ Orders
        token = get_cj_access_token()
        cj_orders = get_cj_orders(token, start_date, end_date)
        st.write(f"✅ Pulled {len(cj_orders)} CJ orders.")

        # Build a mapping from CJ thirdOrderId (Shopify IDs)
        cj_order_map = {}
        for order in cj_orders:
            third_order_id = order.get('thirdOrderId', None)
            if third_order_id:
                cj_order_map[str(third_order_id).strip()] = order

        # Build comparison report
        report = []
        for idx, row in orders.iterrows():
            supplier_order_id = row['ShopifyOrderID'].replace('#','').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = cj_order_map.get(supplier_order_id)
            if cj_order:
                cj_total = float(cj_order['orderAmount'])
                cj_items = sum(item['orderQuantity'] for item in cj_order['orderProductList'])
                qty_match = 'YES' if cj_items == supplier_items else 'NO'
                cost_diff = supplier_total - cj_total
            else:
                cj_total = np.nan
                cj_items = np.nan
                qty_match = 'NO DATA'
                cost_diff = np.nan

            report.append({
                'ShopifyOrderID': supplier_order_id,
                'SupplierTotalPrice': supplier_total,
                'CJTotalPrice': cj_total,
                'CostDifference': cost_diff,
                'SupplierItemCount': supplier_items,
                'CJItemCount': cj_items,
                'QuantityMatch': qty_match
            })

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

    except Exception as e:
        st.error(f"❌ Failed: {e}")
