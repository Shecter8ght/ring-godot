extends SceneTree
# Разбор бинарных токенов GDScript (GDSC, версия 101: Godot 4.5–4.7) обратно в текст.
# Комментарии в .gdc не сохраняются; отступы — по столбцу первого токена строки.
# Запускает tools/research/rtv/run.sh; окружение: RTV_PCK — пакет, RTV_SRC — папка вывода.
# Порядок типов токенов — как в GDScriptTokenizer::Token::Type Godot 4.5+ (с «...» для вариадиков).

const T_NAMES: Array[String] = [
	"", "@", "", "", "<", "<=", ">", ">=", "==", "!=",
	"and", "or", "not", "&&", "||", "!", "&", "|", "~", "^", "<<", ">>",
	"+", "-", "*", "**", "/", "%",
	"=", "+=", "-=", "*=", "**=", "/=", "%=", "<<=", ">>=", "&=", "|=", "^=",
	"if", "elif", "else", "for", "while", "break", "continue", "pass", "return", "match", "when",
	"as", "assert", "await", "breakpoint", "class", "class_name", "const", "enum", "extends", "func",
	"in", "is", "namespace", "preload", "self", "signal", "static", "super", "trait", "var", "void", "yield",
	"[", "]", "{", "}", "(", ")", ",", ";", ".", "..", "...", ":", "$", "->", "_",
	"\n", "<INDENT>", "<DEDENT>", "PI", "TAU", "INF", "NAN", "<VCS>", "`", "?", "<ERROR>", ""]

const T_ANNOTATION := 1
const T_IDENT := 2
const T_LITERAL := 3
const OPEN := ["[", "{", "("]
const CLOSE := ["]", "}", ")"]
const NO_SPACE_BEFORE := [")", "]", "}", ",", ".", ":", ";", "..."]

var fails: PackedStringArray = []

func _init() -> void:
	ProjectSettings.load_resource_pack(OS.get_environment("RTV_PCK"), false)
	var out_dir: String = OS.get_environment("RTV_SRC")
	DirAccess.make_dir_recursive_absolute(out_dir)
	var files: PackedStringArray = []
	_collect("res://", files)
	var ok: int = 0
	for f: String in files:
		var text: String = _decompile(f)
		if text == "":
			continue
		var rel: String = f.trim_prefix("res://").trim_suffix(".gdc") + ".gd"
		var path: String = out_dir.path_join(rel)
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var o: FileAccess = FileAccess.open(path, FileAccess.WRITE)
		o.store_string(text)
		o.close()
		ok += 1
	print("decompiled %d of %d" % [ok, files.size()])
	for s: String in fails:
		print("FAIL ", s)
	quit(0)

func _collect(dir: String, acc: PackedStringArray) -> void:
	var d: DirAccess = DirAccess.open(dir)
	if d == null:
		return
	for f: String in d.get_files():
		if f.ends_with(".gdc"):
			acc.append(dir.path_join(f))
	for sub: String in d.get_directories():
		if sub.begins_with("."):
			continue
		_collect(dir.path_join(sub), acc)

func _decompile(path: String) -> String:
	var raw: PackedByteArray = FileAccess.get_file_as_bytes(path)
	if raw.size() < 12 or raw.slice(0, 4).get_string_from_ascii() != "GDSC":
		fails.append(path + ": not GDSC")
		return ""
	if raw.decode_u32(4) != 101:
		fails.append(path + ": version %d" % raw.decode_u32(4))
		return ""
	var dsize: int = raw.decode_u32(8)
	var c: PackedByteArray = raw.slice(12) if dsize == 0 else raw.slice(12).decompress(dsize, FileAccess.COMPRESSION_ZSTD)
	var n_ids: int = c.decode_u32(0)
	var n_consts: int = c.decode_u32(4)
	var n_lines: int = c.decode_u32(8)
	var n_tokens: int = c.decode_u32(12)
	var p: int = 16
	var ids: PackedStringArray = []
	for i: int in n_ids:
		var n: int = c.decode_u32(p)
		p += 4
		var cps: PackedInt32Array = []
		for j: int in n:
			cps.append((c[p] ^ 0xb6) | ((c[p + 1] ^ 0xb6) << 8) | ((c[p + 2] ^ 0xb6) << 16) | ((c[p + 3] ^ 0xb6) << 24))
			p += 4
		var s: String = ""
		for cp: int in cps:
			s += char(cp)
		ids.append(s)
	var consts: Array = []
	for i: int in n_consts:
		var v: Variant = bytes_to_var(c.slice(p))
		consts.append(v)
		p += var_to_bytes(v).size()
	var line_start: Dictionary = {}
	for i: int in n_lines:
		line_start[c.decode_u32(p)] = c.decode_u32(p + 4)
		p += 8
	var col_start: Dictionary = {}
	for i: int in n_lines:
		col_start[c.decode_u32(p)] = c.decode_u32(p + 4)
		p += 8
	var types: PackedInt32Array = []
	var args: PackedInt32Array = []
	var lines: PackedInt32Array = []
	for i: int in n_tokens:
		if p >= c.size():
			fails.append(path + ": short token stream")
			return ""
		var t: int
		var a: int = 0
		if c[p] & 0x80:
			var u: int = c.decode_u32(p)
			t = u & 0x7f
			a = u >> 8
			p += 4
		else:
			t = c[p]
			p += 1
		lines.append(c.decode_u32(p))
		p += 4
		types.append(t)
		args.append(a)
	if p != c.size():
		fails.append(path + ": %d bytes left" % (c.size() - p))
	return _render(types, args, lines, line_start, col_start, ids, consts)

