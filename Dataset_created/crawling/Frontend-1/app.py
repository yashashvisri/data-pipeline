import os
import time
import re
import sqlite3
import pandas as pd
import fitz  # PyMuPDF
import json
import uuid
import streamlit as st
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ==============================================================================
# ==== 1. CONFIGURATION ====
# ==============================================================================
# We'll make paths relative to the app's directory for portability
BASE_DIR = os.getcwd()
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloaded_pdfs")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(OUTPUT_DIR, "kanoon_cases.db")
EXCEL_PATH = os.path.join(OUTPUT_DIR, "audit_log.xlsx")
JSON_PATH = os.path.join(OUTPUT_DIR, "comprehensive_legal_cases.json")

# Create directories if they don't exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ==============================================================================
# ==== 2. SHARED HELPER FUNCTIONS (From both notebooks) ====
# ==============================================================================

# --- SELENIUM HELPERS ---

def init_driver():
    """Initializes the Selenium WebDriver with download preferences."""
    options = Options()
    # options.add_argument("--headless=new") # Uncomment to run without a browser window
    options.add_experimental_option("prefs", {
        "download.default_directory": DOWNLOAD_DIR,
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
    })
    
    # Use webdriver-manager to automatically handle the driver
    st.toast("Installing/Updating ChromeDriver...")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60) 
    return driver

def wait_for_downloads_to_complete(directory, timeout=300):
    """Waits for all .crdownload files in a directory to disappear."""
    seconds = 0
    while seconds < timeout:
        crdownload_files = [f for f in os.listdir(directory) if f.endswith('.crdownload')]
        if not crdownload_files:
            time.sleep(2)  # Give a slight buffer for file system to catch up
            return True
        seconds += 1
        time.sleep(1)
    return False

# --- PDF & TEXT HELPERS ---

def extract_text_from_pdf(pdf_path):
    """Extracts all text from a given PDF file using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        # Use get_text("text", sort=True) for better reading order
        return "".join(page.get_text("text", sort=True) for page in doc)
    except Exception as e:
        st.error(f"Failed to parse {pdf_path}: {e}")
        return ""

def clean_name(name):
    """Helper function to clean extracted names."""
    if not name: return ""
    return name.strip().split(" on ")[0].strip()

# --- DATABASE AND LOGGING HELPERS ---

@st.cache_resource
def init_db():
    """Initializes the SQLite database with the correct table structure."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, file_name TEXT, court_name TEXT, 
            case_number TEXT, petitioner TEXT, respondent TEXT, judgment_date TEXT, 
            judges TEXT, timestamp TEXT
        )''')
    conn.commit()
    return conn

def save_to_db(cursor, data):
    """Saves a dictionary of case data to the database."""
    cursor.execute('''
        INSERT INTO cases (file_name, court_name, case_number, petitioner, respondent, judgment_date, judges, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data["File Name"], data["Court Name"], data["Case Number"], data["Petitioner"],
        data["Respondent"], data["Judgment Date"], data["Judges"], data["Timestamp"]
    ))

def export_logs(records):
    """Exports a list of dictionaries to Excel."""
    if not records:
        st.warning("No records to export to Excel.")
        return
    df = pd.DataFrame(records)
    df.to_excel(EXCEL_PATH, index=False)
    st.toast(f"Logs saved to: {EXCEL_PATH}")


# ==============================================================================
# ==== 3. CRAWLER LOGIC (Stage 1) ====
# ==============================================================================

