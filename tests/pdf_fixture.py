"""Small born-digital PDF fixtures with an explicit Unicode text map."""

from io import BytesIO

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    TextStringObject,
)


def text_pdf(
    *pages: str | list[tuple[str, int, int]],
    title: str = "Fixture PDF",
    outline: bool = False,
) -> bytes:
    writer = PdfWriter()
    writer.add_metadata({"/Title": title, "/Author": "Contract fixture"})
    cid_info = DictionaryObject(
        {
            NameObject("/Registry"): TextStringObject("Adobe"),
            NameObject("/Ordering"): TextStringObject("Identity"),
            NameObject("/Supplement"): NumberObject(0),
        }
    )
    descendant = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/CIDFontType2"),
            NameObject("/BaseFont"): NameObject("/FixtureUnicode"),
            NameObject("/CIDSystemInfo"): cid_info,
        }
    )
    for page_number, page_text in enumerate(pages, start=1):
        page = writer.add_blank_page(width=612, height=792)
        fragments = [(page_text, 72, 720)] if isinstance(page_text, str) else page_text
        codepoints = list(dict.fromkeys("".join(fragment for fragment, _, _ in fragments)))
        codes = {character: index for index, character in enumerate(codepoints, start=1)}
        mappings = "\n".join(
            f"<{code:04X}> <{ord(character):04X}>" for character, code in codes.items()
        )
        cmap = DecodedStreamObject()
        cmap.set_data(
            (
                "/CIDInit /ProcSet findresource begin\n"
                "12 dict begin\nbegincmap\n"
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                "/CMapName /FixtureUnicode def\n/CMapType 2 def\n"
                "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n"
                f"{len(codes)} beginbfchar\n{mappings}\nendbfchar\n"
                "endcmap\nCMapName currentdict /CMap defineresource pop\n"
                "end\nend"
            ).encode("ascii")
        )
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type0"),
                NameObject("/BaseFont"): NameObject("/FixtureUnicode"),
                NameObject("/Encoding"): NameObject("/Identity-H"),
                NameObject("/DescendantFonts"): ArrayObject([writer._add_object(descendant)]),
                NameObject("/ToUnicode"): writer._add_object(cmap),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        commands = []
        for fragment, x, y in fragments:
            encoded = "".join(f"{codes[character]:04X}" for character in fragment)
            commands.append(f"BT /F1 12 Tf {x} {y} Td <{encoded}> Tj ET")
        content = DecodedStreamObject()
        content.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(content)
        if outline:
            writer.add_outline_item(f"Page {page_number}", page_number - 1)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("fixture-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def scanned_pdf(*images: bytes) -> bytes:
    """Wrap raster fixtures in PDF pages without adding a text layer."""
    pages = []
    for payload in images:
        with Image.open(BytesIO(payload)) as source:
            pages.append(source.convert("RGB"))
    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=144)
    return output.getvalue()


def mixed_page_pdf(image: bytes, native_text: str) -> bytes:
    """Put native text over a raster PDF page to model same-page mixed content."""
    writer = PdfWriter(clone_from=PdfReader(BytesIO(scanned_pdf(image))))
    overlay = PdfWriter(clone_from=PdfReader(BytesIO(text_pdf(native_text))))
    scanned_page = writer.pages[0]
    native_page = overlay.pages[0]
    native_page.scale_to(float(scanned_page.mediabox.width), float(scanned_page.mediabox.height))
    scanned_page.merge_page(native_page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def combine_pdfs(*documents: bytes) -> bytes:
    writer = PdfWriter()
    for payload in documents:
        for page in PdfReader(BytesIO(payload)).pages:
            writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
