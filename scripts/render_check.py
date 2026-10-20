"""Fail deployment builds when the bundled template or renderer is unusable."""

import asyncio

import pymupdf

from app.main import create_app
from app.services.pdf_service import generate_invitation
from app.services.text_layout_service import RecipientText


async def check_runtime() -> None:
    application = create_app()
    paths = application.openapi()["paths"]
    if any("/api/invitations/bulk" in path for path in paths):
        raise RuntimeError("Bulk endpoints must be disabled in this deployment.")

    samples = (
        RecipientText("Amit Jain", "With Family", "Jaipur"),
        RecipientText("श्री अमित जैन", "सपरिवार", "जयपुर"),
    )
    async with application.router.lifespan_context(application):
        template = application.state.template
        layout = application.state.layout
        with pymupdf.open(stream=template.data, filetype="pdf") as original:
            original_pixels = [page.get_pixmap().samples for page in original]
            for recipient in samples:
                invitation = generate_invitation(template, layout, recipient)
                with pymupdf.open(stream=invitation.data, filetype="pdf") as generated:
                    if len(generated) != 4:
                        raise RuntimeError("The generated invitation must have four pages.")
                    if generated[0].get_pixmap().samples == original_pixels[0]:
                        raise RuntimeError("Recipient text did not change the first page.")
                    if not generated[0].get_fonts():
                        raise RuntimeError("The generated invitation must embed its font.")
                    for page_index in range(1, 4):
                        if generated[page_index].get_pixmap().samples != original_pixels[page_index]:
                            raise RuntimeError("An unpersonalized page changed during generation.")

    print("Runtime check passed: startup, English/Hindi, four-page PDFs, unchanged Pages 2-4.")


if __name__ == "__main__":
    asyncio.run(check_runtime())