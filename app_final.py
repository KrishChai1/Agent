# app_final.py — final stable
import os, re, io, json, zipfile, hashlib
from collections import defaultdict
from typing import Dict, List, Any, Tuple

import fitz  # PyMuPDF
import streamlit as st

# ==================== APP CONFIG ====================
st.set_page_config(page_title="USCIS Form Reader & Mapper (LLM-assisted)", layout="wide")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
DEFAULT_OAI_MODEL = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")

# Force-include known DB/schema files if present
FORCE_INCLUDE_FILES = [
    "Attorney object.txt", "Beneficiary.txt", "Beneficiary copy_old.txt",
    "Case Object.txt", "Customer object.txt", "Lawfirm Object.txt", "LCA Object.txt", "Petitioner.txt",
    "g28.json", "h-2b-form.json", "empty_json_structures.json", "G28.ts", "H2B.ts",
]

ALLOWED_EXTS = (".json", ".txt", ".ts", ".tsx")
IGNORE_FILE_RX = re.compile(
    r'^(requirements(\.txt)?|pyproject\.toml|poetry\.lock|package(-lock)?\.json|yarn\.lock|Pipfile(\.lock)?)$',
    re.I
)

# ==================== HELPERS ====================
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
        try: return b.decode(enc)
        except Exception: pass
    return b.decode("utf-8", errors="ignore")

def try_load_json_bytes(b: bytes) -> Tuple[dict, str]:
    b = to_bytes(b); last = ""
    for enc in ("utf-8", "utf-16", "utf-8-sig", "latin-1"):
        try: return json.loads(b.decode(enc)), ""
        except Exception as e: last = str(e)
    return {}, last

def flatten_keys(obj, prefix="") -> List[str]:
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            newp = f"{prefix}.{k}" if prefix else k
            keys.extend(flatten_keys(v, newp))
    elif isinstance(obj, list):
        keys.append(f"{prefix}[*]")
        if obj:
            keys.extend(flatten_keys(obj[0], f"{prefix}[0]"))
    else:
        if prefix: keys.append(prefix)
    return keys

# TXT / TS extractors
LINE_PATH_RX = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+(?:\[\*\])?')
KEY_COLON_RX = re.compile(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*:')

def extract_field_names_from_text_lines(text: str) -> List[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if len(line) <= 200: out.append(line)
        for m in LINE_PATH_RX.finditer(line): out.append(m.group(0))
        for m in KEY_COLON_RX.finditer(line): out.append(m.group(1))
    seen=set(); res=[]
    for k in out:
        if k and k not in seen:
            seen.add(k); res.append(k)
    return res

TS_INTERFACE_RX = re.compile(r'export\s+interface\s+\w+\s*{([^}]*)}', re.DOTALL)
TS_TYPE_OBJ_RX = re.compile(r'export\s+type\s+\w+\s*=\s*{([^}]*)}', re.DOTALL)
TS_CONST_OBJ_RX = re.compile(r'export\s+const\s+\w+\s*=\s*{(.*?)}\s*(?:as\s+const)?', re.DOTALL)
TS_FIELD_KEY_RX = re.compile(r'["\']?([A-Za-z_]\w+)["\']?\s*:')

def extract_field_names_from_ts(text: str) -> List[str]:
    names = []
    for body in (m.group(1) for m in TS_INTERFACE_RX.finditer(text)): names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_TYPE_OBJ_RX.finditer(text)): names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_CONST_OBJ_RX.finditer(text)): names += TS_FIELD_KEY_RX.findall(body)
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
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:[\.\)]\s*([a-z])?)?\s*(.*)$', re.I)  # 1., 1), 1.a., 1.a

