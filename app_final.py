
import io
import os
import re
import json
import fitz  # PyMuPDF
import streamlit as st
from collections import defaultdict
from typing import Dict, List, Tuple, Any

st.set_page_config(page_title="USCIS Form Parser & Mapper", layout="wide")

# -------------------------
# Regexes
# -------------------------

PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.IGNORECASE)
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:\.)?((?:[a-z])?)\.\s*(.*)$')  # 1.  or 1.a.
FIELD_INLINE_RX = re.compile(r'(\b\d+\.[a-z]\.)')

def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()

# -------------------------
# PDF Parsing with label carry-over
# -------------------------
def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse parts and fields; carry label text forward across wrapped lines until the next field/part.
    Returns: { "Part N: Title": [ {id, label, page}, ... ] }
    """
    parts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    current_part_key = None
    last_field_key = None  # (part, id) for label continuation
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    def start_field(part_key: str, fid: str, label: str, page_no: int):
        nonlocal last_field_key
        label = normalize(label)
        item = {"id": fid, "label": label, "page": page_no}
        parts[part_key].append(item)
        last_field_key = (part_key, fid)

    for pno in range(len(doc)):
        page = doc[pno]
        lines = [l for l in page.get_text("text").splitlines()]
        for raw in lines:
            line = raw.strip()
            if not line:
                # Blank line ends continuation
                last_field_key = None
                continue

            # New Part header
            m_part = PART_RX.match(line)
            if m_part:
                idx, title = m_part.group(1), m_part.group(2).strip()
                current_part_key = f"Part {idx}: {title}"
                if current_part_key not in parts:
                    parts[current_part_key] = []
                last_field_key = None
                continue

            # New field head "1." or "1.a."
            m_field = FIELD_HEAD_RX.match(line)
            if m_field and current_part_key:
                num = m_field.group(1)
                sub = m_field.group(2)
                rest = normalize(m_field.group(3) or "")
                fid = f"{num}.{sub}" if sub else num
                start_field(current_part_key, fid, rest, pno + 1)
                continue

            # Inline "1.a." found mid-line
            if current_part_key:
                inlines = list(FIELD_INLINE_RX.finditer(line))
                if inlines:
                    # Push each inline as a field with trailing text as label
                    for m in inlines:
                        fid = m.group(0).strip(".")
                        label_hint = normalize(line[m.end():])
                        start_field(current_part_key, fid, label_hint, pno + 1)
                    continue

            # Continuation of the previous field's label
            if last_field_key:
                pk, fid = last_field_key
                if parts.get(pk):
                    # Append with space
                    prev = parts[pk][-1]
                    if prev["id"] == fid:
                        extended = normalize((prev.get("label") or "") + " " + line)
                        prev["label"] = extended
                continue

    # Deduplicate by id within each part keeping earliest page and longest label
    for pk, items in parts.items():
        best = {}
        for it in items:
            if it["id"] not in best:
                best[it["id"]] = it
            else:
                cur = best[it["id"]]
                # Prefer earliest page
                if it["page"] < cur["page"]:
                    cur["page"] = it["page"]
                # Prefer longer, non-empty label
                if len(it.get("label","")) > len(cur.get("label","")):
                    cur["label"] = it["label"]
        parts[pk] = [best[k] for k in sorted(best.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x))]
    return parts

def merge_parts(maps: List[Dict[str, List[Dict[str, Any]]]]) -> Dict[str, List[Dict[str, Any]]]:
    out = defaultdict(list)
    for mp in maps:
        for k, v in mp.items():
            out[k].extend(v)
    # Re-coalesce
    for k, v in out.items():
        byid = {}
        for it in v:
            if it["id"] not in byid:
                byid[it["id"]] = it
            else:
                if it["page"] < byid[it["id"]]["page"]:
                    byid[it["id"]]["page"] = it["page"]
                if len(it.get("label","")) > len(byid[it["id"]].get("label","")):
                    byid[it["id"]]["label"] = it["label"]
        out[k] = [byid[i] for i in sorted(byid.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x))]
    return out

# -------------------------
# Schema ingestion (JSON/TS)
# -------------------------

def load_json_schema(file_bytes: bytes) -> Dict[str, Any]:
    try:
        return json.loads(file_bytes.decode("utf-8"))
    except Exception:
        return {}

def extract_field_names_from_json(data: Dict[str, Any]) -> List[str]:
    names = []
    # 1) controls[*].name
    ctrls = data.get("controls")
    if isinstance(ctrls, list):
        for c in ctrls:
            if isinstance(c, dict) and c.get("name"):
                names.append(str(c["name"]))
    # 2) fields[*].{name|id|key|label}
    for k in ["fields", "questions", "sections"]:
        val = data.get(k)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    for cand in ["name", "id", "key", "label"]:
                        if item.get(cand):
                            names.append(str(item[cand]))
                            break
    # 3) properties keys (JSON Schema)
    if isinstance(data.get("properties"), dict):
        names.extend(list(data["properties"].keys()))
    # Dedup preserve order
    seen = set()
    out = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out

def extract_field_names_from_ts(ts_text: str) -> List[str]:
    # Look for export interface ... { ... } and type literals
    names = []
    for m in re.finditer(r'export\s+interface\s+\w+\s*{([^}]*)}', ts_text, re.DOTALL):
        body = m.group(1)
        names += re.findall(r'(\w+)\??\s*:', body)
    # Also parse exported type with object literal
    for m in re.finditer(r'export\s+type\s+\w+\s*=\s*{([^}]*)}', ts_text, re.DOTALL):
        body = m.group(1)
        names += re.findall(r'(\w+)\??\s*:', body)
    # Dedup
    seen=set(); out=[]
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

def download_bytes(filename: str, data: bytes, label: str):
    st.download_button(label=label, file_name=filename, mime="application/octet-stream", data=data)

# -------------------------
# Sidebar inputs
# -------------------------

st.sidebar.title("Inputs")
pdf_files = st.sidebar.file_uploader("Upload USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Upload schema files (JSON or TS)", type=["json","ts","tsx"], accept_multiple_files=True)

load_demo_pdfs = st.sidebar.checkbox("Load demo PDFs from /mnt/data", value=False)
auto_scan_schemas = st.sidebar.checkbox("Auto-scan /mnt/data for *.json/*.ts", value=True)

if load_demo_pdfs:
    for path in ["/mnt/data/G28_test.pdf", "/mnt/data/I-129_test.pdf"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                pdf_files.append(type("UploadedFile", (), {"name": os.path.basename(path), "getbuffer": lambda f=f: f.read()}))

# Auto-load schemas if none uploaded
if (not schema_files) and auto_scan_schemas:
    found = []
    for path in ["/mnt/data/g28.json", "/mnt/data/i90-form.json", "/mnt/data/i129-sec1.2.form.json", "/mnt/data/G28.ts"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                found.append(type("UploadedFile", (), {"name": os.path.basename(path), "getbuffer": lambda f=f: f.read()}))
    schema_files = found

# -------------------------
# Parse PDFs
# -------------------------

part_maps = []
if pdf_files:
    for up in pdf_files:
        try:
            parts = parse_pdf_parts_and_fields(up.getbuffer())
            part_maps.append(parts)
        except Exception as e:
            st.error(f"Error parsing {up.name}: {e}")

merged = merge_parts(part_maps) if part_maps else {}

# -------------------------
# Load schemas and extract field names
# -------------------------

schema_field_pool = {}  # filename -> [field names]
if schema_files:
    for sf in schema_files:
        raw = sf.getbuffer()
        if sf.name.lower().endswith((".json",)):
            data = load_json_schema(raw)
            names = extract_field_names_from_json(data)
        else:
            try:
                text = raw.decode("utf-8", errors="ignore")
            except Exception:
                text = ""
            names = extract_field_names_from_ts(text)
        if names:
            schema_field_pool[sf.name] = names

# Flatten into dropdown
db_targets = ["— (unmapped) —"]
for fname, fields in sorted(schema_field_pool.items()):
    for fld in fields:
        db_targets.append(f"{fname}:{fld}")

# -------------------------
# UI
# -------------------------

st.title("USCIS Form Parser → Part-by-Part Field Mapper")

col1, col2 = st.columns([2,1])
with col1:
    st.markdown("**Parsed attributes** now include carried-over labels across lines/pages. Expand a Part to see each item’s full label.")
with col2:
    if not schema_field_pool:
        st.warning("No schema fields detected. Upload JSON/TS schema files or enable auto-scan.")
    else:
        st.success(f"Loaded {sum(len(v) for v in schema_field_pool.values())} DB fields from {len(schema_field_pool)} schema file(s).")

if not merged:
    st.info("Upload at least one PDF to begin.")
    st.stop()

tab_parts, tab_schemas, tab_exports = st.tabs(["📄 Parts & Mapping", "📚 Schema Preview", "⬇️ Exports"])

with tab_schemas:
    if schema_field_pool:
        for fname, fields in schema_field_pool.items():
            with st.expander(f"{fname}  ·  {len(fields)} fields", expanded=False):
                st.write(", ".join(fields[:200]) + (", ..." if len(fields) > 200 else ""))
    else:
        st.caption("No schemas loaded.")

with tab_parts:
    if not db_targets or len(db_targets) == 1:
        st.info("DB dropdown will show targets after you load schema files (JSON with controls[*].name, fields[*], or JSON Schema; or TS interfaces).")

    if "mappings" not in st.session_state:
        st.session_state["mappings"] = {}

    for part_name in sorted(merged.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
        with st.expander(part_name, expanded=False):
            st.caption("Attribute names are derived from the PDF item labels; edit your questionnaire keys to fit your model.")
            if part_name not in st.session_state["mappings"]:
                st.session_state["mappings"][part_name] = {}

            for row in merged[part_name]:
                fid = row["id"]
                label = row.get("label") or ""
                page = row.get("page")
                # Render row
                c1, c2, c3, c4 = st.columns([1,5,3,3])
                with c1:
                    st.write(f"**{fid}**")
                    if page: st.caption(f"p.{page}")
                with c2:
                    st.write(label if label else "—")
                with c3:
                    default_db = st.session_state["mappings"][part_name].get(fid, {}).get("db", "— (unmapped) —")
                    idx = db_targets.index(default_db) if default_db in db_targets else 0
                    choice = st.selectbox(f"DB map ({fid})", options=db_targets, index=idx, key=f"db_{part_name}_{fid}")
                with c4:
                    default_q = st.session_state["mappings"][part_name].get(fid, {}).get("question_key", "")
                    qkey = st.text_input("Question key", value=default_q, key=f"q_{part_name}_{fid}")
                st.session_state["mappings"][part_name][fid] = {"db": choice if choice != "— (unmapped) —" else None, "question_key": qkey or None, "label": label}

with tab_exports:
    def ts_interface(name: str, fields: List[str]) -> str:
        lines = [f"export interface {name} {{"]
        for f in fields:
            safe = re.sub(r'[^a-zA-Z0-9_]', '_', f)
            lines.append(f"  {safe}?: string;")
        lines.append("}")
        return "\\n".join(lines)

    st.subheader("TypeScript (TS) Definitions")
    ts_iface_name = st.text_input("Interface name", value="UscisFormFields")
    all_ids = [f"{p.replace(' ', '_')}_{it['id']}" for p, items in merged.items() for it in items]
    ts_code = ts_interface(ts_iface_name, all_ids)
    st.code(ts_code, language="typescript")

    st.subheader("Questionnaire JSON for Unmapped Fields")
    unmapped = []
    for p, items in merged.items():
        for it in items:
            mp = st.session_state["mappings"].get(p, {}).get(it["id"], {})
            if not mp.get("db"):
                qkey = mp.get("question_key") or f"{p.split(':')[0].replace(' ', '').lower()}_{it['id'].replace('.', '')}"
                unmapped.append({
                    "part": p,
                    "id": it["id"],
                    "question_key": qkey,
                    "label": it.get("label") or f"Please provide value for {it['id']}",
                    "page": it.get("page")
                })
    st.write(f"Unmapped count: **{len(unmapped)}**")
    qjson = json.dumps({"questions": unmapped}, indent=2)
    st.code(qjson, language="json")

    st.download_button("Download TS Interface", "uscis_fields.ts", ts_code.encode("utf-8"))
    st.download_button("Download Questionnaire (Unmapped)", "questionnaire_unmapped.json", qjson.encode("utf-8"))
    fullmap = json.dumps(st.session_state["mappings"], indent=2)
    st.download_button("Download Full Field Mappings", "field_mappings.json", fullmap.encode("utf-8"))
