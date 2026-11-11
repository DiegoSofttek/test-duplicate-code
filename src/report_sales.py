from database import get_connection, fetch_data
from logger import log_activity
from report_common import generate_report

def generate_sales_report():
    return generate_report(
        get_connection,
        table="sales",
        log_name="ReportSales",
        label_inicio="Iniciando generación de reporte de ventas",
        label_fin="Reporte finalizado exitosamente",
    )
