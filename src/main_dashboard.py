from report_sales import generate_sales_report
from report_expenses import generate_expenses_report

def run_dashboard():
    print("--- DASHBOARD FINANCIERO ---")
    
    sales = generate_sales_report()
    print(f"Ventas: {sales}")
    
    print("-" * 20)
    
    expenses = generate_expenses_report()
    print(f"Gastos: {expenses}")

if __name__ == "__main__":
    run_dashboard()