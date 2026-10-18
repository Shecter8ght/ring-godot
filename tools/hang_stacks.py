"""Где стоит зависшая игра: стеки потоков живого процесса Godot (Windows x64), без отладчика.

python -X utf8 tools/hang_stacks.py [pid] [--all] [--frames N]

Без pid берёт процесс Godot, который не отвечает (иначе — последний запущенный не-редактор).
Печатает стек главного потока (--all — всех потоков, одинаковые склеены): модуль+смещение, имя
экспорта системных DLL, а у кадров Godot — строки, на которые ссылается код рядом (имя функции и
файл из сообщений ERR_FAIL движка: «fence_wait», «rendering_device_driver_vulkan.cpp» и т. п.).
Символов движка нет — этого обычно хватает понять, чего ждёт игра (кадр в драйвере, мьютекс, поток).
Игру не трогает: потоки приостанавливаются только на время чтения стека.
Нужен dbghelp.dll — из Windows Kits (Debuggers\\x64) или системный.
"""
import ctypes as C
import ctypes.wintypes as W
import os
import re
import struct
import subprocess
import sys

DBGHELP = [r"C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\dbghelp.dll", "dbghelp.dll"]

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi", use_last_error=True)
dbg = None
for path in DBGHELP:
    if path == "dbghelp.dll" or os.path.exists(path):
        dbg = C.WinDLL(path, use_last_error=True)
        break


class THREADENTRY32(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD),
                ("th32OwnerProcessID", W.DWORD), ("tpBasePri", W.LONG), ("tpDeltaPri", W.LONG), ("dwFlags", W.DWORD)]


class ADDRESS64(C.Structure):
    _fields_ = [("Offset", C.c_uint64), ("Segment", W.WORD), ("Mode", C.c_int)]


class STACKFRAME64(C.Structure):
    # KdHelp64 в конце — с запасом: размер у версий dbghelp разный, лишнее не мешает
    _fields_ = [("AddrPC", ADDRESS64), ("AddrReturn", ADDRESS64), ("AddrFrame", ADDRESS64), ("AddrStack", ADDRESS64),
                ("AddrBStore", ADDRESS64), ("FuncTableEntry", C.c_void_p), ("Params", C.c_uint64 * 4),
                ("Far", W.BOOL), ("Virtual", W.BOOL), ("Reserved", C.c_uint64 * 3), ("KdHelp", C.c_byte * 256)]


k32.OpenProcess.restype = W.HANDLE
k32.OpenThread.restype = W.HANDLE
k32.CreateToolhelp32Snapshot.restype = W.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
k32.Thread32First.argtypes = [W.HANDLE, C.POINTER(THREADENTRY32)]
k32.Thread32Next.argtypes = [W.HANDLE, C.POINTER(THREADENTRY32)]
k32.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.GetThreadContext.argtypes = [W.HANDLE, C.c_void_p]
k32.SuspendThread.argtypes = [W.HANDLE]
k32.ResumeThread.argtypes = [W.HANDLE]
k32.CloseHandle.argtypes = [W.HANDLE]
k32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
psapi.EnumProcessModulesEx.argtypes = [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), W.DWORD]
psapi.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, C.c_wchar_p, W.DWORD]
dbg.SymInitialize.argtypes = [W.HANDLE, C.c_char_p, W.BOOL]
dbg.SymGetModuleBase64.argtypes = [W.HANDLE, C.c_uint64]
dbg.SymGetModuleBase64.restype = C.c_uint64
dbg.SymFunctionTableAccess64.argtypes = [W.HANDLE, C.c_uint64]
dbg.SymFunctionTableAccess64.restype = C.c_void_p
FTA = C.WINFUNCTYPE(C.c_void_p, W.HANDLE, C.c_uint64)
GMB = C.WINFUNCTYPE(C.c_uint64, W.HANDLE, C.c_uint64)
dbg.StackWalk64.argtypes = [W.DWORD, W.HANDLE, W.HANDLE, C.POINTER(STACKFRAME64), C.c_void_p, C.c_void_p, FTA, GMB, C.c_void_p]
_fta = FTA(lambda h, a: dbg.SymFunctionTableAccess64(h, a))
_gmb = GMB(lambda h, a: dbg.SymGetModuleBase64(h, a))


