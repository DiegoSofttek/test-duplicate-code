from report_common import generate_report


def generate_expenses_report():
    return generate_report(
        report_name="ReportExpenses",
        query="SELECT * FROM expenses WHERE month = 'current'",
    )
