"""Change only the reserved MP4 metadata key, without remuxing media or offsets."""
import os
import struct

# FFmpeg unconditionally overwrites/removes 'encoder'. Export an equal-length
# mdta key first, then rename that key after closing the muxer. No atom grows.
ENCODER_KEY = "appname"


def _atoms(file, start, end):
    position = start
    while position < end:
        if end - position < 8:
            raise ValueError("Truncated MP4 atom header")
        file.seek(position)
        size, kind = struct.unpack(">I4s", file.read(8))
        header = 8
        if size == 1:
            if end - position < 16:
                raise ValueError("Truncated extended MP4 atom")
            size = struct.unpack(">Q", file.read(8))[0]
            header = 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            raise ValueError("Invalid MP4 atom size")
        yield kind, position + header, position + size
        position += size


def finalize_encoder_tag(path):
    """Rename the single reserved mdta key to encoder; never search video bytes."""
    with open(path, "r+b") as file:
        end = os.fstat(file.fileno()).st_size
        locations = []
        for kind, start, stop in _atoms(file, 0, end):
            if kind != b"moov":
                continue
            for kind, start, stop in _atoms(file, start, stop):
                if kind != b"udta":
                    continue
                for kind, start, stop in _atoms(file, start, stop):
                    if kind != b"meta":
                        continue
                    if stop - start < 4:
                        raise ValueError("Invalid MP4 meta atom")
                    for kind, start, stop in _atoms(file, start + 4, stop):
                        if kind != b"keys":
                            continue
                        if stop - start < 8:
                            raise ValueError("Invalid MP4 keys atom")
                        file.seek(start + 4)  # FullBox flags, then entry_count
                        count = struct.unpack(">I", file.read(4))[0]
                        pos = start + 8
                        if count > (stop - pos) // 8:
                            raise ValueError("Invalid MP4 metadata key count")
                        for _ in range(count):
                            if stop - pos < 8:
                                raise ValueError("Truncated MP4 metadata key")
                            file.seek(pos)
                            size, namespace = struct.unpack(">I4s", file.read(8))
                            if size < 8 or pos + size > stop:
                                raise ValueError("Invalid MP4 metadata key")
                            if size == 15 and namespace == b"mdta" and file.read(7) == ENCODER_KEY.encode("ascii"):
                                locations.append(pos + 8)
                            pos += size
        if len(locations) != 1:
            raise ValueError("Reserved MP4 encoder tag missing or duplicated")
        file.seek(locations[0])
        file.write(b"encoder")
