"""
bulk_parser.py
--------------
Parse the HTML description field from ManageEngine Service Desk Plus.
The description contains a rich-text table with these columns:
  FirstName | LastName | DisplayName | Description | Telephone Number |
  Email | Manager | Groups | OU

Groups are semicolon-separated.
OU may be wrapped in a nested <table> inside the cell (SDP quirk).
UserLogonName and Password are auto-generated when absent.
"""

import logging
import re
import secrets
import string
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "first_name":      ["firstname", "first name"],
    "last_name":       ["lastname", "last name"],
    "display_name":    ["displayname", "display name"],
    "description":     ["description"],
    "phone":           ["telephonenumber", "telephone number", "phone", "mobile"],
    "email":           ["email", "e-mail", "mail"],
    "manager":         ["manager"],
    "groups":          ["groups", "user groups", "group"],
    "ou":              ["ou", "organizational unit", "path"],
}


def _cell_text(cell) -> str:
    """
    Extract clean text from a <td>/<th>, handling nested tags, <br/>, &nbsp;,
    and any child tables (SDP wraps OU values in an inner <table> sometimes).
    """
    # get_text with separator so adjacent block elements don't merge words
    raw = cell.get_text(separator=" ", strip=True)
    raw = raw.replace("\xa0", " ")          # &nbsp;
    raw = re.sub(r"\s+", " ", raw)          # collapse whitespace
    return raw.strip()


def _detect_columns(header_cells: list) -> dict:
    """
    Build {internal_key: column_index} by matching each header cell's text
    against COLUMN_MAP patterns. Uses exact matching first to avoid 
    substring collisions (e.g., 'ou' matching inside 'groups').
    """
    mapping = {}
    used_indices = set()
    
    # Pre-normalise all headers
    headers = []
    for cell in header_cells:
        headers.append(_cell_text(cell).lower().replace(" ", "").replace("_", ""))

    # Pass 1: Exact matches
    for key, patterns in COLUMN_MAP.items():
        for p in patterns:
            p_norm = p.replace(" ", "")
            for idx, h in enumerate(headers):
                if idx not in used_indices and h == p_norm:
                    mapping[key] = idx
                    used_indices.add(idx)
                    break
            if key in mapping:
                break

    # Pass 2: Fallback to substring if not already mapped
    for key, patterns in COLUMN_MAP.items():
        if key in mapping: continue
        for p in patterns:
            p_norm = p.replace(" ", "")
            for idx, h in enumerate(headers):
                if idx not in used_indices and p_norm in h:
                    mapping[key] = idx
                    used_indices.add(idx)
                    break
            if key in mapping:
                break
    return mapping


def _extract_email(cell) -> str:
    """Prefer mailto: href in <a> tags, fall back to plain text."""
    a = cell.find("a", href=True)
    if a and a["href"].startswith("mailto:"):
        return a["href"].replace("mailto:", "").split("?")[0].strip()
    return _cell_text(cell)


def generate_username(first: str, last: str) -> str:
    """Generate username as firstname.lastname (lowercase, alphanumeric only)."""
    f = re.sub(r"[^a-zA-Z0-9]", "", first).lower()
    l = re.sub(r"[^a-zA-Z0-9]", "", last).lower()
    return f"{f}.{l}"


def generate_password(length: int = 12) -> str:
    """Generate a random password satisfying AD complexity requirements."""
    chars = string.ascii_letters + string.digits + "!@#$%"
    while True:
        pw = "".join(secrets.choice(chars) for _ in range(length))
        if (any(c.islower() for c in pw)
                and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw)
                and any(c in "!@#$%" for c in pw)):
            return pw


def parse_html_table(html: str) -> tuple[list[dict], list[dict]]:
    """
    Parse the SDP description HTML and return (users, skipped).

    users   — list of dicts ready to pass to create_user.py
    skipped — list of {username, reason, row_index} for rows that were skipped
    """
    if not html or not html.strip():
        raise ValueError("Empty HTML content provided to parser.")

    soup = BeautifulSoup(html, "html.parser")

    # Prefer the SDP-branded table; fall back to first table found
    table = soup.find("table", class_="ze_tableView") or soup.find("table")
    if not table:
        raise ValueError("No table found in description")

    # ── Get the <tbody> or fall back to direct <tr> children ─────────────────
    tbody = table.find("tbody", recursive=False) or table
    rows = tbody.find_all("tr", recursive=False)
    if not rows:
        return [], []

    # ── Header row ────────────────────────────────────────────────────────────
    header_row = rows[0]
    # Only direct-child cells of the header row
    header_cells = header_row.find_all(["th", "td"], recursive=False)
    col_map = _detect_columns(header_cells)
    logger.info("Detected columns: %s", col_map)

    if not col_map:
        raise ValueError(
            f"Could not detect any known columns from headers: "
            f"{[_cell_text(c) for c in header_cells]}"
        )

    users: list[dict] = []
    skipped: list[dict] = []

    # ── Data rows ─────────────────────────────────────────────────────────────
    for row_idx, row in enumerate(rows[1:], start=1):
        # CRITICAL: recursive=False so nested <table> cells don't bleed extra <td>s
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue
        if all(not _cell_text(c) for c in cells):
            continue  # skip fully empty rows

        def get(key: str) -> str:
            idx = col_map.get(key)
            if idx is None or idx >= len(cells):
                return ""
            cell = cells[idx]
            if key == "email":
                return _extract_email(cell)
            return _cell_text(cell)

        first_name = get("first_name")
        last_name  = get("last_name")
        email      = get("email")
        ou         = get("ou")

        # Skip completely empty rows
        if not first_name and not last_name and not email:
            continue

        # Validate required fields
        missing = [f for f, v in [
            ("FirstName", first_name), ("LastName", last_name), ("OU", ou)
        ] if not v]

        if missing:
            reason = f"Missing required fields: {', '.join(missing)}"
            logger.warning("Row %d skipped — %s", row_idx, reason)
            skipped.append({
                "username": f"{first_name}.{last_name}" or "unknown",
                "reason": reason,
                "row_index": row_idx,
            })
            continue

        # Auto-generate username if absent
        username = get("username") or generate_username(first_name, last_name)

        # Auto-generate password if absent
        password = get("password") or generate_password()

        # Normalise ChangePassword
        cp_raw = get("change_password").upper()
        change_password = "TRUE" if cp_raw in ("TRUE", "YES", "1", "") else "FALSE"

        # Groups: split by semicolon (SDP table uses ; between group names)
        raw_groups = get("groups")
        groups = [g.strip() for g in raw_groups.split(";") if g.strip()]

        users.append({
            "first_name":      first_name,
            "last_name":       last_name,
            "display_name":    get("display_name"),
            "description":     get("description"),
            "phone":           get("phone"),
            "email":           email,
            "manager":         get("manager"),
            "groups":          groups,
            "ou":              ou,
            "username":        username,
            "password":        password,
            "change_password": change_password,
        })
        logger.info("Parsed user: %s (OU: %s)", username, ou)

    return users, skipped
