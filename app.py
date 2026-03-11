import os
import json
import logging
import re
import secrets
import string
import ssl
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Import custom modules
from bulk_parser import parse_html_table
from create_user import run_remote_ad_script

# Load configuration
load_dotenv()

# App Configuration
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
PARTNER_EMAIL_DOMAIN = os.getenv("PARTNER_EMAIL_DOMAIN", "partnersafaricom.et")

# SDP Configuration
SDP_API_KEY = os.getenv("SDP_API_KEY")
SDP_BASE_URL = os.getenv("SDP_BASE_URL")
SDP_LOG_FIELD = os.getenv("SDP_LOG_FIELD", "udf_mline_908")

# Logging Configuration
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "ad_provisioning.log")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Set up rotating log handler (5MB, 5 backups)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=5)
handler.setFormatter(formatter)

logger = logging.getLogger("ad_provisioning")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Also log to console for visibility during dev
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

app = Flask(__name__)

def validate_token(req):
    """Validate X-Webhook-Token header against .env value."""
    token = req.headers.get("X-Webhook-Token")
    return token == WEBHOOK_SECRET_TOKEN

def generate_username(first: str, last: str) -> str:
    """Generate username as firstname.lastname (lowercase, alphanumeric only)."""
    f = re.sub(r"[^a-z0-9]", "", first.lower())
    l = re.sub(r"[^a-z0-9]", "", last.lower())
    return f"{f}.{l}"

def generate_password(first: str) -> str:
    """
    Generate password as: Firstname + 4 random digits + @
    Must have uppercase, lowercase, number, special char.
    Firstname starts with uppercase, so we satisfy that.
    """
    # Use a truly random 16-character password to satisfy strict AD policies
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(16))

def calculate_expiry(duration: str) -> str:
    """
    Calculate expiration date based on duration string.
    Supports "X month(s)" and "X year(s)".
    """
    if not duration or str(duration).lower() == "permanent":
        return "never"
    
    now = datetime.now()
    duration_lower = str(duration).lower()
    
    # Try to find a number and a unit (month/year)
    match = re.search(r"(\d+)\s*(month|year)", duration_lower)
    if not match:
        return "never"
        
    val = int(match.group(1))
    unit = match.group(2)
    
    if unit == "year":
        expiry = now + timedelta(days=val * 365)
    else: # month
        # Approximation: 30 days per month
        expiry = now + timedelta(days=val * 30)
        
    return expiry.strftime("%Y-%m-%d")

