# asset_pdf_app.py
import os
import base64
from io import BytesIO
from datetime import date
import zipfile
import numpy as np

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from jinja2 import Template
from weasyprint import HTML

# -------------------- Streamlit Config --------------------
st.set_page_config(page_title="Client Asset Report Generator", layout="wide")
st.title("📊 Client Asset Report Generator")

with st.sidebar:
    st.markdown("### ℹ️ Instructions")
    st.write("""
    1. Upload the **Master Excel** file.
    2. Select report date.
    3. Preview client allocations.
    4. Download individual or multiple client reports.
    """)

# ====== CONFIG: where your templates + bg images live ======
TEMPLATE_DIR = r"C:\Users\DELL\OneDrive\Desktop\Asset Summary"

# -------------------- Helpers --------------------
def clean_number(x):
    try:
        x = str(x).replace("₹", "").replace(",", "").strip()
        return float(x) if x not in ["", "nan", "None"] else 0.0
    except Exception:
        return 0.0

def fig_to_base64_png(fig) -> str:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150, transparent=True)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def format_indian_currency(amount):
    amount = float(amount)
    if amount == 0:
        return "₹ 0"
    amount_str = str(int(round(amount)))
    if len(amount_str) <= 3:
        formatted = amount_str
    else:
        last_three = amount_str[-3:]
        remaining = amount_str[:-3]
        groups = []
        while len(remaining) > 2:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.append(remaining)
        groups.reverse()
        formatted = ','.join(groups) + ',' + last_three
    return f"₹ {formatted}"