func _literal(v: Variant) -> String:
	match typeof(v):
		TYPE_STRING:
			return var_to_str(v)
		TYPE_STRING_NAME:
			return "&" + var_to_str(String(v))
		TYPE_NODE_PATH:
			return "^" + var_to_str(String(v))
		TYPE_FLOAT:
			var f: float = v
			var s: String = str(f)
			if not ("." in s or "e" in s or "inf" in s or "nan" in s):
				s += ".0"
			return s
		_:
			return var_to_str(v)

func _render(types: PackedInt32Array, args: PackedInt32Array, lines: PackedInt32Array, line_start: Dictionary,
		col_start: Dictionary, ids: PackedStringArray, consts: Array) -> String:
	var out: PackedStringArray = []
	var cur: String = ""
	var indent_cols: Array[int] = [int(col_start.get(0, 1))]
	var depth: int = 0 # вложенность скобок: внутри скобок перенос строки — продолжение выражения
	var prev_line: int = -1
	var prev_text: String = ""
	var prev_type: int = -1
	for i: int in types.size():
		var t: int = types[i]
		if t >= T_NAMES.size() - 1:
			continue
		var text: String
		if t == T_IDENT:
			text = ids[args[i]]
		elif t == T_ANNOTATION:
			text = ids[args[i]]
			if not text.begins_with("@"):
				text = "@" + text
		elif t == T_LITERAL:
			text = _literal(consts[args[i]])
		else:
			text = T_NAMES[t]
		if text == "\n" or text == "<INDENT>" or text == "<DEDENT>":
			continue
		var line: int = lines[i]
		if line_start.has(i) and prev_line != -1:
			# новая логическая строка
			out.append(cur)
			var gap: int = line - prev_line
			if gap > 1 and depth == 0:
				out.append("")
			var col: int = int(col_start.get(i, 1))
			if depth == 0:
				while col < indent_cols.back() and indent_cols.size() > 1:
					indent_cols.pop_back()
				if col > indent_cols.back():
					indent_cols.append(col)
				cur = "\t".repeat(indent_cols.size() - 1)
			else:
				cur = "\t".repeat(indent_cols.size())
			prev_text = ""
		elif line_start.has(i):
			cur = ""
		# Пробелы — по виду соседних токенов; исходного форматирования в .gdc нет.
		var need_space: bool = cur.strip_edges() != "" and prev_text != ""
		if need_space:
			if text in NO_SPACE_BEFORE:
				need_space = false
			if prev_text in OPEN or prev_text == "." or prev_text == "$" or prev_text == "@":
				need_space = false
			if text == "(" and (prev_type == T_IDENT or prev_text in CLOSE or prev_text in ["preload", "super", "assert", "func"]):
				need_space = false
			if text == "[" and (prev_type == T_IDENT or prev_text in CLOSE or prev_type == T_LITERAL):
				need_space = false
			if prev_text == "-" and _unary_minus_context(types, i - 1):
				need_space = false
			if prev_text in ["!", "~"]:
				need_space = false
			if prev_type == T_ANNOTATION and text == "(":
				need_space = false
		if need_space:
			cur += " "
		cur += text
		if text in OPEN:
			depth += 1
		elif text in CLOSE:
			depth = max(0, depth - 1)
		prev_line = line
		prev_text = text
		prev_type = t
	out.append(cur)
	return "\n".join(out) + "\n"

func _unary_minus_context(types: PackedInt32Array, minus_idx: int) -> bool:
	if minus_idx <= 0:
		return true
	var t: int = types[minus_idx - 1]
	if t == T_IDENT or t == T_LITERAL:
		return false
	var s: String = T_NAMES[t] if t < T_NAMES.size() else ""
	if s in CLOSE or s in ["self", "PI", "TAU", "INF", "NAN"]:
		return false
	return true
