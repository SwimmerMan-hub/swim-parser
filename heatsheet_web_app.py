import io
import re
import requests
import pypdf
import streamlit as st
from bs4 import BeautifulSoup

# Global timeout and connection pool handling constants
HTTP_TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SwimMeetParser/2.0"}

# App configuration optimized for scannability
st.set_page_config(page_title="SwimAtlanta Meet Parser", page_icon="🏊‍♂️", layout="centered")

# --- CACHED DISCOVERY SCRAPER (Fast Cache Pipeline) ---
@st.cache_data(ttl=1800)  # Lowers refresh threshold to 30 mins for optimal data rotation
def fetch_heatsheet_names():
    base_url = "https://swimatlanta.com"
    news_url = "https://swimatlanta.com/news"
    
    database = {
        "🏆 Splash Jam Heat Sheet": "https://swimatlanta.com/f/splashjamheatsheet.pdf",
        "🏆 AAU Lucky Splash Sunday": "https://swimatlanta.com/f/Lucky%20Splash%20Heat%20Sheets.pdf",
        "🏆 Father's Day Spectacular": "https://swimatlanta.com/f/FathersDayHeatSheet.pdf",
        "🏆 Betsy Dunbar LC Meet": "https://swimatlanta.com/f/rev1betsysatpm.pdf"
    }
    
    try:
        response = requests.get(news_url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/f/" in href and any(k in href.lower() for k in ["heatsheet", "meet", "sheet"]):
                    full_url = href if href.startswith("http") else base_url + href
                    clean_name = "🏆 " + href.split('/')[-1].replace('%20', ' ').replace('.pdf', '').title()
                    database[clean_name] = full_url
    except Exception:
        pass
    return database

# --- NEW: CRITICAL HIGH-TRAFFIC NETWORK INJECTOR (In-Memory Stream Saver) ---
@st.cache_resource(ttl=600)  # Caches raw binary data across all parents for 10 minutes
def load_remote_pdf_stream(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        if response.content and b"%PDF" in response.content[:5]:
            return response.content
    except Exception:
        pass
    return None

# --- UI WINDOW CONTENT ---
st.title("🏊‍♂️ SwimAtlanta Heat Sheet Parser")
st.write("Isolated micro-engine for automated race sheet parsing. High-concurrency cluster layout.")
st.markdown("---")

with st.spinner("🔄 Syncing SwimAtlanta database stream..."):
    MEET_DATABASE = fetch_heatsheet_names()

selected_sheet = st.selectbox("📅 Choose Your Swim Meet Session:", list(MEET_DATABASE.keys()))
TARGET_URL = MEET_DATABASE[selected_sheet]

swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="Type a name to extract schedules...")

# --- OPTIMIZED PARSING LAYER ---
if swimmer_name:
    # Clean text inputs instantly to eliminate crash variables
    clean_search_name = swimmer_name.strip().upper()
    
    # Download file once per meet block, bypassing repetitive server downloads
    pdf_bytes = load_remote_pdf_stream(TARGET_URL)
    
    if not pdf_bytes:
        st.warning(f"🔄 **Meet Sheet Notice:** SwimAtlanta server is currently updating files for **{selected_sheet}**. Please retry or switch sessions.")
    else:
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            swimmer_profiles = {}
            
            # Pre-compile structural search strings for immediate CPU execution loops
            name_pattern = re.compile(r'([A-Za-z]+,\s*[A-Za-z\s\.]+)')
            markers = ["-", "GA", "NT", ":", "."]

            # Fast Pass 1: Localized entity isolation
            for page_num, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text()
                page_text_upper = page_text.upper()
                
                # Instantly drop index sheets out of loop calculations to preserve CPU processing power
                if "PSYCH SHEET" in page_text_upper or "SEED LIST" in page_text_upper:
                    continue
                    
                if clean_search_name in page_text_upper:
                    lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                    
                    for current_line in lines:
                        if clean_search_name in current_line.upper():
                            if any(m in current_line for m in markers):
                                name_match = name_pattern.search(current_line)
                                identity_key = f"👤 {name_match.group(1).strip().title()}" if name_match else f"👤 {swimmer_name.title()}"
                                
                                if identity_key not in swimmer_profiles:
                                    swimmer_profiles[identity_key] = []
                                swimmer_profiles[identity_key].append({"page": page_num, "raw_line": current_line})

            # --- PARSING DEDUPLICATION LOGIC ---
            chosen_profile = None
            if len(swimmer_profiles) == 0:
                st.error(f"❌ Could not find '{swimmer_name}' inside this document layout.")
            elif len(swimmer_profiles) > 1:
                st.info("💡 Multiple entries matched! Select your entry profile:")
                chosen_profile = st.selectbox("🎯 Select Your Profile Entry Configuration:", list(swimmer_profiles.keys()))
            else:
                chosen_profile = list(swimmer_profiles.keys())[0]

            # Fast Pass 2: Localized trace scheduling
            if chosen_profile:
                schedule_blocks = []
                event_count = 0
                
                for match_data in swimmer_profiles[chosen_profile]:
                    target_page_num = match_data["page"]
                    target_line_text = match_data["raw_line"]
                    
                    page = reader.pages[target_page_num - 1]
                    lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
                    
                    for index, current_line in enumerate(lines):
                        if current_line == target_line_text:
                            
                            # Optimized Event title trace lookup loop
                            matched_event = "Unknown Event"
                            for back_idx in range(index, -1, -1):
                                line_check = lines[back_idx]
                                if "EVENT" in line_check.upper() or ("#" in line_check and any(w in line_check for w in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC", "Girls", "Boys"])):
                                    matched_event = line_check
                                    break
                            
                            # Optimized Heat block trace lookup loop
                            matched_heat = "Unknown Heat"
                            lane_counter = 0
                            for back_idx in range(index, -1, -1):
                                line_check = lines[back_idx]
                                if line_check.upper().startswith("HEAT") or "HEAT " in line_check.upper():
                                    matched_heat = line_check
                                    break
                                if back_idx < index and any(m in line_check for m in markers):
                                    lane_counter += 1
                            
                            lane_counter += 1  
                            
                            # Boundary data filter locks
                            if matched_heat == "Unknown Heat" or lane_counter > 10:
                                continue
                                
                            event_count += 1
                            schedule_blocks.append({
                                "event": matched_event,
                                "heat": matched_heat,
                                "lane": f"Lane {lane_counter}",
                                "line": current_line,
                                "page": target_page_num
                            })
                            break 

                # --- MULTI-CONTAINER METRIC RENDERER ---
                if event_count > 0:
                    st.success("✅ Race schedule isolated successfully!")
                    st.metric(label="📊 Total Scheduled Events Found", value=event_count)
                    st.markdown(f"### 📋 Verified Schedule for **{chosen_profile}**")
                    
                    for i, block in enumerate(schedule_blocks, start=1):
                        with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                            st.write(f"🔥 **{block['heat']}**")
                            st.write(f"🚪 **Lane Assignment:** {block['lane']} *(Page {block['page']})*")
                            st.caption(f"📝 Raw Row Data: `{block['line']}`")
                else:
                    st.warning(f"❌ '{swimmer_name}' was found in the index list, but explicit heat/lane listings aren't finalized in this file block.")

        except Exception as e:
            st.error(f"⚠️ Performance pipeline block encountered: {e}")
