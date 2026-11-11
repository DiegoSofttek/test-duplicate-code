from database import get_connection
from report_common import generate_report

def generate_sales_report():
    return generate_report("ReportSales", "sales", "ventas", get_connection)
