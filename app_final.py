import io
import os
import re
import json
import fitz  # PyMuPDF
import streamlit as st
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# ================= CONFIG =================
st.set_page_config(page_title="USCIS Form Reader & Mapper", layout="wide")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)  # Future AI integration

DEFAULT_PATTERNS = [
    {"match": ["Family Name", "Given Name", "Middle Name"], "subs": ["a", "b", "c"]},
    {"match": ["Street Number and Name", "Apt. Ste. Flr.", "City or Town", "State", "ZIP Code"], "subs": ["a", "b", "c", "d", "e"]},
    {"match": ["Date of Birth", "City/Town of Birth", "Country of Birth"], "subs": ["a", "b", "c"]},
    {"match": ["Daytime Telephone", "Mobile Telephone", "Email Address"], "subs": ["a", "b", "c"]},
]

# ================= HELPERS =================
PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.IGNORECASE)
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:\.)?([a-z]?)\.\s*(.*)$')
FIELD_INLINE_RX = re.compile(r'(\b\d+\.[a-z]\.)')

def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()

def _decode_best(b: bytes) -> str:
    for enc in ("utf-8", "utf-16", "utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")

def try_load_json_bytes(b: bytes) -> Tuple[dict, str]:
    """Return (obj, err). If err == '', obj is valid json."""
    for enc in ("utf-8", "utf-16", "utf-8-sig", "latin-1"):
        try:
            return json.loads(b.decode(enc)), ""
        except Exception as e:
            last = str(e)
    return {}, last

def flatten_keys(obj, prefix="") -> List[str]:
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            newp = f"{prefix}.{k}" if prefix else k
            keys.extend(flatten_keys(v, newp))
    elif isinstance(obj, list):
        keys.append(f"{prefix}[*]")
        for i, v in enumerate(obj[:1]):
            keys.extend(flatten_keys(v, f"{prefix}[{i}]"))
    else:
        if prefix:
            keys.append(prefix)
    return keys

LINE_PATH_RX = re.compile(r'[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*(?:\[\*\])?')

def extract_field_names_from_text_lines(text: str) -> List[str]:
    """
    Fallback for .txt that aren't JSON: treat each non-empty line as a candidate,
    and also extract dotted/array-ish paths within the line.
    """
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # whole line as key if it looks like a path or label
        if len(line) <= 200:
            out.append(line)
        # extract embedded paths like a.b.c or a[*]
        for m in LINE_PATH_RX.finditer(line):
            out.append(m.group(0))
    # de-dup but keep order
    seen = set(); res=[]
    for k in out:
        if k and k not in seen:
            seen.add(k); res.append(k)
    return res

TS_INTERFACE_RX = re.compile(r'export\s+interface\s+\w+\s*{([^}]*)}', re.DOTALL)
TS_TYPE_OBJ_RX = re.compile(r'export\s+type\s+\w+\s*=\s*{([^}]*)}', re.DOTALL)
TS_CONST_OBJ_RX = re.compile(r'export\s+const\s+\w+\s*=\s*{(.*?)}\s*(?:as\s+const)?', re.DOTALL)
TS_FIELD_KEY_RX = re.compile(r'(\w+)\??\s*:')

