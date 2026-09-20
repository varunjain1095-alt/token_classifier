"""Load complete stored datasets and build eligibility-aware records."""
import glob
import os
from typing import Any, Dict, List, Optional, Tuple

from src.intake.csv_parser import csv_parser
from src.intake.excel_parser import excel_parser
from src.shared.config import get_settings
from src.shared.logger import get_logger
from src.snapshot.eligibility_screener import eligibility_screener

logger = get_logger(__name__)

settings = get_settings()


def _is_blank_row(row: Any) -> bool:
    """Check if a raw data row is completely blank."""
    if not row:
        return True
    cells = row if isinstance(row, (list, tuple)) else list(row.values())
    return all(c is None or not str(c).strip() for c in cells)


def load_stored_rows(file_id: str) -> Tuple[List[str], List[List[Any]], str]:
    """Load all rows from a stored upload file by file_id.

    Returns (headers, data_rows, file_path). data_rows contains every
    physical data row including blank ones.
    """
    pattern = os.path.join(settings.upload_folder, f"{file_id}_*")
    matches = glob.glob(pattern)
    if not matches:
        raise FileNotFoundError(f"No stored file for file_id {file_id}")

    file_path = matches[0]
    file_extension = os.path.splitext(file_path)[1].lower()

    with open(file_path, 'rb') as f:
        file_content = f.read()

    if file_extension == '.csv':
        parse_result = csv_parser.parse_file(file_content, max_rows=10**9)
    elif file_extension in ['.xlsx', '.xls']:
        sheet_info = excel_parser.get_sheet_names(file_content, file_extension)
        sheet_name = sheet_info['sheet_names'][0] if sheet_info.get('sheet_names') else None
        parse_result = excel_parser.parse_file(
            file_content, file_extension, sheet_name, max_rows=10**9
        )
    else:
        raise ValueError(f"Unsupported file type: {file_extension}")

    if not parse_result['success']:
        raise ValueError(parse_result.get('error', 'Failed to parse stored file'))

    return parse_result['headers'], parse_result['preview_rows'], file_path


def build_dataset_records(headers: List[str],
                          data_rows: List[List[Any]],
                          field_mapping: Dict[str, str],
                          use_column_ids: bool = True) -> Dict[str, Any]:
    """Build records from stored rows.

    - Completely blank rows never become records or receive IDs.
    - source_row preserves the physical data-row number (1-based).
    - When a Record ID column is mapped and use_column_ids, its values are
      used; otherwise immutable ROW-XXXXXX IDs are generated per record.
    - Each record is checked for eligibility; rows with blank review text
      are ineligible.
    """
    header_index = {h: i for i, h in enumerate(headers)}
    review_text_col = next(
        (h for h, t in field_mapping.items() if t == 'review_text'), None
    )
    record_id_col = next(
        (h for h, t in field_mapping.items() if t == 'record_id'), None
    )

    records: List[Dict[str, Any]] = []
    blank_rows = 0

    for physical_index, row in enumerate(data_rows):
        if _is_blank_row(row):
            blank_rows += 1
            continue

        cells = row if isinstance(row, (list, tuple)) else list(row.values())
        metadata = {
            h: (cells[header_index[h]] if header_index[h] < len(cells) else '')
            for h in headers
        }

        review_text = ''
        if review_text_col is not None:
            review_text = metadata.get(review_text_col, '')

        if use_column_ids and record_id_col is not None:
            record_id = str(metadata.get(record_id_col, '') or f"ROW-{len(records) + 1:06d}")
        else:
            record_id = f"ROW-{len(records) + 1:06d}"

        record = {
            'id': record_id,
            'source_row': physical_index + 1,
            'original_review_text': review_text,
            'mapped_metadata': metadata,
        }
        record['eligible'] = eligibility_screener.check_record(
            record, field_mapping, len(records)
        )
        records.append(record)

    eligible_records = [r for r in records if r['eligible']]

    return {
        'records': records,
        'eligible_records': eligible_records,
        'loaded_physical_rows': len(data_rows),
        'blank_rows_excluded': blank_rows,
        'eligible_count': len(eligible_records),
    }
