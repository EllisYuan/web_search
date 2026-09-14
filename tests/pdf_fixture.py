"""Small born-digital PDF fixtures with an explicit Unicode text map."""

from io import BytesIO

from pypdf import PdfWriter
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
