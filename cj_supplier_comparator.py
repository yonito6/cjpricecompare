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
# CJ API Authentication (exactly your working code)

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

def get_cj_orders(token, start_date, end_date):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    params = {
        "page": 1,
        "pageSize": 200,  # Increase pageSize to get more orders
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

st.title("Eleganto COG Audit Tool ✅ (FINAL FULLY FIXED VERSION)")

# Supplier file uploader
uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

# Allow selecting date range to pull CJ orders:
st.write("Select CJ orders time range:")

default_end_date = datetime.now()
default_start_date = default_end_date - timedelta(days=30)

start_date = st.date_input("Start date", default_start_date, key="start_date").strftime('%Y-%m-%d 00:00:00')
end_date = st.date_input("End date", default_end_date, key="end_date").strftime('%Y-%m-%d 23:59:59')

if uploaded_file and st.button("Run Full Comparison"):
    try:
        # Process supplier file
        supplier_df = pd.read_excel(uploaded_file)
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

        # Pull CJ Orders
        token = get_cj_access_token()
        cj_orders = get_cj_orders(token, start_date, end_date)
        st.write(f"✅ Pulled {len(cj_orders)} CJ orders.")

        # Build CJ mapping using correct 'orderNum' field
        cj_order_map = {}
        for order in cj_orders:
            order_num = order.get('orderNum', None)
            if order_num:
                cj_order_map[str(order_num).replace('#', '').strip()] = order

        # Build comparison report
        report = []
        for idx, row in supplier_orders.iterrows():
            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = cj_order_map.get(supplier_order_id)
            if cj_order:
                cj_total = float(cj_order['orderAmount'])  # Correct cost comparison
                cj_items = 0
                if 'orderProductList' in cj_order and cj_order['orderProductList']:
                    cj_items = sum(item['orderQuantity'] for item in cj_order['orderProductList'])
                qty_match = 'YES' if cj_items == supplier_items else 'NO'
                price_diff = supplier_total - cj_total
            else:
                cj_total = np.nan
                cj_items = np.nan
                qty_match = 'NO DATA'
                price_diff = np.nan

            report.append({
                'ShopifyOrderID': supplier_order_id,
                'SupplierTotalPrice': supplier_total,
                'CJOrderAmount': cj_total,
                'PriceDifference': price_diff,
                'SupplierItemCount': supplier_items,
                'CJItemCount': cj_items,
                'QuantityMatch': qty_match
            })

        report_df = pd.DataFrame(report)

        # Add total summary row
        total_row = pd.DataFrame({
            'ShopifyOrderID': ['TOTAL'],
            'SupplierTotalPrice': [report_df['SupplierTotalPrice'].sum()],
            'CJOrderAmount': [report_df['CJOrderAmount'].sum()],
            'PriceDifference': [report_df['PriceDifference'].sum()],
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
