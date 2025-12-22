"""Spreadsheet export helpers for sar_tracker.

Exports current database contents into a multi-sheet XLSX workbook for
readable presentation.
"""
from pathlib import Path
import json

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

import storage


def _auto_width(ws, max_width=60):
    for column_cells in ws.columns:
        try:
            length = max((len(str(cell.value)) if cell.value is not None else 0) for cell in column_cells)
        except Exception:
            length = 10
        col = get_column_letter(column_cells[0].column)
        ws.column_dimensions[col].width = min(max(length + 2, 10), max_width)


def _style_header(ws):
    bold = Font(bold=True)
    for cell in ws[1]:
        cell.font = bold
    ws.freeze_panes = "A2"


def export_to_xlsx(db_path, xlsx_fp):
    """Export the sqlite DB at `db_path` to an XLSX file at `xlsx_fp`.

    Creates three sheets:
    - `Current Status`: one row per team with current status and location
    - `Status History`: flattened history rows (team + timestamp + location/status)
    - `Transmissions`: chronological messages

    Returns True on success.
    """
    data = storage.load_db(db_path) or {'status_by_team': {}, 'location_by_team': {}, 'transmissions': []}

    wb = openpyxl.Workbook()

    # Current Status sheet (separate columns)
    ws = wb.active
    ws.title = 'Current Status'
    headers = ['Team', 'Current Location', 'Location Status', 'Transit', 'Status Code', 'Updated']
    ws.append(headers)
    for team, history in sorted(data.get('status_by_team', {}).items()):
        current = history[-1] if history else None
        current_loc = data.get('location_by_team', {}).get(team, '')
        if current and isinstance(current, dict):
            loc_status = current.get('location_status', '')
            transit = current.get('transit', '')
            status_code = current.get('status_code', '')
            updated = current.get('timestamp', '')
        else:
            loc_status = transit = status_code = updated = ''
        ws.append([team, current_loc, loc_status, transit, status_code, updated])
    # style and formatting
    header_fill = PatternFill(start_color='DDDDDD', end_color='DDDDDD', fill_type='solid')
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:F{ws.max_row}"
    _auto_width(ws)

    # Status History sheet
    ws2 = wb.create_sheet('Status History')
    headers2 = ['Team', 'Timestamp', 'Location', 'Location Status', 'Transit', 'Status Code']
    ws2.append(headers2)
    for team, history in sorted(data.get('status_by_team', {}).items()):
        for e in history:
            ws2.append([
                team,
                e.get('timestamp'),
                e.get('location'),
                e.get('location_status'),
                e.get('transit'),
                e.get('status_code'),
            ])
    # style header and autofilter
    for cell in ws2[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    ws2.freeze_panes = 'A2'
    ws2.auto_filter.ref = f"A1:F{ws2.max_row}"
    _auto_width(ws2)

    # Transmissions sheet
    ws3 = wb.create_sheet('Transmissions')
    headers3 = ['Timestamp', 'Dest', 'Src', 'Message']
    ws3.append(headers3)
    for t in data.get('transmissions', []):
        ws3.append([t.get('timestamp'), t.get('dest'), t.get('src'), t.get('msg')])
    # style header and wrap message column for readability
    for cell in ws3[1]:
        cell.font = Font(bold=True)
        cell.fill = header_fill
    msg_col = get_column_letter(4)
    for row in ws3.iter_rows(min_row=2, min_col=4, max_col=4, max_row=ws3.max_row):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True)
    ws3.freeze_panes = 'A2'
    ws3.auto_filter.ref = f"A1:D{ws3.max_row}"
    _auto_width(ws3, max_width=120)

    p = Path(xlsx_fp)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb.save(p)
    return True