def extract_field_names_from_ts(text: str) -> List[str]:
    names = []
    for body in (m.group(1) for m in TS_INTERFACE_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_TYPE_OBJ_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    # crude parse of exported const object keys
    for body in (m.group(1) for m in TS_CONST_OBJ_RX.finditer(text)):
        names += [k for k in re.findall(r'["\']?([A-Za-z_]\w+)["\']?\s*:', body)]
    # de-dup
    seen=set(); out=[]
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

def extract_field_names(file) -> List[str]:
    raw = file.getbuffer()
    name = file.name.lower()
    if name.endswith((".json", ".txt")):
        obj, err = try_load_json_bytes(raw)
        if obj:
            return [k for k in flatten_keys(obj) if k]
        # fallback line-based if not JSON
        text = _decode_best(raw)
        return extract_field_names_from_text_lines(text)
    elif name.endswith((".ts", ".tsx")):
        text = _decode_best(raw)
        return extract_field_names_from_ts(text)
    return []

# ================= PDF PARSING =================
def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    parts = defaultdict(list)
    current_part_key = None
    last_field_key = None
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    def start_field(part_key, fid, label, page_no):
        nonlocal last_field_key
        item = {"id": fid, "label": normalize(label), "page": page_no}
        parts[part_key].append(item)
        last_field_key = (part_key, fid)

    for pno in range(len(doc)):
        lines = [l for l in doc[pno].get_text("text").splitlines()]
        for raw in lines:
            line = raw.strip()
            if not line:
                last_field_key = None
                continue
            m_part = PART_RX.match(line)
            if m_part:
                idx, title = m_part.group(1), m_part.group(2).strip()
                current_part_key = f"Part {idx}: {title}"
                if current_part_key not in parts:
                    parts[current_part_key] = []
                last_field_key = None
                continue
            m_field = FIELD_HEAD_RX.match(line)
            if m_field and current_part_key:
                num, sub, rest = m_field.group(1), m_field.group(2), normalize(m_field.group(3) or "")
                fid = f"{num}.{sub}" if sub else num
                start_field(current_part_key, fid, rest, pno + 1)
                continue
            if current_part_key:
                inlines = list(FIELD_INLINE_RX.finditer(line))
                if inlines:
                    for m in inlines:
                        fid = m.group(0).strip(".")
                        start_field(current_part_key, fid, normalize(line[m.end():]), pno + 1)
                    continue
            if last_field_key:
                pk, fid = last_field_key
                prev = parts[pk][-1]
                if prev["id"] == fid:
                    prev["label"] = normalize((prev.get("label") or "") + " " + line)

    # Deduplicate & order
    for pk, items in parts.items():
        best = {}
        for it in items:
            if it["id"] not in best:
                best[it["id"]] = it
            else:
                cur = best[it["id"]]
                if it["page"] < cur["page"]:
                    cur["page"] = it["page"]
                if len(it.get("label","")) > len(cur.get("label","")):
                    cur["label"] = it["label"]
        parts[pk] = [best[k] for k in sorted(best.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x))]
    return parts

def merge_parts(maps: List[Dict[str, List[Dict[str, Any]]]]) -> Dict[str, List[Dict[str, Any]]]:
    out = defaultdict(list)
    for mp in maps:
        for k, v in mp.items():
            out[k].extend(v)
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

# ================= AUTO-SPLIT =================
def auto_split_fields(merged_parts, patterns):
    new_parts = defaultdict(list)
    for part, fields in merged_parts.items():
        for field in fields:
            matched = False
            for pat in patterns:
                if all(term in field["label"] for term in pat["match"]):
                    for sub, term in zip(pat["subs"], pat["match"]):
                        new_parts[part].append({
                            "id": f"{field['id']}.{sub}",
                            "label": term,
                            "page": field["page"]
                        })
                    matched = True
                    break
            if not matched:
                new_parts[part].append(field)
    return new_parts

# ================= UI =================
st.sidebar.header("Upload Inputs")
pdf_files = st.sidebar.file_uploader("USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Extra DB Objects/Schemas", type=["json","ts","tsx","txt"], accept_multiple_files=True)
patterns_file = st.sidebar.file_uploader("Auto-split Patterns JSON (optional)", type=["json"])
show_split_preview = st.sidebar.checkbox("Show Auto-split Preview", value=True)

# Load patterns
patterns = DEFAULT_PATTERNS
if patterns_file:
    try:
        patterns = json.loads(patterns_file.getbuffer().decode("utf-8"))
    except:
        st.sidebar.error("Invalid patterns.json format. Using defaults.")

# Parse PDFs
merged = {}
if pdf_files:
    part_maps = [parse_pdf_parts_and_fields(up.getbuffer()) for up in pdf_files]
    merged = merge_parts(part_maps)
    merged = auto_split_fields(merged, patterns)

# DB Targets: auto-load + uploads, with debug
scan_dir = "/mnt/data" if os.path.exists("/mnt/data") else os.getcwd()
loaded_db_sources = []
all_fields = []

