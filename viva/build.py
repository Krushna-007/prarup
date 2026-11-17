"""Build the viva books from the code itself.

    python3 viva/build.py            # all four PDFs into viva/

Every function, class and method in prarup/ is shown with its real code and
line numbers, next to the explanation written for it in viva/notes/. The
build stops if any piece of code has no explanation, or an explanation
names code that no longer exists, so the books always match the code.

Notes format (viva/notes/<module>.txt, e.g. ui_window.txt):

    @purpose            what the file is for (paragraphs)
    @imports            why it imports what it imports
    == name             one entry per function / Class / Class.method
    plain paragraph     explanation
    - bullet            a step
    > text              a trace line, shown in a box exactly as written
    ? question          a viva question about this code...
    ! answer            ...and its answer
    * text              a design note (SOLID principle or pattern used here)
"""

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIVA = ROOT / "viva"
NOTES = VIVA / "notes"
PARTS = VIVA / "parts"
OUT = VIVA / "build"

MEMBERS = {
    "Prateek": ["pandoc", "ingest", "frontmatter", "texsource", "manuscript", "images"],
    "Krushna": ["models", "analyze", "renderer", "compile", "figures", "measure", "checks",
                "fit", "fix"],
    "Om": ["project", "main", "process", "ui/window", "ui/outline", "ui/panels", "ui/editors",
           "ui/preview", "ui/style"],
}
ROLE = {"Prateek": "Reading the paper, and checking its images",
        "Krushna": "Building the IEEE PDF, and checking it",
        "Om": "The Tkinter window, and joining everything"}


# ---------------------------------------------------------------- reading the code

class Unit:
    """One function, class or method, with its source lines."""

    def __init__(self, module, name, kind, node, lines):
        self.module, self.name, self.kind, self.node = module, name, kind, node
        self.start = node.lineno
        if node.decorator_list:
            self.start = node.decorator_list[0].lineno
        self.end = node.end_lineno
        if kind == "class":                 # a class header stops at its first method
            methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            if methods:
                first = methods[0]
                self.end = (first.decorator_list[0].lineno if first.decorator_list else first.lineno) - 1
        self.code = "\n".join(lines[self.start - 1:self.end]).rstrip()
        self.short = name.split(".")[-1]


def read_module(module):
    path = ROOT / "prarup" / f"{module}.py"
    text = path.read_text()
    tree = ast.parse(text)
    lines = text.splitlines()
    units = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            units.append(Unit(module, node.name, "function", node, lines))
        elif isinstance(node, ast.ClassDef):
            units.append(Unit(module, node.name, "class", node, lines))
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    units.append(Unit(module, f"{node.name}.{item.name}", "method", item, lines))
    imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("prarup"):
            imports.append((node.module.replace("prarup.", "").replace(".", "/"),
                            [a.name for a in node.names]))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, [a.name for a in node.names]))
        elif isinstance(node, ast.Import):
            imports += [(a.name, []) for a in node.names]
    return {"path": path, "units": units, "imports": imports, "lines": len(lines),
            "doc": ast.get_docstring(tree) or ""}


# ---------------------------------------------------------------- what the code uses

FEATURES = [
    ("dataclass", lambda n: any(_name(d) == "dataclass" for d in getattr(n, "decorator_list", []))),
    ("@classmethod", lambda n: any(_name(d) == "classmethod" for d in getattr(n, "decorator_list", []))),
    ("@staticmethod", lambda n: any(_name(d) == "staticmethod" for d in getattr(n, "decorator_list", []))),
    ("@property", lambda n: any(_name(d) == "property" for d in getattr(n, "decorator_list", []))),
    ("inheritance", lambda n: isinstance(n, ast.ClassDef) and bool(n.bases)),
    ("list/dict comprehension", lambda n: _has(n, (ast.ListComp, ast.DictComp, ast.SetComp))),
    ("generator expression", lambda n: _has(n, ast.GeneratorExp)),
    ("lambda", lambda n: _has(n, ast.Lambda)),
    ("with", lambda n: _has(n, ast.With)),
    ("try/except", lambda n: _has(n, ast.Try)),
    ("raise", lambda n: _has(n, ast.Raise)),
    ("regex", lambda n: _calls_attr(n, "re")),
    ("f-string", lambda n: _has(n, ast.JoinedStr)),
    ("nested function", lambda n: any(isinstance(c, ast.FunctionDef) for c in ast.walk(n) if c is not n)),
    ("recursion", lambda n: isinstance(n, ast.FunctionDef) and any(
        isinstance(c, ast.Call) and _name(c.func) == n.name for c in ast.walk(n))),
    ("global", lambda n: _has(n, ast.Global)),
    ("yield", lambda n: _has(n, (ast.Yield, ast.YieldFrom))),
    ("subprocess", lambda n: _calls_attr(n, "subprocess") or _calls_name(n, "run_tool")),
    ("thread", lambda n: _calls_method(n, "submit")),
    ("tuple unpacking", lambda n: any(isinstance(c, ast.Assign) and isinstance(c.targets[0], ast.Tuple)
                                      for c in ast.walk(n))),
    ("isinstance", lambda n: _calls_name(n, "isinstance")),
    ("enumerate/zip", lambda n: _calls_name(n, "enumerate") or _calls_name(n, "zip")),
    ("next(...)", lambda n: _calls_name(n, "next")),
]


