"""What did the browser actually put on the wire, and did it still carry GPS?

Reads the multipart bodies the tap kept and answers, per upload: the declared
filename and content type, the encoded size, the image dimensions, and every
EXIF tag that survived -- with GPS and Orientation called out by name, because
those are the two that matter to a person.

This is the client half of the EXIF question. The server half is
test_exif_duong_bill.py, which asks the same thing one layer further in.
"""

from __future__ import annotations

import io
import pathlib
import re
import sys

from PIL import Image

WIRE = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/rd-qa-37-wire")


def tach(body: bytes) -> list[tuple[str, str, bytes]]:
    """Pull (filename, content-type, bytes) out of a multipart/form-data body."""
    m = re.match(rb"--([^\r\n]+)\r\n", body)
    if not m:
        return []
    sep = b"--" + m.group(1)
    parts = []
    for chunk in body.split(sep):
        if b"\r\n\r\n" not in chunk:
            continue
        head, data = chunk.split(b"\r\n\r\n", 1)
        h = head.decode("utf-8", "replace")
        fn = re.search(r'filename="([^"]*)"', h)
        ct = re.search(r"Content-Type:\s*([^\r\n]+)", h, re.I)
        if fn:
            parts.append((fn.group(1), ct.group(1).strip() if ct else "?", data.rstrip(b"\r\n-")))
    return parts


def main() -> None:
    files = sorted(WIRE.glob("scan-*.bin"))
    if not files:
        print(f"KHONG CO body nao trong {WIRE} -- may do co the da chet")
        raise SystemExit(1)

    print(f"{len(files)} upload da qua day\n")
    for f in files:
        for name, ctype, data in tach(f.read_bytes()):
            print(f"--- {f.name}  ten='{name}'  type={ctype}  {len(data):,d} bytes")
            try:
                with Image.open(io.BytesIO(data)) as im:
                    ex = im.getexif()
                    gps = dict(ex.get_ifd(0x8825))
                    tags = {hex(k): v for k, v in ex.items()}
                    print(f"    kich thuoc : {im.size}  format={im.format}")
                    print(f"    orientation: {ex.get(0x0112)}")
                    print(f"    GPS        : {gps if gps else 'KHONG CO'}")
                    print(f"    EXIF khac  : {tags if tags else 'KHONG CO'}")
            except Exception as exc:  # noqa: BLE001 - a non-image is a real answer
                print(f"    khong giai ma duoc: {type(exc).__name__}: {exc}")
            print()


if __name__ == "__main__":
    main()
