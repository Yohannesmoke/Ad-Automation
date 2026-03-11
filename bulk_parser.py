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
    "phone":           ["telephonenumber", "telephone number", "phone", "mobile"],
    "email":           ["email", "e-mail", "mail"],
}


def _cell_text(cell) -> str:
    """
    Extract clean text from a <td>/<th>, handling nested tags, <br/>, &nbsp;,
    and any child tables (SDP wraps values in an inner <table> sometimes).
    """
    if not cell:
        return ""
    # get_text with separator so adjacent block elements don't merge words
    raw = cell.get_text(separator=" ", strip=True)
    raw = raw.replace("\xa0", " ")          # &nbsp;
    raw = re.sub(r"\s+", " ", raw)          # collapse whitespace
    return raw.strip()


def _detect_columns(header_cells: list) -> dict:
    """
    Build {internal_key: column_index} by matching each header cell's text
    against COLUMN_MAP patterns. 
    """
    mapping = {}
    used_indices = set()
    
    # Pre-normalise all headers
    headers = []
    for cell in header_cells:
        h_text = _cell_text(cell)
        h_norm = h_text.lower().replace(" ", "").replace("_", "")
        headers.append(h_norm)

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


def parse_html_table(html: str) -> tuple[list[dict], list[dict]]:
    """
    Parse the SDP description HTML and return (users, skipped).

    users   — list of dicts with raw data from the 4-column table
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
        phone      = get("phone")
        email      = get("email")

        # Skip completely empty rows
        if not first_name and not last_name:
            continue

        # Validate required fields for the row itself
        missing = [f for f, v in [
            ("FirstName", first_name), ("LastName", last_name)
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

        users.append({
            "first_name": first_name,
            "last_name":  last_name,
            "phone":      phone,
            "email_raw":  email,
        })
        logger.info("Parsed user row: %s %s", first_name, last_name)

    return users, skipped
