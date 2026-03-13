import re
from datetime import datetime, timedelta

# Mocking the functions from app.py to test them
def calculate_expiry(duration: str) -> str:
    if not duration or str(duration).lower() in ["permanent", "none", "0"]:
        return "never"
    
    now = datetime.now()
    duration_str = str(duration).strip().lower()
    
    if duration_str.isdigit():
        val = int(duration_str)
        expiry = now + timedelta(days=val * 30)
        return expiry.strftime("%Y-%m-%d")

    match = re.search(r"(\d+)\s*(month|year|day)", duration_str)
    if not match:
        return "never"
        
    val = int(match.group(1))
    unit = match.group(2)
    
    if "year" in unit:
        expiry = now + timedelta(days=val * 365)
    elif "month" in unit:
        expiry = now + timedelta(days=val * 30)
    else: # day
        expiry = now + timedelta(days=val)
        
    return expiry.strftime("%Y-%m-%d")

def test_expiry():
    print("Testing Expiry Logic:")
    tests = [
        ("3", "digit only (months)"),
        ("3 months", "string with units"),
        ("1 year", "year units"),
        ("permanent", "permanent string"),
        ("0", "zero string"),
        ("None", "None string"),
        ("", "empty string")
    ]
    for val, desc in tests:
        res = calculate_expiry(val)
        print(f"  Input: '{val}' ({desc}) -> Output: {res}")

def test_email_logic(email_req, email_raw, username, domain):
    print("\nTesting Email Logic:")
    # Replicating the logic in app.py
    if str(email_req).strip().lower() == "yes":
        email = f"{username}@{domain}"
    else:
        email = email_raw
        if not email:
            email = f"{username}@{domain}"
    print(f"  Req: '{email_req}', Raw: '{email_raw}' -> Result: {email}")

if __name__ == "__main__":
    test_expiry()
    test_email_logic("YES", "test@old.com", "j.doe", "Partner.safaricom.et")
    test_email_logic("Yes ", "test@old.com", "j.doe", "Partner.safaricom.et")
    test_email_logic("No", "test@old.com", "j.doe", "Partner.safaricom.et")
    test_email_logic("No", "", "j.doe", "Partner.safaricom.et")
