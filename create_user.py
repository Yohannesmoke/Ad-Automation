import subprocess
import json
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def escape_ps_val(val):
    """Escape single quotes for PowerShell strings."""
    if val is None:
        return ""
    # PowerShell escapes single quotes by doubling them
    return str(val).replace("'", "''")

def run_remote_ad_script(user_data: dict) -> dict:
    """
    Execute create_ad_user.ps1 locally using subprocess.
    """
    script_path = os.path.join(os.path.dirname(__file__), "create_ad_user.ps1")
    
    if not os.path.exists(script_path):
        return {"success": False, "message": f"PowerShell script not found at {script_path}"}

    # Prepare parameters for PowerShell
    groups_str = ",".join(user_data.get("groups", []))
    
    # Map Boolean text to PowerShell booleans (ChangePassword)
    change_pw = "$true" if str(user_data.get("change_password")).upper() == "TRUE" else "$false"

    # Escape all text values
    f_name = escape_ps_val(user_data.get('first_name'))
    l_name = escape_ps_val(user_data.get('last_name'))
    d_name = escape_ps_val(user_data.get('display_name'))
    desc   = escape_ps_val(user_data.get('description'))
    phone  = escape_ps_val(user_data.get('phone'))
    email  = escape_ps_val(user_data.get('email'))
    uname  = escape_ps_val(user_data.get('username'))
    pw     = escape_ps_val(user_data.get('password'))
    mgr    = escape_ps_val(user_data.get('manager'))
    groups = escape_ps_val(groups_str)
    ou     = escape_ps_val(user_data.get('ou'))
    expiry = escape_ps_val(user_data.get('account_expires'))

    cmd = [
        "powershell.exe",
        "-NonInteractive",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        f"& '{script_path}' "
        f"-FirstName '{f_name}' "
        f"-LastName '{l_name}' "
        f"-DisplayName '{d_name}' "
        f"-Description '{desc}' "
        f"-TelephoneNumber '{phone}' "
        f"-Email '{email}' "
        f"-UserLogonName '{uname}' "
        f"-Password '{pw}' "
        f"-ChangePassword {change_pw} "
        f"-Manager '{mgr}' "
        f"-Groups '{groups}' "
        f"-OU '{ou}' "
        f"-AccountExpirationDate '{expiry}'"
    ]

    try:
        logger.info(f"Executing PowerShell script locally for user: {user_data.get('username')}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            logger.error(f"PowerShell execution failed with exit code {result.returncode}")
            logger.error(f"STDERR: {result.stderr}")
            # Try to see if there's JSON in stdout even on non-zero exit
            stdout = result.stdout.strip()
            lines = stdout.splitlines()
            for line in reversed(lines):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            
            return {
                "success": False, 
                "message": f"PowerShell Error: {result.stderr.strip()}",
                "username": user_data.get("username")
            }

        stdout = result.stdout.strip()
        logger.debug(f"PowerShell STDOUT: {stdout}")

        # Extract JSON from output
        lines = stdout.splitlines()
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        
        return {
            "success": False,
            "message": "PowerShell executed but returned no valid JSON result.",
            "raw_output": stdout,
            "username": user_data.get("username")
        }

    except subprocess.TimeoutExpired:
        logger.error("PowerShell script execution timed out.")
        return {"success": False, "message": "PowerShell execution timed out after 60 seconds."}
    except Exception as e:
        logger.exception("Unexpected error during local script execution")
        return {
            "success": False,
            "message": f"Execution Error: {str(e)}",
            "username": user_data.get("username")
        }