def find_pid() -> int:
    """Godot, который не отвечает; иначе последний запущенный не-редактор."""
    ps = ("Get-Process -Name 'godot*' | ForEach-Object { $c = (Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.Id)\").CommandLine; "
          "'{0}|{1}|{2}|{3}' -f $_.Id, $_.Responding, $_.StartTime.Ticks, ($c -match '--editor') }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.strip().split("|")
        if len(parts) == 4:
            rows.append((int(parts[0]), parts[1] == "True", int(parts[2]), parts[3] == "True"))
    hung = [r for r in rows if not r[1]]
    if hung:
        return hung[0][0]
    games = sorted([r for r in rows if not r[3]], key=lambda r: r[2])
    if games:
        return games[-1][0]
    sys.exit("Процесс Godot не найден")


def modules(h: int) -> list:
    arr = (W.HMODULE * 2048)()
    need = W.DWORD()
    psapi.EnumProcessModulesEx(h, arr, C.sizeof(arr), C.byref(need), 3)
    out = []
    for i in range(need.value // C.sizeof(W.HMODULE)):
        if not arr[i]:
            continue
        name = C.create_unicode_buffer(1024)
        psapi.GetModuleFileNameExW(h, W.HMODULE(arr[i]), name, 1024)
        out.append((arr[i], name.value))
    return sorted(out)


class PeFile:
    """Экспорты и чтение по RVA из файла модуля на диске (адреса совпадают с образом в памяти)."""

    def __init__(self, path: str):
        self.f = open(path, "rb")
        hdr = self.f.read(4096)
        pe = struct.unpack_from("<I", hdr, 0x3C)[0]
        nsec = struct.unpack_from("<H", hdr, pe + 6)[0]
        soh = struct.unpack_from("<H", hdr, pe + 20)[0]
        opt = pe + 24
        magic = struct.unpack_from("<H", hdr, opt)[0]
        self.exp_rva = struct.unpack_from("<I", hdr, opt + (112 if magic == 0x20B else 96))[0]
        self.secs = []
        for i in range(nsec):
            s = opt + soh + i * 40
            vsz, va, rsz, raw = struct.unpack_from("<IIII", hdr, s + 8)
            self.secs.append((va, max(vsz, rsz), raw, rsz))
        self._exports = None

    def read(self, rva: int, n: int) -> bytes:
        for va, sz, raw, rsz in self.secs:
            if va <= rva < va + sz and rva - va < rsz:
                self.f.seek(raw + rva - va)
                return self.f.read(n)
        return b""

    def exports(self) -> list:
        if self._exports is None:
            self._exports = []
            if self.exp_rva:
                d = self.read(self.exp_rva, 40)
                nfun, nnames, afun, aname, aord = struct.unpack_from("<IIIII", d, 20)
                funcs = struct.unpack("<%dI" % nfun, self.read(afun, 4 * nfun))
                names = struct.unpack("<%dI" % nnames, self.read(aname, 4 * nnames))
                ords = struct.unpack("<%dH" % nnames, self.read(aord, 2 * nnames))
                for nrva, o in zip(names, ords):
                    self._exports.append((funcs[o], self.read(nrva, 128).split(b"\0")[0].decode(errors="replace")))
                self._exports.sort()
        return self._exports

    def near_export(self, rva: int) -> str:
        best = None
        for r, n in self.exports():
            if r <= rva:
                best = (r, n)
        # дальше 64 КБ от экспорта — это уже внутренняя функция, имя экспорта только запутает
        return "%s+0x%x" % (best[1], rva - best[0]) if best and rva - best[0] < 0x10000 else ""

    def strings_near(self, rva: int, before: int = 600, after: int = 900) -> list:
        code = self.read(rva - before, before + after)
        out = []
        for m in re.finditer(rb"[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]", code):
            i = m.start()
            disp = int.from_bytes(code[i + 3:i + 7], "little", signed=True)
            s = self.read(rva - before + i + 7 + disp, 160).split(b"\0")[0]
            if len(s) >= 5 and all(32 <= c < 127 for c in s):
                out.append((i - before, s.decode()))
        return out


def walk(h: int, tid: int, max_frames: int) -> list:
    ht = k32.OpenThread(0x1F03FF, False, tid)
    if not ht:
        return []
    k32.SuspendThread(ht)
    try:
        buf = (C.c_byte * (1232 + 16))()
        ctx = (C.addressof(buf) + 15) & ~15
        C.c_uint32.from_address(ctx + 0x30).value = 0x10000B  # CONTEXT_FULL (AMD64)
        if not k32.GetThreadContext(ht, C.c_void_p(ctx)):
            return []
        sf = STACKFRAME64()
        sf.AddrPC.Offset, sf.AddrPC.Mode = C.c_uint64.from_address(ctx + 0xF8).value, 3
        sf.AddrStack.Offset, sf.AddrStack.Mode = C.c_uint64.from_address(ctx + 0x98).value, 3
        sf.AddrFrame.Offset, sf.AddrFrame.Mode = C.c_uint64.from_address(ctx + 0xA0).value, 3
        frames = []
        for _ in range(max_frames):
            if not dbg.StackWalk64(0x8664, h, ht, C.byref(sf), C.c_void_p(ctx), None, _fta, _gmb, None):
                break
            if sf.AddrPC.Offset == 0:
                break
            frames.append(sf.AddrPC.Offset)
        return frames
    finally:
        k32.ResumeThread(ht)
        k32.CloseHandle(ht)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    max_frames = 24
    if "--frames" in sys.argv:
        max_frames = int(sys.argv[sys.argv.index("--frames") + 1])
        args = [a for a in args if a != str(max_frames)]
    pid = int(args[0]) if args else find_pid()
    h = k32.OpenProcess(0x1F0FFF, False, pid)
    if not h:
        sys.exit("Не открыть процесс %d (код %d)" % (pid, C.get_last_error()))
    dbg.SymSetOptions(0x2 | 0x4)
    dbg.SymInitialize(h, None, True)
    mods = modules(h)
    pes = {}

    def describe(addr: int, with_strings: bool) -> list:
        base, path = None, ""
        for b, p in mods:
            if b <= addr:
                base, path = b, p
        if base is None:
            return ["0x%x" % addr]
        name = os.path.basename(path)
        rva = addr - base
        if path not in pes:
            try:
                pes[path] = PeFile(path)
            except OSError:
                pes[path] = None
        pe = pes[path]
        line = "%s+0x%x" % (name, rva)
        if pe is not None:
            ex = pe.near_export(rva)
            if ex:
                line += "  (%s)" % ex
        out = [line]
        if with_strings and pe is not None and name.lower().startswith("godot"):
            # имя функции и файл движка из сообщений об ошибках рядом с местом вызова
            hints = [s for _, s in pe.strings_near(rva) if re.search(r"\.(cpp|h)$|^[a-z_]+$", s)]
            if hints:
                out.append("        рядом: " + ", ".join(dict.fromkeys(hints[:8])))
        return out

    snap = k32.CreateToolhelp32Snapshot(0x4, 0)
    te = THREADENTRY32()
    te.dwSize = C.sizeof(THREADENTRY32)
    tids = []
    ok = k32.Thread32First(snap, C.byref(te))
    while ok:
        if te.th32OwnerProcessID == pid:
            tids.append(te.th32ThreadID)
        ok = k32.Thread32Next(snap, C.byref(te))
    k32.CloseHandle(snap)
    print("процесс %d, потоков %d; первый — главный" % (pid, len(tids)))
    groups = {}
    for n, tid in enumerate(tids if show_all else tids[:1]):
        frames = walk(h, tid, max_frames)
        key = tuple(frames[:6]) if n else ("main",)
        groups.setdefault(key, []).append((tid, frames))
    for key, items in groups.items():
        tid, frames = items[0]
        extra = " (+%d таких же)" % (len(items) - 1) if len(items) > 1 else ""
        print("== поток %d%s" % (tid, extra))
        for i, a in enumerate(frames):
            for line in describe(a, with_strings=i < 12):
                print("   " + line)


if __name__ == "__main__":
    main()
