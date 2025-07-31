#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 31 10:59:52 2025

@author: jan.kuethe
"""

import streamlit as st
import pandas as pd
import numpy as np
import gzip
import requests
import time
import webbrowser
import os
from io import BytesIO
from urllib.parse import unquote_plus


# --- Load Config from TXT ---
def load_config(filename="config.txt"):
    # Find the full path to config.txt relative to this .py file
    base_path = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_path, filename)

    config = {}
    with open(full_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Convert to int or float if applicable
                if value.isdigit():
                    value = int(value)
                elif value.replace(".", "", 1).isdigit():
                    value = float(value)

                config[key] = value
    return config


# --- Load and unpack global vars from config ---
config = load_config()
CSV_PATH = config.get("CSV_PATH", "urls.csv")
NUM_TO_OPEN = config.get("NUM_TO_OPEN", 20)
WAIT_BETWEEN_TABS = config.get("WAIT_BETWEEN_TABS", 0.1)
BROWSER = config.get("BROWSER", "firefox")
COUNTRY = config.get("COUNTRY", "de")
COUNTRY_URL = config.get("COUNTRY_URL", "die-staemme.de")

# --- URL Builder for World ---
def get_village_url(world_number, country, country_url):
    return f"https://{country}{world_number}.{country_url}/map/village.txt.gz"

# --- Step 1–8: Download, Process, and Save CSV ---
def fetch_and_prepare_data(x_own, y_own, world_number):
    try:
        # Step 1: Download and read the gzip file
        url = get_village_url(world_number, COUNTRY, COUNTRY_URL)
        response = requests.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to download data file: {response.status_code}")

        # Step 2: Load into DataFrame
        compressed_data = BytesIO(response.content)
        with gzip.open(compressed_data, mode='rt', encoding='ISO-8859-1') as f:
            df = pd.read_csv(f, header=None, names=['id', 'name', 'x', 'y', 'player', 'points', 'rank'])

        # Step 2.5: Decode village names and filter out barbarians
        df = df[df['player'] != 0]
        df['name'] = df['name'].apply(unquote_plus)

        # Step 3: Compute Euclidean distance to own coordinates
        df['distance'] = np.sqrt((df['x'] - x_own)**2 + (df['y'] - y_own)**2)

        # Step 4: Per player, keep only the closest village
        df_closest = df.loc[df.groupby('player')['distance'].idxmin()].copy()

        # Step 5: Sort by distance
        df_closest.sort_values('distance', inplace=True)

        # Step 6: Add target URL to open
        df_closest['url_to_open'] = df_closest.apply(
            lambda row: f"https://{COUNTRY}{world_number}.{COUNTRY_URL}/game.php?screen=place&x={row['x']}&y={row['y']}&spy=5",
            axis=1
        )

        # Step 7: Add 'opened' boolean column
        df_closest['opened'] = False

        # Step 8: Save to CSV
        df_closest.to_csv(CSV_PATH, index=False)
        st.success(f"✅ Data saved to {CSV_PATH}.")
        st.dataframe(df_closest.head(20))
    except Exception as e:
        st.error(f"❌ Fetch failed:\n{e}")

# --- Open Next N Unopened URLs ---
def open_next_unopened():
    # Step 1: Load CSV
    if not os.path.exists(CSV_PATH):
        st.error(f"{CSV_PATH} not found. Run 'Fetch & Prepare' first.")
        return

    df_full = pd.read_csv(CSV_PATH)

    # Step 2: Find unopened entries
    df_unopened = df_full[df_full['opened'] == False].copy()

    if df_unopened.empty:
        st.info("📭 No more unopened URLs.")
        return

    # Step 3: Open URLs in browser
    browser = webbrowser.get(BROWSER)
    count = 0
    for i in df_unopened.index[:NUM_TO_OPEN]:
        url = df_unopened.at[i, 'url_to_open']
        try:
            browser.open_new_tab(url)
            df_full.at[i, 'opened'] = True
            count += 1
            st.write(f"[OPENED] {url}")
            time.sleep(WAIT_BETWEEN_TABS)
        except Exception as e:
            st.error(f"[ERROR] Could not open {url}: {e}")

    # Step 4: Save updated CSV
    df_full.to_csv(CSV_PATH, index=False)
    st.success(f"✅ {count} URLs opened.")

# --- Web App Interface with Streamlit ---
def main():
    st.set_page_config(page_title="Tribal Wars Spy Tool")
    st.title("🏹 Tribal Wars Spy Tool")

    # --- Info Section (adapted from Tkinter Text widget) ---
    with st.expander("ℹ️ Anleitung (Info anzeigen/verstecken)", expanded=True):
        st.markdown("""
        Dieses Skript erlaubt es einfach den Erfolg für 250 angegriffene Spieler zu erreichen.  
        - Bitte Weltnummer eintragen. z.B. `239`  
        - Bitte Koordinaten eines deiner Dörfer eintragen. z.B. `500` und `500`  
        - **Nur auf der deutschen Version nutzbar.**  
        
        **Fetch & Prepare** sollte nur einmal ausgeführt werden, sonst werden bereits angegriffene Ziele überschrieben.  
        Falls nicht genug Späher da sind, kann später mit **Open Next** weitergemacht werden.  
        Angriffe werden aus dem aktuellen Dorf vorbereitet.  
        Wenn leer: in DS zum nächsten Dorf wechseln.
        """)

    # --- User Input Form ---
    with st.form("fetch_form"):
        world = st.number_input("🌍 World Number", min_value=1, value=239)
        x = st.number_input("🧭 x_own", min_value=0, value=500)
        y = st.number_input("🧭 y_own", min_value=0, value=500)
        submit = st.form_submit_button("📥 Fetch & Prepare")

    if submit:
        fetch_and_prepare_data(x, y, world)

    # --- Button to Open Next N URLs ---
    st.markdown("---")
    if st.button("🚀 Open Next 20 URLs"):
        open_next_unopened()

    # --- Optional: CSV status info ---
    if os.path.exists(CSV_PATH):
        try:
            df_check = pd.read_csv(CSV_PATH)
            if 'opened' in df_check.columns and 'distance' in df_check.columns:
                remaining = df_check[df_check['opened'] == False].shape[0]
                min_dist = df_check[df_check['opened'] == False]['distance'].min()
                st.info(
                    f"🗂️ Bereits gespeicherte Datei erkannt:\n\n"
                    f"✅ Du kannst mit **Open Next** fortfahren.\n\n"
                    f"🔢 Noch offen: `{remaining}`\n\n"
                    f"📏 Kleinste Distanz: `{min_dist:.2f}`"
                )
        except Exception as e:
            st.warning(f"⚠️ Datei konnte nicht gelesen werden: {e}")

# --- Run the App ---
if __name__ == "__main__":
    main()



git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/twtoolsde/twtools.git
git push -u origin main


git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/twtoolsde/twtools.git
git push -u origin main