def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """
    Parse USCIS PDF using blocks; merge continuation lines; split simple Yes/No into a/b.
    If no Part headers exist, assign Part 1 (Auto).
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
            if not line: continue

            m_part = PART_RX.match(line)
            if m_part:
                idx, title = m_part.groups()
                current_part = f"Part {idx}: {normalize(title)}"
                last_fid = None
                continue

            if not current_part:
                current_part = "Part 1 (Auto)"

            m_field = FIELD_HEAD_RX.match(line)
            if m_field:
                num, sub, rest = m_field.groups()
                fid = f"{num}.{sub}" if sub else num
                label = normalize(rest) or line
                parts[current_part].append({"id": fid, "label": label, "page": pno+1})
                last_fid = fid
            else:
                if last_fid and re.search(r'\b(Yes|No)\b', line):
                    base = last_fid.split(".")[0]
                    opts = re.findall(r'\b(Yes|No)\b', line)
                    for i, opt in enumerate(opts, start=1):
                        opt_id = f"{base}.{chr(96+i)}"  # a,b,c
                        parts[current_part].append({"id": opt_id, "label": opt, "page": pno+1})
                elif parts[current_part]:
                    parts[current_part][-1]["label"] = normalize(parts[current_part][-1]["label"] + " " + line)

    # Sort within each part
    for pk, rows in parts.items():
        def sort_key(r):
            m = re.match(r"(\d+)(?:\.([a-z]))?$", r["id"])
            if not m: return (99999, r["id"])
            num, sub = m.groups()
            return (int(num), sub or "")
        parts[pk] = sorted(rows, key=sort_key)

    return parts

def _num_and_suffix(fid: str):
    m = re.match(r'^(\d+)(?:\.([a-z]))?$', fid.strip())
    if not m: return None, None
    return int(m.group(1)), (m.group(2) or "")

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
                byid[fid] = dict(it)
            else:
                if it.get("page") and (not byid[fid].get("page") or it["page"] < byid[fid]["page"]):
                    byid[fid]["page"] = it["page"]
                if len(it.get("label","")) > len(byid[fid].get("label","")):
                    byid[fid]["label"] = it["label"]
        out[k] = [byid[fid] for fid in sorted(byid.keys(), key=lambda x: (_num_and_suffix(x)[0] or 0, x))]
    return out

# Grouped split patterns
DEFAULT_PATTERNS = [
    {"match": ["Family Name", "Given Name", "Middle Name"], "subs": ["a","b","c"]},
    {"match": ["Street Number and Name", "Apt. Ste. Flr.", "City or Town", "State", "ZIP Code"], "subs": ["a","b","c","d","e"]},
    {"match": ["Date of Birth", "City/Town of Birth", "Country of Birth"], "subs": ["a","b","c"]},
    {"match": ["Daytime Telephone", "Mobile Telephone", "Email Address"], "subs": ["a","b","c"]},
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

# ============== LLM (optional) =========================
def oai_chat(messages, model=None, temperature=0.0, max_tokens=2000):
    if not OPENAI_API_KEY: return None
    if not model: model = DEFAULT_OAI_MODEL
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        return resp.choices[0].message.content
    except Exception:
        try:
            import openai
            openai.api_key = OPENAI_API_KEY
            resp = openai.ChatCompletion.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
            return resp.choices[0].message.content
        except Exception:
            return None

def llm_enhance_parts(pdf_bytes_list: List[bytes], merged_parts: Dict[str, List[Dict[str, Any]]], model=None) -> Dict[str, List[Dict[str, Any]]]:
    if not OPENAI_API_KEY or not pdf_bytes_list: return merged_parts
    try:
        doc = safe_open_pdf(pdf_bytes_list[0])
        raw_text = "\n".join([doc[p].get_text("text") for p in range(len(doc))])[:24000]
    except Exception:
        return merged_parts
    system = "You are a precise USCIS form structure extractor. Return clean JSON only."
    user = f"""
Return JSON:
{{
  "parts": [
    {{"name":"Part N: Title","fields":[{{"id":"1","label":"..."}}]}}
  ]
}}
- ids are "1" or "1.a"; include only present fields
- keep labels short; split Name/Address/Birth/Contact into a/b/c if grouped

