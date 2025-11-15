import os
import time
import re
import sqlite3
import pandas as pd
import fitz  # PyMuPDF
import json
import uuid
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# ===============================================================
# CONSOLIDATED HELPER FUNCTIONS (FROM BOTH NOTEBOOKS)
# ===============================================================

# ==== SELENIUM HELPERS ====

def init_driver(download_dir):
    """Initializes the Selenium WebDriver with download preferences."""
    options = Options()
    # Run in "headless" mode (no browser window) which is essential for servers
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
    })
    
    try:
        # --- Plan A: Try the automatic method first ---
        print("Attempting to automatically install/update chromedriver via webdriver-manager...")
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("ChromeDriver is up-to-date and driver is initialized automatically.")
        return driver
        
    except Exception as e1:
        print(f"Warning: webdriver-manager failed ({e1}).")
        print("--- Falling back to Plan B: Manual chromedriver in PATH ---")
        try:
            # --- Plan B: Try the manual method (requires chromedriver in PATH) ---
            driver = webdriver.Chrome(options=options)
            print("Successfully initialized driver using manual chromedriver in PATH.")
            return driver
        except Exception as e2:
            print(f"ERROR: Both automatic and manual methods failed.")
            print(f"Automatic error: {e1}")
            print(f"Manual error: {e2}")
            print("Please ensure you are either online (for automatic) or have 'chromedriver' in your system's PATH (for manual).")
            return None

def wait_for_downloads_to_complete(directory, timeout=300):
    """Waits for all .crdownload files in a directory to disappear."""
    seconds = 0
    while seconds < timeout:
        crdownload_files = [f for f in os.listdir(directory) if f.endswith('.crdownload')]
        if not crdownload_files:
            time.sleep(2) # Give a 2-sec buffer for file to be fully written
            return True
        seconds += 1
        time.sleep(1)
    return False

# ==== PDF PARSING HELPER ====

def extract_text_from_pdf(pdf_path):
    """Extracts all text from a given PDF file."""
    try:
        doc = fitz.open(pdf_path)
        # Use the sorted text extraction
        return "".join(page.get_text("text", sort=True) for page in doc)
    except Exception as e:
        print(f"Warning: Failed to parse {pdf_path}: {e}")
        return ""

# ==== METADATA PARSER FUNCTIONS (Notebook 1) ====

def clean_name_meta(name):
    if not name: return ""
    return name.strip().split(" on ")[0].strip()

