from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time, re, random, string, os
import requests

# === Settings ===
SAVE_FILE = "iptv_daily/iptv_daily_update.m3u"
EPG_SAVE_FILE = "iptv_daily/iptv_daily_update_epg.xml"
DRIVER_PATH = "/usr/bin/chromedriver"

# === Improved Chrome Options for Stability ===
options = webdriver.ChromeOptions()

# Basic headless settings
options.add_argument("--headless=new")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Memory and crash prevention
options.add_argument("--memory-pressure-off")
options.add_argument("--max-old-space-size=4096")
options.add_argument("--disable-background-timer-throttling")
options.add_argument("--disable-renderer-backgrounding")
options.add_argument("--disable-backgrounding-occluded-windows")

# Window size and display settings
options.add_argument("--window-size=1080,960")
# options.add_argument("--start-maximized")
options.add_argument("--disable-web-security")
options.add_argument("--disable-features=VizDisplayCompositor")

# Stability improvements
options.add_argument("--force-device-scale-factor=1")
options.add_argument("--disable-extensions")
options.add_argument("--disable-plugins")
options.add_argument("--disable-images")
options.add_argument("--disable-javascript-harmony-shipping")

# Anti-detection
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Additional stability options
options.add_argument("--disable-crash-reporter")
options.add_argument("--disable-logging")
options.add_argument("--log-level=3")
options.add_argument("--silent")

# Set preferences
prefs = {
    "profile.default_content_setting_values": {
        "notifications": 2
    }
}
options.add_experimental_option("prefs", prefs)

driver = webdriver.Chrome(service=Service(DRIVER_PATH), options=options)
driver.implicitly_wait(10)
driver.set_window_size(1080, 960)
wait = WebDriverWait(driver, 20)

start_time = time.time()

def elapsed_time():
    """Return HH:MM:SS since start"""
    elapsed = int(time.time() - start_time)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs:02}:{mins:02}:{secs:02}"

def js_click(elem):
    """More reliable click using JavaScript"""
    try:
        # First scroll element into view
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", elem)
        time.sleep(0.5)
        # Then click
        driver.execute_script("arguments[0].click();", elem)
        return True
    except Exception as e:
        print(f"[!] JS click failed: {e}")
        return False

def try_find_click(selectors, timeout=5):
    """Try multiple selectors to find and click an element"""
    for by, selector in selectors:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector)))
            if js_click(elem):
                return True
        except TimeoutException:
            continue
    return False

def try_find_element(selectors, timeout=10):
    """Try multiple selectors to find an element"""
    for by, selector in selectors:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, selector)))
            return elem
        except TimeoutException:
            continue
    return None

def handle_cookies_and_popups():
    """Try to accept cookies or close modals"""
    print("[+] Handling cookies/popups...")
    selectors = [
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'accept')]"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'agree')]"),
        (By.XPATH, "//button[contains(text(),'OK')]"),
        (By.CSS_SELECTOR, "button#onetrust-accept-btn-handler"),
    ]
    try_find_click(selectors)
    driver.execute_script("""
        document.querySelectorAll('div[class*="cookie"],div[class*="modal"],div[class*="overlay"]').forEach(e => e.remove());
        document.body.style.overflow = 'auto';
    """)

