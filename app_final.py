import os, re, json, io, zipfile
from collections import defaultdict
from typing import Dict, List, Any, Tuple

import fitz  # PyMuPDF
import streamlit as st

# ==================== APP CONFIG ====================
st.set_page_config(page_title="Universal USCIS Form Mapper", layout="wide")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)

# Force-include known DB/schema files if present
FORCE_INCLUDE_FILES = [
    "Attorney object.txt", "Beneficiary.txt", "Case Object.txt", "Customer object.txt",
    "Lawfirm Object.txt", "LCA Object.txt", "Petitioner.txt",
    "g28.json", "h-2b-form.json", "G28.ts", "H2B.ts"
]

# Extensions and ignore patterns
ALLOWED_EXTS = (".json", ".txt", ".ts", ".tsx")
IGNORE_FILE_RX = re.compile(
    r'^(requirements(\.txt)?|pyproject\.toml|poetry\.lock|package(-lock)?\.json|yarn\.lock|Pipfile(\.lock)?)$',
    re.I
)

# ==================== TEXT/TS HELPERS ====================
def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def to_bytes(buf) -> bytes:
    if isinstance(buf, (bytes, bytearray)):
        return bytes(buf)
    try:
        return bytes(buf)
    except Exception:
        return str(buf).encode("utf-8", errors="ignore")

def _decode_best(b: bytes) -> str:
    b = to_bytes(b)
    for enc in ("utf-8", "utf-16", "utf-8-sig", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("utf-8", errors="ignore")

def try_load_json_bytes(b: bytes) -> Tuple[dict, str]:
    b = to_bytes(b)
    last = ""
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

LINE_PATH_RX = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?:\[\*\])?')
KEY_COLON_RX = re.compile(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*:')

def extract_field_names_from_text_lines(text: str) -> List[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) <= 200:
            # whole line might be a usable key in your TXT objects
            out.append(line)
        for m in LINE_PATH_RX.finditer(line):
            out.append(m.group(0))
        for m in KEY_COLON_RX.finditer(line):
            out.append(m.group(1))
    seen = set(); res=[]
    for k in out:
        if k and k not in seen:
            seen.add(k); res.append(k)
    return res

# TS parsing
TS_INTERFACE_RX = re.compile(r'export\s+interface\s+\w+\s*{([^}]*)}', re.DOTALL)
TS_TYPE_OBJ_RX = re.compile(r'export\s+type\s+\w+\s*=\s*{([^}]*)}', re.DOTALL)
TS_CONST_OBJ_RX = re.compile(r'export\s+const\s+\w+\s*=\s*{(.*?)}\s*(?:as\s+const)?', re.DOTALL)
TS_FIELD_KEY_RX = re.compile(r'["\']?([A-Za-z_]\w+)["\']?\s*:')

def extract_field_names_from_ts(text: str) -> List[str]:
    names = []
    for body in (m.group(1) for m in TS_INTERFACE_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_TYPE_OBJ_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_CONST_OBJ_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    seen=set(); out=[]
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

def extract_field_names_from_uploadlike(name: str, raw: bytes) -> List[str]:
    lname = name.lower()
    raw = to_bytes(raw)
    if lname.endswith((".json", ".txt")):
        obj, _ = try_load_json_bytes(raw)
        if obj:
            return [k for k in flatten_keys(obj) if k]
        text = _decode_best(raw)
        return extract_field_names_from_text_lines(text)
    elif lname.endswith((".ts", ".tsx")):
        text = _decode_best(raw)
        return extract_field_names_from_ts(text)
    return []

# ==================== SAFE PDF OPEN ====================
def safe_open_pdf(raw: bytes):
    if not raw or not isinstance(raw, (bytes, bytearray)):
        raise RuntimeError("Empty or invalid PDF bytes")
    try:
        return fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {e}")

# ==================== PDF PARSING ======================
PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.I)
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:[\.\)]\s*([a-z])?)?\s*(.*)$', re.I)

