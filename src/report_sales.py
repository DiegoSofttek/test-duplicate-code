from database import get_connection
from report_common import generate_report


def generate_sales_report():
    return generate_report(
        table="sales",
        log_name="ReportSales",
        start_message="Iniciando generación de reporte de ventas",
        get_conn=get_connection,
    )
