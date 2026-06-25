import io
import re
import requests
import pypdf
import streamlit as st
from bs4 import BeautifulSoup

# App layout setup
st.set_page_config(page_title="SwimAtlanta Meet Parser", page_icon="🏊‍♂️", layout="centered")

# --- DATABASE DISCOVERY SCAPER ---
@st.cache_data(ttl=3600)
def fetch_heatsheet_names():
    base_url = "https://swimatlanta.com"
    news_url = "https://swimatlanta.com/news"
    
    database = {
        "🏆 Splash Jam Heat Sheet": "https://swimatlanta.com/f/splashjamheatsheet.pdf",
        "🏆 AAU Lucky Splash Sunday": "https://swimatlanta.com/f/Lucky%20Splash%20Heat%20Sheets.pdf",
        "🏆 Betsy Dunbar LC Meet": "https://swimatlanta.com/f/rev1betsysatpm.pdf"
    }
    
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(news_url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if "/f/" in href and ("heatsheet" in href.lower() or "meet" in href.lower() or "sheet" in href.lower()):
                    full_url = href if href.startswith("http") else base_url + href
                    clean_name = href.split('/')[-1].replace('%20', ' ').replace('.pdf', '')
                    clean_name = "🏆 " + clean_name.title()
                    database[clean_name] = full_url
    except Exception:
        pass
    return database

# --- UI WINDOW CONTENT ---
st.title("🏊‍♂️ SwimAtlanta Automated Meet Parser")
st.write("Select a heat sheet, type your name, and extract your schedule configuration.")
st.markdown("---")

with st.spinner("🔄 Loading SwimAtlanta heat sheet names..."):
    MEET_DATABASE = fetch_heatsheet_names()

selected_sheet = st.selectbox("📅 Select the Heat Sheet you want to look at:", list(MEET_DATABASE.keys()))
TARGET_URL = MEET_DATABASE[selected_sheet]

swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="e.g., Bhardwaj")

# --- PARSING ENGINE ---
if swimmer_name:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        if not response.content or b"%PDF" not in response.content[:5]:
            st.warning(f"🔄 **Meet Sheet Notice:** SwimAtlanta is currently uploading or updating the files for **{selected_sheet}** on their server! Please try a different meet sheet or check back in a few minutes.")
        else:
            pdf_file = io.BytesIO(response.content)
            reader = pypdf.PdfReader(pdf_file)
            
            # This dictionary groups match instances by a clean Swimmer Identity string
            swimmer_profiles = {}

            # First Pass: Find all matches and group them by the swimmer's exact name identity
            for page_num, page in enumerate(reader.pages, start=1):
                lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
                
                for index, current_line in enumerate(lines):
                    if swimmer_name.upper() in current_line.upper():
                        if any(marker in current_line for marker in ["-", "GA", "NT", ":", "."]):
                            
                            # --- FIXED EXTRACTION LINE ---
                            # Extracting ONLY the "Lastname, Firstname" part and dropping age parameters
                            name_match = re.search(r'([A-Za-z]+,\s*[A-Za-z\s\.]+)', current_line)
                            if name_match:
                                identity_key = f"👤 {name_match.group(1).strip().title()}"
                            else:
                                identity_key = f"👤 {swimmer_name.title()}"
                            
                            if identity_key not in swimmer_profiles:
                                swimmer_profiles[identity_key] = []
                                
                            swimmer_profiles[identity_key].append({"page": page_num, "raw_line": current_line})

            # --- DEDUPLICATION SELECTION LOGIC ---
            chosen_profile = None
            
            if len(swimmer_profiles) == 0:
                st.warning(f"❌ Could not find '{swimmer_name}' inside the selected sheet.")
            elif len(swimmer_profiles) > 1:
                st.info("💡 Multiple different swimmers found with that last name! Please choose yours:")
                chosen_profile = st.selectbox("🎯 Choose Your Profile Configuration:", list(swimmer_profiles.keys()))
            else:
                chosen_profile = list(swimmer_profiles.keys())

            # Second Pass: Extract Event, Heat, and Lane values locally on target pages
            if chosen_profile:
                schedule_blocks = []
                event_count = 0
                
                for match_data in swimmer_profiles[chosen_profile]:
                    event_count += 1
                    target_page_num = match_data["page"]
                    target_line_text = match_data["raw_line"]
                    
                    page = reader.pages[target_page_num - 1]
                    lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
                    
                    for index, current_line in enumerate(lines):
                        if current_line == target_line_text:
                            
                            # Backward Lookup for Event Title
                            matched_event = "Unknown Event"
                            for back_idx in range(index, -1, -1):
                                line_check = lines[back_idx]
                                if "EVENT" in line_check.upper() or ("#" in line_check and any(word in line_check for word in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC", "Girls", "Boys"])):
                                    matched_event = line_check
                                    break
                            
                            # Backward Lookup for Heat header
                            matched_heat = "Unknown Heat"
                            lane_counter = 0
                            for back_idx in range(index, -1, -1):
                                line_check = lines[back_idx]
                                if line_check.upper().startswith("HEAT") or "HEAT " in line_check.upper():
                                    matched_heat = line_check
                                    break
                                if back_idx < index and any(m in line_check for m in ["-", "GA", "NT", ":", "."]):
                                    lane_counter += 1
                            
                            lane_counter += 1  
                            
                            schedule_blocks.append({
                                "event": matched_event,
                                "heat": matched_heat,
                                "lane": f"Lane {lane_counter}",
                                "line": current_line,
                                "page": target_page_num
                            })
                            break 

                # --- RENDER CLEAN INTEGRATED SCHEDULE ---
                st.metric(label="Total Races Found", value=event_count)
                st.subheader(f"📋 Verified Schedule for {chosen_profile}:")
                
                for i, block in enumerate(schedule_blocks, start=1):
                    with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                        st.write(f"🔥 **{block['heat']}**")
                        st.write(f"🚪 **Lane Assignment:** {block['lane']} *(Page {block['page']})*")
                        st.caption(f"📝 Line Entry: {block['line']}")

    except Exception as e:
        st.error(f"⚠️ Error accessing the file stream: {e}")