def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse a USCIS PDF into parts/fields using blocks mode across ALL pages.
    - Keeps order (top->down, left->right)
    - Merges continuation lines
    - Splits Yes/No options under base number
    """
    parts = defaultdict(list)
    doc = safe_open_pdf(pdf_bytes)
    current_part = None
    last_fid = None

    for pno in range(len(doc)):
        blocks = doc[pno].get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1],1), round(b[0],1)))
        for b in blocks:
            line = (b[4] or "").strip()
            if not line:
                continue

            m_part = PART_RX.match(line)
            if m_part:
                idx, title = m_part.groups()
                current_part = f"Part {idx}: {normalize(title)}"
                last_fid = None
                continue

            if not current_part:
                continue

            m_field = FIELD_HEAD_RX.match(line)
            if m_field:
                num, sub, rest = m_field.groups()
                fid = f"{num}.{sub}" if sub else num
                label = normalize(rest) or line
                parts[current_part].append({"id": fid, "label": label, "page": pno+1})
                last_fid = fid
            else:
                # Split simple Yes/No options found on a lonely line
                # Attach as  a/b under last base number
                if last_fid and re.search(r'\b(Yes|No)\b', line):
                    base = last_fid.split(".")[0]
                    opts = re.findall(r'\b(Yes|No)\b', line)
                    for i, opt in enumerate(opts, start=1):
                        opt_id = f"{base}.{chr(96+i)}"  # 'a','b',...
                        parts[current_part].append({"id": opt_id, "label": opt, "page": pno+1})
                elif parts[current_part]:
                    parts[current_part][-1]["label"] = normalize(parts[current_part][-1]["label"] + " " + line)

    # Sort inside each part strictly by (number, suffix)
    for pk, rows in parts.items():
        def sort_key(r):
            m = re.match(r"(\d+)(?:\.([a-z]))?$", r["id"])
            if not m:
                # Could be .opt or other—they go last but stable
                return (99999, r["id"])
            num, sub = m.groups()
            return (int(num), sub or "")
        parts[pk] = sorted(rows, key=sort_key)

    return parts

def merge_parts(maps: List[Dict[str, List[Dict[str, Any]]]]) -> Dict[str, List[Dict[str, Any]]]:
    out = defaultdict(list)
    for mp in maps:
        for k, v in mp.items():
            out[k].extend(v)
    for k, v in out.items():
        byid = {}
        for it in v:
            fid = it["id"]
            if fid not in byid:
                byid[fid] = it
            else:
                if it.get("page") and (not byid[fid].get("page") or it["page"] < byid[fid]["page"]):
                    byid[fid]["page"] = it["page"]
                if len(it.get("label","")) > len(byid[fid].get("label","")):
                    byid[fid]["label"] = it["label"]
        # reorder
        def sort_key_id(fid):
            m = re.match(r"(\d+)(?:\.([a-z]))?$", fid)
            if not m: return (99999, fid)
            n, s = m.groups()
            return (int(n), s or "")
        out[k] = [byid[f] for f in sorted(byid.keys(), key=sort_key_id)]
    return out

# ==================== AUTO-SPLIT GROUPED =================
DEFAULT_PATTERNS = [
    {"match": ["Family Name", "Given Name", "Middle Name"], "subs": ["a","b","c"]},
    {"match": ["Street Number and Name", "Apt. Ste. Flr.", "City or Town", "State", "ZIP Code"], "subs": ["a","b","c","d","e"]},
    {"match": ["Date of Birth", "City/Town of Birth", "Country of Birth"], "subs": ["a","b","c"]},
    {"match": ["Daytime Telephone", "Mobile Telephone", "Email Address"], "subs": ["a","b","c"]}
]

def auto_split_fields(merged_parts, patterns=DEFAULT_PATTERNS):
    new_parts = defaultdict(list)
    for part, fields in merged_parts.items():
        for f in fields:
            matched = False
            for pat in patterns:
                if all(term in f["label"] for term in pat["match"]):
                    for sub, term in zip(pat["subs"], pat["match"]):
                        new_parts[part].append({"id": f"{f['id']}.{sub}", "label": term, "page": f["page"]})
                    matched = True
                    break
            if not matched:
                new_parts[part].append(f)
    return new_parts

# ==================== LLM ENHANCEMENT (optional) ========
def oai_chat(messages, model="gpt-4o-mini", temperature=0.0, max_tokens=2000):
    if not OPENAI_API_KEY: return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model=model, messages=messages,
                                              temperature=temperature, max_tokens=max_tokens)
        return resp.choices[0].message.content
    except Exception:
        return None

def llm_enhance_parts(pdf_bytes_list, merged_parts):
    if not OPENAI_API_KEY or not pdf_bytes_list:
        return merged_parts
    try:
        doc = safe_open_pdf(pdf_bytes_list[0])
        raw_text = "\n".join([doc[p].get_text("text") for p in range(len(doc))])[:20000]
    except Exception:
        return merged_parts
    system = "You are a USCIS form extractor. Return clean JSON only."
    user = f"""
