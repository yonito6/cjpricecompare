import streamlit as st
import pandas as pd
import numpy as np
import requests
import json

# ---------------------------
# CJ API Credentials (masked here, but you will insert securely)
CJ_API_KEY = "be10e4ca3f4649cfbf4f0c6e79b8df0b"

# ---------------------------
# CJ API Functions

def get_cj_token():
    url = "https://developers.cjdropshipping.com/api2.0/open/getAccessToken"
    data = {
        "developerKey": CJ_API_KEY
    }
    response = requests.post(url, json=data)
    token = response.json()['data']['accessToken']
    return token

def get_cj_order(order_id, token):
    url = "https://developers.cjdropshipping.com/api2.0/open/getOrderList"
    headers = {'CJ-Access-Token': token}
    data = {
        "page": 1,
        "pageSize": 50,
        "shopifyOrderId": order_id.replace("#", "")  # Remove '#' if exists
    }
    response = requests.post(url, headers=headers, json=data)
    orders = response.json()['data']['list']
    if orders:
        total_amount = float(orders[0]['orderAmount'])
        item_count = sum(item['orderQuantity'] for item in orders[0]['orderProductVos'])
        return total_amount, item_count
    else:
        return None, None

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool v1.0")
st.write("Upload your Supplier CSV file to compare with CJ Dropshipping.")

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

    st.write("Found", len(orders), "orders in your file.")

    if st.button("Start Comparison with CJ"):
        token = get_cj_token()
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