def _add_upload_like(path: str):
    with open(path, "rb") as f:
        fake_upload = type("UploadedFile", (), {
            "name": os.path.basename(path),
            "getbuffer": lambda f=f: f.read()
        })
        fields = extract_field_names(fake_upload)
        if fields:
            all_fields.extend(fields)
            loaded_db_sources.append((os.path.basename(path), len(fields)))

# auto-scan
try:
    for fname in os.listdir(scan_dir):
        if fname.lower().endswith((".json", ".txt", ".ts", ".tsx")):
            _add_upload_like(os.path.join(scan_dir, fname))
except Exception as e:
    st.warning(f"Could not scan {scan_dir}: {e}")

# user uploads extend the list
if schema_files:
    for sf in schema_files:
        fields = extract_field_names(sf)
        if fields:
            all_fields.extend(fields)
            loaded_db_sources.append((sf.name, len(fields)))

db_targets = ["— (unmapped) —"] + sorted(set(all_fields))

# State
if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}

# Tabs
tab_map, tab_dbdebug, tab_export = st.tabs(["📄 Parts & Mapping", "🧭 DB/Schema Debug", "⬇️ Exports"])

with tab_dbdebug:
    st.write(f"Scanning directory: `{scan_dir}`")
    if not loaded_db_sources:
        st.warning("No DB objects discovered. Drop JSON/TXT/TS files into the scan folder or upload in the sidebar.")
    else:
        for name, cnt in loaded_db_sources:
            st.write(f"- **{name}** → {cnt} fields")
    if db_targets and len(db_targets) > 1:
        st.success(f"Total unique DB fields loaded: {len(db_targets)-1}")
        st.caption("Example fields:")
        st.code("\n".join(list(sorted(set(all_fields)))[:50]))

with tab_map:
    st.title("Universal USCIS Form Reader & Mapper")
    if not merged:
        st.info("Upload at least one USCIS PDF to start.")
        st.stop()

    for part_name in sorted(merged.keys(), key=lambda x: int(re.search(r'\d+', x).group())):
        with st.expander(part_name, expanded=False):
            if part_name not in st.session_state["mappings"]:
                st.session_state["mappings"][part_name] = {}
            for row in merged[part_name]:
                fid, label, page = row["id"], row.get("label",""), row.get("page")
                c1, c2, c3, c4, c5 = st.columns([1,4,3,3,1])
                with c1:
                    st.write(f"**{fid}**")
                    if page: st.caption(f"p.{page}")
                with c2:
                    st.write(label or "—")
                with c3:
                    choice = st.selectbox("Map DB", db_targets, index=0, key=f"db_{part_name}_{fid}")
                with c4:
                    manual = st.text_input("Manual DB Path", key=f"man_{part_name}_{fid}")
                with c5:
                    send_q = st.checkbox("Q?", key=f"q_{part_name}_{fid}")
                st.session_state["mappings"][part_name][fid] = {
                    "db": manual or (choice if choice != "— (unmapped) —" else None),
                    "questionnaire": send_q,
                    "label": label
                }

with tab_export:
    st.header("Exports")
    all_ids = [f"{p.replace(' ', '_')}_{fid}" for p, fields in st.session_state["mappings"].items() for fid in fields]
    ts_code = "export interface USCISForm {\n" + "\n".join([f"  {re.sub(r'[^a-zA-Z0-9_]','_',fid)}?: string;" for fid in all_ids]) + "\n}"
    unmapped = []
    for p, items in st.session_state["mappings"].items():
        for fid, mapping in items.items():
            if not mapping["db"] or mapping["questionnaire"]:
                unmapped.append({
                    "part": p, "id": fid,
                    "label": mapping.get("label",""),
                    "question_key": f"{p.split(':')[0]}_{fid}".replace(".",""),
                })
    qjson = json.dumps({"questions": unmapped}, indent=2)
    fullmap = json.dumps(st.session_state["mappings"], indent=2)

    st.download_button("Download TS Interface", data=ts_code.encode("utf-8"), file_name="uscis_fields.ts", mime="text/plain")
    st.download_button("Download Questionnaire (Unmapped/Flagged)", data=qjson.encode("utf-8"), file_name="questionnaire.json", mime="application/json")
    st.download_button("Download Full Field Mappings", data=fullmap.encode("utf-8"), file_name="field_mappings.json", mime="application/json")