Extract parts with fields:
{{
  "parts": [
    {{"name":"Part N: Title","fields":[{{"id":"1","label":"..."}}]}}
  ]
}}
TEXT:
{raw_text}
"""
    content = oai_chat([{"role":"system","content":system},{"role":"user","content":user}], max_tokens=4000)
    if not content: return merged_parts
    try:
        start = content.find("{"); end = content.rfind("}")
        data = json.loads(content[start:end+1])
        for part in data.get("parts", []):
            pname = part.get("name"); fields = part.get("fields", [])
            if not pname: continue
            exist_ids = set(r["id"] for r in merged_parts.get(pname, []))
            for f in fields:
                fid = f.get("id"); lbl = normalize(f.get("label",""))
                if not fid: continue
                if fid not in exist_ids:
                    merged_parts.setdefault(pname, []).append({"id": fid, "label": lbl, "page": None})
        # order
        for pname in merged_parts:
            merged_parts[pname] = sorted(
                merged_parts[pname],
                key=lambda r: (int(re.match(r"(\d+)", r["id"]).group()) if re.match(r"(\d+)", r["id"]) else 99999, r["id"])
            )
    except Exception:
        pass
    return merged_parts

# ==================== SIDEBAR / DB LOADING ==============
st.sidebar.header("Upload Inputs")
pdf_files = st.sidebar.file_uploader("USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Extra DB Objects/Schemas", type=["json","ts","tsx","txt"], accept_multiple_files=True)
zip_db = st.sidebar.file_uploader("Upload ZIP of DB objects (json/txt/ts inside)", type=["zip"])
st.sidebar.header("DB Catalog (Optional)")
manual_db_text = st.sidebar.text_area("Paste DB fields (one per line)", height=150, placeholder="Attorney.name.first\nBeneficiary.address.city\n...")

# Build DB targets from scan + force includes + uploaded + manual
scan_dir = "/mnt/data" if os.path.exists("/mnt/data") else os.getcwd()
all_fields: List[str] = []
loaded_db_sources = []

def add_source(name: str, raw: bytes, label: str):
    fields = extract_field_names_from_uploadlike(name, raw)
    if fields:
        all_fields.extend(fields)
        loaded_db_sources.append((label, name, len(fields)))

# (A) Force include
for fname in FORCE_INCLUDE_FILES:
    p = os.path.join(scan_dir, fname)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                add_source(fname, f.read(), "forced")
        except Exception as e:
            st.sidebar.warning(f"Could not read {fname}: {e}")

# (B) Autoscan directory
try:
    for fname in os.listdir(scan_dir):
        if fname in FORCE_INCLUDE_FILES: continue
        if not fname.lower().endswith(ALLOWED_EXTS): continue
        if IGNORE_FILE_RX.match(fname): continue
        path = os.path.join(scan_dir, fname)
        try:
            with open(path, "rb") as f:
                add_source(fname, f.read(), "scan")
        except Exception as e:
            st.sidebar.warning(f"Could not read {fname}: {e}")
except Exception as e:
    st.sidebar.warning(f"Could not scan {scan_dir}: {e}")

# (C) ZIP DB upload
if zip_db is not None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(to_bytes(zip_db.read())))
        for info in zf.infolist():
            name = os.path.basename(info.filename)
            if not name.lower().endswith(ALLOWED_EXTS): continue
            if IGNORE_FILE_RX.match(name): continue
            add_source(name, zf.read(info), "zip")
    except Exception as e:
        st.sidebar.error(f"ZIP parse failed: {e}")

# (D) uploaded extra schema files
if schema_files:
    for sf in schema_files:
        add_source(sf.name, sf.getbuffer(), "upload")

# (E) manual pasted
manual_lines = []
if manual_db_text.strip():
    for ln in manual_db_text.splitlines():
        s = ln.strip()
        if s:
            manual_lines.append(s)
if manual_lines:
    all_fields.extend(manual_lines)
    loaded_db_sources.append(("manual", "pasted_fields", len(manual_lines)))

db_targets = ["— (unmapped) —"] + sorted(set(all_fields))

# ==================== PDF → PARTS =======================
merged = {}
pdf_bytes_list = []
if pdf_files:
    part_maps = []
    for up in pdf_files:
        raw = up.read()
        if not raw:
            st.error(f"❌ {up.name} is empty or unreadable")
            continue
        try:
            parsed = parse_pdf_parts_and_fields(raw)
            if parsed:
                part_maps.append(parsed)
                pdf_bytes_list.append(raw)
        except Exception as e:
            st.error(f"❌ Skipped file {up.name}: {e}")
    if part_maps:
        merged = merge_parts(part_maps)
        merged = auto_split_fields(merged)

# ==================== STATE ============================
if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}  # {part: {fid: {db, questionnaire, label}}}

def make_key(prefix: str, part: str, fid: str, idx: int) -> str:
    # Unique, stable keys for widgets
    safe_part = re.sub(r'[^a-zA-Z0-9_]', '_', part)
    safe_fid = re.sub(r'[^a-zA-Z0-9_]', '_', fid)
    return f"{prefix}_{safe_part}_{safe_fid}_{idx}"

# ==================== UI TABS ==========================
st.title("Universal USCIS Form Mapper")

tabs = st.tabs(["📝 Preview", "📄 Mapping", "🧭 DB/Schema Debug", "⬇️ Exports"])

# ---- PREVIEW ----
with tabs[0]:
    if not merged:
        st.info("Upload at least one USCIS PDF to begin.")
    else:
        st.subheader("Extracted Attributes by Part (sequenced)")
        for part, rows in merged.items():
            st.markdown(f"### {part} ({len(rows)} fields)")
            for r in rows:
                st.write(f"**{r['id']}** → {r['label']} (p.{r['page']})")

# ---- MAPPING ----
with tabs[1]:
    if not merged:
        st.info("Upload at least one USCIS PDF to begin.")
    else:
        for part_idx, part_name in enumerate(sorted(merged.keys(), key=lambda x: int(re.search(r'\d+', x).group()))):
            with st.expander(part_name, expanded=False):
                if part_name not in st.session_state["mappings"]:
                    st.session_state["mappings"][part_name] = {}
                for row_idx, row in enumerate(merged[part_name]):
                    fid, label, page = row["id"], row.get("label",""), row.get("page")
                    key_suffix = make_key("row", part_name, fid, row_idx)
                    c1, c2, c3, c4, c5 = st.columns([1,4,3,3,1])
                    with c1:
                        st.write(f"**{fid}**")
                        if page: st.caption(f"p.{page}")
                    with c2:
                        st.write(label or "—")
                    with c3:
                        choice = st.selectbox("Map DB", db_targets, index=0, key=make_key("db", part_name, fid, row_idx))
                    with c4:
                        manual = st.text_input("Manual DB Path", key=make_key("man", part_name, fid, row_idx))
                    with c5:
                        send_q = st.checkbox("Q?", key=make_key("q", part_name, fid, row_idx))
                    st.session_state["mappings"][part_name][fid] = {
                        "db": manual or (choice if choice != "— (unmapped) —" else None),
                        "questionnaire": send_q,
                        "label": label
                    }

# ---- DB/SCHEMA DEBUG ----
with tabs[2]:
    st.write(f"Scanning directory: `{scan_dir}`")
    if not loaded_db_sources and not manual_lines:
        st.warning("No DB objects discovered. Place your DB object files in the scan folder, upload a ZIP, or paste fields.")
    else:
        for src, name, cnt in loaded_db_sources:
            st.write(f"- **{src}** · {name} → {cnt} fields")
    if db_targets and len(db_targets) > 1:
        st.success(f"Total unique DB fields loaded: {len(db_targets)-1}")
        # show sample fields
        sample = sorted(set(all_fields))[:50]
        if sample:
            st.caption("Sample fields:")
            st.code("\n".join(sample))

# ---- EXPORTS ----
with tabs[3]:
    if not st.session_state["mappings"]:
        st.info("No mappings yet.")
    else:
        st.header("Exports")

        # TypeScript interface
        all_ids = [f"{p.replace(' ', '_')}_{fid}" for p, fields in st.session_state["mappings"].items() for fid in fields]
        ts_code = "export interface USCISForm {\n" + "\n".join([
            f"  {re.sub(r'[^a-zA-Z0-9_]','_',fid)}?: string;" for fid in all_ids
        ]) + "\n}"
        st.download_button("⬇️ Download TS Interface", ts_code, "uscis_fields.ts", "text/plain")

        # Questionnaire JSON (unmapped or flagged)
        qjson = json.dumps({"questions": [
            {"part": p, "id": fid, "label": m["label"], "question_key": f"{p.split(':')[0]}_{fid}".replace('.','')}
            for p, items in st.session_state["mappings"].items()
            for fid, m in items.items() if not m["db"] or m["questionnaire"]
        ]}, indent=2)
        st.download_button("⬇️ Download Questionnaire JSON", qjson, "questionnaire.json", "application/json")

        # Full mappings JSON
        fullmap = json.dumps(st.session_state["mappings"], indent=2)
        st.download_button("⬇️ Download Full Mappings JSON", fullmap, "field_mappings.json", "application/json")

        # LLM Enhancement button
        if st.button("✨ Run LLM Enhancement (optional)"):
            if pdf_bytes_list:
                new_merged = llm_enhance_parts(pdf_bytes_list, merged)
                if new_merged != merged:
                    merged = new_merged
                    st.success("LLM enhancement applied. Reopen Preview/Mapping to see updates.")
                else:
                    st.info("No additional fields found by LLM.")
            else:
                st.info("No PDFs loaded for LLM enhancement.")
