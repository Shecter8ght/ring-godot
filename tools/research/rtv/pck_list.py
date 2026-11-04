# Оглавление .pck Godot 4 (только чтение): версия движка, флаги, список файлов с размерами.
# python -I -X utf8 pck_list.py <пакет.pck> <выход.tsv>  → строки «размер<TAB>флаги<TAB>путь»
import collections
import struct
import sys


def main() -> None:
    path, out = sys.argv[1], sys.argv[2]
    with open(path, "rb") as f:
        if f.read(4) != b"GDPC":
            sys.exit("не пакет Godot")
        fmt, vmaj, vmin, vpat, flags = struct.unpack("<5I", f.read(20))
        file_base = struct.unpack("<Q", f.read(8))[0]
        dir_offset = struct.unpack("<Q", f.read(8))[0] if fmt >= 3 else None
        f.read(16 * 4)
        print("format", fmt, "godot", f"{vmaj}.{vmin}.{vpat}", "flags", flags,
              "file_base", file_base, "dir_offset", dir_offset)
        if flags & 1:
            sys.exit("оглавление зашифровано")
        if dir_offset is not None:
            f.seek(dir_offset)
        count = struct.unpack("<I", f.read(4))[0]
        entries = []
        for _ in range(count):
            n = struct.unpack("<I", f.read(4))[0]
            p = f.read(n).rstrip(b"\0").decode("utf-8", "replace")
            _off, size = struct.unpack("<QQ", f.read(16))
            f.read(16)  # md5
            entries.append((p, size, struct.unpack("<I", f.read(4))[0]))
    with open(out, "w", encoding="utf-8", newline="\n") as o:
        for p, s, fl in entries:
            o.write(f"{s}\t{fl}\t{p}\n")
    print("files", count, "encrypted", sum(1 for e in entries if e[2] & 1))
    by_ext = collections.Counter()
    by_size = collections.Counter()
    for p, s, _fl in entries:
        name = p.rsplit("/", 1)[-1]
        e = name.rsplit(".", 1)[-1] if "." in name else "(none)"
        by_ext[e] += 1
        by_size[e] += s
    for e, c in by_ext.most_common(20):
        print(f"{e:14s} {c:6d} {by_size[e] / 1e6:10.1f} MB")


if __name__ == "__main__":
    main()
