from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time, re, random, string, os
import requests

# === Settings ===
# SAVE_FILE = "iptv_daily/iptvore_daily_update.m3u"
# EPG_SAVE_FILE = "iptv_daily/iptvore_daily_update_epg.xml"
# DRIVER_PATH = "/usr/bin/chromedriver"

SAVE_FILE = r"C:\Users\James\Documents\daily-iptv\iptv_daily/iptvore_daily_update.m3u"
EPG_SAVE_FILE = r"C:\Users\James\Documents\daily-iptv\iptv_daily/iptvore_daily_update_epg.xml"
DRIVER_PATH = r"C:\Users\James\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"

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
    """Fetch a disposable email address"""
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
        
        driver.switch_to.window(driver.window_handles[0])
        return email.strip()
        
    except Exception as e:
        print(f"[!] Error getting disposable email: {e}")
        fallback_email = f"{''.join(random.choices(string.ascii_lowercase, k=10))}@example.com"
        print(f"[!] Using fallback email: {fallback_email}")
        try:
            driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return fallback_email

def wait_for_email_link(max_wait=3600):
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
    """Search for M3U links in current context - optimized for IPTVore email format"""
    try:
        # Get page content
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            page_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
            combined_content = page_html + " " + page_text
        except Exception as e:
            print(f"[{elapsed_time()}] Error reading page content: {e}")
            return None
        
        print(f"[{elapsed_time()}] Searching email content for M3U and EPG links...")
        
        m3u_url = None
        epg_url = None
        
        # Method 1: Look for direct M3U links in HTML elements
        m3u_selectors = [
            (By.XPATH, "//a[contains(@href, 'get.php') and contains(@href, 'type=m3u')]"),
            (By.XPATH, "//a[contains(@href, '.m3u')]"),
            (By.CSS_SELECTOR, "a[href*='get.php'][href*='type=m3u']"),
            (By.CSS_SELECTOR, "a[href*='.m3u']"),
        ]
        
        for by, selector in m3u_selectors:
            try:
                m3u_elements = driver.find_elements(by, selector)
                for elem in m3u_elements:
                    href = elem.get_attribute("href")
                    if href and ("get.php" in href and "type=m3u" in href):
                        m3u_url = href.replace("&amp;", "&")
                        print(f"[{elapsed_time()}] Found M3U link via HTML: {m3u_url}")
                        break
                if m3u_url:
                    break
            except Exception:
                continue
        
        # Method 2: Look for EPG links in HTML elements
        epg_selectors = [
            (By.XPATH, "//a[contains(@href, 'xmltv.php')]"),
            (By.CSS_SELECTOR, "a[href*='xmltv.php']"),
        ]
        
        for by, selector in epg_selectors:
            try:
                epg_elements = driver.find_elements(by, selector)
                for elem in epg_elements:
                    href = elem.get_attribute("href")
                    if href and "xmltv.php" in href:
                        epg_url = href.replace("&amp;", "&")
                        print(f"[{elapsed_time()}] Found EPG link via HTML: {epg_url}")
                        break
                if epg_url:
                    break
            except Exception:
                continue
        
        # Method 3: Regex search for IPTVore specific patterns
        if not m3u_url or not epg_url:
            print(f"[{elapsed_time()}] Trying regex patterns for IPTVore format...")
            
            # IPTVore specific M3U patterns
            m3u_patterns = [
                r'https?://[^\s<>"\']+/get\.php\?username=[^&\s<>"\']+&password=[^&\s<>"\']+&type=m3u_plus[^\s<>"\']*',
                r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u_plus[^\s<>"\']*',
                r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u[^\s<>"\']*',
                r'M3U LINK:\s*([^\s<>"\']+get\.php[^\s<>"\']*)',
            ]
            
            for pattern in m3u_patterns:
                matches = re.findall(pattern, combined_content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    url = match.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    if url and "get.php" in url and ("m3u" in url.lower() or "type=" in url):
                        m3u_url = url
                        print(f"[{elapsed_time()}] Found M3U URL via regex: {m3u_url}")
                        break
                if m3u_url:
                    break
            
            # IPTVore specific EPG patterns  
            epg_patterns = [
                r'https?://[^\s<>"\']+/xmltv\.php\?username=[^&\s<>"\']+&password=[^&\s<>"\']+',
                r'https?://[^\s<>"\']+xmltv\.php[^\s<>"\']*',
                r'EPG LINK:\s*([^\s<>"\']+xmltv\.php[^\s<>"\']*)',
            ]
            
            for pattern in epg_patterns:
                matches = re.findall(pattern, combined_content, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    url = match.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                    if url and "xmltv.php" in url:
                        epg_url = url
                        print(f"[{elapsed_time()}] Found EPG URL via regex: {epg_url}")
                        break
                if epg_url:
                    break
        
        # Method 4: Look for text patterns in the M3U Section
        if not m3u_url or not epg_url:
            print(f"[{elapsed_time()}] Searching for M3U Section text patterns...")
            
            # Look for the M3U section and extract URLs from it
            m3u_section_pattern = r'M3U Section.*?(?=\n\n|Important Note|$)'
            m3u_section_match = re.search(m3u_section_pattern, combined_content, re.IGNORECASE | re.DOTALL)
            
            if m3u_section_match:
                m3u_section_text = m3u_section_match.group(0)
                print(f"[{elapsed_time()}] Found M3U Section text")
                
                # Extract M3U link from section
                if not m3u_url:
                    m3u_in_section = re.search(r'(https?://[^\s]+get\.php[^\s]*)', m3u_section_text)
                    if m3u_in_section:
                        m3u_url = m3u_in_section.group(1)
                        print(f"[{elapsed_time()}] Extracted M3U from section: {m3u_url}")
                
                # Extract EPG link from section  
                if not epg_url:
                    epg_in_section = re.search(r'(https?://[^\s]+xmltv\.php[^\s]*)', m3u_section_text)
                    if epg_in_section:
                        epg_url = epg_in_section.group(1)
                        print(f"[{elapsed_time()}] Extracted EPG from section: {epg_url}")
        
        # Return results
        if m3u_url:
            print(f"[{elapsed_time()}] Final M3U URL: {m3u_url}")
            if epg_url:
                print(f"[{elapsed_time()}] Final EPG URL: {epg_url}")
                return m3u_url, epg_url
            else:
                print(f"[{elapsed_time()}] No EPG URL found")
                return m3u_url, None
        else:
            print(f"[{elapsed_time()}] No M3U URL found")
            return None
        
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

    driver.get("https://iptvore.net/iptv-free-trial-2025/")
    handle_cookies_and_popups()
    time.sleep(3)

    print("[+] Filling out IPTVore form...")

    # Email input - looking for common email field patterns
    email_selectors = [
        "//input[@type='email']",
        "//input[contains(@name, 'email')]",
        "//input[contains(@id, 'email')]",
        "//input[contains(@placeholder, 'email')]"
    ]
    
    print("[+] Looking for email field...")
    email_input = None
    for selector in email_selectors:
        try:
            email_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, selector))
            )
            print(f"[+] Found email field with selector: {selector}")
            break
        except TimeoutException:
            continue
    
    if not email_input:
        print("[!] Could not find email field, trying fallback...")
        # Fallback to any input field that might be email
        email_input = wait_for_element(["//input[@type='text'][1]"])
    
    email_input.clear()
    email_input.send_keys(email)
    print(f"[+] Entered email: {email}")
    
    # Properly exit the email field
    try:
        email_input.send_keys(Keys.TAB)  # Tab out of email field
        time.sleep(1)
    except:
        pass
    
    # Click somewhere neutral to ensure focus is removed from email field
    try:
        driver.execute_script("document.activeElement.blur();")
        time.sleep(1)
    except:
        pass


    # Country field - simplified working version
    print("[+] Looking for country field...")
    try:
        # Find the Select2 container
        country_field = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/article/div/div/section[2]/div/div[1]/div/div[3]/div/div/form/div[2]/div[1]/div/div[2]/div/span"))
        )
        print(f"[+] Found country field")
        
        # Scroll to element and ensure it's visible
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", country_field)
        time.sleep(2)
        
        # Click to open dropdown (regular click worked)
        country_field.click()
        time.sleep(3)
        
        # Find and use the search box
        search_box = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//input[@class='select2-search__field']"))
        )
        print("[+] Found search box")
        
        # Type and select United Kingdom
        search_box.clear()
        search_box.send_keys("United Kingdom")
        time.sleep(2)
        search_box.send_keys(Keys.ENTER)
        
        print("[+] Successfully selected United Kingdom")
        
    except Exception as e:
        print(f"[!] Error with country selection: {e}")
        print("[!] Continuing without country selection...")

    time.sleep(2)


    # Submit button
    print("[+] Submitting form...")
    submit_button = wait_for_element([
        "//*[@id='wpforms-submit-10636']",
        "//button[@type='submit']",
        "//input[@type='submit']",
        "//button[contains(text(), 'Submit')]"
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