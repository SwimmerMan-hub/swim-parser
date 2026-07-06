import io
import re
import requests
import pypdf
import streamlit as st
from bs4 import BeautifulSoup

# App setup: centered layout for a clean, single-focused screen
st.set_page_config(page_title="SwimAtlanta Meet Parser", page_icon="🏊‍♂️", layout="centered")

# --- DATABASE DISCOVERY SCAPER ---
@st.cache_data(ttl=3600)  # Caches the names for 1 hour so it loads instantly
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
st.title("🏊‍♂️ SwimAtlanta Heat Sheet Parser")
st.write("Pick an active meet from the database, type a last name, and instantly generate an event map.")
st.markdown("---")

with st.spinner("🔄 Checking SwimAtlanta database feed..."):
    MEET_DATABASE = fetch_heatsheet_names()

selected_sheet = st.selectbox("📅 Choose Your Swim Meet Session:", list(MEET_DATABASE.keys()))
TARGET_URL = MEET_DATABASE[selected_sheet]

swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="Type a name to extract schedules...")

# --- EXTRACTION ENGINE ---
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
            
            swimmer_profiles = {}

            # First Pass: Find all matches and group them by the swimmer's exact name identity
            for page_num, page in enumerate(reader.pages, start=1):
                lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
                
                # --- PSYCH SHEET FILTER SHIELD ---
                page_text_block = page.extract_text().upper()
                if "PSYCH SHEET" in page_text_block or "SEED LIST" in page_text_block:
                    continue

                for index, current_line in enumerate(lines):
                    if swimmer_name.upper() in current_line.upper():
                        if any(marker in current_line for marker in ["-", "GA", "NT", ":", "."]):
                            
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
                st.error(f"❌ Could not find '{swimmer_name}' inside this heat sheet. Check your spelling or select a different meet session.")
            elif len(swimmer_profiles) > 1:
                st.info("💡 Multiple entries found with that last name! Please choose yours:")
                chosen_profile = st.selectbox("🎯 Select Your Profile Entry Configuration:", list(swimmer_profiles.keys()))
            else:
                chosen_profile = list(swimmer_profiles.keys())

            # Second Pass: Extract Event, Heat, and Lane values locally on target pages
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
                            
                            # --- POSITION SECURITY CHECK ---
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

                # --- RENDER THE LEGACY DISPLAY OUTPUT ---
                if event_count > 0:
                    st.success("✅ Race schedule isolated successfully!")
                    st.metric(label="📊 Total Scheduled Events Found", value=event_count)
                    st.markdown(f"### 📋 Verified Schedule for **{chosen_profile}**")
                    
                    for i, block in enumerate(schedule_blocks, start=1):
                        with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                            # Back to the chunky vertical alignment that looks awesome on mobile!
                            st.write(f"🔥 **{block['heat']}**")
                            st.write(f"🚪 **Lane Assignment:** {block['lane']} *(Page {block['page']})*")
                            st.caption(f"📝 Raw Row Data: `{block['line']}`")
                else:
                    st.warning(f"❌ '{swimmer_name}' was found in the index, but their official Heat and Lane assignments haven't been posted in this document yet.")

    except Exception as e:
        st.error(f"⚠️ Error parsing the chosen file stream: {e}")
