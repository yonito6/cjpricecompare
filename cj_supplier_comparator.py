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
# Query CJ Order by OrderNum using List API

def get_cj_orders_by_orderNums(token, order_nums):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    cj_order_map = {}

    # batch the request in chunks of 20 to avoid CJ API limits
    batch_size = 20
    for i in range(0, len(order_nums), batch_size):
        batch = order_nums[i:i+batch_size]
        params = {
            "page": 1,
            "pageSize": 50,
            "orderIds": ','.join(batch)
        }
        response = requests.get(url, headers=headers, params=params)
        response_json = response.json()

        if response_json['code'] == 200:
            orders = response_json['data']['list']
            for order in orders:
                order_num = order.get('orderNum', None)
                if order_num:
                    cj_order_map[str(order_num).replace('#', '').strip()] = order

        time.sleep(0.3)  # avoid flooding

    return cj_order_map

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅ (Supplier More Expensive Version)")

uploaded_file = st.file_uploader("Upload Supplier File (.csv or .xlsx)", type=["csv", "xlsx"])

if uploaded_file and st.button("Run Full Comparison"):
    try:
        # Read supplier file
        if uploaded_file.name.endswith(".xlsx"):
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

        token = get_cj_access_token()

        supplier_order_ids = [str(x).replace('#', '').strip() for x in supplier_orders['ShopifyOrderID']]
        cj_orders = get_cj_orders_by_orderNums(token, supplier_order_ids)
        st.write(f"✅ Pulled {len(cj_orders)} matching CJ orders.")

        report = []
        supplier_more_expensive_orders = []

        progress = st.progress(0)
        for idx, row in supplier_orders.iterrows():
            progress.progress((idx+1) / len(supplier_orders))

            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = cj_orders.get(supplier_order_id)
            if cj_order:
                cj_total = float(cj_order.get('orderAmount', 0))
                cj_items = 0
                if 'orderProductList' in cj_order and cj_order['orderProductList']:
                    cj_items = sum(item['orderQuantity'] for item in cj_order['orderProductList'])
                qty_match = 'YES' if cj_items == supplier_items else 'NO'
                price_diff = supplier_total - cj_total

                if supplier_total > cj_total:
                    supplier_more_expensive_orders.append({
                        'OrderID': supplier_order_id,
                        'Diff': round(supplier_total - cj_total, 2)
                    })

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

            time.sleep(0.1)

        progress.empty()

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

        final_df = pd.concat([total_row, report_df], ignore_index=True)

        # Show total extra paid to supplier
        st.header("💰 Supplier More Expensive Summary:")
        if supplier_more_expensive_orders:
            more_exp_df = pd.DataFrame(supplier_more_expensive_orders)
            more_exp_sum = more_exp_df['Diff'].sum()
            st.write(f"Total extra paid to supplier: **${more_exp_sum:.2f}**")
            st.write(more_exp_df)
        else:
            st.write("✅ Supplier never more expensive than CJ.")

        # Show full table
        st.write(final_df)

        # Export CSV with your format:
        export_df = report_df[['ShopifyOrderID', 'SupplierTotalPrice']].copy()
        export_df['ShopifyOrderID'] = export_df['ShopifyOrderID'].str.replace('#', '').str.strip()
        export_df['Total'] = export_df['SupplierTotalPrice'].map(lambda x: f"{x:.2f}")
        export_df = export_df[['ShopifyOrderID', 'Total']]

        csv = export_df.to_csv(index=False)
        st.download_button("Download Export CSV", data=csv, file_name="eleganto_cogs_export.csv", mime='text/csv')

    except Exception as e:
        st.error(f"❌ Failed: {e}")
