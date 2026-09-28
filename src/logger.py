import datetime

def log_activity(module_name: str, message: str):
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] [{module_name}] INFO: {message}")