def get_disposable_email():
    """Fetch a disposable email address and extend duration to 2 hours"""
    print("[+] Fetching disposable email...")
    driver.execute_script("window.open('https://www.disposablemail.com/', '_blank');")
    driver.switch_to.window(driver.window_handles[1])
    
    handle_cookies_and_popups()
    
    try:
        # Get the email address
        email_elem = wait.until(EC.visibility_of_element_located((By.ID, "email")))
        email = email_elem.get_attribute("value") or email_elem.text
        if not email or "@" not in email:
            raise Exception("Email not found")
        print(f"[+] Disposable email acquired: {email}")

        
        # Shortened +10 min extension - using the working method
        print(f"[+] Extending email duration to 2 hours...")
        for i in range(6):
            print(f"[+] Clicking +10 min button (attempt {i+1}/6)")
            try:
                # Use the working selector (adjust based on which one worked for you)
                extend_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/div/div[3]/div/div[2]/ul/li[5]/a"))
                )
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", extend_button)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", extend_button)
                print(f"[+] Successfully clicked +10 min button")
                time.sleep(3)
            except Exception as e:
                print(f"[!] Failed to click +10 min button: {e}")
                # If this attempt fails, continue anyway
                continue
        
        print(f"[+] Email duration extension completed")
        
        
        driver.switch_to.window(driver.window_handles[0])
        return email.strip()
        
    except Exception as e:
        print(f"[!] Error getting disposable email: {e}")
        fallback_email = f"{''.join(random.choices(string.ascii_lowercase, k=10))}@example.com"
        print(f"[!] Using fallback email: {fallback_email}")
        try:
            # Make sure to revert window size even on error
            driver.set_window_size(960, 980)
            time.sleep(2)
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return fallback_email

