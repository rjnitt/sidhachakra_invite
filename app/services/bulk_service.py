"""Stateless validation and independent invitation generation for each Excel row."""

import json
from dataclasses import dataclass, field, replace
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from app.models.schemas import TemplateLayout
from app.services.excel_service import WorkbookRows
from app.services.pdf_service import Template, TemplateError, generate_invitation
from app.services.text_layout_service import LayoutError, TextLayoutService


@dataclass(frozen=True)
class GeneratedBatch:
    data: bytes = field(repr=False)
    summary: dict


def validate_recipients(workbook: WorkbookRows, configuration: TemplateLayout) -> WorkbookRows:
    service = TextLayoutService(configuration)
    records = []
    for row in workbook.rows:
        if row.recipient is None:
            records.append(row)
            continue
        try:
            layout = service.fit(row.recipient)
            records.append(replace(row, warnings=layout.warnings))
        except LayoutError as error:
            records.append(replace(row, error=str(error), warnings=(str(error),)))
    return WorkbookRows(tuple(records))


def validation_report(workbook: WorkbookRows) -> dict:
    valid = [row for row in workbook.rows if row.recipient is not None and not row.error]
    selected = set()
    if valid:
        selected.update((0, len(valid) // 2, len(valid) - 1))
        selected.add(max(range(len(valid)), key=lambda index: len(valid[index].recipient.name)))
        for index in range(len(valid)):
            if len(selected) >= min(5, len(valid)):
                break
            selected.add(index)
    return {
        "total_rows": workbook.total_rows,
        "valid_recipients": len(valid),
        "generated": 0,
        "skipped": sum(row.skipped for row in workbook.rows),
        "failed": sum(bool(row.error) for row in workbook.rows),
        "layout_warnings": sum(bool(row.warnings) for row in workbook.rows),
        "records": [
            {"row": row.number, "status": "skipped" if row.skipped else "failed" if row.error else "valid",
             "message": row.error, "warnings": list(row.warnings)}
            for row in workbook.rows
        ],
        "warnings": [
            {"row": row.number, "message": warning}
            for row in workbook.rows for warning in row.warnings
        ],
        "preview_records": [
            {"row": valid[index].number, "name": valid[index].recipient.name,
             "second_line": valid[index].recipient.second_line, "city": valid[index].recipient.city}
            for index in sorted(selected)
        ],
    }


def generate_batch(template: Template, configuration: TemplateLayout, workbook: WorkbookRows) -> GeneratedBatch:
    validated = validate_recipients(workbook, configuration)
    report = validation_report(validated)
    report.pop("preview_records")
    filenames = set()
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for row, record in zip(validated.rows, report["records"]):
            if record["status"] != "valid":
                continue
            try:
                invitation = generate_invitation(template, configuration, row.recipient, filenames)
                archive.writestr(invitation.filename, invitation.data)
                record.update(status="generated", filename=invitation.filename)
                report["generated"] += 1
            except TemplateError:
                raise
            except Exception:
                record.update(status="failed", message="This invitation could not be generated. Correct the row and retry.")
                report["failed"] += 1
        archive.writestr("summary.json", json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"))
    return GeneratedBatch(output.getvalue(), report)