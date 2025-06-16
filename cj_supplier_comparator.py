import streamlit as st
import pandas as pd
import numpy as np
import requests
import json

# ---------------------------
# CJ API Functions

def get_cj_token(app_key, app_secret):
    url = "https://developers.cjdropshipping.com/api2.0/open/getAccessToken"
    data = {
        "appKey": app_key,
        "appSecret": app_secret
    }
    response = requests.post(url, json=data)
    response_json = response.json()
    if response_json['code'] != 200:
        raise Exception(f"Failed to get CJ token: {response_json.get('msg', 'Unknown error')}")
    token = response_json['data']['accessToken']
    return token

def get_cj_order(order_id, token):
    url = "https://developers.cjdropshipping.com/api2.0/open/getOrderList"
    headers = {'CJ-Access-Token': token}
    data = {
        "page": 1,
        "pageSize": 50,
        "shopifyOrderId": order_id.replace("#", "")
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

st.title("Eleganto COG Audit Tool v2.0")
st.write("Upload your Supplier CSV file to compare with CJ Dropshipping.")

# CJ API credentials input
cj_app_key = st.text_input("Enter your CJ App Key")
cj_app_secret = st.text_input("Enter your CJ App Secret")

uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

if uploaded_file and cj_app_key and cj_app_secret:
    try:
        token = get_cj_token(cj_app_key, cj_app_secret)
    except Exception as e:
        st.error(f"Error authenticating with CJ API: {e}")
    else:
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

        report = []

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
