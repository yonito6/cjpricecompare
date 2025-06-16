import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timedelta
from tqdm import tqdm

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
# Get basic order list from CJ (only IDs, to query details after)

def get_cj_orders(token, shopify_order_ids):
    cj_orders = {}
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}

    page = 1
    while True:
        params = {
            "pageNum": page,
            "pageSize": 50
        }
        response = requests.get(url, headers=headers, params=params)
        response_json = response.json()

        if response_json['code'] != 200:
            raise Exception(f"Failed to get CJ orders: {response_json.get('message', 'Unknown error')}")

        orders = response_json['data']['list']
        if not orders:
            break

        for order in orders:
            order_num = str(order.get("orderNum", "")).replace("#", "").strip()
            if order_num in shopify_order_ids:
                cj_orders[order_num] = order.get("orderId")

        if page >= response_json['data']['total'] / 50:
            break

        page += 1

    return cj_orders

# ---------------------------
# Get full order details (with productInfoList)

def get_cj_order_details(token, cj_order_ids):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/getOrderDetail"
    headers = {'CJ-Access-Token': token}

    cj_details = {}

    for order_num, order_id in tqdm(cj_order_ids.items(), desc="Fetching CJ order details"):
        params = {"orderId": order_id}
        response = requests.get(url, headers=headers, params=params)
        response_json = response.json()

        if response_json['code'] != 200:
            cj_details[order_num] = None
            continue

        cj_details[order_num] = response_json['data']

    return cj_details

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅ (FINAL FIXED VERSION)")

uploaded_file = st.file_uploader("Upload Supplier CSV (.xlsx)", type=["xlsx"])

if uploaded_file and st.button("Run Full Comparison"):
    try:
        # Load supplier file
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

        shopify_order_ids = set(str(x).replace('#', '').strip() for x in supplier_orders['ShopifyOrderID'])

        token = get_cj_access_token()
        cj_order_ids = get_cj_orders(token, shopify_order_ids)
        cj_order_details = get_cj_order_details(token, cj_order_ids)

        st.write(f"✅ Pulled {len(cj_order_ids)} matched CJ orders.")

        # Build final comparison report
        report = []

        for idx, row in supplier_orders.iterrows():
            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_data = cj_order_details.get(supplier_order_id)

            if cj_data:
                cj_total = float(cj_data.get('orderAmount', 0))
                product_info_list = cj_data.get('productInfoList', [])

                cj_items = 0

                for product in product_info_list:
                    is_group = product.get('isGroup', False)
                    if is_group:
                        sub_products = product.get('subOrderProducts', [])
                        cj_items += sum(sub.get('quantity', 0) for sub in sub_products)
                    else:
                        cj_items += product.get('quantity', 0)

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

        # Total summary row
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
