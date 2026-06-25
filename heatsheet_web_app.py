import io
import requests
import pypdf
import streamlit as st
from bs4 import BeautifulSoup

# App setup: centered layout for a clean, single-focused screen
st.set_page_config(page_title="SwimAtlanta Meet Parser", page_icon="🏊‍♂️", layout="centered")

# --- DATABASE DISCOVERY SCAPER ---
@st.cache_data(ttl=3600)  # Caches the names for 1 hour so it loads instantly
def fetch_heatsheet_names():
    base_url = "https://www.swimatlanta.com"
    news_url = "https://www.swimatlanta.com/news"
    
    # Static fallbacks from their direct file paths in case the site goes down
    database = {
        "🏆 Splash Jam Heat Sheet": "https://swimatlanta.com",
        "🏆 AAU Lucky Splash Sunday": "https://www.swimatlanta.com/f/Lucky%20Splash%20Heat%20Sheets.pdf",
        "🏆 Father's Day Spectacular": "https://www.swimatlanta.com/f/FathersDayHeatSheet.pdf",
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
st.write("Pick a heat sheet file from the active database below, type your name, and extract your lane map schedule.")
st.markdown("---")

# Discover all active sheets
with st.spinner("🔄 Loading SwimAtlanta heat sheet names..."):
    MEET_DATABASE = fetch_heatsheet_names()

# 1. DROP-DOWN CHOOSE BOX FOR SHEETS
selected_sheet = st.selectbox("📅 Select the Heat Sheet you want to look at:", list(MEET_DATABASE.keys()))
TARGET_URL = MEET_DATABASE[selected_sheet]

# 2. NAME ENTRY BOX FOR FILTERING
swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="e.g., Zubelevitskiy")

# --- EXTRACTION ENGINE ---
if swimmer_name:
    try:
        # Load up the specific file chosen above
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        found_any = False
        event_count = 0
        schedule_blocks = []

        # Parse every single row line by line
        for page_num, page in enumerate(reader.pages, start=1):
            lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
            
            for index, current_line in enumerate(lines):
                if swimmer_name.upper() in current_line.upper():
                    found_any = True
                    event_count += 1
                    
                    # Backward Lookup mapping for Event Name
                    matched_event = "Unknown Event"
                    for back_idx in range(index, -1, -1):
                        line_check = lines[back_idx]
                        if "EVENT" in line_check.upper() or ("#" in line_check and any(word in line_check for word in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC"])):
                            matched_event = line_check
                            break
                    
                    # Backward Lookup mapping for Heat number
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
                        "line": current_line
                    })

        # --- OUTPUT VIEW FOR THE SELECTED SELECTION ---
        if found_any:
            st.metric(label="Races Found", value=event_count)
            st.subheader(f"📋 Results from: {selected_sheet}")
            
            for i, block in enumerate(schedule_blocks, start=1):
                with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                    st.write(f"🔥 **{block['heat']}**")
                    st.write(f"🚪 **Lane Assignment:** {block['lane']}")
                    st.caption(f"📝 Row Data Line: {block['line']}")
        else:
            st.warning(f"❌ Could not find '{swimmer_name}' inside the selected sheet. Try changing the file selector above or checking spelling.")

    except Exception as e:
        st.error(f"⚠️ Error parsing the chosen file stream: {e}")