# -------------------- Report Builders --------------------
def build_unified_html(client_name: str, client_df: pd.DataFrame, report_dt: date, chart_b64: str) -> str:
    rows_html = []
    for _, row in client_df.iterrows():
        if row['Asset Type'] == 'Total':
            formatted_value = f"<strong>{format_indian_currency(row['Value'])}</strong>"
            allocation = f"<strong>{row['% Allocation']:.2f}%</strong>"
        else:
            formatted_value = format_indian_currency(row['Value'])
            allocation = f"{row['% Allocation']:.2f}%"
        rows_html.append(
            f"<tr><td>{row['Asset Type']}</td>"
            f"<td style='text-align: right;'>{formatted_value}</td>"
            f"<td style='text-align: right;'>{allocation}</td></tr>"
        )
    rows_html = "\n".join(rows_html)

    client_name_upper = client_name.upper()
    report_date_str = report_dt.strftime("%d %B %Y").upper()

    # HTML with background images (relative path -> resolved via base_url=TEMPLATE_DIR)
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Client Asset Report</title>
<style>
  @page {{ size: A4; margin: 0; }}
  body {{ margin:0; padding:0; font-family: 'Open Sans', Arial, sans-serif; }}

  .cover-page {{
    width: 794px; height: 1123px;
    background: url('cover_page_bg.jpg') no-repeat center/cover;
    page-break-after: always;
  }}
  .client-name {{
    position: absolute; top: 70px; right: 300px;
    font-size: 30px; color: white; font-style: italic;
  }}
  .report-date {{
    position: absolute; bottom: 80px; left: 360px;
    font-size: 21px; color: #2F2F2F; font-style: italic;
  }}

  .report-page {{
    width: 794px; height: 1123px;
    padding: 40px; background: white;
    page-break-after: always;
  }}
  .header h1 {{ text-align:center; margin:0 0 20px; }}
  table {{ width:100%; border-collapse:collapse; font-size:12px; }}
  th, td {{ border:1px solid #b0b0b0; padding:10px; }}
  th {{ background:#4a4a4a; color:white; }}
  tr:nth-child(even){{ background:#f2f2f2; }}

  .end-page {{
    width: 794px; height: 1123px;
    background: url('end_page_bg.jpg') no-repeat center/cover;
  }}
</style>
</head>
<body>
  <div class="cover-page">
    <div class="client-name">{client_name_upper}</div>
    <div class="report-date">{report_date_str}</div>
  </div>

  <div class="report-page">
    <div class="header"><h1>ASSET ALLOCATION</h1></div>
    <div style="text-align:center;">
      <img src="data:image/png;base64,{chart_b64}" style="max-width:500px;" />
    </div>
    <table>
      <thead><tr><th>Asset Type</th><th>Value</th><th>% Allocation</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div class="end-page"></div>
</body>
</html>
"""

def build_client_pdf_bytes(client_name: str, client_df: pd.DataFrame, report_dt: date) -> bytes:
    # Pie chart data
    plot_df = client_df[client_df["Asset Type"].str.lower() != "total"]
    plot_df = plot_df[plot_df["Value"] > 0]

    colors = ["#d65a8d","#d4b483","#274472","#c0c0c0","#3d6ba0","#f5e6d3","#5f84ce","#a8dadc","#f2a7bb"]
    colors = colors[:max(1, len(plot_df))]

    fig, ax = plt.subplots(figsize=(6,6))
    wedges, _ = ax.pie(plot_df["Value"], startangle=90, colors=colors)
    ax.axis("equal")
    chart_b64 = fig_to_base64_png(fig)

    html_str = build_unified_html(client_name, client_df, report_dt, chart_b64)
    return HTML(string=html_str, base_url=TEMPLATE_DIR).write_pdf()

# -------------------- UI --------------------
uploaded_file = st.file_uploader("📂 Upload Master Excel", type=["xlsx"])
report_date = st.date_input("📅 Report Date", value=date.today())
st.caption(f"📁 Templates folder: `{TEMPLATE_DIR}`")

if uploaded_file:
    df = pd.read_excel(uploaded_file, dtype=str).fillna("0")
    df = df.replace(["NA","N.A","N/A","na","n.a","n/a","","Pending","pending"], "0")

    for col in df.columns[1:]:
        df[col] = df[col].apply(clean_number)

    df = df[df.iloc[:,0].str.strip() != ""]
    client_list = df.iloc[:,0].astype(str).tolist()

    st.success("✅ File processed successfully!")
    st.dataframe(df.head())

    selected_client = st.selectbox("🔎 Preview Client", client_list)
    if selected_client:
        row = df[df.iloc[:,0]==selected_client].iloc[0]
        assets = row.iloc[1:]
        client_df = pd.DataFrame({"Asset Type": assets.index, "Value": assets.values.astype(float)})
        total_value = client_df["Value"].sum()
        client_df["% Allocation"] = (client_df["Value"]/total_value*100).round(2) if total_value>0 else 0
        client_df = pd.concat([client_df, pd.DataFrame({"Asset Type":["Total"],"Value":[total_value],"% Allocation":[100]})])

        st.dataframe(client_df)

        try:
            pdf_bytes = build_client_pdf_bytes(selected_client, client_df, report_date)
            st.download_button("📥 Download Report (PDF)", data=pdf_bytes, file_name=f"{selected_client}_Report.pdf", mime="application/pdf")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

    st.write("---")
    st.write("### 📦 Generate Multiple Reports")
    selected_clients = st.multiselect("Select Clients", client_list)
    if st.button("Generate ZIP"):
        if selected_clients:
            out = BytesIO()
            with zipfile.ZipFile(out, "w") as zf:
                for cname in selected_clients:
                    crow = df[df.iloc[:,0]==cname].iloc[0]
                    assets = crow.iloc[1:]
                    cdf = pd.DataFrame({"Asset Type": assets.index, "Value": assets.values.astype(float)})
                    ctotal = cdf["Value"].sum()
                    cdf["% Allocation"] = (cdf["Value"]/ctotal*100).round(2) if ctotal>0 else 0
                    cdf = pd.concat([cdf, pd.DataFrame({"Asset Type":["Total"],"Value":[ctotal],"% Allocation":[100]})])
                    pdf = build_client_pdf_bytes(cname, cdf, report_date)
                    zf.writestr(f"{cname}_Report.pdf", pdf)
            st.download_button("📦 Download ZIP", data=out.getvalue(), file_name="Client_Reports.zip", mime="application/zip")
        else:
            st.warning("⚠️ Select at least one client.")