def run_crawler(base_url, max_pages, status_container):
    """
    Main crawling function.
    Logs its progress to the Streamlit `status_container`.
    """
    try:
        driver = init_driver()
        status_container.update(label="WebDriver initialized. Starting crawl...")
    except Exception as e:
        st.error(f"Failed to initialize WebDriver. Is Chrome installed? Error: {e}")
        status_container.update(label="Error!", state="error")
        return

    driver.get(base_url)
    all_case_links = set()
    
    for page in range(1, max_pages + 1):
        status_container.update(label=f"Scraping page {page}/{max_pages}...")
        time.sleep(2)  # Be polite to the server
        try:
            links_on_page = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/doc/"]')
            all_case_links.update(a.get_attribute("href") for a in links_on_page)
            
            if page < max_pages:
                next_button = driver.find_element(By.LINK_TEXT, str(page + 1))
                next_button.click()
            status_container.write(f"Found {len(links_on_page)} links on page {page}.")
        except Exception as e:
            status_container.write(f"⚠️ No more pages found or error clicking next: {e}")
            break
    
    status_container.update(label=f"Found {len(all_case_links)} unique links. Starting downloads...")
    
    for idx, link in enumerate(all_case_links, start=1):
        progress_text = f"Downloading PDF {idx}/{len(all_case_links)}"
        status_container.update(label=progress_text)
        try:
            driver.get(link)
            download_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'pdfdoc')))
            download_button.click()
            
            if wait_for_downloads_to_complete(DOWNLOAD_DIR, 60): # 60 sec timeout per file
                status_container.write(f"✅ Download complete for: {link}")
            else:
                status_container.write(f"⚠️ Download timed out for: {link}")
        
        except TimeoutException:
            status_container.write(f"❌ Page timed out: {link}. Skipping.")
        except Exception as e:
            status_container.write(f"❌ Error on page {link}: {e}. Skipping.")
    
    driver.quit()
    status_container.update(label="Crawling and downloading complete!", state="complete")


# ==============================================================================
# ==== 4. PARSER LOGIC (Stage 2 & 3) ====
# ==============================================================================

# --- Parser A: Simple Metadata Parser (from Scrapping_pdfs_crawling.ipynb) ---

