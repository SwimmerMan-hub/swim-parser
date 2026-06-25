import io
import requests
import pypdf
import streamlit as st

# Live URL to download the heat sheet automatically from the web server
URL = "https://swimatlanta.com"

# Page styling configurations
st.set_page_config(page_title="SwimAtlanta Parser", page_icon="🏊‍♂️", layout="centered")

# --- UI HEADER DESIGN ---
st.title("🏊‍♂️ SwimAtlanta Heat Sheet Parser")
st.write("Type a swimmer's last name below to instantly extract their upcoming meet schedule.")

st.link_button("🌐 Open Live Official Heat Sheet (PDF)", URL)
st.markdown("---") 

# --- USER INPUT ---
swimmer_name = st.text_input("Enter Swimmer Last Name:", placeholder="e.g., Zubelevitskiy")

# --- PARSING ENGINE ---
if swimmer_name:
    try:
        # Fetch the live file straight into memory using requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Read the binary stream data directly
        pdf_file = io.BytesIO(response.content)
        reader = pypdf.PdfReader(pdf_file)
        
        found_any = False
        event_count = 0
        schedule_blocks = []

        # Scan through every page of the PDF layout
        for page_num, page in enumerate(reader.pages, start=1):
            lines = [line.strip() for line in page.extract_text().split('\n') if line.strip()]
            
            for index, current_line in enumerate(lines):
                if swimmer_name.upper() in current_line.upper():
                    found_any = True
                    event_count += 1
                    
                    # High-Precision Lookbacks
                    matched_event = "Unknown Event"
                    for back_idx in range(index, -1, -1):
                        line_check = lines[back_idx]
                        if "EVENT" in line_check.upper() or ("#" in line_check and any(word in line_check for word in ["Free", "Fly", "Back", "Breast", "Medley", "Relay", "LC", "SC"])):
                            matched_event = line_check
                            break
                    
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

        # --- DISPLAY RESULTS ---
        if found_any:
            st.metric(label="Total Races Found", value=event_count)
            st.subheader(f"📋 Schedule Summary for {swimmer_name.upper()}")
            
            for i, block in enumerate(schedule_blocks, start=1):
                with st.expander(f"🏅 Race {i}: {block['event']}", expanded=True):
                    st.write(f"🔥 **{block['heat']}**")
                    st.write(f"🚪 **Lane Position:** {block['lane']}")
                    st.caption(f"📝 Raw Entry Line: {block['line']}")
        else:
            st.warning(f"❌ No events found for '{swimmer_name}'. Double check spelling.")

    except Exception as e:
        st.error(f"⚠️ Cloud Error Loading Live PDF: {e}")
