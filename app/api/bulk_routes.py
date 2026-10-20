"""Bounded, memory-only workbook uploads and stateless ZIP downloads."""

import json
from io import BytesIO

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from python_multipart.multipart import FormParser, parse_options_header
from python_multipart.exceptions import MultipartParseError
from starlette.concurrency import run_in_threadpool

from app.api.routes import generation_lock
from app.services.bulk_service import generate_batch, validate_recipients, validation_report
from app.services.excel_service import MAX_UPLOAD_BYTES, ExcelError, example_workbook, parse_workbook
from app.services.pdf_service import TemplateError
from app.services.text_layout_service import LayoutError

router = APIRouter(prefix="/api/invitations/bulk")
NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
UPLOAD_SCHEMA = {
    "requestBody": {"required": True, "content": {"multipart/form-data": {
        "schema": {"type": "object", "required": ["file"],
                   "properties": {"file": {"type": "string", "format": "binary"}}}
    }}}
}


def uploaded_workbook(body: bytes, content_type: str):
    media_type, options = parse_options_header(content_type)
    if media_type != b"multipart/form-data" or not options.get(b"boundary"):
        raise ExcelError("Upload one .xlsx file in the multipart field named file.")
    files = []
    uploads = []
    completed = []

    def on_field(field):
        field.close()
        raise ExcelError("Only the file upload field is accepted.")

    def on_file(file):
        uploads.append(file)
        if files or file.field_name != b"file":
            raise ExcelError("Upload exactly one file in the field named file.")
        file.file_object.seek(0)
        files.append((file.file_object.read(MAX_UPLOAD_BYTES + 1), (file.file_name or b"").decode("utf-8", errors="replace")))

    parser = FormParser(
        "multipart/form-data", on_field, on_file, on_end=lambda: completed.append(True),
        boundary=options[b"boundary"],
        config={"MAX_MEMORY_FILE_SIZE": MAX_UPLOAD_BYTES + 65536},
    )
    try:
        parser.write(body)
        parser.finalize()
        if not completed or len(files) != 1:
            raise ExcelError("Upload one complete .xlsx file.")
        return parse_workbook(*files[0])
    finally:
        parser.close()
        for file in uploads:
            file.close()


async def process_upload(request: Request, generate: bool):
    try:
        body = BytesIO()
        async for chunk in request.stream():
            if body.tell() + len(chunk) > MAX_UPLOAD_BYTES + 65536:
                raise HTTPException(413, "Upload exceeds the 5 MB workbook limit.", headers=NO_STORE)
            body.write(chunk)

        def process():
            workbook = uploaded_workbook(body.getvalue(), request.headers.get("content-type", ""))
            with generation_lock:
                if generate:
                    return generate_batch(request.app.state.template, request.app.state.layout, workbook)
                return validation_report(validate_recipients(workbook, request.app.state.layout))

        return await run_in_threadpool(process)
    except HTTPException:
        raise
    except ExcelError as error:
        raise HTTPException(422, str(error), headers=NO_STORE) from None
    except MultipartParseError:
        raise HTTPException(422, "The multipart upload is malformed or incomplete.", headers=NO_STORE) from None
    except (TemplateError, LayoutError):
        raise HTTPException(503, "The invitation template or font is unavailable.", headers=NO_STORE) from None
    except Exception:
        raise HTTPException(500, "Unable to process this workbook. Please try again.", headers=NO_STORE) from None


@router.get("/template", response_class=Response)
def download_template() -> Response:
    return Response(
        example_workbook(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={**NO_STORE, "Content-Disposition": 'attachment; filename="Recipients_Example.xlsx"'},
    )


@router.post("/validate", openapi_extra=UPLOAD_SCHEMA)
async def validate_upload(request: Request) -> JSONResponse:
    return JSONResponse(await process_upload(request, False), headers=NO_STORE)


@router.post("/generate", openapi_extra=UPLOAD_SCHEMA, response_class=Response,
             responses={200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}})
async def generate_upload(request: Request) -> Response:
    result = await process_upload(request, True)
    if not result.summary["generated"]:
        return JSONResponse(
            {"detail": "No invitations could be generated. Correct the reported rows and retry.", "summary": result.summary},
            status_code=422, headers=NO_STORE,
        )
    counts = {key: result.summary[key] for key in (
        "total_rows", "valid_recipients", "generated", "skipped", "failed", "layout_warnings"
    )}
    counts["failed_rows"] = [record["row"] for record in result.summary["records"] if record["status"] == "failed"]
    return Response(result.data, media_type="application/zip", headers={
        **NO_STORE, "Content-Disposition": 'attachment; filename="Invitations_Batch.zip"',
        "X-Generation-Summary": json.dumps(counts, separators=(",", ":")),
    })