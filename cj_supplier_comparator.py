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
# CJ API Order Detail Fetch

def get_cj_order_detail(token, order_id):
    url = f"https://developers.cjdropshipping.com/api2.0/v1/shopping/order/getOrderDetail?orderId={order_id}"
    headers = {'CJ-Access-Token': token}
    response = requests.get(url, headers=headers)
    response_json = response.json()

    if response_json['code'] != 200:
        return None

    return response_json['data']

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅ (Stable Version Without tqdm)")

# Supplier file uploader
uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

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

        # Extract order numbers to fetch
        order_nums = supplier_orders['ShopifyOrderID'].astype(str).str.replace('#', '').str.strip().tolist()

        token = get_cj_access_token()

        # Build CJ mapping by querying details for each order
        cj_order_map = {}
        for order_num in order_nums:
            search_url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
            headers = {'CJ-Access-Token': token}
            params = {"orderIds": [order_num], "pageNum": 1, "pageSize": 10}
            response = requests.get(search_url, headers=headers, params=params)
            data = response.json()

            if data['code'] == 200 and data['data']['list']:
                cj_order = data['data']['list'][0]
                cj_order_map[order_num] = cj_order
            else:
                cj_order_map[order_num] = None

        report = []
        for idx, row in supplier_orders.iterrows():
            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = cj_order_map.get(supplier_order_id)
            if cj_order:
                cj_total = float(cj_order.get('orderAmount', 0))
                cj_items = 0

                # Call the detailed order to extract proper quantity from productList
                detailed = get_cj_order_detail(token, cj_order['orderId'])
                if detailed and 'productList' in detailed and detailed['productList']:
                    cj_items = sum(item.get('quantity', 0) for item in detailed['productList'])

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
