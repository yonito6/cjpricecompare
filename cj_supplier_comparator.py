import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta

# ---------------------------
# Your CJ Seller Credentials
# (Tip: consider moving these to environment variables)
CJ_EMAIL = "elgantoshop@gmail.com"
CJ_API_KEY = "7e07bce6c57b4d918da681a3d85d3bed"

# ---------------------------
# Utils

def find_col(df: pd.DataFrame, candidates, required=True) -> str:
    """
    Return the actual column name in df that matches one of the candidate names
    (case/space-insensitive). Raises a helpful error if not found and required=True.
    """
    # normalize once
    normalized = {c.strip().lower(): c for c in df.columns}
    for cand in candidates:
        key = cand.strip().lower()
        if key in normalized:
            return normalized[key]
    if required:
        raise KeyError(
            f"None of the expected columns found: {candidates}. "
            f"Available columns: {list(df.columns)}"
        )
    return None

def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

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

    if response_json.get('code') != 200:
        raise Exception(f"Failed to get CJ token: {response_json.get('message', 'Unknown error')}")

    return response_json['data']['accessToken']

# ---------------------------
# CJ API Order Fetch using paging

def get_all_cj_orders(token, pages_to_pull=10):
    url = "https://developers.cjdropshipping.com/api2.0/v1/shopping/order/list"
    headers = {'CJ-Access-Token': token}
    cj_orders = []

    for page in range(1, pages_to_pull + 1):
        params = {
            "pageNum": page,
            "pageSize": 50
        }
        response = requests.get(url, headers=headers, params=params)
        response_json = response.json()

        if response_json.get('code') == 200:
            data = response_json.get('data') or {}
            cj_orders += (data.get('list') or [])
        else:
            break

        time.sleep(0.2)

    return cj_orders

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

        # --------- Resolve column names flexibly ---------
        # Order name
        name_col = find_col(supplier_df, [
            "Name", "Order", "Order Name", "Shopify Order", "Order ID"
        ])

        # Quantity: accept QTY or Lineitem quantity (your sheet) and common variants
        qty_col = find_col(supplier_df, [
            "QTY", "Qty", "Quantity", "Lineitem quantity", "Line item quantity", "Line Item Quantity"
        ])

        # Product fee / cost
        pf_col = find_col(supplier_df, [
            "Product fee", "Product Fee", "Product cost", "Cost", "Item cost", "Unit cost"
        ])

        # Total price
        total_col = find_col(supplier_df, [
            "Total price", "Total", "Order Total", "Total Price"
        ])

        # --------- Clean numerics ---------
        supplier_df[pf_col]    = pd.to_numeric(supplier_df[pf_col], errors='coerce')
        supplier_df[qty_col]   = pd.to_numeric(supplier_df[qty_col], errors='coerce')
        supplier_df[total_col] = pd.to_numeric(supplier_df[total_col], errors='coerce')

        # Forward-fill order name (common structure: only first row has it)
        supplier_df[name_col] = supplier_df[name_col].fillna(method='ffill')

        # --------- Aggregate to order level ---------
        supplier_orders = supplier_df.groupby(name_col).agg({
            pf_col: 'sum',
            qty_col: 'sum',
            total_col: 'first'   # first non-null total per order header row
        }).reset_index()

        # Standardize schema used downstream
        supplier_orders.rename(columns={
            name_col: 'ShopifyOrderID',
            pf_col: 'SupplierProductCost',
            qty_col: 'SupplierItemCount',
            total_col: 'SupplierTotalPrice'
        }, inplace=True)

        # Ensure rounding for display consistency
        supplier_orders['SupplierTotalPrice'] = supplier_orders['SupplierTotalPrice'].round(2)

        st.write(f"✅ Loaded {len(supplier_orders)} supplier orders.")

        # --------- Pull CJ orders ---------
        token = get_cj_access_token()
        cj_orders_all = get_all_cj_orders(token, pages_to_pull=15)

        # Map CJ orders by number (strip '#')
        cj_order_map = {}
        for order in cj_orders_all:
            order_num = (order or {}).get('orderNum')
            if order_num:
                cj_order_map[str(order_num).replace('#', '').strip()] = order

        supplier_order_ids = [str(x).replace('#', '').strip() for x in supplier_orders['ShopifyOrderID']]

        cj_orders = {oid: cj_order_map[oid] for oid in supplier_order_ids if oid in cj_order_map}
        st.write(f"✅ Pulled {len(cj_orders)} matching CJ orders.")

        # --------- Build report ---------
        report = []
        supplier_more_expensive_orders = []

        progress = st.progress(0)

        for idx, row in supplier_orders.iterrows():
            progress.progress((idx + 1) / len(supplier_orders))

            supplier_order_id = str(row['ShopifyOrderID']).replace('#', '').strip()
            supplier_total = row['SupplierTotalPrice']
            supplier_items = row['SupplierItemCount']

            cj_order = cj_orders.get(supplier_order_id)
            if cj_order:
                cj_total = safe_float(cj_order.get('orderAmount'))
                cj_items = 0
                if cj_order.get('orderProductList'):
                    cj_items = sum(safe_float(item.get('orderQuantity', 0)) for item in cj_order['orderProductList'])
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

            time.sleep(0.02)

        progress.empty()

        report_df = pd.DataFrame(report)

        total_supplier = report_df['SupplierTotalPrice'].sum(skipna=True)
        total_cj = report_df['CJOrderAmount'].sum(skipna=True)
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
            st.dataframe(more_exp_df, use_container_width=True)
        else:
            st.write("✅ Supplier never more expensive than CJ.")

        st.header("Full Orders Comparison Table")
        st.dataframe(report_df, use_container_width=True)

        # ---- Export CSV (Order, Total) ----
        export_df = report_df[['ShopifyOrderID', 'SupplierTotalPrice']].copy()
        export_df['ShopifyOrderID'] = export_df['ShopifyOrderID'].astype(str).str.replace('#', '').str.strip()
        export_df['Total'] = export_df['SupplierTotalPrice'].map(lambda x: f"{x:.2f}")
        export_df = export_df.rename(columns={'ShopifyOrderID': 'Order'})
        export_df = export_df[['Order', 'Total']]

        csv = export_df.to_csv(index=False)
        st.download_button("Download Export CSV", data=csv, file_name="eleganto_cogs_export.csv", mime='text/csv')

    except Exception as e:
        st.error(f"❌ Failed: {e}")
