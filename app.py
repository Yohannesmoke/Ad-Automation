import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
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
    logger.info(f"Incoming webhook request from {request.remote_addr} (Headers: {dict(request.headers)})")

    # 1. Validate Token
    if not validate_token(request):
        logger.warning(f"Unauthorized access attempt from {request.remote_addr}")
        return jsonify({"error": "Unauthorized"}), 401

    # 2. Parse Payload
    payload = request.get_json(silent=True)
    if not payload or "description" not in payload:
        logger.error("Invalid payload: Missing 'description' field")
        return jsonify({"error": "No table found in description"}), 400

    html_content = payload.get("description", "")
    logger.info(f"Webhook received from {request.remote_addr}. Parsing HTML table...")

    # 3. Extract Users from HTML
    # Note: Parser now automatically generates usernames/passwords if missing
    try:
        users, skipped = parse_html_table(html_content)
    except ValueError as e:
        logger.error(f"Parsing error: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error during parsing")
        return jsonify({"error": "Internal parsing error"}), 500

    if not users and not skipped:
        logger.info("No user data found in the HTML table.")
        return jsonify({"error": "No table found in description"}), 400

    # 4. Process Users
    total_users = len(users) + len(skipped)
    results = []
    
    # Add skipped users to results
    for skip in skipped:
        results.append({
            "username": skip.get("username"),
            "success": False,
            "message": skip.get("reason")
        })

    succeeded = 0
    failed = len(skipped)

    for user in users:
        username = user.get("username")
        password = user.get("password")
        logger.info(f"Attempting to create user: {username}")
        
        try:
            # Call WinRM script
            res = run_remote_ad_script(user)
            
            if res.get("success"):
                succeeded += 1
                logger.info(f"User created successfully: {username} | Password: {password}")
            else:
                failed += 1
                logger.error(f"Failed to create user {username}: {res.get('message')}")
            
            # Add password to report if it was generated
            report_data = {
                "username": username,
                "password": password, 
                "success": res.get("success"),
                "message": res.get("message")
            }
            results.append(report_data)
            
        except Exception as e:
            failed += 1
            msg = f"Unexpected error during user creation: {str(e)}"
            logger.error(f"Error for {username}: {msg}")
            results.append({
                "username": username,
                "success": False,
                "message": msg
            })

    # 5. Return Report
    report = {
        "total": total_users,
        "succeeded": succeeded,
        "failed": failed,
        "results": results
    }
    
    logger.info(f"Batch processed: {succeeded} succeeded, {failed} failed out of {total_users}")
    return jsonify(report), 200

if __name__ == "__main__":
    logger.info(f"Starting AD Provisioning Automation on {FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT)