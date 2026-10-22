from report_common import generate_report


def generate_sales_report():
    return generate_report(
        report_name="ReportSales",
        query="SELECT * FROM sales WHERE month = 'current'",
    )