def extract_judgment_date_simple(text):
    """Finds dates and returns the most likely judgment date."""
    matches1 = re.findall(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", text)
    matches2 = re.findall(r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b", text, re.IGNORECASE)
    dates = []
    try:
        for d in matches1: dates.append(datetime.strptime(d.replace('.', '/').replace('-', '/'), "%d/%m/%Y"))
        for d in matches2: dates.append(datetime.strptime(d, "%B %d, %Y"))
        return max(dates).strftime("%d-%m-%Y") if dates else "Not Found"
    except:
        return "Not Found"

def parse_case_info_simple(text, file):
    """Parses text to find basic case details."""
    court_name = "Not Found"
    if "Supreme Court of India" in text: court_name = "Supreme Court of India"
    elif "High Court of Judicature at Madras" in text: court_name = "High Court of Judicature at Madras"

    case_number = "Not Found"
    patterns = [
        r"W\.P\.\(MD\)No\.\s*([\d\s&,]+\s+of\s+\d{4})", r"C\.M\.A\.No\.\s*([\d\s&,]+\s+of\s+\d{4})",
        r"CIVIL\s+APPEAL\s+NO\.\s*(\d+\s+OF\s+\d{4})", r"Special\s+Leave\s+to\s+Appeal\s+\(C\)\s+No\(s\)\.\s*(\d+/\d{4})"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            case_number = match.group(1).strip()
            break
            
    pet_match = re.search(r"\n(.*?)\s+(?:VERSUS|\.\.\.PETITIONER\(S\)|vs|\.\.APPELLANT\(S\))\s*\n", text, re.DOTALL | re.IGNORECASE)
    res_match = re.search(r"\n.*?\s+(?:VERSUS|vs)\s*\n(.*?)\s+(?:\.\.\.RESPONDENT\(S\)|CORAM)", text, re.DOTALL | re.IGNORECASE)
    petitioner = clean_name(pet_match.group(1).strip()) if pet_match else "Not Found"
    respondent = clean_name(res_match.group(1).strip()) if res_match else "Not Found"

    judges = "Not Found"
    coram_match = re.search(r"(?:Coram|CORAM)\s*:?\s*\n(.*?)(?=\n\w|\n\n)", text, re.DOTALL)
    if coram_match:
        judges = ' '.join(coram_match.group(1).strip().split())
    else:
        judge_list = re.findall(r"HON'BLE\s+MR\.?\s*JUSTICE\s+([A-Z\.\s\w]+)", text)
        if judge_list: judges = " & ".join([j.strip() for j in judge_list])

    return {
        "File Name": file, "Court Name": court_name, "Case Number": case_number,
        "Petitioner": petitioner, "Respondent": respondent,
        "Judgment Date": extract_judgment_date_simple(text), "Judges": judges,
        "Timestamp": datetime.now().isoformat()
    }

def run_metadata_parser(progress_bar):
    """Runs the simple metadata parser on all PDFs in DOWNLOAD_DIR."""
    conn = init_db()
    cursor = conn.cursor()
    audit_records = []
    pdf_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.lower().endswith(".pdf")]
    
    for i, filename in enumerate(pdf_files):
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        full_text = extract_text_from_pdf(file_path)
        
        if full_text:
            data = parse_case_info_simple(full_text, filename)
            save_to_db(cursor, data)
            audit_records.append(data)
        
        progress_bar.progress((i + 1) / len(pdf_files), text=f"Parsing metadata: {filename}")
    
    conn.commit()
    conn.close()
    export_logs(audit_records)
    progress_bar.empty()
    st.success(f"Successfully parsed metadata for {len(audit_records)} files.")
    st.info(f"Data saved to `{DB_PATH}` and `{EXCEL_PATH}`.")


# --- Parser B: Comprehensive Parser (from parser_func.ipynb, Cell 5) ---

SECTION_KEYWORDS = {
    "facts_of_case": ["Facts of the case", "Factual Background", "The Prosecution Story", "The facts", "Factual Matrix", "Brief facts", "Case of the Prosecution"],
    "legal_issues": ["Issues", "Issues for consideration", "Points for determination", "Legal issues", "Questions of law"],
    "petitioner_arguments": ["Arguments of the Petitioner", "Petitioner's Arguments", "Arguments on behalf of the appellant", "Submissions of the learned counsel for the petitioner"],
    "respondent_arguments": ["Arguments of the Respondent", "Respondent's Arguments", "Arguments on behalf of the respondent", "Submissions of the learned counsel for the respondent"],
    "judgment_analysis": ["Analysis by the Court", "Court's Analysis", "Reasoning", "Court's findings", "Discussion", "Consideration of the Court"],
    "outcome": ["Conclusion", "Held", "Final Order", "Order", "For the aforesaid reasons", "In the result", "Judgment", "Decision"],
    "citations": ["Relied upon", "Cases cited", "Authorities relied upon", "Citations", "Case law"],
    "sections_acts_cited": ["Provisions of law", "Legal provisions", "Statutory provisions", "Under section", "Section", "Act", "Rule"]
}

METADATA_PATTERNS = {
    "court": re.compile(r"IN THE (?:HIGH COURT|SUPREME COURT|DISTRICT COURT) OF (.*?)\n", re.IGNORECASE),
    "parties": re.compile(r"(.+?)\s+(?:VERSUS|VS\.?|V\.)\s+(.+?)(?:\n\s*Coram|\n\s*JUDGMENT|\n\s*BEFORE)", re.IGNORECASE | re.DOTALL),
    "judge_name": re.compile(r"(?:CORAM|BEFORE)\s*:\s*(?:THE\s+)?(?:HON'BLE\s+)?(?:MR\.?\s+|MRS\.?\s+|MS\.?\s+)?(?:JUSTICE\s+)?(.*?)\n", re.IGNORECASE),
    "case_number": re.compile(r"((?:CRIMINAL|CIVIL|WRIT|MISCELLANEOUS|SPECIAL)\s+(?:APPEAL|PETITION|APPLICATION|CASE)\s+NO\.?\s+\d+(?:/\d+)?\s+OF\s+\d{4})", re.IGNORECASE),
    "case_type": re.compile(r"(CRIMINAL|CIVIL|WRIT|MISCELLANEOUS|SPECIAL|TAX|CONSTITUTIONAL|MATRIMONIAL)", re.IGNORECASE)
}

OUTCOME_PATTERNS = {
    "allowed": re.compile(r"\b(?:petition|appeal|application)\s+(?:is\s+)?(?:allowed|granted)\b", re.IGNORECASE),
    "dismissed": re.compile(r"\b(?:petition|appeal|application)\s+(?:is\s+)?dismissed\b", re.IGNORECASE),
    "acquitted": re.compile(r"\b(?:accused|defendant)\s+(?:is\s+)?acquitted\b", re.IGNORECASE),
    "convicted": re.compile(r"\b(?:accused|defendant)\s+(?:is\s+)?(?:convicted|found guilty)\b", re.IGNORECASE),
    "partly_allowed": re.compile(r"\b(?:petition|appeal)\s+(?:is\s+)?(?:partly|partially)\s+allowed\b", re.IGNORECASE)
}

def generate_case_id(): return str(uuid.uuid4())[:8].upper()

def extract_date_comprehensive(text):
    header_text = text[:3000]
    patterns = [
        r"(?:DATED|DECIDED ON|PRONOUNCED ON)\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
        r"(?:DATED|DECIDED ON|PRONOUNCED ON)\s*:?\s*(\d{1,2}\s+\w+\s+\d{4})",
        r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})",
        r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"
    ]
    for pattern in patterns:
        match = re.search(pattern, header_text, re.IGNORECASE)
        if match: return match.group(1).strip()
    return "Not Found"

