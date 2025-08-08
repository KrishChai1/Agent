
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
# Helpers
# -------------------------

PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.IGNORECASE)
# Matches: "1.", "1.a.", "12.b.", "4.c", "11.b (Yes/No)" etc.
FIELD_RX = re.compile(r'^\s*(\d+)(?:\.(?:([a-z])|([a-z])\))?)?\.\s*(.*)$')
# Looser line-level item like "1.a" ending with label elsewhere
FIELD_INLINE_RX = re.compile(r'(\b\d+\.[a-z]\.)')

def normalize_spaces(s: str) -> str:
    return re.sub(r'\s+', ' ', s).strip()

def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return structure: { "Part N: Title": [{"id":"1.a", "label":"..." , "page": 1}, ...], ...}
    """
    parts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    current_part_key = None
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for pno in range(len(doc)):
        page = doc[pno]
        # We use text blocks preserving reading order
        text = page.get_text("text")
        lines = [l for l in text.splitlines() if l.strip()]
        for line in lines:
            line_norm = normalize_spaces(line)
            # Detect "Part N. Title"
            m_part = PART_RX.match(line_norm)
            if m_part:
                idx = m_part.group(1)
                title = m_part.group(2).strip()
                current_part_key = f"Part {idx}: {title or ''}".strip()
                if current_part_key not in parts:
                    parts[current_part_key] = []
                continue

            # Detect field lines "1.", "1.a.", "12.b."
            m_field = FIELD_RX.match(line_norm)
            if m_field and current_part_key:
                num = m_field.group(1)
                sub = m_field.group(2) or m_field.group(3)
                tail = m_field.group(4).strip()
                fid = f"{num}.{sub}" if sub else f"{num}"
                parts[current_part_key].append({
                    "id": fid,
                    "label": tail,
                    "page": pno + 1,
                })
                continue

            # Detect scattered "1.a." inline occurrences and split out following text as label hint
            if current_part_key:
                for m in FIELD_INLINE_RX.finditer(line_norm):
                    fid = m.group(0).strip(".")
                    # Take substring after the match as a hint
                    post = line_norm[m.end():].strip(" :-")
                    parts[current_part_key].append({
                        "id": fid,
                        "label": post,
                        "page": pno + 1,
                    })
    # Deduplicate keeping first occurrence (earliest page)
    for pk, items in parts.items():
        seen = set()
        dedup = []
        for it in items:
            if it["id"] in seen:
                # Prefer earlier one with non-empty label
                continue
            seen.add(it["id"])
            dedup.append(it)
        parts[pk] = dedup
    return parts

def merge_parts(part_maps: List[Dict[str, List[Dict[str, Any]]]]) -> Dict[str, List[Dict[str, Any]]]:
    out = defaultdict(list)
    for pm in part_maps:
        for k, v in pm.items():
            out[k].extend(v)
    # Basic coalesce by id inside each part
    for k, v in out.items():
        byid = {}
        for it in v:
            if it["id"] not in byid:
                byid[it["id"]] = it
            else:
                if not byid[it["id"]].get("label") and it.get("label"):
                    byid[it["id"]]["label"] = it["label"]
                byid[it["id"]]["page"] = min(byid[it["id"]]["page"], it["page"])
        out[k] = sorted(byid.values(), key=lambda x: (int(re.match(r'\d+', x["id"]).group()), x["id"]))
    return out

def load_json_controls(file_bytes: bytes) -> Dict[str, Any]:
    try:
        data = json.loads(file_bytes.decode("utf-8"))
        return data
    except Exception:
        st.warning("Could not parse JSON schema file.")
        return {}

def extract_control_names(data: Dict[str, Any]) -> List[str]:
    names = []
    controls = data.get("controls", [])
    for c in controls:
        if isinstance(c, dict) and "name" in c and c.get("name"):
            names.append(c["name"])
    return names

def to_ts_interface(name: str, fields: List[str]) -> str:
    lines = [f"export interface {name} {{"]
    for f in fields:
        safe = re.sub(r'[^a-zA-Z0-9_]', '_', f)
        lines.append(f"  {safe}?: string;")
    lines.append("}")
    return "\n".join(lines)

def download_bytes(filename: str, data: bytes, label: str):
    st.download_button(label=label, file_name=filename, mime="application/octet-stream", data=data)

# -------------------------
# Sidebar: Inputs
# -------------------------

st.sidebar.title("Inputs")

pdf_files = st.sidebar.file_uploader("Upload USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Upload DB/Questionnaire JSON schemas (optional)", type=["json"], accept_multiple_files=True)

demo = st.sidebar.checkbox("Load demo files from /mnt/data (if available)", value=False)

if demo:
    demo_paths = [
        "/mnt/data/G28_test.pdf",
        "/mnt/data/I-129_test.pdf",
    ]
    for path in demo_paths:
        if os.path.exists(path):
            with open(path, "rb") as f:
                pdf_files.append(type("UploadedFile", (), {"name": os.path.basename(path), "getbuffer": lambda f=f: f.read()}))

schema_pool: Dict[str, Dict[str, Any]] = {}
schema_field_pool: Dict[str, List[str]] = {}

if schema_files:
    for sf in schema_files:
        data = load_json_controls(sf.getbuffer())
        if data:
            schema_pool[sf.name] = data
            schema_field_pool[sf.name] = extract_control_names(data)

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
else:
    merged = {}

# -------------------------
# Session state for mappings
# -------------------------

if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}  # { "Part 1: Title": { "1.a": {"db": "file.json:fieldName", "question_key": "..."}, ... } }

# -------------------------
# UI Layout
# -------------------------

st.title("USCIS Form Parser → Part-by-Part Field Mapper")

col1, col2 = st.columns([2,1])
with col1:
    st.markdown("Upload any **USCIS PDF** above. I'll show **Part-by-Part** with items like `1.a / 1.b / 1.c`, even if they span multiple pages.")

with col2:
    st.markdown("### Shortcuts")
    st.button("Clear mappings", on_click=lambda: st.session_state.update({"mappings":{}}))

if not merged:
    st.info("Upload at least one PDF to begin.")
    st.stop()

# Build flat list of DB fields across schemas
db_targets = [f"{fname}:{fld}" for fname, fields in schema_field_pool.items() for fld in fields]
db_targets = ["— (unmapped) —"] + sorted(db_targets)

# -------------------------
# Display Parts & Fields
# -------------------------

tab_parts, tab_exports = st.tabs(["📄 Parts & Field Mapping", "⬇️ Exports"])

with tab_parts:
    for part_name in sorted(merged.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
        with st.expander(part_name, expanded=False):
            # Ensure dict exists
            if part_name not in st.session_state["mappings"]:
                st.session_state["mappings"][part_name] = {}

            rows = merged[part_name]
            for row in rows:
                fid = row["id"]
                label = row.get("label", "")
                page = row.get("page", None)

                c1, c2, c3, c4 = st.columns([1,4,3,3])
                with c1:
                    st.write(f"**{fid}**")
                    if page:
                        st.caption(f"p.{page}")
                with c2:
                    st.write(label or "—")
                with c3:
                    # DB mapping dropdown
                    default_value = st.session_state["mappings"][part_name].get(fid, {}).get("db", "— (unmapped) —")
                    choice = st.selectbox(f"Map DB ({part_name} {fid})", options=db_targets, index=db_targets.index(default_value) if default_value in db_targets else 0, key=f"db_{part_name}_{fid}")
                with c4:
                    # Questionnaire key free text
                    default_q = st.session_state["mappings"][part_name].get(fid, {}).get("question_key", "")
                    qkey = st.text_input("Question key", value=default_q, key=f"q_{part_name}_{fid}")

                # Persist to session state
                st.session_state["mappings"][part_name][fid] = {"db": choice if choice != "— (unmapped) —" else None, "question_key": qkey or None, "label": label}

with tab_exports:
    st.subheader("TypeScript (TS) Definitions")
    ts_iface_name = st.text_input("Interface name", value="UscisFormFields")
    # Collect all field ids as TS keys
    all_ids = []
    for p, items in merged.items():
        for it in items:
            all_ids.append(f"{p.replace(' ', '_')}_{it['id']}")
    ts_code = to_ts_interface(ts_iface_name, all_ids)
    st.code(ts_code, language="typescript")

    st.subheader("Questionnaire JSON for Unmapped Fields")
    # Compute unmapped
    unmapped = []
    for p, items in merged.items():
        for it in items:
            mp = st.session_state["mappings"].get(p, {}).get(it["id"], {})
            if not mp.get("db"):
                # Build a reasonable question
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

    # Downloads
    download_bytes("uscis_fields.ts", ts_code.encode("utf-8"), "Download TS Interface")
    download_bytes("questionnaire_unmapped.json", qjson.encode("utf-8"), "Download Questionnaire (Unmapped)")
    # Full mapping
    fullmap = json.dumps(st.session_state["mappings"], indent=2)
    download_bytes("field_mappings.json", fullmap.encode("utf-8"), "Download Full Field Mappings")
