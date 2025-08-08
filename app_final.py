import io
import os
import re
import json
import fitz  # PyMuPDF
import zipfile
import streamlit as st
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# ============== PAGE CONFIG / API KEY ==================
st.set_page_config(page_title="USCIS Form Reader & Mapper (LLM-assisted)", layout="wide")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)  # REQUIRED for LLM assist

# ============== AUTO-SPLIT PATTERNS ====================
DEFAULT_PATTERNS = [
    {"match": ["Family Name", "Given Name", "Middle Name"], "subs": ["a", "b", "c"]},
    {"match": ["Street Number and Name", "Apt. Ste. Flr.", "City or Town", "State", "ZIP Code"], "subs": ["a", "b", "c", "d", "e"]},
    {"match": ["Date of Birth", "City/Town of Birth", "Country of Birth"], "subs": ["a", "b", "c"]},
    {"match": ["Daytime Telephone", "Mobile Telephone", "Email Address"], "subs": ["a", "b", "c"]},
]

# Force-include your provided DB files if present
FORCE_INCLUDE_FILES = [
    "Attorney object.txt", "Beneficiary.txt", "Case Object.txt", "Customer object.txt",
    "Lawfirm Object.txt", "LCA Object.txt", "Petitioner.txt",
    "g28.json", "i90-form.json", "i129-sec1.2.form.json", "G28.ts",
]

# ============== REGEX / HELPERS ========================
PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.IGNORECASE)
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:\.)?([a-z]?)\.\s*(.*)$')
FIELD_INLINE_RX = re.compile(r'(\b\d+\.[a-z]\.)')

TS_INTERFACE_RX = re.compile(r'export\s+interface\s+\w+\s*{([^}]*)}', re.DOTALL)
TS_TYPE_OBJ_RX = re.compile(r'export\s+type\s+\w+\s*=\s*{([^}]*)}', re.DOTALL)
TS_CONST_OBJ_RX = re.compile(r'export\s+const\s+\w+\s*=\s*{(.*?)}\s*(?:as\s+const)?', re.DOTALL)
TS_FIELD_KEY_RX = re.compile(r'(\w+)\??\s*:')

LINE_PATH_RX = re.compile(r'[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*(?:\[\*\])?')
KEY_COLON_RX = re.compile(r'\b([A-Za-z_][\w\.]*)\s*:')

ALLOWED_EXTS = (".json", ".txt", ".ts", ".tsx")
IGNORE_FILE_RX = re.compile(
    r'^(requirements(\.txt)?|pyproject\.toml|poetry\.lock|package(-lock)?\.json|yarn\.lock|Pipfile(\.lock)?)$',
    re.I
)

def to_bytes(buf) -> bytes:
    """Normalize memoryview/bytearray/str/etc. to bytes."""
    if isinstance(buf, (bytes, bytearray)):
        return bytes(buf)
    try:
        return bytes(buf)
    except Exception:
        return str(buf).encode("utf-8", errors="ignore")

def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()

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