def extract_sections_acts(text):
    sections = set()
    patterns = [
        r"Section\s+(\d+(?:\([a-z0-9]+\))?)\s+of\s+(?:the\s+)?([^.]+(?:Act|Code|Rules?))",
        r"(?:under\s+)?Section\s+(\d+(?:\([a-z0-9]+\))?)",
        r"Article\s+(\d+(?:\([a-z0-9]+\))?)"
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if len(match.groups()) > 1: sections.add(f"Section {match.group(1)} of {match.group(2).strip()}")
            else: sections.add(f"Section {match.group(1)}")
    return list(sections)[:10] if sections else ["Not Found"]

def extract_citations(text):
    citations = set()
    patterns = [
        r"(\w+(?:\s+\w+)*)\s+v\.?\s+(\w+(?:\s+\w+)*)\s+\((\d{4})\)",
        r"(\d{4})\s+\((\d+)\)\s+([A-Z]+)\s+(\d+)",
        r"AIR\s+(\d{4})\s+([A-Z]+)\s+(\d+)"
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            citations.add(match.group().strip())
    return list(citations)[:15] if citations else ["Not Found"]

def determine_outcome(text):
    conclusion_text = text[-2000:].lower()
    for outcome, pattern in OUTCOME_PATTERNS.items():
        if pattern.search(conclusion_text):
            return outcome.replace("_", " ").title()
    return "Not determined"

def extract_comprehensive_metadata(text, filename):
    metadata = {
        "case_id": generate_case_id(), "court": "Not Found", "date_judgment": "Not Found",
        "parties": {"petitioner": "Not Found", "respondent": "Not Found"},
        "case_type": "Not Found", "sections_acts_cited": [], "summary": "Not Found",
        "outcome": "Not Found", "judges": [], "source_url": filename, "language": "English",
        "legal_issues": [], "citations": [],
    }
    header_text = text[:4000]

    parties_match = METADATA_PATTERNS["parties"].search(header_text)
    if parties_match:
        metadata["parties"]["petitioner"] = ' '.join(parties_match.group(1).replace('\n', ' ').split())
        metadata["parties"]["respondent"] = ' '.join(parties_match.group(2).replace('\n', ' ').split())

    for key, pattern in METADATA_PATTERNS.items():
        if key == "parties": continue
        match = pattern.search(header_text)
        if match:
            if key == "court": metadata["court"] = f"High Court of {match.group(1).strip()}"
            elif key == "judge_name": metadata["judges"] = [match.group(1).strip()]
            elif key == "case_number": metadata["case_id"] = match.group(1).strip()
            elif key == "case_type": metadata["case_type"] = match.group(1).strip().title()

    metadata["date_judgment"] = extract_date_comprehensive(text)
    metadata["sections_acts_cited"] = extract_sections_acts(text)
    metadata["citations"] = extract_citations(text)
    metadata["outcome"] = determine_outcome(text)
    if len(text) > 1000: metadata["summary"] = ' '.join(text[1000:1500].strip().split())[:500] + "..."
    
    return metadata

def parse_judgment_sections_optimized(text):
    found_sections = []
    keyword_to_section_map = {}
    all_keywords = []

    for section_name, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            keyword_to_section_map[kw.lower()] = section_name
            all_keywords.append(re.escape(kw))

    master_keyword_regex = "|".join(all_keywords)
    pattern = re.compile(r"^[ \t]*(?:\d+\.?\s*)?(" + master_keyword_regex + r")[ \t]*[:.-]?", re.IGNORECASE | re.MULTILINE)

    for match in pattern.finditer(text):
        section_name = keyword_to_section_map[match.group(1).lower()]
        found_sections.append({'name': section_name, 'start': match.start(), 'end': match.end()})

    if not found_sections: return {key: "Not Found" for key in SECTION_KEYWORDS}
    found_sections.sort(key=lambda x: x['start'])
    
    unique_sections = []
    if found_sections:
        unique_sections.append(found_sections[0])
        for i in range(1, len(found_sections)):
            if found_sections[i]['start'] >= unique_sections[-1]['end']:
                unique_sections.append(found_sections[i])

    extracted_data = {}
    for i, section in enumerate(unique_sections):
        section_name, start_index = section['name'], section['end']
        end_index = unique_sections[i+1]['start'] if i + 1 < len(unique_sections) else len(text)
        content = re.sub(r'\s+', ' ', text[start_index:end_index].strip()).strip()
        if len(content) > 5000: content = content[:5000] + "..." # Limit content length
        extracted_data[section_name] = content

    for section_name in SECTION_KEYWORDS:
        if section_name not in extracted_data:
            extracted_data[section_name] = "Not Found"
    return extracted_data

def run_comprehensive_parser(progress_bar):
    """Runs the comprehensive parser on all PDFs in DOWNLOAD_DIR."""
    all_cases_data = {}
    pdf_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.lower().endswith(".pdf")]
    
    for i, filename in enumerate(pdf_files):
        progress_bar.progress((i + 1) / len(pdf_files), text=f"Comprehensively parsing: {filename}")
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        full_text = extract_text_from_pdf(file_path)
        if not full_text: continue

        case_metadata = extract_comprehensive_metadata(full_text, filename)
        parsed_sections = parse_judgment_sections_optimized(full_text)
        
        judgment_text = full_text[:10000] + "..." if len(full_text) > 10000 else full_text
        
        case_data = {
            **case_metadata,
            "facts_of_case": parsed_sections.get("facts_of_case", "Not Found"),
            "judgment_text": judgment_text,
            "petitioners_arguments": parsed_sections.get("petitioner_arguments", "Not Found"),
            "respondents_arguments": parsed_sections.get("respondent_arguments", "Not Found")
        }
        
        petitioner = case_data["parties"]["petitioner"]
        respondent = case_data["parties"]["respondent"]
        case_key = f"{petitioner} vs {respondent}" if petitioner != "Not Found" else filename
        all_cases_data[case_key] = case_data

    if all_cases_data:
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_cases_data, f, indent=2, ensure_ascii=False)
        progress_bar.empty()
        st.success(f"Successfully parsed {len(all_cases_data)} cases.")
        st.info(f"Data saved to `{JSON_PATH}`.")
    else:
        st.warning("No data was processed.")


