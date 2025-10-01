# IPTVore Fetch Script

## Overview
This script automates the process of signing up for a LayerSeven IPTV free trial, retrieving the IPTV playlist (M3U), extracting Xtream Codes details, and generating a cleaned, merged playlist on a VPS.  

The script is optimized for use on low-resource VPS environments.

---

## Features
- Automated LayerSeven signup using a disposable email address  
- Automatic handling of cookies and popups  
- Google reCAPTCHA solving via 2Captcha  
- Waits for the IPTV trial email and extracts:
  - M3U playlist link  
  - EPG link  
  - Xtream Codes details (server, username, password) from the **Hostname / URL / Server address** section of the email  
- Downloads and validates M3U and EPG files with retries and progress reporting  
- Truncates large M3U files for stability  
- Executes [`xtream2m3u`](https://github.com/bmillham/xtream2m3u) with extracted Xtream credentials  
- Filters and merges selected categories into a single playlist file  
- Uses a VPS-optimized, headless Chrome/Selenium configuration  

---

## Output Files
- `iptv_daily/iptv_daily_update.m3u` – final merged playlist  
- `iptv_daily/iptv_daily_update_epg.xml` – EPG file (if available)  
- `iptv_daily/live_m3u/` – generated live category playlists  
- `iptv_daily/vod_m3u/` – generated VOD category playlists  

---

## Requirements
- Linux VPS with:
  - Python 3.8 or newer  
  - [Google Chrome](https://www.google.com/chrome/) and [ChromeDriver](https://chromedriver.chromium.org/) (installed at `/usr/bin/chromedriver`)  
  - Rust and [`xtream2m3u`](https://github.com/bmillham/xtream2m3u) installed  

- Python dependencies:
  ```bash
  pip install selenium requests