TEXT:
{raw_text}
"""
    content = oai_chat([{"role":"system","content":system},{"role":"user","content":user}], model=model, max_tokens=4000)
    if not content: return merged_parts
    try:
        start = content.find("{"); end = content.rfind("}")
        data = json.loads(content[start:end+1])
        for part_obj in data.get("parts", []):
            pname = part_obj.get("name")
            if not pname: continue
            exist = {r["id"]: r for r in merged_parts.get(pname, [])}
            for f in part_obj.get("fields", []):
                fid = f.get("id"); lbl = normalize(f.get("label",""))
                if not fid: continue
                if fid not in exist:
                    merged_parts.setdefault(pname, []).append({"id": fid, "label": lbl, "page": None})
                else:
                    if len(lbl) > len(exist[fid].get("label","")):
                        exist[fid]["label"] = lbl
        for pname in merged_parts:
            merged_parts[pname] = sorted(merged_parts[pname], key=lambda r: (_num_and_suffix(r["id"])[0] or 0, r["id"]))
    except Exception:
        pass
    return merged_parts

# ==================== SIDEBAR INPUTS ====================
st.sidebar.header("Upload Inputs")
pdf_files = st.sidebar.file_uploader("USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Extra DB Objects/Schemas", type=["json","ts","tsx","txt"], accept_multiple_files=True)
zip_db = st.sidebar.file_uploader("Upload ZIP of DB objects (json/txt/ts inside)", type=["zip"])
patterns_file = st.sidebar.file_uploader("Auto-split Patterns JSON (optional)", type=["json"])
st.sidebar.header("DB Catalog (Optional)")
manual_db_text = st.sidebar.text_area("Paste DB fields (one per line)", height=140, placeholder="Attorney.name.first\nBeneficiary.address.city\n...")

st.sidebar.header("LLM Options")
model_choice = st.sidebar.selectbox("OpenAI Model", [DEFAULT_OAI_MODEL, "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"], index=0)
auto_llm = st.sidebar.checkbox("Auto-enhance after upload", value=True)

# Patterns override
patterns = DEFAULT_PATTERNS
if patterns_file:
    try: patterns = json.loads(to_bytes(patterns_file.read()).decode("utf-8"))
    except: st.sidebar.error("Invalid patterns.json format. Using defaults.")

# ==================== PDF → PARTS ======================
merged: Dict[str, List[Dict[str, Any]]] = {}
pdf_bytes_list: List[bytes] = []
if pdf_files:
    part_maps = []
    for up in pdf_files:
        raw = up.read()  # IMPORTANT: real bytes, not getbuffer()
        if not raw:
            st.sidebar.error(f"❌ {up.name} is empty or unreadable")
            continue
        try:
            pmap = parse_pdf_parts_and_fields(raw)
            part_maps.append(pmap)
            pdf_bytes_list.append(raw)
        except Exception as e:
            st.sidebar.error(f"❌ Could not parse {up.name}: {e}")
    if part_maps:
        merged = merge_parts(part_maps)
        merged = auto_split_fields(merged, patterns)
        if auto_llm:
            merged = llm_enhance_parts(pdf_bytes_list, merged, model=model_choice)

# ==================== DB TARGETS BUILD =================
scan_dir = "/mnt/data" if os.path.exists("/mnt/data") else os.getcwd()
loaded_db_sources = []
all_fields: List[str] = []

def add_source(name: str, raw: bytes, label: str):
    fields = extract_field_names_from_uploadlike(name, raw)
    if fields:
        all_fields.extend(fields)
        loaded_db_sources.append((label, name, len(fields)))

# (A) force-includes
for fname in FORCE_INCLUDE_FILES:
    path = os.path.join(scan_dir, fname)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f: add_source(fname, f.read(), "forced")
        except Exception as e:
            st.sidebar.warning(f"Could not read {fname}: {e}")

# (B) autoscan directory
try:
    for fname in os.listdir(scan_dir):
        if fname in FORCE_INCLUDE_FILES: continue
        if not fname.lower().endswith(ALLOWED_EXTS): continue
        if IGNORE_FILE_RX.match(fname): continue
        path = os.path.join(scan_dir, fname)
        try:
            with open(path, "rb") as f: add_source(fname, f.read(), "scan")
        except Exception as e:
            st.sidebar.warning(f"Could not read {fname}: {e}")
except Exception as e:
    st.sidebar.warning(f"Could not scan {scan_dir}: {e}")

# (C) ZIP DB
if zip_db is not None:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_db.read()))
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
        add_source(sf.name, sf.read(), "upload")

# (E) manual pasted
manual_lines = []
if manual_db_text.strip():
    for ln in manual_db_text.splitlines():
        s = ln.strip()
        if s: manual_lines.append(s)
if manual_lines:
    all_fields.extend(manual_lines)
    loaded_db_sources.append(("manual", "pasted_fields", len(manual_lines)))

db_targets = ["— (unmapped) —"] + sorted(set(map(str, all_fields)))

# ==================== STATE / KEYS =====================
if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}

def hash_key(*parts) -> str:
    base = "||".join(str(p) for p in parts)
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:10]

def make_key(prefix: str, part: str, fid: str) -> str:
    safe_part = re.sub(r'[^A-Za-z0-9_]+', '_', part)
    safe_fid = re.sub(r'[^A-Za-z0-9_]+', '_', fid)
    return f"{prefix}_{safe_part}_{safe_fid}_{hash_key(prefix, part, fid)}"

# ==================== UI TABS ==========================
tab_map, tab_dbdebug, tab_validate, tab_export = st.tabs(["📄 Parts & Mapping", "🧭 DB/Schema Catalog", "✅ Validation", "⬇️ Exports"])

# ---- DB/SCHEMA CATALOG ----
with tab_dbdebug:
    st.write(f"Scanning directory: `{scan_dir}`")
    if not loaded_db_sources and not manual_lines:
        st.warning("No DB objects discovered. Place DB object files in the scan folder, upload a ZIP, or paste fields.")
    else:
        st.success(f"Total unique DB fields loaded: {len(db_targets)-1}")
        q = st.text_input("Search fields", "")
        fields_view = sorted(set(all_fields))
        if q.strip():
            fields_view = [f for f in fields_view if q.lower() in f.lower()]
        st.caption("Fields (showing first 1000):")
        st.code("\n".join(fields_view[:1000]))
        with st.expander("Sources"):
            for src, name, cnt in loaded_db_sources:
                st.write(f"- **{src}** · {name} → {cnt} fields")

# ---- VALIDATION ----
def _num_sfx(fid: str):
    m = re.match(r'^(\d+)(?:\.([a-z]))?$', fid.strip())
    if not m: return None, None
    return int(m.group(1)), (m.group(2) or "")

def validate_parts(merged_parts: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    report = {}
    for part, rows in merged_parts.items():
        ids = [r["id"] for r in rows]
        dups = sorted(set([x for x in ids if ids.count(x) > 1]))
        parsed = [(_num_sfx(fid), fid) for fid in ids]
        parsed = [(p, fid) for (p, fid) in parsed if p[0] is not None]
        nums = sorted(set([p[0] for p, _ in parsed]))
        missing_numbers = []
        if nums:
            for k in range(nums[0], nums[-1] + 1):
                if k not in nums: missing_numbers.append(str(k))
        missing_suffixes = {}
        groups = {}
        for (n, sfx), fid in parsed:
            groups.setdefault(n, []).append(sfx)
        for n, suffixes in groups.items():
            ss = sorted([s for s in suffixes if s])
            if ss and 'a' not in ss:
                missing_suffixes[str(n)] = {'expected_including': ['a'], 'have': ss}
        report[part] = {"missing_numbers": missing_numbers, "missing_suffixes": missing_suffixes, "duplicates": dups, "total": len(rows)}
    return report

with tab_validate:
    st.header("Validation & Recovery")
    if not merged:
        st.info("Upload at least one USCIS PDF.")
    else:
        val = validate_parts(merged)
        for part, rep in val.items():
            miss_nums, miss_sfx, dups = rep["missing_numbers"], rep["missing_suffixes"], rep["duplicates"]
            title = f"{part} · {rep['total']} fields"
            if miss_nums or miss_sfx or dups:
                with st.expander(f"⚠️ {title}", expanded=False):
                    if dups: st.error(f"Duplicates: {', '.join(dups)}")
                    if miss_nums: st.warning(f"Missing numeric IDs: {', '.join(miss_nums)}")
                    if miss_sfx:
                        st.warning("Missing suffixes (have → expected includes 'a'):")
                        st.code(json.dumps(miss_sfx, indent=2))
            else:
                with st.expander(f"✅ {title}", expanded=False):
                    st.write("No gaps detected.")

# ---- PARTS & MAPPING ----
with tab_map:
    st.title("Universal USCIS Form Reader & Mapper")
    if not merged:
        st.info("Upload at least one USCIS PDF to start.")
    else:
        ordered_parts = sorted(merged.keys(), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 99999)
        for part_name in ordered_parts:
            rows = merged[part_name]
            with st.expander(part_name, expanded=(part_name.startswith("Part 1"))):
                st.caption("Extracted attributes")
                st.dataframe(
                    [{"ID": r["id"], "Label": r.get("label",""), "Page": r.get("page")} for r in rows],
                    use_container_width=True, hide_index=True
                )
                if part_name not in st.session_state["mappings"]:
                    st.session_state["mappings"][part_name] = {}
                for r in rows:
                    fid, label, page = r["id"], r.get("label",""), r.get("page")
                    c1, c2, c3, c4, c5 = st.columns([1,4,3,3,1])
                    with c1:
                        st.write(f"**{fid}**")
                        if page: st.caption(f"p.{page}")
                    with c2:
                        st.write(label or "—")
                    with c3:
                        choice = st.selectbox("Map DB", db_targets, index=0, key=make_key("db", part_name, fid))
                    with c4:
                        manual = st.text_input("Manual DB Path", key=make_key("man", part_name, fid))
                    with c5:
                        send_q = st.checkbox("Q?", key=make_key("q", part_name, fid))
                    st.session_state["mappings"][part_name][fid] = {
                        "db": (manual or (choice if choice != "— (unmapped) —" else None)),
                        "questionnaire": bool(send_q),
                        "label": label
                    }

# ---- EXPORTS ----
with tab_export:
    st.header("Exports")
    if not st.session_state["mappings"]:
        st.info("No mappings yet.")
    else:
        mappings = st.session_state["mappings"]

        # TS interface
        all_ids = [f"{p.split(':')[0].replace(' ','_')}_{fid}" for p in mappings for fid in mappings[p]]
        iface_lines = [f"  {re.sub(r'[^a-zA-Z0-9_]','_',fid)}?: string;" for fid in all_ids]
        ts_code = "export interface USCISFormFields {\n" + "\n".join(iface_lines) + "\n}\n"

        ts_types = """// Mapping/Questionnaire types
