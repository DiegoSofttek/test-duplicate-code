from database import get_connection
from report_common import generate_report


def generate_sales_report():
    return generate_report(
        log_name="ReportSales",
        table="sales",
        start_message="Iniciando generación de reporte de ventas",
        connect=get_connection,
    )
