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
# CJ API Order Fetch using paging

def get_all_cj_orders(token, pages_to_pull=10):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    cj_orders = []

    for page in range(1, pages_to_pull+1):
        params = {
            "pageNum": page,
            "pageSize": 50
        }
        response = requests.get(url, headers=headers, params=params)
        response_json = response.json()

        if response_json['code'] == 200:
            cj_orders += response_json['data']['list']
        else:
            break

        time.sleep(0.2)

    return cj_orders

# ---------------------------
# Helper function for safe float conversion

def safe_float(val):
    try:
        if isinstance(val, str):
            val = val.replace('$', '').replace(',', '').strip()
        return float(val)
    except (TypeError, ValueError):
        return 0.0

# ---------------------------
# Streamlit UI

st.title("Eleganto COG Audit Tool ✅")

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

        supplier_orders['SupplierTotalPrice'] = supplier_orders['SupplierTotalPrice'].apply(safe_float).round(2)
        supplier_orders['SupplierItemCount'] = supplier_orders['SupplierItemCount'].apply(safe_float)

        st.write(f"✅ Loaded {len(supplier_orders)} supplier orders.")

        token = get_cj_access_token()
        cj_orders_all = get_all_cj_orders(token, pages_to_pull=15)

        cj_order_map = {}
        for order in cj_orders_all:
            order_num = order.get('orderNum', None)
            if order_num:
                cj_order_map[str(order_num).replace('#', '').strip()] = order

        supplier_order_ids = [str(x).replace('#', '').strip() for x in supplier_orders['ShopifyOrderID']]

        cj_orders = {order_id: cj_order_map[order_id] for order_id in supplier_order_ids if order_id in cj_order_map}
        st.write(f"✅ Pulled {len(cj_orders)} matching CJ orders.")

        report = []
        supplier_more_expensive_orders = []

        progress = st.progress(0)
        for idx, row in supplier_orders.iterrows():
            progress.progress((idx+1) / len(supplier_orders))

            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = safe_float(row['SupplierTotalPrice'])
            supplier_items = safe_float(row['SupplierItemCount'])

            cj_order = cj_orders.get(supplier_order_id)
            if cj_order:
                cj_total = safe_float(cj_order.get('orderAmount'))
                cj_items = sum([safe_float(item.get('orderQuantity')) for item in cj_order.get('orderProductList', [])], start=0.0)

                qty_match = 'YES' if cj_items == supplier_items else 'NO'
                price_diff = supplier_total - cj_total

                if supplier_total > cj_total:
                    supplier_more_expensive_orders.append({
                        'OrderID': supplier_order_id,
                        'Diff': round(price_diff, 2)
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

            time.sleep(0.05)

        progress.empty()

        report_df = pd.DataFrame(report)

        total_supplier = report_df['SupplierTotalPrice'].sum()
        total_cj = report_df['CJOrderAmount'].sum()
        total_saved = total_cj - total_supplier

        # ---- Top Summary ----
        st.header("📊 Total Sum Up Information")
        st.write(f"✅ Total amount Supplier: **${total_supplier:.2f}**")
        st.write(f"✅ Total amount CJ: **${total_cj:.2f}**")
        st.write(f"✅ Total amount saved: **${total_saved:.2f}** (Private supplier)")

        st.header("💰 Supplier More Expensive Orders:")
        if supplier_more_expensive_orders:
            more_exp_df = pd.DataFrame(supplier_more_expensive_orders)
            more_exp_sum = more_exp_df['Diff'].sum()
            st.write(f"Total extra paid to supplier: **${more_exp_sum:.2f}**")
            st.write(more_exp_df)
        else:
            st.write("✅ Supplier never more expensive than CJ.")

        st.header("Full Orders Comparison Table")
        st.write(report_df)

        export_df = report_df[['ShopifyOrderID', 'SupplierTotalPrice']].copy()
        export_df['ShopifyOrderID'] = export_df['ShopifyOrderID'].astype(str).str.replace('#', '').str.strip()
        export_df['Total'] = export_df['SupplierTotalPrice'].map(lambda x: f"{x:.2f}")
        export_df = export_df.rename(columns={'ShopifyOrderID': 'Order'})
        export_df = export_df[['Order', 'Total']]

        csv = export_df.to_csv(index=False)
        st.download_button("Download Export CSV", data=csv, file_name="eleganto_cogs_export.csv", mime='text/csv')

    except Exception as e:
        st.error(f"❌ Failed: {e}")
