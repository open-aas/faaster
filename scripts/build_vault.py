"""Generate the Obsidian vault (obsidian-vault/) from docs/ and the faaster package tree.

Run from anywhere: ``python scripts/build_vault.py``. The vault is rebuilt from scratch each run.
"""
import ast
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "obsidian-vault"
DOCS = ROOT / "docs"
PACKAGE = ROOT / "faaster"


def note_name(path: Path) -> str:
    """Unique note name for a package path: faaster/hda/manager.py -> faaster.hda.manager."""
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def module_info(path: Path) -> tuple[str, list[str], list[str]]:
    """Return (docstring first line, top-level classes, faaster imports) of a module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return "", [], []
    doc = (ast.get_docstring(tree) or "").strip().splitlines()
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("faaster"):
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(a.name for a in node.names if a.name.startswith("faaster"))
    return (doc[0] if doc else ""), classes, sorted(imports)


def resolve_import(module: str, known: set[str]) -> str | None:
    """Map an imported module to an existing note, walking up to the parent package."""
    while module:
        if module in known:
            return module
        module = module.rpartition(".")[0]
    return None


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_docs(doc_notes: dict[str, str]) -> None:
    """Copy docs/*.md as notes, turning relative .md links into wikilinks."""
    link = re.compile(r"\[([^\]]+)\]\((?!https?:)([^)#]+)\.md(#[^)]*)?\)")
    for src in sorted(DOCS.glob("*.md")):
        text = link.sub(lambda m: f"[[{doc_notes.get(Path(m[2]).name, Path(m[2]).name)}|{m[1]}]]",
                        src.read_text(encoding="utf-8"))
        write(VAULT / "docs" / f"{doc_notes[src.stem]}.md", f"{text}\n\nUp: [[docs/_index|Docs]]\n")
    lines = ["# Docs", "", "Up: [[Faaster]]", ""]
    lines += [f"- [[{doc_notes[p.stem]}]]" for p in sorted(DOCS.glob("*.md"))]
    write(VAULT / "docs" / "_index.md", "\n".join(lines) + "\n")


def build_package() -> list[str]:
    """One note per module and an _index per package, linked by containment and imports."""
    modules = sorted(p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts)
    packages = sorted({p.parent for p in modules})
    known = {note_name(p) for p in modules} | {note_name(p / "__init__.py") for p in packages}
    imported_by: dict[str, set[str]] = {}
    infos = {}
    for path in modules:
        name = note_name(path)
        infos[path] = module_info(path)
        for imp in infos[path][2]:
            target = resolve_import(imp, known)
            if target and target != name:
                imported_by.setdefault(target, set()).add(name)

    for path in modules:
        if path.name == "__init__.py":
            continue
        name = note_name(path)
        doc, classes, imports = infos[path]
        deps = sorted({t for i in imports if (t := resolve_import(i, known)) and t != name})
        parent = note_name(path.parent / "__init__.py")
        lines = [f"# {name}", "", f"File: `{path.relative_to(ROOT)}`", f"Package: [[{parent}]]", ""]
        if doc:
            lines += [doc, ""]
        if classes:
            lines += ["## Classes", ""] + [f"- `{c}`" for c in classes] + [""]
        if deps:
            lines += ["## Imports", ""] + [f"- [[{d}]]" for d in deps] + [""]
        if imported_by.get(name):
            lines += ["## Imported by", ""] + [f"- [[{d}]]" for d in sorted(imported_by[name])] + [""]
        write(VAULT / "code" / f"{name}.md", "\n".join(lines))

    for pkg in packages:
        name = note_name(pkg / "__init__.py")
        up = "[[Faaster]]" if pkg == PACKAGE else f"[[{note_name(pkg.parent / '__init__.py')}]]"
        children = sorted(note_name(p) for p in modules if p.parent == pkg and p.name != "__init__.py")
        subpkgs = sorted(note_name(p / "__init__.py") for p in packages if p.parent == pkg)
        lines = [f"# {name}", "", f"Folder: `{pkg.relative_to(ROOT)}/`", f"Up: {up}", ""]
        if subpkgs:
            lines += ["## Packages", ""] + [f"- [[{s}]]" for s in subpkgs] + [""]
        if children:
            lines += ["## Modules", ""] + [f"- [[{c}]]" for c in children] + [""]
        write(VAULT / "code" / f"{name}.md", "\n".join(lines))

    lines = ["# Code", "", "Up: [[Faaster]]", ""]
    lines += [f"- [[{note_name(p / '__init__.py')}]]" for p in packages]
    write(VAULT / "code" / "_index.md", "\n".join(lines) + "\n")
    return [note_name(p / "__init__.py") for p in packages if p.parent == PACKAGE]


def main() -> None:
    if VAULT.exists():
        shutil.rmtree(VAULT)
    (VAULT / ".obsidian").mkdir(parents=True)
    write(VAULT / ".obsidian" / "app.json", '{\n  "useMarkdownLinks": false\n}\n')

    doc_notes = {p.stem: f"doc-{p.stem}" for p in DOCS.glob("*.md")}
    build_docs(doc_notes)
    top_packages = build_package()

    root = [
        "# Faaster",
        "",
        "Reactive AAS Type 2 over OPC UA. Generated by `scripts/build_vault.py` — do not edit by hand.",
        "",
        "## Navigation",
        "",
        "- [[docs/_index|Docs]] — guides from `docs/`",
        "- [[code/_index|Code]] — one note per package and module",
        "",
        "## Guides",
        "",
    ]
    root += [f"- [[{doc_notes[p.stem]}]]" for p in sorted(DOCS.glob("*.md"))]
    root += ["", "## Packages", "", "- [[faaster]]"] + [f"- [[{p}]]" for p in sorted(top_packages)]
    write(VAULT / "Faaster.md", "\n".join(root) + "\n")
    print(f"Vault written to {VAULT}")


if __name__ == "__main__":
    main()