def extract_judgment_date_meta(text):
    matches1 = re.findall(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", text)
    matches2 = re.findall(r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b", text, re.IGNORECASE)
    dates = []
    try:
        for d in matches1:
            dates.append(datetime.strptime(d.replace('.', '/').replace('-', '/'), "%d/%m/%Y"))
        for d in matches2:
            dates.append(datetime.strptime(d, "%B %d, %Y"))
        return max(dates).strftime("%d-%m-%Y") if dates else "Not Found"
    except:
        return "Not Found"

def parse_case_info(text, file):
    court_name = "Not Found"
    if "Supreme Court of India" in text:
        court_name = "Supreme Court of India"
    elif "High Court of Judicature at Madras" in text:
        court_name = "High Court of Judicature at Madras"

    case_number = "Not Found"
    patterns = [
        r"W\.P\.\(MD\)No\.\s*([\d\s&,]+\s+of\s+\d{4})",
        r"C\.M\.A\.No\.\s*([\d\s&,]+\s+of\s+\d{4})",
        r"CIVIL\s+APPEAL\s+NO\.\s*(\d+\s+OF\s+\d{4})",
        r"Special\s+Leave\s+to\s+Appeal\s+\(C\)\s+No\(s\)\.\s*(\d+/\d{4})"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            case_number = match.group(1).strip()
            break
            
    petitioner_match = re.search(r"\n(.*?)\s+(?:VERSUS|\.\.\.PETITIONER\(S\)|vs|\.\.APPELLANT\(S\))\s*\n", text, re.DOTALL | re.IGNORECASE)
    respondent_match = re.search(r"\n.*?\s+(?:VERSUS|vs)\s*\n(.*?)\s+(?:\.\.\.RESPONDENT\(S\)|CORAM)", text, re.DOTALL | re.IGNORECASE)
    petitioner = clean_name_meta(petitioner_match.group(1).strip()) if petitioner_match else "Not Found"
    respondent = clean_name_meta(respondent_match.group(1).strip()) if respondent_match else "Not Found"

    judges = "Not Found"
    coram_match = re.search(r"(?:Coram|CORAM)\s*:?\s*\n(.*?)(?=\n\w|\n\n)", text, re.DOTALL)
    if coram_match:
        judges = ' '.join(coram_match.group(1).strip().split())
    else:
        judge_list = re.findall(r"HON'BLE\s+MR\.?\s*JUSTICE\s+([A-Z\.\s\w]+)", text)
        if judge_list:
            judges = " & ".join([j.strip() for j in judge_list])

    return {
        "File Name": file, "Court Name": court_name, "Case Number": case_number,
        "Petitioner": petitioner, "Respondent": respondent,
        "Judgment Date": extract_judgment_date_meta(text), "Judges": judges,
        "Timestamp": datetime.now().isoformat()
    }

# ==== DATABASE AND LOGGING (Notebook 1) ====
def init_db(db_path):
    conn = sqlite3.connect(db_path)
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
    cursor.execute('''
        INSERT INTO cases (file_name, court_name, case_number, petitioner, respondent, judgment_date, judges, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data["File Name"], data["Court Name"], data["Case Number"], data["Petitioner"],
        data["Respondent"], data["Judgment Date"], data["Judges"], data["Timestamp"]
    ))

def export_logs(records, excel_path):
    if not records:
        print("No records to export.")
        return
    df = pd.DataFrame(records)
    df.to_excel(excel_path, index=False)


# ==== ADVANCED SECTION PARSER FUNCTIONS (Notebook 2) ====
SECTION_KEYWORDS = {
    "facts_of_case": ["Facts of the case", "Factual Background", "The Prosecution Story", "The facts", "Factual Matrix", "Brief facts", "Case of the Prosecution", "Background", "Factual background", "Facts in brief"],
    "legal_issues": ["Issues", "Issues for consideration", "Points for determination", "Legal issues", "Questions of law", "Issues involved", "Points involved"],
    "petitioner_arguments": ["Arguments of the Petitioner", "Petitioner's Arguments", "Arguments on behalf of the appellant", "Submissions of the learned counsel for the petitioner", "contentions of the petitioner", "Case for the petitioner", "Petitioner's case", "Appellant's arguments"],
    "respondent_arguments": ["Arguments of the Respondent", "Respondent's Arguments", "Arguments on behalf of the respondent", "Submissions of the learned counsel for the respondent", "contentions of the respondent", "Case for the respondent", "Respondent's case"],
    "judgment_analysis": ["Analysis by the Court", "Court's Analysis", "Reasoning", "Court's findings", "Discussion", "Consideration of the Court", "Reasons for the decision", "Analysis and decision", "Court's reasoning"],
    "outcome": ["Conclusion", "Held", "Final Order", "Order", "For the aforesaid reasons", "In the result", "Judgment", "Decision", "Disposed of", "Allowed", "Dismissed"],
    "citations": ["Relied upon", "Cases cited", "Authorities relied upon", "Citations", "Case law", "Precedents", "Legal authorities"],
    "sections_acts_cited": ["Provisions of law", "Legal provisions", "Statutory provisions", "Under section", "Section", "Act", "Rule", "Regulation"]
}
METADATA_PATTERNS = {
    "court": re.compile(r"IN THE (?:HIGH COURT|SUPREME COURT|DISTRICT COURT) OF (.*?)\n", re.IGNORECASE),
    "parties": re.compile(r"(.+?)\s+(?:VERSUS|VS\.?|V\.?)\s+(.+?)(?:\n\s*Coram|\n\s*JUDGMENT|\n\s*BEFORE)", re.IGNORECASE | re.DOTALL),
    "judge_name": re.compile(r"(?:CORAM|BEFORE)\s*:\s*(?:THE\s+)?(?:HON'BLE\s+)?(?:MR\.?\s+|MRS\.?\s+|MS\.?\s+)?(?:JUSTICE\s+)?(.*?)\n", re.IGNORECASE),
    "case_number": re.compile(r"((?:CRIMINAL|CIVIL|WRIT|MISCELLANEOUS|SPECIAL)\s+(?:APPEAL|PETITION|APPLICATION|CASE)\s+NO\.?\s+\d+(?:/\d+)?\s+OF\s+\d{4})", re.IGNORECASE),
    "date": re.compile(r"(?:DATED|DECIDED ON|PRONOUNCED ON)\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4}|\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE),
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
def extract_date(text):
    header_text = text[:3000]
    date_patterns = [r"(?:DATED|DECIDED ON|PRONOUNCED ON)\s*:?\s*(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})", r"(?:DATED|DECIDED ON|PRONOUNCED ON)\s*:?\s*(\d{1,2}\s+\w+\s+\d{4})", r"(\d{1,2}[-/.]\d{1,2}[-/.]\d{4})", r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})"]
    for pattern in date_patterns:
        match = re.search(pattern, header_text, re.IGNORECASE)
        if match: return match.group(1).strip()
    return "Not Found"
def extract_sections_acts(text):
    sections = set()
    section_patterns = [r"Section\s+(\d+(?:\([a-z0-9]+\))?)\s+of\s+(?:the\s+)?([^.]+(?:Act|Code|Rules?))", r"(?:under\s+)?Section\s+(\d+(?:\([a-z0-9]+\))?)", r"Article\s+(\d+(?:\([a-z0-9]+\))?)"]
    for pattern in section_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match.groups()) > 1: sections.add(f"Section {match.group(1)} of {match.group(2).strip()}")
            else: sections.add(f"Section {match.group(1)}")
    return list(sections)[:10] if sections else ["Not Found"]
def extract_citations(text):
    citations = set()
    citation_patterns = [r"(\w+(?:\s+\w+)*)\s+v\.?\s+(\w+(?:\s+\w+)*)\s+\((\d{4})\)", r"(\d{4})\s+\((\d+)\)\s+([A-Z]+)\s+(\d+)", r"AIR\s+(\d{4})\s+([A-Z]+)\s+(\d+)"]
    for pattern in citation_patterns:
        matches = re.finditer(pattern, text)
        for match in matches: citations.add(match.group().strip())
    return list(citations)[:15] if citations else ["Not Found"]
def determine_outcome(text):
    conclusion_text = text[-2000:].lower()
    for outcome, pattern in OUTCOME_PATTERNS.items():
        if pattern.search(conclusion_text): return outcome.replace("_", " ").title()
    return "Not determined"
def extract_appeal_history(text):
    appeal_indicators = ["appeal from", "revision petition", "writ petition", "special leave petition", "appealed against", "challenged the order", "impugned order"]
    for indicator in appeal_indicators:
        if re.search(indicator, text, re.IGNORECASE): return "Yes"
    return "No"
def extract_comprehensive_metadata(text, filename):
    metadata = {"case_id": generate_case_id(), "court": "Not Found", "date_judgment": "Not Found", "parties": {"petitioner": "Not Found", "respondent": "Not Found"}, "case_type": "Not Found", "sections_acts_cited": [], "summary": "Not Found", "outcome": "Not Found", "judges": [], "source_url": "Not Found", "language": "English", "legal_issues": [], "citations": [], "appeal_history": "Not Found", "publication_reporter": "Not Found"}
    header_text = text[:4000]
    parties_match = METADATA_PATTERNS["parties"].search(header_text)
    if parties_match:
        petitioner = ' '.join(parties_match.group(1).replace('\n', ' ').split()); respondent = ' '.join(parties_match.group(2).replace('\n', ' ').split())
        metadata["parties"]["petitioner"] = petitioner; metadata["parties"]["respondent"] = respondent
    for key, pattern in METADATA_PATTERNS.items():
        if key == "parties": continue
        match = pattern.search(header_text)
        if match:
            if key == "court": metadata["court"] = f"High Court of {match.group(1).strip()}"
            elif key == "judge_name": metadata["judges"] = [match.group(1).strip()]
            elif key == "case_number": metadata["case_id"] = match.group(1).strip()
            elif key == "case_type": metadata["case_type"] = match.group(1).strip().title()
    metadata["date_judgment"] = extract_date(text); metadata["sections_acts_cited"] = extract_sections_acts(text); metadata["citations"] = extract_citations(text); metadata["outcome"] = determine_outcome(text); metadata["appeal_history"] = extract_appeal_history(text)
    if len(text) > 1000: summary_text = text[1000:1500].strip(); metadata["summary"] = ' '.join(summary_text.split())[:500] + "..."
    metadata["source_url"] = filename
    return metadata
def parse_judgment_sections_optimized(text):
    found_sections = []; keyword_to_section_map = {}; all_keywords = []
    for section_name, keywords in SECTION_KEYWORDS.items():
        for kw in keywords: keyword_to_section_map[kw.lower()] = section_name; all_keywords.append(re.escape(kw))
    master_keyword_regex = "|".join(all_keywords); pattern = re.compile(r"^[ \t]*(?:\d+\.?\s*)?(" + master_keyword_regex + r")[ \t]*[:.-]?", re.IGNORECASE | re.MULTILINE)
    for match in pattern.finditer(text):
        matched_keyword = match.group(1).lower(); section_name = keyword_to_section_map[matched_keyword]
        found_sections.append({'name': section_name, 'start': match.start(), 'end': match.end()})
    if not found_sections: return {key: "Not Found" for key in SECTION_KEYWORDS}
    found_sections.sort(key=lambda x: x['start']); unique_sections = []
    if found_sections:
        unique_sections.append(found_sections[0])
        for i in range(1, len(found_sections)):
            if found_sections[i]['start'] >= unique_sections[-1]['end']: unique_sections.append(found_sections[i])
    extracted_data = {}
    for i, section in enumerate(unique_sections):
        section_name, start_index = section['name'], section['end']; end_index = unique_sections[i+1]['start'] if i + 1 < len(unique_sections) else len(text)
        content = re.sub(r'\s+', ' ', text[start_index:end_index].strip()).strip()
        if len(content) > 5000: content = content[:5000] + "..."
        extracted_data[section_name] = content
    for section_name in SECTION_KEYWORDS:
        if section_name not in extracted_data: extracted_data[section_name] = "Not Found"
    return extracted_data


# ===============================================================
# --- MAIN "RUNNER" FUNCTIONS (Called by Flask) ---
# ===============================================================

def run_crawling(config, user_url, max_pages):
    """
    Main function to execute the crawling and downloading stage.
    """
    download_dir = config['DOWNLOAD_DIR']
    print(f"--- Starting Stage 1: Crawling & Downloading ---")
    print(f"Downloading to: {download_dir}")
    
    driver = init_driver(download_dir)
    if not driver:
        return {"status": "error", "message": "Failed to initialize WebDriver. Check 'chromedriver'."}

    all_case_links = set()
    log = []
    
    try:
        driver.get(user_url)
        for page in range(1, max_pages + 1):
            msg = f"📄 Scraping page {page}..."
            print(msg); log.append(msg)
            time.sleep(2)
            links_on_page = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/doc/"]')
            all_case_links.update(a.get_attribute("href") for a in links_on_page)
            
            try:
                next_button = driver.find_element(By.LINK_TEXT, str(page + 1))
                next_button.click()
            except Exception:
                msg = "⚠️ No more pages found."; print(msg); log.append(msg)
                break
        
        msg = f"🔗 Found {len(all_case_links)} unique case links. Starting downloads..."
        print(msg); log.append(msg)
        
        downloaded_count = 0
        for idx, link in enumerate(list(all_case_links), start=1):
            try:
                driver.get(link)
                download_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.ID, 'pdfdoc')))
                download_button.click()
                
                msg = f"     Waiting for download: {link}"; print(msg); log.append(msg)
                if wait_for_downloads_to_complete(download_dir):
                    msg = f"     ✅ Download complete for: {link}"; print(msg); log.append(msg)
                    downloaded_count += 1
                else:
                    msg = f"     ⚠️ Download timed out for: {link}"; print(msg); log.append(msg)

            except TimeoutException:
                msg = f"     ❌ Page timed out: {link}. Skipping."; print(msg); log.append(msg)
            except Exception as e:
                msg = f"     ❌ Error on page {link}: {e}. Skipping."; print(msg); log.append(msg)

        final_msg = f"Stage 1 Complete: {downloaded_count} / {len(all_case_links)} PDFs downloaded."
        return {"status": "success", "message": final_msg, "log": log}

    except Exception as e:
        return {"status": "error", "message": f"An error occurred: {str(e)}", "log": log}
    finally:
        driver.quit()

def run_meta_parsing(config):
    """
    Main function to execute the metadata parsing stage.
    """
    download_dir = config['DOWNLOAD_DIR']
    db_path = config['DB_PATH']
    excel_path = config['EXCEL_PATH']
    
    print(f"--- Starting Stage 2: Parse Basic Metadata ---")
    log = []
    pdf_files = [f for f in os.listdir(download_dir) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        return {"status": "error", "message": f"No PDF files found in '{download_dir}'. Run Stage 1 first."}

    conn = init_db(db_path)
    cursor = conn.cursor()
    all_records = []
    
    for idx, file in enumerate(pdf_files, start=1):
        file_path = os.path.join(download_dir, file)
        text = extract_text_from_pdf(file_path)
        
        if text:
            data = parse_case_info(text, file) # From Notebook 1
            save_to_db(cursor, data)
            all_records.append(data)
            msg = f"✅ Processed: {file}"; print(msg); log.append(msg)
        else:
            msg = f"❌ Failed to read: {file}"; print(msg); log.append(msg)
    
    conn.commit()
    conn.close()
    export_logs(all_records, excel_path)
    
    final_msg = f"Basic metadata parsing complete! {len(all_records)} files processed. Saved to DB and Excel."
    return {"status": "success", "message": final_msg, "log": log, "data": all_records}


def run_section_parsing(config):
    """
    Main function to execute the advanced section parsing stage.
    """
    download_dir = config['DOWNLOAD_DIR']
    json_path = config['JSON_COMPREHENSIVE_PATH']
    
    print(f"--- Starting Stage 3: Parse Document Sections (Advanced) ---")
    log = []
    pdf_files = [f for f in os.listdir(download_dir) if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        return {"status": "error", "message": f"No PDF files found in '{download_dir}'. Run Stage 1 first."}
    
    all_cases_data = {}
    for idx, filename in enumerate(pdf_files, start=1):
        file_path = os.path.join(download_dir, filename)
        full_text = extract_text_from_pdf(file_path)
        
        if not full_text:
            msg = f"❌ Failed to read: {filename}"; print(msg); log.append(msg)
            continue

        case_metadata = extract_comprehensive_metadata(full_text, filename)
        parsed_sections = parse_judgment_sections_optimized(full_text)
        
        judgment_text = full_text[:10000] + "..." if len(full_text) > 10000 else full_text

        case_data = {
            **case_metadata,
            "facts_of_case": parsed_sections.get("facts_of_case", "Not Found"),
            "judgment_text": judgment_text,
            "petitioners_arguments": parsed_sections.get("petitioner_arguments", "Not Found"),
            "respondents_arguments": parsed_sections.get("respondent_arguments", "Not Found"),
            "judgment_analysis": parsed_sections.get("judgment_analysis", "Not Found"),
            "outcome_section": parsed_sections.get("outcome", "Not Found")
        }

        petitioner = case_data["parties"]["petitioner"]
        respondent = case_data["parties"]["respondent"]
        case_key = f"{petitioner} vs {respondent}" if petitioner != "Not Found" and respondent != "Not Found" else filename
        
        all_cases_data[case_key] = case_data
        msg = f"✅ Advanced processing complete: {filename}"; print(msg); log.append(msg)

    if all_cases_data:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_cases_data, f, indent=2, ensure_ascii=False)
        
        final_msg = f"Advanced parsing complete! Data saved to '{json_path}'."
        
        # --- Create Summary ---
        case_types = {}
        outcomes = {}
        for case_data in all_cases_data.values():
            case_type = case_data.get("case_type", "Unknown")
            outcome = case_data.get("outcome", "Unknown")
            case_types[case_type] = case_types.get(case_type, 0) + 1
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        summary = {
            "total_processed": len(all_cases_data),
            "case_types": case_types,
            "outcomes": outcomes
        }
        return {"status": "success", "message": final_msg, "log": log, "data": list(all_cases_data.values())[:5], "summary": summary}
    else:
        return {"status": "error", "message": "No data was successfully processed.", "log": log}