def _name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    return ""


def _has(node, kinds):
    return any(isinstance(c, kinds) for c in ast.walk(node))


def _calls_attr(node, module):
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and isinstance(c.func.value, ast.Name) and c.func.value.id == module
               for c in ast.walk(node))


def _calls_name(node, name):
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == name
               for c in ast.walk(node))


def _calls_method(node, name):
    return any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == name
               for c in ast.walk(node))


def features(unit):
    node = unit.node
    if unit.kind == "class":                # judge the header only, not its methods
        node = ast.ClassDef(name=node.name, bases=node.bases, keywords=[], decorator_list=node.decorator_list,
                            body=[b for b in node.body if not isinstance(b, ast.FunctionDef)] or [ast.Pass()],
                            type_params=[])
    return [label for label, test in FEATURES if test(node)]


def callers(all_units):
    """For each unit: the units that call it (matched by name, only when the name is unique)."""
    by_short = {}
    for u in all_units:
        if u.kind != "class":
            by_short.setdefault(u.short, []).append(u)
    called_by = {id(u): [] for u in all_units}
    for u in all_units:
        if u.kind == "class":
            continue
        for c in ast.walk(u.node):
            if isinstance(c, ast.Call):
                target = _name(c.func)
                matches = by_short.get(target, [])
                if len(matches) == 1 and matches[0] is not u:
                    label = f"{u.module}.{u.name}"
                    if label not in called_by[id(matches[0])]:
                        called_by[id(matches[0])].append(label)
    for u in all_units:                     # classes: where they are constructed
        if u.kind == "class":
            for v in all_units:
                if v.kind != "class" and v.module != "" and any(
                        isinstance(c, ast.Call) and _name(c.func) == u.name for c in ast.walk(v.node)):
                    label = f"{v.module}.{v.name}"
                    if label not in called_by[id(u)]:
                        called_by[id(u)].append(label)
    return called_by


# ---------------------------------------------------------------- reading the notes

def read_notes(module):
    path = NOTES / (module.replace("/", "_") + ".txt")
    if not path.exists():
        sys.exit(f"missing notes file {path.relative_to(ROOT)}")
    sections, current = {}, None
    for raw in path.read_text().splitlines():
        if raw.startswith("== "):
            current = raw[3:].strip()
            sections[current] = []
        elif raw.startswith("@"):
            current = raw.strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(raw)
        elif raw.strip():
            sys.exit(f"{path.name}: text before the first heading: {raw!r}")
    return sections


# ---------------------------------------------------------------- writing LaTeX

def esc(text):
    """Escape plain text for LaTeX, then turn `code` and **bold** into markup."""
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(r"\cc{" + _esc(part[1:-1]) + "}")
        else:
            piece = _esc(part)
            piece = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", piece)
            out.append(piece)
    return "".join(out)


def _esc(text):
    table = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
             "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    table.update({ch: "{\\dvs " + ch + "}" for ch in "⚠⁰¹²³⁴⁵⁶⁷⁸⁹‖‡†↑↓"})
    table["⛔"] = "\\noentry{}"
    return "".join(table.get(ch, ch) for ch in text)


def render_notes(lines):
    """Turn a note's lines into LaTeX: paragraphs, bullets, trace box, Q&A."""
    out, para, bullets, trace, qa = [], [], [], [], []

    def flush_para():
        if para:
            out.append("\\leavevmode{\\color{ink}" + esc(" ".join(para)) + "}\n")
            para.clear()

    def flush_bullets():
        if bullets:
            out.append("\\begin{itemize}\n" + "".join(f"\\item \\leavevmode{{\\color{{ink}}{esc(b)}}}\n" for b in bullets)
                       + "\\end{itemize}\n")
            bullets.clear()

    def flush_trace():
        if trace:
            out.append("\\begin{tracebox}\n" + "\n".join(printable(l) for l in trace) + "\n\\end{tracebox}\n")
            trace.clear()

    for line in lines:
        s = line.rstrip()
        if s.startswith("* "):
            flush_para(), flush_bullets(), flush_trace()
            out.append("\\designnote{" + esc(s[2:]) + "}\n")
        elif s.startswith("- "):
            flush_para(), flush_trace()
            bullets.append(s[2:])
        elif s.startswith("> ") or s == ">":
            flush_para(), flush_bullets()
            trace.append(s[2:])
        elif s.startswith("? "):
            flush_para(), flush_bullets(), flush_trace()
            qa.append([s[2:], ""])
        elif s.startswith("! "):
            if not qa:
                sys.exit(f"answer without a question: {s}")
            qa[-1][1] += (" " if qa[-1][1] else "") + s[2:]
        elif not s.strip():
            flush_para(), flush_bullets(), flush_trace()
        else:
            if bullets and line.startswith("  "):
                bullets[-1] += " " + s.strip()
            else:
                flush_bullets(), flush_trace()
                para.append(s.strip())
    flush_para(), flush_bullets(), flush_trace()
    return "".join(out), qa