# ==============================================================================
# ==== 5. STREAMLIT UI ====
# ==============================================================================

st.set_page_config(layout="wide", page_title="Legal Doc Crawler")
st.title("⚖️ Indian Kanoon Crawler & Parser")
st.caption(f"Using download folder: `{DOWNLOAD_DIR}` | Output folder: `{OUTPUT_DIR}`")

tab1, tab2, tab3 = st.tabs(["1. Crawl & Download", "2. Parse PDFs", "3. View Results"])

# --- TAB 1: CRAWL & DOWNLOAD ---
with tab1:
    st.header("Stage 1: Crawl & Download PDFs")
    st.markdown("Enter a search URL from Indian Kanoon and the number of pages you want to scrape.")
    
    with st.form("crawl_form"):
        default_url = "https://indiankanoon.org/search/?formInput=criminal%202000%20to%202010&pagenum=4"
        url = st.text_input("Indian Kanoon Search URL", value=default_url)
        pages = st.number_input("Number of pages to scrape", min_value=1, max_value=50, value=5)
        
        submitted = st.form_submit_button("Start Crawling", type="primary")

    if submitted:
        if not url or "indiankanoon.org" not in url:
            st.error("Please enter a valid Indian Kanoon URL.")
        else:
            with st.status("Starting crawl...", expanded=True) as status:
                run_crawler(url, pages, status)