def wait_for_email_link(max_wait=6600):
    """Poll mailbox for M3U link"""
    print("[+] Waiting for M3U email...")
    driver.switch_to.window(driver.window_handles[1])
    
    start = time.time()
    while time.time() - start < max_wait:
        try:
            driver.get("https://www.disposablemail.com/email/id/2")
            
            # Handle consent popups
            consent_selectors = [
                (By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'OK') or contains(text(), 'Agree')]"),
                (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"),
            ]
            try_find_click(consent_selectors, timeout=2)

            print(f"[{elapsed_time()}] Searching for M3U links...")
            
            # Search for M3U links directly
            m3u_url = search_for_m3u_links()
            if m3u_url:
                return m3u_url
            
            # Try iframe approach
            iframe_selectors = [
                (By.TAG_NAME, "iframe"),
                (By.CSS_SELECTOR, "iframe[src*='email']"),
            ]
            
            for by, selector in iframe_selectors:
                try:
                    iframe_elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    driver.switch_to.frame(iframe_elem)
                    m3u_url = search_for_m3u_links()
                    driver.switch_to.default_content()
                    if m3u_url:
                        return m3u_url
                    break
                except TimeoutException:
                    continue

            print(f"[{elapsed_time()}] No M3U link found, retrying in 30s...")
            time.sleep(30)

        except Exception as e:
            print(f"[{elapsed_time()}] Error checking email: {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            time.sleep(30)

    print(f"[{elapsed_time()}] Timed out waiting for M3U link")
    return None

def search_for_m3u_links():
    """Search for M3U links in current context"""
    try:
        # Get page content
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            page_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
            combined_content = page_html + " " + page_text
        except Exception as e:
            print(f"[{elapsed_time()}] Error reading page content: {e}")
            return None
        
        found_urls = []
        
        # Method 1: Look for direct M3U links
        m3u_selectors = [
            (By.XPATH, "//a[contains(@href, '.m3u')]"),
            (By.XPATH, "//a[contains(@href, 'get.php') and contains(@href, 'type=m3u')]"),
            (By.CSS_SELECTOR, "a[href*='.m3u']"),
            (By.CSS_SELECTOR, "a[href*='get.php'][href*='type=m3u']"),
        ]
        
        for by, selector in m3u_selectors:
            try:
                m3u_elements = driver.find_elements(by, selector)
                for elem in m3u_elements:
                    href = elem.get_attribute("href")
                    if href and ("m3u" in href.lower() or "get.php" in href.lower()):
                        # Get context
                        try:
                            parent_text = ""
                            current = elem
                            for _ in range(3):
                                current = current.find_element(By.XPATH, "..")
                                parent_text += " " + current.text
                        except:
                            parent_text = elem.text
                        
                        found_urls.append({
                            'url': href,
                            'context': parent_text.lower()
                        })
                        print(f"[{elapsed_time()}] Found M3U link: {href}")
                        
            except Exception:
                continue
        
        # Method 2: Regex search
        m3u_patterns = [
            r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u_plus[^\s<>"\']*',
            r'https?://[^\s<>"\']+\.m3u[^\s<>"\']*',
            r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u[^\s<>"\']*',
        ]
        
        for pattern in m3u_patterns:
            matches = re.findall(pattern, combined_content, re.IGNORECASE)
            for match in matches:
                url = match.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                if url and ("m3u" in url.lower() or "get.php" in url.lower()):
                    url_pos = combined_content.lower().find(url.lower())
                    context_start = max(0, url_pos - 200)
                    context_end = min(len(combined_content), url_pos + len(url) + 200)
                    context = combined_content[context_start:context_end].lower()
                    
                    found_urls.append({
                        'url': url,
                        'context': context
                    })
                    print(f"[{elapsed_time()}] Found M3U URL via regex: {url}")
        
        if not found_urls:
            return None
        
        # Prioritize TiviMate-friendly URLs
        tivimate_indicators = ['tivimate', 'vpn', 'cf.cdn-90', 'cdn-90']
        scored_urls = []
        
        for url_info in found_urls:
            score = 0
            context = url_info['context']
            url = url_info['url']
            
            for indicator in tivimate_indicators:
                if indicator in context:
                    score += 10
                if indicator in url:
                    score += 15
            
            if 'type=m3u_plus' in url:
                score += 5
            
            scored_urls.append({
                'url': url,
                'score': score
            })
        
        # Return highest scored URL and look for EPG
        scored_urls.sort(key=lambda x: x['score'], reverse=True)
        best_url = scored_urls[0]['url']
        print(f"[{elapsed_time()}] Selected best URL: {best_url}")

        # Look for EPG URL in the same context
        epg_url = None
        epg_patterns = [
            r'https?://[^\s<>"\']+xmltv\.php[^\s<>"\']*',
            r'https?://[^\s<>"\']+/xmltv\.php\?username=[^&\s<>"\']+&password=[^&\s<>"\']+',
        ]

        for pattern in epg_patterns:
            matches = re.findall(pattern, combined_content, re.IGNORECASE)
            for match in matches:
                clean_url = match.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                # Prioritize TiviMate-friendly EPG URLs (same domain as M3U)
                if any(domain in clean_url for domain in ['cf.cdn-90.me', 'cdn-90']):
                    epg_url = clean_url
                    print(f"[{elapsed_time()}] Found EPG URL: {epg_url}")
                    break
            if epg_url:
                break

        return best_url, epg_url
        
    except Exception as e:
        print(f"[{elapsed_time()}] Error in search_for_m3u_links: {e}")
        return None

def download_m3u_file(m3u_url, save_path, max_retries=3):
    """Download M3U file with proper headers"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/plain, application/x-mpegURL, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    
    for attempt in range(max_retries):
        try:
            print(f"[{elapsed_time()}] Download attempt {attempt + 1}")
            
            session = requests.Session()
            session.headers.update(headers)
            
            response = session.get(m3u_url, timeout=(10, 30), allow_redirects=True, stream=True)
            response.raise_for_status()
            
            print(f"[{elapsed_time()}] Response status: {response.status_code}")
            
            total_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
            
            print(f"[{elapsed_time()}] Downloaded {total_size} bytes")
            
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                print(f"[{elapsed_time()}] File saved: {save_path} ({file_size} bytes)")
                return True
                
        except Exception as e:
            print(f"[!] Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 3)
    
    return False

def download_and_save_m3u(m3u_url, save_path):
    """Main download function"""
    print(f"[+] Downloading M3U from: {m3u_url}")
    return download_m3u_file(m3u_url, save_path)


# === Helper Function ===
def wait_for_element(xpaths, wait_time=10, clickable=False):
    """
    Try multiple XPaths and return the first one that works.
    """
    for xpath in xpaths:
        try:
            if clickable:
                elem = WebDriverWait(driver, wait_time).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            else:
                elem = WebDriverWait(driver, wait_time).until(EC.presence_of_element_located((By.XPATH, xpath)))
            print(f"[+] Found element with XPath: {xpath}")
            return elem
        except TimeoutException:
            print(f"[!] Element not found/clickable for XPath: {xpath}, trying next...")
    raise Exception("[-] None of the XPaths worked for this element")


# === Main Workflow ===
try:
    email = get_disposable_email()

    driver.get("https://lemonrealm.com/24-hours/")
    handle_cookies_and_popups()
    time.sleep(3)

    print("[+] Filling out form...")

    # Step 1: Email input
    email_input = wait_for_element(["//*[@id='b1-2-1']"])
    email_input.clear()
    email_input.send_keys(email)
    time.sleep(1)

    # Step 1: Next Button
    print("[+] Clicking Next button for Step 1...")
    next_btn_step1 = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[1]/div[2]/div/button[2]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[1]/div[2]/div/button[2]"
    ], clickable=True)
    js_click(next_btn_step1)
    time.sleep(5)

    # Step 2: Language dropdown
    print("[+] Waiting for Step 2 to load...")
    language_dropdown = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]"
    ], clickable=True)
    js_click(language_dropdown)
    time.sleep(2)

    # Step 2: English option
    print("[+] Selecting English...")
    english_option = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[6]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[6]"
    ], clickable=True)
    js_click(english_option)
    time.sleep(1)

    # Step 2: Adult content OFF
    print("[+] Setting adult content to OFF...")
    try:
        adult_off_label = wait_for_element(["//label[@for='b1-4-1-chk-1']"], clickable=True)
        js_click(adult_off_label)
        print("[+] Clicked OFF label")
        time.sleep(1)
    except Exception as e:
        print(f"[!] Error selecting adult content OFF: {e}")

    # Step 2: Next Button
    print("[+] Clicking Next button for Step 2...")
    next_btn_step2 = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[2]/div/button[2]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[2]/div/button[2]"
    ], clickable=True)
    js_click(next_btn_step2)
    time.sleep(2)

    # Step 3: Devices dropdown
    print("[+] Clicking devices dropdown...")
    devices_dropdown = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]"
    ], clickable=True)
    js_click(devices_dropdown)
    time.sleep(2)

    # Step 3: Select "4 Simultaneously"
    print("[+] Selecting 4 Simultaneously...")
    four_devices_option = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[4]",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[4]"
    ], clickable=True)
    js_click(four_devices_option)
    time.sleep(1)

    # Step 3: Submit Button
    print("[+] Submitting form...")
    submit_button = wait_for_element([
        "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[2]/div/div/div/button",
        "/html/body/div[1]/div[2]/div/div/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[2]/div/div/div/button"
    ], clickable=True)
    js_click(submit_button)
    print("[+] Form submitted!")
    time.sleep(5)

    print(f"[+] Current URL after submission: {driver.current_url}")
    print(f"[+] Page title after submission: {driver.title}")



    # Wait for email and download
    result = wait_for_email_link()
    if result:
        if isinstance(result, tuple):
            m3u_url, epg_url = result
        else:
            m3u_url, epg_url = result, None
        
        if download_and_save_m3u(m3u_url, SAVE_FILE):
            print("[✓] M3U saved successfully.")
        else:
            print("[!] Failed to download M3U file.")
        
        # Download EPG if found
        if epg_url:
            epg_file = SAVE_FILE.replace('.m3u', '_epg.xml')
            if download_and_save_m3u(epg_url, epg_file):
                print("[✓] EPG saved successfully.")
            else:
                print("[!] Failed to download EPG file.")
        else:
            print("[!] No EPG URL found.")
    else:
        print("[!] Failed to retrieve M3U link.")

        # Switch back to main tab to check the form page
        driver.switch_to.window(driver.window_handles[0])
        print(f"[DEBUG] Final form page URL: {driver.current_url}")
        print(f"[DEBUG] Final form page title: {driver.title}")

except Exception as e:
    print(f"[!] Error occurred: {e}")
    
finally:
    driver.quit()