SYMBOLS = set("⚠↑↓‖‡†⁰¹²³⁴⁵⁶⁷⁸⁹")


def printable(code):
    """Send characters the code font lacks to fonts that have them."""
    code = re.sub(r"[ऀ-ॿ]+", lambda m: "(*@{\\deva " + m.group() + "}@*)", code)
    code = code.replace("⛔", "(*@\\noentry{}@*)")
    return "".join("(*@{\\dvs " + ch + "}@*)" if ch in SYMBOLS else ch for ch in code)


def listing(unit):
    code = printable(unit.code)
    return (f"\\begin{{codebox}}[firstnumber={unit.start}]\n{code}\n\\end{{codebox}}\n")


def unit_latex(unit, notes, called_by):
    body, qa = render_notes(notes)
    kind = {"function": "function", "class": "class", "method": "method"}[unit.kind]
    title = esc(unit.name)
    lines = f"lines {unit.start}--{unit.end}"
    out = [f"\\unithead{{{title}}}{{{kind}}}{{{lines}}}\n",
           f"\\label{{u:{unit.module}:{unit.name}}}\n"]
    chips = features(unit)
    if chips:
        out.append("\\chips{" + "".join(f"\\chip{{{esc(c)}}}" for c in chips) + "}\n")
    out.append(listing(unit))
    out.append(body)
    if called_by:
        out.append("\\calledby{" + esc(", ".join(called_by[:8]) + (" …" if len(called_by) > 8 else ""))
                   + "}\n")
    if qa:
        out.append("\\begin{askbox}\n")
        for q, a in qa:
            out.append(f"\\qa{{{esc(q)}}}{{{esc(a)}}}\n")
        out.append("\\end{askbox}\n")
    return "".join(out), qa


def module_latex(module, info, notes, called_by, imported_by):
    title = f"prarup/{module}.py"
    out = [f"\\chapter{{\\texttt{{{esc(title)}}}}}\n\\label{{m:{module}}}\n"]
    purpose, purpose_qa = render_notes(notes.get("@purpose", []))
    out.append(f"\\begin{{purposebox}}\n{purpose}\\end{{purposebox}}\n")
    if purpose_qa:
        out.append("\\begin{askbox}\n" + "".join(f"\\qa{{{esc(q)}}}{{{esc(a)}}}\n" for q, a in purpose_qa)
                   + "\\end{askbox}\n")
    stats = (f"{info['lines']} lines \\textperiodcentered{{}} "
             f"{sum(u.kind != 'method' for u in info['units'])} top-level definitions \\textperiodcentered{{}} "
             f"{sum(u.kind == 'method' for u in info['units'])} methods")
    out.append(f"\\modstats{{{stats}}}\n")
    ours = [(m, names) for m, names in info["imports"] if (ROOT / "prarup" / f"{m}.py").exists()]
    outside = [(m, names) for m, names in info["imports"] if (m, names) not in ours]
    rows = []
    for m, names in ours:
        rows.append(f"\\importrow{{\\hyperref[m:{m}]{{{esc(m)}.py}}}}{{{esc(', '.join(names))}}}")
    for m, names in outside:
        rows.append(f"\\importrow{{{esc(m)}}}{{{esc(', '.join(names)) or '(the whole module)'}}}")
    users = ", ".join(f"\\hyperref[m:{u}]{{{esc(u)}.py}}" for u in sorted(imported_by)) or "nobody (it is the entry point)"
    out.append("\\begin{importbox}\n" + "\n".join(rows) + f"\n\\importedby{{{users}}}\n\\end{{importbox}}\n")
    why, _ = render_notes(notes.get("@imports", []))
    if why:
        out.append(why)
    all_qa = [("(the file)", q, a) for q, a in purpose_qa]
    for unit in info["units"]:
        text, qa = unit_latex(unit, notes.get(unit.name, []), called_by[id(unit)])
        out.append(text)
        all_qa += [(unit.name, q, a) for q, a in qa]
    return "".join(out), all_qa


