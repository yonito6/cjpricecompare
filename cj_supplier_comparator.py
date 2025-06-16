import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
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
# Get CJ Order By OrderNum

def get_cj_order_by_order_num(token, order_num):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    params = {
        "orderNumber": order_num,
        "page": 1,
        "pageSize": 10  # <-- Corrected pageSize limit
    }
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ order: {response_json.get('message', 'Unknown error')}")

    data_list = response_json['data']['list']
    if len(data_list) > 0:
        return data_list[0]
    else:
        return None

# ---------------------------
# Get order details (productList)

def get_cj_order_detail(token, order_id):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/getOrderDetail"
    headers = {'CJ-Access-Token': token}
    params = {"orderId": order_id}
    response = requests.get(url, headers=headers, params=params)
    response_json = response.json()

    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ order detail: {response_json.get('message', 'Unknown error')}")

    return response_json['data']

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅ (FINAL FULL WORKING VERSION 🚀)")

uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

if uploaded_file and st.button("Run Full Comparison"):
    try:
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

        token = get_cj_access_token()

        report = []
        progress = st.progress(0)

        for idx, row in supplier_orders.iterrows():
            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = get_cj_order_by_order_num(token, supplier_order_id)
            if cj_order:
                cj_total = float(cj_order['orderAmount'])
                order_id = cj_order['orderId']

                time.sleep(0.3)  # prevent hitting rate limit

                detail = get_cj_order_detail(token, order_id)
                product_list = detail.get('productList', [])

                # Filtering packaging products
                exclude_keywords = ['case', 'box', 'storage', 'package', 'packaging']

                cj_items = 0
                for item in product_list:
                    product_name = item.get('productName', '').lower()
                    qty = item.get('quantity', 0)

                    if not any(keyword in product_name for keyword in exclude_keywords):
                        cj_items += qty

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

            progress.progress((idx + 1) / len(supplier_orders))

        report_df = pd.DataFrame(report)

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
