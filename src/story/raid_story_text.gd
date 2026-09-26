class_name RaidStoryText
extends RefCounted
## Хроника рейда: русский текст из чисел — прописью с родом, согласование («1 человек, 2 человека,
## 5 человек»), деньги, время, формы слов (оружие, противник) из data/raid_story.json; подстановка
## {переменных} в фразы.

const ONES_M := ["", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
const ONES_F := ["", "одна", "две", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
const ONES_N := ["", "одно", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"]
const TEENS := ["десять", "одиннадцать", "двенадцать", "тринадцать", "четырнадцать", "пятнадцать", "шестнадцать", "семнадцать", "восемнадцать", "девятнадцать"]
const TENS := ["", "", "двадцать", "тридцать", "сорок", "пятьдесят", "шестьдесят", "семьдесят", "восемьдесят", "девяносто"]
const HUNDREDS := ["", "сто", "двести", "триста", "четыреста", "пятьсот", "шестьсот", "семьсот", "восемьсот", "девятьсот"]
const ORDINALS := ["", "первый", "второй", "третий", "четвёртый", "пятый", "шестой", "седьмой", "восьмой", "девятый", "десятый"]


## Форма слова по числу: plural(3, "человек", "человека", "человек").
static func plural(n: int, one: String, few: String, many: String) -> String:
	var a := absi(n) % 100
	if a >= 11 and a <= 14:
		return many
	match a % 10:
		1:
			return one
		2, 3, 4:
			return few
	return many


## Прописью до 999 (больше — цифрами); род: "m", "f", "n".
static func words(n: int, gender: String = "m") -> String:
	if n <= 0:
		return "ноль"
	if n > 999:
		return str(n)
	var ones: Array = ONES_F if gender == "f" else (ONES_N if gender == "n" else ONES_M)
	var parts: Array[String] = []
	if n >= 100:
		parts.append(HUNDREDS[n / 100])
	var r := n % 100
	if r >= 10 and r < 20:
		parts.append(TEENS[r - 10])
	else:
		if r >= 20:
			parts.append(TENS[r / 10])
		if r % 10 > 0:
			parts.append(String(ones[r % 10]))
	return " ".join(parts)


## «двадцать человек», «один противник»: прописью до сотни, дальше — цифрами.
static func count(n: int, one: String, few: String, many: String, gender: String = "m") -> String:
	return "%s %s" % [words(n, gender) if n < 100 else str(n), plural(n, one, few, many)]


static func ordinal(n: int) -> String:
	return String(ORDINALS[n]) if n > 0 and n < ORDINALS.size() else "%d-й" % n


static func money(v: int) -> String:
	return "%s ₽" % InventoryUI.money(v)


## «38 секунд», «12 минут», «1 час 5 минут».
static func duration(sec: float) -> String:
	var s := int(round(sec))
	if s < 60:
		return "%d %s" % [s, plural(s, "секунду", "секунды", "секунд")]
	var m := s / 60
	if m < 60:
		return "%d %s" % [m, plural(m, "минуту", "минуты", "минут")]
	var h := m / 60
	m = m % 60
	var t := "%d %s" % [h, plural(h, "час", "часа", "часов")]
	return t if m == 0 else "%s %d %s" % [t, m, plural(m, "минуту", "минуты", "минут")]


## Подставить {переменные}; чего нет — оставить как есть (видно при проверке данных).
static func fill(line: String, vars: Dictionary) -> String:
	var out := line
	for k in vars:
		out = out.replace("{%s}" % String(k), String(vars[k]))
	return out


## «с снайперской» → «со снайперской»: перед с/з/ш/ж с согласной предлог «с» звучит как «со».
static func prepositions(text: String) -> String:
	var re := RegEx.new()
	re.compile("(^|[\\s(«—])([Сс]) ([сзшжщСЗШЖЩ][бвгджзйклмнпрстфхцчшщ])")
	return re.sub(text, "$1$2о $3", true)


## Первая буква — заглавная.
static func cap(s: String) -> String:
	return s.substr(0, 1).to_upper() + s.substr(1) if s != "" else s