def check_notes(module, info, notes):
    names = {u.name for u in info["units"]}
    have = {k for k in notes if not k.startswith("@")}
    missing = [n for n in names if n not in have or not any(l.strip() for l in notes[n])]
    extra = sorted(have - names)
    problems = []
    if missing:
        problems.append(f"{module}: no explanation for {', '.join(sorted(missing))}")
    if extra:
        problems.append(f"{module}: notes for code that does not exist: {', '.join(extra)}")
    if "@purpose" not in notes:
        problems.append(f"{module}: no @purpose")
    return problems


# ---------------------------------------------------------------- the books

def build():
    modules = [m for ms in MEMBERS.values() for m in ms]
    on_disk = sorted(str(p.relative_to(ROOT / "prarup"))[:-3] for p in (ROOT / "prarup").rglob("*.py")
                     if p.name != "__init__.py")
    forgotten = sorted(set(on_disk) - set(modules))
    if forgotten:
        sys.exit(f"modules with no owner: {forgotten}")

    infos = {m: read_module(m) for m in modules}
    notes = {m: read_notes(m) for m in modules}
    problems = [p for m in modules for p in check_notes(m, infos[m], notes[m])]
    if problems:
        sys.exit("The notes do not match the code:\n  " + "\n  ".join(problems))

    all_units = [u for m in modules for u in infos[m]["units"]]
    called_by = callers(all_units)
    imported_by = {m: set() for m in modules}
    for m in modules:
        for other, _ in infos[m]["imports"]:
            if other in imported_by:
                imported_by[other].add(m)

    OUT.mkdir(exist_ok=True)
    chapters, bank = {}, {}
    for m in modules:
        chapters[m], bank[m] = module_latex(m, infos[m], notes[m], called_by, imported_by[m])
        (OUT / f"mod_{m.replace('/', '_')}.tex").write_text(chapters[m])

    # the question bank: every question, by member and module
    for member, ms in MEMBERS.items():
        lines = [f"\\section{{{member}: {esc(ROLE[member])}}}\n"]
        for m in ms:
            if bank[m]:
                lines.append(f"\\subsection*{{\\texttt{{{esc(m)}.py}}}}\n\\begin{{enumerate}}[leftmargin=2em]\\color{{ink}}\n")
                for name, q, a in bank[m]:
                    target = f"m:{m}" if name == "(the file)" else f"u:{m}:{name}"
                    lines.append(f"\\item \\textbf{{{esc(q)}}} {{\\small\\color{{slate}}(\\hyperref[{target}]"
                                 f"{{{esc(name)}}})}}\\\\ {esc(a)}\n")
                lines.append("\\end{enumerate}\n")
        (OUT / f"bank_{member}.tex").write_text("".join(lines))

    counts = {member: sum(infos[m]["lines"] for m in ms) for member, ms in MEMBERS.items()}
    questions = {member: sum(len(bank[m]) for m in ms) for member, ms in MEMBERS.items()}
    (OUT / "numbers.tex").write_text("".join(
        f"\\newcommand{{\\lines{member}}}{{{counts[member]}}}\n"
        f"\\newcommand{{\\questions{member}}}{{{questions[member]}}}\n" for member in MEMBERS)
        + f"\\newcommand{{\\unitsTotal}}{{{len(all_units)}}}\n"
        + f"\\newcommand{{\\questionsTotal}}{{{sum(questions.values())}}}\n")

    books = {"Prarup_Viva_Book": list(MEMBERS)}
    books.update({f"Viva_{member}": [member] for member in MEMBERS})
    for name, members in books.items():
        body = []
        for member in members:
            body.append(f"\\input{{{PARTS / ('part_' + member + '.tex')}}}\n")
            for m in MEMBERS[member]:
                body.append(f"\\input{{{OUT / ('mod_' + m.replace('/', '_') + '.tex')}}}\n")
        bank_parts = "".join(f"\\input{{{OUT / ('bank_' + member + '.tex')}}}\n" for member in members)
        title = "The whole codebase" if len(members) > 1 else f"{members[0]}: {ROLE[members[0]]}"
        main = (PARTS / "book.tex").read_text()
        main = main.replace("%%TITLE%%", esc(title)).replace("%%BODY%%", "".join(body))
        main = main.replace("%%BANK%%", bank_parts).replace("%%VIVA%%", str(VIVA))
        main = main.replace("%%OUT%%", str(OUT))
        (OUT / f"{name}.tex").write_text(main)
        result = subprocess.run(["tectonic", "--keep-logs", "-o", str(OUT), str(OUT / f"{name}.tex")],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[-4000:])
            sys.exit(f"{name} did not compile")
        shutil.copy(OUT / f"{name}.pdf", VIVA / f"{name}.pdf")
        print("built", VIVA / f"{name}.pdf")
    print(f"{len(all_units)} pieces of code explained; questions: {questions}; lines: {counts}")


if __name__ == "__main__":
    build()
