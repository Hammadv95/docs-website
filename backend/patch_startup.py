from pathlib import Path
import re

path = Path("main.py")
src = path.read_text(encoding="utf-8")
bak = path.with_suffix(".py.bak")
bak.write_text(src, encoding="utf-8")

lines = src.splitlines(True)

def has_line(pattern):
    return any(re.search(pattern, l) for l in lines)

# 1) Ensure `import logging`
if not has_line(r"^\s*import\s+logging\s*$") and not has_line(r"^\s*from\s+logging\s+import\s+"):
    insert_at = 0
    for i, l in enumerate(lines):
        if re.match(r"^\s*(from|import)\s+", l):
            insert_at = i + 1
        elif insert_at > 0 and l.strip() == "":
            continue
        elif insert_at > 0:
            break
    lines.insert(insert_at, "import logging\n")

# 2) Ensure logger definition (near app = FastAPI())
text = "".join(lines)
lines = text.splitlines(True)

if not any(re.search(r'logger\s*=\s*logging\.getLogger\("uvicorn\.error"\)', l) for l in lines):
    for i, l in enumerate(lines):
        if re.search(r"^\s*app\s*=\s*FastAPI\(", l):
            lines.insert(i+1, 'logger = logging.getLogger("uvicorn.error")\n')
            lines.insert(i+2, "\n")
            break

# 3) Wrap startup event handler body with try/except (first occurrence)
text = "".join(lines)
lines = text.splitlines(True)

startup_dec_idx = None
for i, l in enumerate(lines):
    if re.match(r'^\s*@app\.on_event\(\s*["\']startup["\']\s*\)\s*$', l):
        startup_dec_idx = i
        break
if startup_dec_idx is None:
    raise SystemExit("Could not find @app.on_event('startup') in main.py")

def_idx = None
for j in range(startup_dec_idx+1, min(startup_dec_idx+6, len(lines))):
    if re.match(r"^\s*(async\s+def|def)\s+\w+\s*\(.*\)\s*:\s*$", lines[j]):
        def_idx = j
        break
if def_idx is None:
    raise SystemExit("Found startup decorator but couldn't find the function definition right after it.")

if any("Startup failed (continuing anyway)" in l for l in lines[def_idx:def_idx+80]):
    print("Startup handler already wrapped; no changes needed.")
    path.write_text("".join(lines), encoding="utf-8")
    raise SystemExit(0)

def_indent = re.match(r"^(\s*)", lines[def_idx]).group(1)
body_indent = def_indent + "    "

body_start = def_idx + 1
while body_start < len(lines) and lines[body_start].strip() == "":
    body_start += 1

body_end = body_start
while body_end < len(lines):
    l = lines[body_end]
    if (re.match(r"^\s*@", l) or re.match(r"^\s*(async\s+def|def)\s+", l)) and len(re.match(r"^(\s*)", l).group(1)) <= len(def_indent):
        break
    body_end += 1

lines.insert(body_start, body_indent + "try:\n")
body_end += 1

for k in range(body_start+1, body_end):
    if lines[k].strip() == "":
        continue
    # add one indent level inside try
    lines[k] = body_indent + "    " + lines[k]

except_block = (
    f"{body_indent}except Exception as e:\n"
    f"{body_indent}    logger.exception(\"Startup failed (continuing anyway): %s\", e)\n"
)
lines.insert(body_end, except_block)

path.write_text("".join(lines), encoding="utf-8")
print("Patched main.py (backup saved as main.py.bak)")
