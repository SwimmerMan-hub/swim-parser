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

swimmer_name = st.text_input("👤 Enter Swimmer Last Name:", placeholder="e.g., Bansen")

# --- PARSING ENGINE ---
if swimmer_name:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(TARGET_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        # This dictionary will group entries by the swimmer's exact text row
        swimmer_matches = {}

        # First Pass: Find all lines matching the name across the entire document
        for page_num, page in enumerate(reader.pages, start=1):
            lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
            
            for index, current_line in enumerate(lines):
                if swimmer_name.upper() in current_line.upper():
                    # Smart team checker: Looks for standard swim line markers like team hyphens, NT, seed times with colons/periods
                    if "-" in current_line or "GA" in current_line or "NT" in current_line or ":" in current_line or "." in current_line:
                        if current_line not in swimmer_matches:
                            swimmer_matches[current_line] = []
                        # Save the page number and line position so we can reference it exactly later
                        swimmer_matches[current_line].append({"page": page_num, "line_idx": index})

        # --- DEDUPLICATION FILTER ---
        chosen_swimmer_line = None
        
        if len(swimmer_matches) == 0:
            st.warning(f"❌ Could not find '{swimmer_name}' inside the selected sheet.")
        elif len(swimmer_matches) > 1:
            st.info("💡 Multiple swimmers found with that last name! Please choose yours below:")
            chosen_swimmer_line = st.selectbox("🎯 Choose Your Exact Entry Line:", list(swimmer_matches.keys()))
        else:
            chosen_swimmer_line = list(swimmer_matches.keys())[0]

        # Second Pass: Extract exact details ONLY for the matches of the selected swimmer line
        if chosen_swimmer_line:
            schedule_blocks = []
            event_count = 0
            
            # Loop back through the exact pages where this specific swimmer line was found
            for match_info in swimmer_matches[chosen_swimmer_line]:
                event_count += 1
                target_page_num = match_info["page"]
                
                # Reload the lines for that specific page to keep counting local
                page = reader.pages[target_page_num - 1]
                lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
                
                # Find where our swimmer sits on this specific page text array
                for index, current_line in enumerate(lines):
                    if current_line == chosen_swimmer_line:
                        
                        # Backward Lookup for Event Title
                        matched_event = "Unknown Event"
                        for back_idx in range(index, -1, -1):
                            line_check = lines[back_idx]
                            if "EVENT" in line_check.upper() or ("#" in line_check and any(word in line_check for word in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC", "Girls", "Boys"])):
                                matched_event = line_check
                                break
                        
                        # Backward Lookup for Heat and Lane counting
                        matched_heat = "Unknown Heat"
                        lane_counter = 0
                        for back_idx in range(index, -1, -1):
                            line_check = lines[back_idx]
                            if line_check.upper().startswith("HEAT") or "HEAT " in line_check.upper():
                                matched_heat = line_check
                                break
                            # Count rows between the Heat header and the swimmer that look like competitor data
                            if back_idx < index and ("-" in line_check or "GA" in line_check or "NT" in line_check or ":" in line_check or "." in line_check):
                                lane_counter += 1
                        
                        lane_counter += 1  # Add 1 for our swimmer's position
                        
                        schedule_blocks.append({
                            "event": matched_event,
                            "heat": matched_heat,
                            "lane": f"Lane {lane_counter}",
                            "line": current_line,
                            "page": target_page_num
                        })
                        break # Stop searching this page once this specific instance is processed

            # --- RENDER THE FINAL FIXED SCHEDULE ---
            st.metric(label="Races Found", value=event_count)
            st.subheader("📋 Verified Schedule:")
            
            for i, block in enumerate(schedule_blocks, start=1):
                with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                    st.write(f"🔥 **{block['heat']}**")
                    st.write(f"🚪 **Lane Assignment:** {block['lane']} *(Page {block['page']})*")
                    st.caption(f"📝 Line Entry: {block['line']}")

    except Exception as e:
        st.error(f"⚠️ Error parsing the chosen file stream: {e}")
