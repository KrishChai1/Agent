import io, os, re, json
import fitz  # PyMuPDF
import streamlit as st
from collections import defaultdict
from typing import Dict, List, Any

# ==================== CONFIG =====================
st.set_page_config(page_title="Universal USCIS Form Mapper", layout="wide")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)

FORCE_INCLUDE_FILES = [
    "Attorney object.txt", "Beneficiary.txt", "Case Object.txt", "Customer object.txt",
    "Lawfirm Object.txt", "LCA Object.txt", "Petitioner.txt",
    "g28.json", "h-2b-form.json", "G28.ts", "H2B.ts"
]

# ==================== HELPERS =====================
def normalize(s: str) -> str:
    return re.sub(r'\s+', ' ', s or '').strip()

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
        if prefix: keys.append(prefix)
    return keys

def try_load_json_bytes(b: bytes):
    try:
        return json.loads(b.decode("utf-8")), ""
    except Exception as e:
        return {}, str(e)

def extract_field_names_from_uploadlike(name: str, raw: bytes) -> List[str]:
    lname = name.lower()
    if lname.endswith((".json", ".txt")):
        obj, _ = try_load_json_bytes(raw)
        if obj:
            return flatten_keys(obj)
    return []

# ==================== SAFE PDF OPEN =====================
def safe_open_pdf(raw: bytes):
    if not raw or not isinstance(raw, (bytes, bytearray)):
        raise RuntimeError("Empty or invalid PDF bytes")
    try:
        return fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF: {e}")

# ==================== PDF PARSING =====================
PART_RX = re.compile(r'^\s*Part\s+(\d+)\.\s*(.*)$', re.I)
FIELD_HEAD_RX = re.compile(r'^\s*(\d+)(?:[\.\)]\s*([a-z])?)?\s*(.*)$', re.I)

def parse_pdf_parts_and_fields(pdf_bytes: bytes) -> Dict[str, List[Dict[str, Any]]]:
    """Parse a USCIS PDF using blocks mode (better for structured forms)."""
    parts = defaultdict(list)
    doc = safe_open_pdf(pdf_bytes)
    current_part = None

    for pno in range(len(doc)):
        blocks = doc[pno].get_text("blocks")
        blocks = sorted(blocks, key=lambda b: (round(b[1],1), round(b[0],1)))  # sort by y, then x
        for b in blocks:
            line = (b[4] or "").strip()
            if not line: 
                continue

            # detect "Part 1. Information ..."
            m_part = PART_RX.match(line)
            if m_part:
                idx, title = m_part.groups()
                current_part = f"Part {idx}: {title.strip()}"
                continue

            if not current_part:
                continue

            # detect numbered field "1.", "1.a", etc.
            m_field = FIELD_HEAD_RX.match(line)
            if m_field:
                num, sub, rest = m_field.groups()
                fid = f"{num}.{sub}" if sub else num
                label = normalize(rest) or line
                parts[current_part].append({"id": fid, "label": label, "page": pno+1})
            else:
                # If line has Yes/No or options, attach separately
                if any(opt in line for opt in ["Yes", "No", "☐", "□"]):
                    fid = f"{len(parts[current_part])+1}.opt"
                    parts[current_part].append({"id": fid, "label": line, "page": pno+1})
                elif parts[current_part]:
                    # continuation of previous label
                    parts[current_part][-1]["label"] += " " + line

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
        out[k] = [byid[fid] for fid in sorted(byid, key=lambda x: (int(re.match(r"\d+", x).group()) if re.match(r"\d+", x) else 0, x))]
    return out

# Split grouped fields like Name / Address / DOB
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

# ==================== LLM ENHANCEMENT =====================
def oai_chat(messages, model="gpt-4o-mini", temperature=0.0, max_tokens=2000):
    if not OPENAI_API_KEY: return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature, max_tokens=max_tokens)
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
    user = f"Extract parts/fields and options from this USCIS form:\n{raw_text}"
    content = oai_chat([{"role":"system","content":system},{"role":"user","content":user}], max_tokens=4000)
    if not content: return merged_parts
    try:
        data = json.loads(content[content.find("{"):content.rfind("}")+1])
        for part in data.get("parts", []):
            pname = part["name"]; fields = part.get("fields", [])
            exist_ids = set(r["id"] for r in merged_parts.get(pname, []))
            for f in fields:
                fid, lbl = f.get("id"), normalize(f.get("label",""))
                if fid and fid not in exist_ids:
                    merged_parts.setdefault(pname, []).append({"id": fid, "label": lbl, "page": None})
    except: pass
    return merged_parts

# ==================== UI =====================
st.sidebar.header("Upload Inputs")
pdf_files = st.sidebar.file_uploader("USCIS PDF(s)", type=["pdf"], accept_multiple_files=True)

# Load DB objects
scan_dir = "/mnt/data" if os.path.exists("/mnt/data") else os.getcwd()
all_fields = []
for fname in FORCE_INCLUDE_FILES:
    path = os.path.join(scan_dir, fname)
    if os.path.exists(path):
        with open(path, "rb") as f:
            fields = extract_field_names_from_uploadlike(fname, f.read())
            all_fields.extend(fields)
db_targets = ["— (unmapped) —"] + sorted(set(all_fields))

# Parse PDFs
merged, pdf_bytes_list = {}, []
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

# ==================== MAIN =====================
st.title("Universal USCIS Form Mapper")

if not merged:
    st.info("Upload at least one USCIS PDF to begin.")
    st.stop()

if "mappings" not in st.session_state:
    st.session_state["mappings"] = {}

tabs = st.tabs(["📝 Preview", "📄 Mapping", "⬇️ Exports"])

# ---- PREVIEW ----
with tabs[0]:
    st.subheader("Extracted Attributes by Part")
    for part, rows in merged.items():
        st.markdown(f"### {part} ({len(rows)} fields)")
        for r in rows:
            st.write(f"**{r['id']}** → {r['label']} (p.{r['page']})")

# ---- MAPPING ----
with tabs[1]:
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
                with c2: st.write(label or "—")
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

# ---- EXPORTS ----
with tabs[2]:
    st.header("Exports")

    # TypeScript interface
    all_ids = [f"{p.replace(' ', '_')}_{fid}" for p, fields in st.session_state["mappings"].items() for fid in fields]
    ts_code = "export interface USCISForm {\n" + "\n".join([
        f"  {re.sub(r'[^a-zA-Z0-9_]','_',fid)}?: string;" for fid in all_ids
    ]) + "\n}"

    # Questionnaire JSON
    qjson = json.dumps({"questions": [
        {"part": p, "id": fid, "label": m["label"], "question_key": f"{p.split(':')[0]}_{fid}".replace('.','')}
        for p, items in st.session_state["mappings"].items()
        for fid, m in items.items() if not m["db"] or m["questionnaire"]
    ]}, indent=2)

    st.download_button("⬇️ Download TS Interface", ts_code, "uscis_fields.ts", "text/plain")
    st.download_button("⬇️ Download Questionnaire JSON", qjson, "questionnaire.json", "application/json")
    st.download_button("⬇️ Download Full Mappings JSON",
                       json.dumps(st.session_state["mappings"], indent=2),
                       "field_mappings.json", "application/json")

    if st.button("✨ Run LLM Enhancement (optional)"):
        merged = llm_enhance_parts(pdf_bytes_list, merged)
        st.success("LLM enhancement applied. Reopen tabs to see updates.")