# --- TAB 2: PARSE PDFS ---
with tab2:
    st.header("Stage 2: Parse Downloaded PDFs")
    st.markdown(f"This will process all `.pdf` files found in the `{DOWNLOAD_DIR}` directory.")
    
    st.subheader("Option 1: Basic Metadata Parsing")
    st.markdown("Extracts basic info (Parties, Case No., Date) and saves to an Excel file and a SQLite database.")
    
    if st.button("Parse Metadata (to DB/Excel)"):
        pdf_count = len([f for f in os.listdir(DOWNLOAD_DIR) if f.lower().endswith(".pdf")])
        if pdf_count == 0:
            st.error(f"No PDFs found in `{DOWNLOAD_DIR}`. Please run Stage 1 first.")
        else:
            st.info(f"Found {pdf_count} PDFs to parse.")
            progress_bar = st.progress(0, text="Starting metadata parsing...")
            run_metadata_parser(progress_bar)

    st.divider()

    st.subheader("Option 2: Comprehensive Text Parsing")
    st.markdown("Performs a deep parse of the PDF text to find sections (Facts, Arguments, Outcome) and saves to a structured JSON file.")
    
    if st.button("Parse Full Text (to JSON)"):
        pdf_count = len([f for f in os.listdir(DOWNLOAD_DIR) if f.lower().endswith(".pdf")])
        if pdf_count == 0:
            st.error(f"No PDFs found in `{DOWNLOAD_DIR}`. Please run Stage 1 first.")
        else:
            st.info(f"Found {pdf_count} PDFs to parse.")
            progress_bar = st.progress(0, text="Starting comprehensive parsing...")
            run_comprehensive_parser(progress_bar)

# --- TAB 3: VIEW RESULTS ---
with tab3:
    st.header("Stage 3: View Results")
    st.markdown("Review the data extracted from the parsing stages. Click 'Refresh Data' to load new results.")

    if st.button("Refresh Data", type="primary"):
        st.cache_data.clear() # Clear cache to reload files
        st.rerun()

    # Display Excel / DB (Metadata)
    st.subheader("Metadata (from DB/Excel)")
    if os.path.exists(DB_PATH):
        try:
            conn = init_db()
            df_db = pd.read_sql_query("SELECT * FROM cases", conn)
            conn.close()
            st.dataframe(df_db)
            st.caption(f"Showing data from `{DB_PATH}`")
        except Exception as e:
            st.error(f"Could not read database: {e}")
    else:
        st.info("No database file found. Run the 'Parse Metadata' job in Tab 2.")

    # Display JSON (Comprehensive)
    st.subheader("Comprehensive JSON Output")
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                data_json = json.load(f)
            st.json(data_json, expanded=False)
            st.caption(f"Showing data from `{JSON_PATH}`. Expand to see full text.")
        except Exception as e:
            st.error(f"Could not read JSON file: {e}")
    else:
        st.info("No JSON file found. Run the 'Parse Full Text' job in Tab 2.")