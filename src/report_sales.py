from database import get_connection, fetch_data
from logger import log_activity
from report_common import generate_report

def generate_sales_report():
    return generate_report("sales", "ReportSales", get_connection)
