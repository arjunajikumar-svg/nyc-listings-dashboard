NYC LISTINGS DASHBOARD

Files in this bundle:
- listings_dashboard.py: responsive one-page interactive Streamlit dashboard
- listings_conservative_working_copy.csv: conservative working copy of the listings data
- requirements.txt: Python packages needed to run the dashboard

Run locally:
1. Install Python 3.10 or newer.
2. Open a terminal in this folder.
3. Run: python -m pip install -r requirements.txt
4. Run: streamlit run listings_dashboard.py
5. Open the local URL printed in the terminal.

The four interactive charts are Monthly trend, Top neighbourhoods, Geographic distribution, and Surprise chart. Hover over points/bars to inspect values. Filters apply to all charts and KPI cards. The dashboard does not modify the original CSV or fill missing values.
