import io
import requests
import pypdf
import streamlit as st
from bs4 import BeautifulSoup

# App setup
st.set_page_config(page_title="SwimAtlanta Meet Parser", page_icon="🏊‍♂️", layout="centered")

# --- DATABASE DISCOVERY SCAPER ---
@st.cache_data(ttl=3600)
def fetch_heatsheet_names():
    base_url = "https://www.swimatlanta.com"
    news_url = "https://www.swimatlanta.com/news"
    
    database = {
        "🏆 Splash Jam Heat Sheet": "https://swimatlanta.com",
        "🏆 AAU Lucky Splash Sunday": "https://www.swimatlanta.com/f/Lucky%20Splash%20Heat%20Sheets.pdf",
        "🏆 Betsy Dunbar LC Meet": "https://swimatlanta.com"
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

swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="e.g., Zubelevitskiy")

# --- PARSING ENGINE ---
if swimmer_name:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        # Dictionary to group raw entry rows by the swimmer's exact full line text
        swimmer_matches = {}

        # First Pass: Find all unique rows matching the last name
        for page_num, page in enumerate(reader.pages, start=1):
            lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
            
            for index, current_line in enumerate(lines):
                if swimmer_name.upper() in current_line.upper():
                    # Only collect entries that resemble competitor layout slots
                    if any(team in current_line for team in ["SA-GA", "GA", "NT", ":"]):
                        # Key by the full line text to isolate individuals completely
                        if current_line not in swimmer_matches:
                            swimmer_matches[current_line] = []
                        swimmer_matches[current_line].append((page_num, index, lines))

        # --- DUPLICATION VERIFICATION ENGINE ---
        target_lines_to_parse = []
        
        if len(swimmer_matches) == 0:
            st.warning(f"❌ Could not find '{swimmer_name}' inside the selected sheet.")
        
        elif len(swimmer_matches) > 1:
            # MULTIPLE SWIMMERS DETECTED: Show choice menu
            st.info("💡 Multiple entries found with that last name! Please choose yours below:")
            chosen_swimmer_line = st.selectbox("🎯 Choose Your Exact Competitor Entry:", list(swimmer_matches.keys()))
            target_lines_to_parse = swimmer_matches[chosen_swimmer_line]
            
        else:
            # ONLY ONE SWIMMER DETECTED: Proceed automatically
            chosen_swimmer_line = list(swimmer_matches.keys())[0]
            target_lines_to_parse = swimmer_matches[chosen_swimmer_line]

        # Second Pass: Extract Event, Heat, and Lane configurations for the chosen individual row profile
        if target_lines_to_parse:
            schedule_blocks = []
            event_count = 0
            
            for page_num, index, lines in target_lines_to_parse:
                event_count += 1
                
                # High-Precision Lookbacks for Event
                matched_event = "Unknown Event"
                for back_idx in range(index, -1, -1):
                    line_check = lines[back_idx]
                    if "EVENT" in line_check.upper() or ("#" in line_check and any(word in line_check for word in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC"])):
                        matched_event = line_check
                        break
                
                # High-Precision Lookbacks for Heat
                matched_heat = "Unknown Heat"
                lane_counter = 0
                for back_idx in range(index, -1, -1):
                    line_check = lines[back_idx]
                    if line_check.upper().startswith("HEAT"):
                        matched_heat = line_check
                        break
                    if back_idx < index and any(team in line_check for team in ["SA-GA", "GA", "NT", ":"]):
                        lane_counter += 1
                
                lane_counter += 1
                
                schedule_blocks.append({
                    "event": matched_event,
                    "heat": matched_heat,
                    "lane": f"Lane {lane_counter}",
                    "line": lines[index]
                })

            # --- RENDER SCHEDULE ---
            st.metric(label="Races Found", value=event_count)
            st.subheader(f"📋 Verified Schedule:")
            
            for i, block in enumerate(schedule_blocks, start=1):
                with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                    st.write(f"🔥 **{block['heat']}**")
                    st.write(f"🚪 **Lane Assignment:** {block['lane']}")
                    st.caption(f"📝 Line Entry: {block['line']}")

    except Exception as e:
        st.error(f"⚠️ Error parsing the chosen file stream: {e}")