def extract_field_names_from_text_lines(text: str) -> List[str]:
    """Fallback for .txt that aren't valid JSON: grab lines + dotted/colon keys."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) <= 200:
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

def extract_field_names_from_ts(text: str) -> List[str]:
    names = []
    for body in (m.group(1) for m in TS_INTERFACE_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_TYPE_OBJ_RX.finditer(text)):
        names += TS_FIELD_KEY_RX.findall(body)
    for body in (m.group(1) for m in TS_CONST_OBJ_RX.finditer(text)):
        names += [k for k in re.findall(r'["\']?([A-Za-z_]\w+)["\']?\s*:', body)]
    seen=set(); out=[]
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out

def extract_field_names_from_uploadlike(name: str, raw: bytes) -> List[str]:
    lname = name.lower()
    raw = to_bytes(raw)
    if lname.endswith((".json", ".txt")):
        obj, err = try_load_json_bytes(raw)
        if obj:
            return [k for k in flatten_keys(obj) if k]
        text = _decode_best(raw)
        return extract_field_names_from_text_lines(text)
    elif lname.endswith((".ts", ".tsx")):
        text = _decode_best(raw)
        return extract_field_names_from_ts(text)
    return []

# ============== PDF PARSING ============================
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
                byid[i] = it
            else:
                if it["page"] < byid[i]["page"]:
                    byid[i]["page"] = it["page"]
                if len(it.get("label","")) > len(byid[i].get("label","")):
                    byid[i]["label"] = it["label"]
        out[k] = [byid[i] for i in sorted(byid.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x))]
    return out

# ============== AUTO-SPLIT & VALIDATION ================
def auto_split_fields(merged_parts, patterns):
    new_parts = defaultdict(list)
    for part, fields in merged_parts.items():
        for field in fields:
            matched = False
            for pat in patterns:
                if all(term in field["label"] for term in pat["match"]):
                    for sub, term in zip(pat["subs"], pat["match"]):
                        new_parts[part].append({"id": f"{field['id']}.{sub}", "label": term, "page": field["page"]})
                    matched = True
                    break
            if not matched:
                new_parts[part].append(field)
    return new_parts

def _num_and_suffix(fid: str):
    m = re.match(r'^(\d+)(?:\.([a-z]))?$', fid.strip())
    if not m:
        return None, None
    n = int(m.group(1)); sfx = m.group(2) or ""
    return n, sfx

def validate_parts(merged_parts: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    report = {}
    for part, rows in merged_parts.items():
        ids = [r["id"] for r in rows]
        dups = sorted(set([x for x in ids if ids.count(x) > 1]))
        parsed = [(_num_and_suffix(fid), fid) for fid in ids]
        parsed = [(p, fid) for (p, fid) in parsed if p[0] is not None]
        nums = sorted(set([p[0] for p, _ in parsed]))
        missing_numbers = []
        if nums:
            for k in range(nums[0], nums[-1] + 1):
                if k not in nums:
                    missing_numbers.append(str(k))
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

def recover_fields(pdf_bytes: bytes, merged_parts: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    from itertools import groupby
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    recovered = defaultdict(list)
    seen = set((part, row["id"]) for part, rows in merged_parts.items() for row in rows)

    def add_or_improve(part_key, fid, label, page_no):
        key = (part_key, fid); label = normalize(label)
        if not label and not fid:
            return
        if key not in seen:
            recovered[part_key].append({"id": fid, "label": label, "page": page_no})
            seen.add(key)
        else:
            for row in merged_parts.get(part_key, []):
                if row["id"] == fid and len(label) > len(row.get("label","")):
                    row["label"] = label

    current_part_key = None
    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1],1), round(b[0],1)))
        for b in blocks:
            text = (b[4] or "").strip()
            if not text: continue
            for line in text.splitlines():
                line = line.strip()
                if not line: continue
                m_part = PART_RX.match(line)
                if m_part:
                    idx, title = m_part.group(1), m_part.group(2).strip()
                    current_part_key = f"Part {idx}: {title}"
                    continue
                if not current_part_key: continue
                m_field = FIELD_HEAD_RX.match(line)
                if m_field:
                    num, sub, rest = m_field.group(1), m_field.group(2), normalize(m_field.group(3) or "")
                    fid = f"{num}.{sub}" if sub else num
                    add_or_improve(current_part_key, fid, rest, pno + 1)
                    continue
                m = re.match(r'^([a-z])\.\s*(.*)$', line)
                if m:
                    sub = m.group(1); rest = normalize(m.group(2) or "")
                    prev_nums = [r for r in merged_parts.get(current_part_key, []) if re.match(r'^\d+$', r["id"])]
                    if prev_nums:
                        last_num = prev_nums[-1]["id"]
                        fid = f"{last_num}.{sub}"
                        add_or_improve(current_part_key, fid, rest, pno + 1)
                    continue
        # left-column sweep
        words = page.get_text("words")
        if words:
            words_sorted = sorted(words, key=lambda w: (w[7], w[1], w[0]))
            for _, line_words in groupby(words_sorted, key=lambda w: w[7]):
                line_words = list(line_words)
                line_text = " ".join(w[4] for w in line_words).strip()
                if not current_part_key:
                    m_part = PART_RX.match(line_text)
                    if m_part:
                        idx, title = m_part.group(1), m_part.group(2).strip()
                        current_part_key = f"Part {idx}: {title}"
                    continue
                m_field = FIELD_HEAD_RX.match(line_text)
                if m_field:
                    num, sub, rest = m_field.group(1), m_field.group(2), normalize(m_field.group(3) or "")
                    fid = f"{num}.{sub}" if sub else num
                    add_or_improve(current_part_key, fid, rest, pno + 1)
                    continue
                leftmost = min(line_words, key=lambda w: w[0])
                token = leftmost[4].strip().lower()
                if re.match(r'^[a-z]\.$', token):
                    sub = token.strip('.')
                    right_text = " ".join(w[4] for w in line_words if w[0] > leftmost[2])
                    prev_nums = [r for r in merged_parts.get(current_part_key, []) if re.match(r'^\d+$', r["id"])]
                    if prev_nums:
                        last_num = prev_nums[-1]["id"]
                        add_or_improve(current_part_key, f"{last_num}.{sub}", right_text, pno + 1)

    for part, newrows in recovered.items():
        existing = {r["id"]: r for r in merged_parts.get(part, [])}
        for r in newrows:
            if r["id"] not in existing:
                merged_parts.setdefault(part, []).append(r)
        merged_parts[part] = sorted(merged_parts[part], key=lambda r: (_num_and_suffix(r["id"])[0] or 0, r["id"]))
    return merged_parts

# ============== LLM-ASSISTED EXTRACTION =================
def oai_chat(messages, model="gpt-4o-mini", temperature=0.0, max_tokens=2000):
    """Works with both old and new openai SDKs."""
    if not OPENAI_API_KEY:
        return None
    try:
        # New SDK
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
        return resp.choices[0].message.content
    except Exception:
        try:
            # Old SDK
            import openai
            openai.api_key = OPENAI_API_KEY
            resp = openai.ChatCompletion.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
            return resp.choices[0].message.content
        except Exception:
            return None

def llm_enhance_parts(pdf_bytes_list: List[bytes], merged_parts: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Ask the LLM for missing IDs/labels & merge back."""
    if not OPENAI_API_KEY:
        return merged_parts
    # Concatenate text from first PDF (enough context)
    raw_texts = []
    try:
        doc = fitz.open(stream=pdf_bytes_list[0], filetype="pdf")
        for p in range(len(doc)):
            raw_texts.append(doc[p].get_text("text"))
    except Exception:
        return merged_parts
    raw_text = "\n".join(raw_texts)[:25000]

    present = [{"part": part, "ids": [r["id"] for r in rows]} for part, rows in merged_parts.items()]
    system = "You are a precise USCIS form structure extractor. Return clean JSON only."
    user = f"""
Given this raw text from a USCIS form, return a JSON object with:
{{
  "parts": [
    {{"name": "Part N: Title", "fields": [{{"id": "1", "label": "..."}}]}}
  ]
}}
Rules:
- Field ids must be like "1" or "1.a".
- Include all fields and subfields you detect; do NOT invent fields not present.
- For grouped lines (Name/Address/Birth/Contact), split into a/b/c etc. with accurate labels.
- Prefer shortest precise label for each id.
- Only return JSON.

Known parsed (for reference, may be incomplete):
{json.dumps(present)[:5000]}

TEXT:
{raw_text}
"""
    content = oai_chat([{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=4000)
    if not content:
        return merged_parts
    # Try parse JSON
    try:
        start = content.find("{")
        end = content.rfind("}")
        data = json.loads(content[start:end+1])
        for part_obj in data.get("parts", []):
            pname = part_obj.get("name")
            if not pname: continue
            fields = part_obj.get("fields", [])
            exist_ids = set(r["id"] for r in merged_parts.get(pname, []))
            for f in fields:
                fid = f.get("id"); lbl = normalize(f.get("label",""))
                if not fid: continue
                if fid not in exist_ids:
                    merged_parts.setdefault(pname, []).append({"id": fid, "label": lbl, "page": None})
                else:
                    # prefer longer label
                    for r in merged_parts[pname]:
                        if r["id"] == fid and len(lbl) > len(r.get("label","")):
                            r["label"] = lbl
        # sort each part by numeric then suffix
        for pname in merged_parts:
            merged_parts[pname] = sorted(merged_parts[pname], key=lambda r: (_num_and_suffix(r["id"])[0] or 0, r["id"]))
    except Exception:
        pass
    return merged_parts

# ============== SIDEBAR INPUTS =========================
st.sidebar.header("Upload Inputs")
pdf_files = st.sidebar.file_uploader("USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)
schema_files = st.sidebar.file_uploader("Extra DB Objects/Schemas", type=["json","ts","tsx","txt"], accept_multiple_files=True)
zip_db = st.sidebar.file_uploader("Upload ZIP of DB objects (json/txt/ts inside)", type=["zip"])
patterns_file = st.sidebar.file_uploader("Auto-split Patterns JSON (optional)", type=["json"])
st.sidebar.header("DB Catalog (Optional)")
manual_db_text = st.sidebar.text_area("Paste DB fields (one per line)", height=150, placeholder="Attorney.name.first\nBeneficiary.address.city\n...")

# Patterns
patterns = DEFAULT_PATTERNS
if patterns_file:
    try:
        patterns = json.loads(to_bytes(patterns_file.getbuffer()).decode("utf-8"))
    except:
        st.sidebar.error("Invalid patterns.json format. Using defaults.")

# Parse PDFs
merged = {}
pdf_bytes_list = []
if pdf_files:
    part_maps = []
    for up in pdf_files:
        raw = to_bytes(up.getbuffer())
        pdf_bytes_list.append(raw)
        part_maps.append(parse_pdf_parts_and_fields(raw))
    merged = merge_parts(part_maps)
    merged = auto_split_fields(merged, patterns)

# ============== DB TARGETS BUILD =======================
scan_dir = "/mnt/data" if os.path.exists("/mnt/data") else os.getcwd()
loaded_db_sources = []
all_fields: List[str] = []

def add_source(name: str, raw: bytes, label: str):
    raw = to_bytes(raw)
    fields = extract_field_names_from_uploadlike(name, raw)
    if fields:
        all_fields.extend(fields)
        loaded_db_sources.append((label, name, len(fields)))

# (A) force-include exact files if present
for fname in FORCE_INCLUDE_FILES:
    p = os.path.join(scan_dir, fname)
    if os.path.exists(p):
        try:
            with open(p, "rb") as f:
                add_source(fname, f.read(), "forced")
        except Exception as e:
            st.warning(f"Could not read {fname}: {e}")

# (B) autoscan directory (filter obvious junk)
try:
    for fname in os.listdir(scan_dir):
        if fname in FORCE_INCLUDE_FILES:
            continue
        if not fname.lower().endswith(ALLOWED_EXTS):
            continue
        if IGNORE_FILE_RX.match(fname):
            continue
        path = os.path.join(scan_dir, fname)
        try:
            with open(path, "rb") as f:
                add_source(fname, f.read(), "scan")
        except Exception as e:
            st.warning(f"Could not read {fname}: {e}")
except Exception as e:
    st.warning(f"Could not scan {scan_dir}: {e}")

# (C) ZIP DB
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

# ============== STATE & TABS ===========================
if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}

tab_map, tab_dbdebug, tab_validate, tab_export = st.tabs(["📄 Parts & Mapping", "🧭 DB/Schema Debug", "✅ Validation", "⬇️ Exports"])

# ---------- DB/SCHEMA DEBUG ----------
with tab_dbdebug:
    st.write(f"Scanning directory: `{scan_dir}`")
    if not loaded_db_sources and not manual_lines:
        st.warning("No DB objects discovered. Place your DB object files in the scan folder, upload a ZIP, or paste fields.")
    else:
        for src, name, cnt in loaded_db_sources:
            st.write(f"- **{src}** · {name} → {cnt} fields")
    if db_targets and len(db_targets) > 1:
        st.success(f"Total unique DB fields loaded: {len(db_targets)-1}")
        st.caption("Sample fields:")
        st.code("\n".join(list(sorted(set(all_fields)))[:50]))

# ---------- VALIDATION ----------
with tab_validate:
    st.header("Validation & Recovery")
    if not merged:
        st.info("Upload at least one USCIS PDF in the sidebar.")
    else:
        val = validate_parts(merged)
        problems = 0
        for part, rep in val.items():
            miss_nums = rep["missing_numbers"]; miss_sfx = rep["missing_suffixes"]; dups = rep["duplicates"]
            if miss_nums or miss_sfx or dups:
                problems += 1
                with st.expander(f"⚠️ {part} · {rep['total']} fields", expanded=False):
                    if dups: st.error(f"Duplicates: {', '.join(dups)}")
                    if miss_nums: st.warning(f"Missing numeric IDs: {', '.join(miss_nums)}")
                    if miss_sfx:
                        st.warning("Missing suffixes (have → expected includes 'a'):")
                        st.code(json.dumps(miss_sfx, indent=2))
            else:
                with st.expander(f"✅ {part} · {rep['total']} fields", expanded=False):
                    st.write("No gaps detected.")
        colA, colB, colC = st.columns(3)
        with colA:
            if st.button("Run Recovery Pass (blocks/words)"):
                if pdf_bytes_list:
                    for raw in pdf_bytes_list:
                        merged = recover_fields(raw, merged)
                    st.success("Recovery pass applied. Check Parts & Mapping.")
                else:
                    st.info("No PDFs loaded.")
        with colB:
            if st.button("LLM-Assist: Enhance Parts/Fields"):
                if OPENAI_API_KEY and pdf_bytes_list:
                    merged = llm_enhance_parts(pdf_bytes_list, merged)
                    st.success("LLM enhancement applied.")
                elif not OPENAI_API_KEY:
                    st.warning("Add OPENAI_API_KEY in .streamlit/secrets.toml to enable this.")
                else:
                    st.info("No PDFs loaded.")
        with colC:
            st.caption("Tip: Use both Recovery and LLM to get the most complete capture.")

# ---------- PARTS & MAPPING ----------
with tab_map:
    st.title("Universal USCIS Form Reader & Mapper (LLM-assisted)")
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

# ---------- EXPORTS ----------
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

    st.download_button(label="Download TS Interface", data=ts_code.encode("utf-8"), file_name="uscis_fields.ts", mime="text/plain")
    st.download_button(label="Download Questionnaire (Unmapped/Flagged)", data=qjson.encode("utf-8"), file_name="questionnaire.json", mime="application/json")
    st.download_button(label="Download Full Field Mappings", data=fullmap.encode("utf-8"), file_name="field_mappings.json", mime="application/json")