export type FieldId = keyof USCISFormFields;
export type FieldMapping = Record<string, {
  db?: string;
  questionnaire: boolean;
  label: string;
}>;
"""

        # Questionnaire JSON (unmapped or flagged)
        questions = []
        for p, items in mappings.items():
            for fid, m in items.items():
                if not m["db"] or m["questionnaire"]:
                    qkey = f"{p.split(':')[0]}_{fid}".replace('.','')
                    questions.append({"part": p, "id": fid, "label": m.get("label",""), "question_key": qkey})
        qjson = json.dumps({"questions": questions}, indent=2)

        # Full mappings JSON
        fullmap = json.dumps(mappings, indent=2)

        st.download_button("⬇️ Download TS Interface", (ts_code+ts_types).encode("utf-8"), "uscis_fields.ts", "text/plain")
        st.download_button("⬇️ Download Questionnaire JSON", qjson.encode("utf-8"), "questionnaire.json", "application/json")
        st.download_button("⬇️ Download Full Mappings JSON", fullmap.encode("utf-8"), "field_mappings.json", "application/json")

        if st.button("✨ LLM Enhance Now"):
            if pdf_bytes_list:
                merged2 = llm_enhance_parts(pdf_bytes_list, merged, model=model_choice)
                if merged2 != merged:
                    st.success("LLM enhancement applied. Reopen Parts & Mapping to see updates.")
                else:
                    st.info("No additional fields found by LLM.")
            else:
                st.info("No PDFs loaded.")