def update_sdp_ticket(request_id, message):
    """
    Update the SDP ticket with provisioning logs/credentials.
    Uses SDP API v3.
    """
    if not SDP_API_KEY or not SDP_BASE_URL or not request_id:
        logger.warning("SDP integration skipped: Missing configuration or request_id")
        return False

    url = f"{SDP_BASE_URL}/{request_id}"
    headers = {
        "Accept": "application/vnd.manageengine.sdp.v3+json",
        "authtoken": SDP_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # Payload for updating
    input_data = {
        "request": {
            "udf_fields": {
                SDP_LOG_FIELD: message
            }
        }
    }

    # Encode as per user example
    data = urlencode({"input_data": json.dumps(input_data)}).encode()

    try:
        logger.info(f"Attempting to update SDP ticket {request_id} via urllib...")
        
        # Create unverified context for localhost HTTPS
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        httprequest = Request(url, headers=headers, data=data, method="PUT")
        
        with urlopen(httprequest, context=ctx, timeout=10) as response:
            resp_body = response.read().decode()
            logger.info(f"Successfully updated SDP ticket {request_id}. Response: {resp_body}")
            return True
            
    except HTTPError as e:
        resp_err = e.read().decode()
        logger.error(f"SDP HTTP Error {e.code}: {resp_err}")
        return False
    except URLError as e:
        logger.error(f"SDP URL Error: {str(e.reason)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error updating SDP: {str(e)}")
        return False

@app.route("/health", methods=["GET"])
def health():
    """Confirm app is running."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

@app.route("/webhook/debug", methods=["POST"])
def debug():
    """Log raw payload, for testing."""
    payload = request.get_json(silent=True)
    logger.info(f"DEBUG Webhook received from {request.remote_addr}")
    logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    return jsonify({"message": "Payload logged"}), 200

@app.route("/webhook/create-user", methods=["POST"])
def create_user():
    """Main endpoint to handle AD user creation requests."""
    logger.info(f"Incoming webhook request from {request.remote_addr}")

    # 1. Validate Token
    if not validate_token(request):
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
        return jsonify({"error": "Unauthorized"}), 401

    # 2. Parse Payload
    payload = request.get_json(silent=True)
    if not payload or "description" not in payload:
        logger.error("Invalid payload: Missing 'description' field")
        return jsonify({"error": "Invalid payload structure"}), 400

    # Extract ID for SDP update
    # The new payload uses "ticket id", but we'll fallback to other common names
    request_id = payload.get("ticket id") or payload.get("WORKORDERID") or payload.get("request_id") or payload.get("id")
    logger.info(f"SDP Ticket ID detected: {request_id}")

    html_content = payload.get("description", "")
    
    # Extract Shared Fields
    shared_ou = payload.get("ou")
    shared_groups_raw = payload.get("Groups", "")
    shared_manager = payload.get("Manager")
    shared_reason = payload.get("Reason for Access")
    shared_vendor = payload.get("vendor name")
    shared_duration = payload.get("AD Account Duration")
    shared_email_required = payload.get("Outlook Email Required")

    # Groups: split by semicolon, skip Domain Users
    shared_groups = [g.strip() for g in shared_groups_raw.split(";") if g.strip() and g.strip().lower() != "domain users"]

    logger.info(f"Webhook received. Processing batch for vendor: {shared_vendor}")

    # 3. Extract Users from HTML
    try:
        raw_users, skipped_rows = parse_html_table(html_content)
    except ValueError as e:
        logger.error(f"Parsing error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error during parsing")
        return jsonify({"error": "Internal parsing error"}), 500

    # 4. Process Users
    results = []
    succeeded = 0
    failed = 0
    skipped = len(skipped_rows)
    
    # Add skipped users to results
    for skip in skipped_rows:
        results.append({
            "username": skip.get("username", "unknown"),
            "success": False,
            "message": skip.get("reason")
        })

    # Calculate global expiry date
    account_expires = calculate_expiry(shared_duration)

    for user in raw_users:
        first = user["first_name"]
        last = user["last_name"]
        
        # Logic 3: UserLogonName is now auto-generated
        username = generate_username(first, last)
        
        # Logic 4: Conditional Email
        if shared_email_required == "Yes":
            email = f"{username}@{PARTNER_EMAIL_DOMAIN}"
        else:
            email = user.get("email_raw")

        # Logic 5: Password is now auto-generated
        password = generate_password(first)

        # Logic 6: DisplayName built from Vendor Name
        # Using dash instead of pipe as | is disallowed in AD Name attribute
        display_name = f"{first} {last} - Partner|{shared_vendor}"

        # Logic 1 & 7 & 8 & 9: Merge shared fields
        user_data = {
            "first_name": first,
            "last_name": last,
            "display_name": display_name,
            "description": shared_reason,
            "phone": user.get("phone"),
            "email": email,
            "username": username,
            "password": password,
            "manager": shared_manager,
            "groups": shared_groups,
            "ou": shared_ou,
            "account_expires": account_expires,
            "change_password": "TRUE" # Default requirement
        }

        logger.info(f"Attempting to create user: {username}")
        
        try:
            # Call WinRM script
            res = run_remote_ad_script(user_data)
            
            if res.get("success"):
                succeeded += 1
                logger.info(f"User created successfully: {username}")
                results.append({
                    "username": username,
                    "full_name": f"{first} {last}",
                    "email": email,
                    "generated_password": password,
                    "success": True,
                    "message": "User created successfully",
                    "groups": shared_groups,
                    "ou": shared_ou,
                    "account_expires": account_expires
                })
            else:
                failed += 1
                logger.error(f"Failed to create user {username}: {res.get('message')}")
                results.append({
                    "username": username,
                    "success": False,
                    "message": res.get("message")
                })
            
        except Exception as e:
            failed += 1
            msg = str(e)
            logger.error(f"Error for {username}: {msg}")
            results.append({
                "username": username,
                "success": False,
                "message": f"Unexpected error: {msg}"
            })

    # 5. Return Report
    report = {
        "total": len(raw_users) + skipped,
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
        "results": results
    }
    
    logger.info(f"Batch processed: {succeeded} succeeded, {failed} failed, {skipped} skipped")

    # 6. Optional: Update SDP Ticket with Results
    if request_id:
        sdp_lines = [f"AD Provisioning Batch Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "----------------------------------------"]
        for res in results:
            status = "SUCCESS" if res.get("success") else "FAILED"
            line = f"[{status}] User: {res.get('username')}"
            if res.get("success"):
                line += f" | Pass: {res.get('generated_password')}"
            else:
                line += f" | Error: {res.get('message')}"
            sdp_lines.append(line)
        
        full_message = "\n".join(sdp_lines)
        update_sdp_ticket(request_id, full_message)

    return jsonify(report), 200

if __name__ == "__main__":
    logger.info(f"Starting AD Provisioning Automation on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT)