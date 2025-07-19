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
SAVE_FILE = r"C:\Users\James\Documents\daily-iptv\iptv_daily\iptv_daily_update.m3u"
DRIVER_PATH = r"C:\Users\James\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"

# === Chrome Options ===
options = webdriver.ChromeOptions()
# options.add_argument("--headless")  # Enable headless
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(DRIVER_PATH), options=options)
wait = WebDriverWait(driver, 20)


start_time = time.time()

def elapsed_time():
    """Return HH:MM:SS since start"""
    elapsed = int(time.time() - start_time)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs:02}:{mins:02}:{secs:02}"


# === Utility Functions ===
def js_click(elem):
    driver.execute_script("arguments[0].click();", elem)


def try_find_click(selectors, timeout=5):
    """Try multiple selectors to find and click an element"""
    for by, selector in selectors:
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((by, selector)))
            js_click(elem)
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


def debug_page_state():
    """Debug function to inspect current page state"""
    print("[DEBUG] Current URL:", driver.current_url)
    print("[DEBUG] Page title:", driver.title)
    # Look for any elements that might be language-related
    try:
        elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'English') or contains(text(), 'language') or contains(text(), 'Language')]")
        print(f"[DEBUG] Found {len(elements)} language-related elements:")
        for i, elem in enumerate(elements[:5]):  # Show first 5
            print(f"  {i+1}. Tag: {elem.tag_name}, Text: '{elem.text}', Visible: {elem.is_displayed()}")
    except Exception as e:
        print(f"[DEBUG] Error finding language elements: {e}")


def get_disposable_email():
    """Fetch a disposable email address"""
    print("[+] Fetching disposable email...")
    # Open disposable email in a new tab
    driver.execute_script("window.open('https://www.disposablemail.com/', '_blank');")
    driver.switch_to.window(driver.window_handles[1])  # Switch to new tab
    
    handle_cookies_and_popups()
    try:
        email_elem = wait.until(EC.visibility_of_element_located((By.ID, "email")))
        email = email_elem.get_attribute("value") or email_elem.text
        if not email or "@" not in email:
            raise Exception("Email not found")
        print(f"[+] Disposable email acquired: {email}")
        
        # Switch back to main tab
        driver.switch_to.window(driver.window_handles[0])
        return email.strip()
    except Exception:
        # Fallback random email
        fallback_email = f"{''.join(random.choices(string.ascii_lowercase, k=10))}@example.com"
        print(f"[!] Using fallback email: {fallback_email}")
        # Switch back to main tab
        driver.switch_to.window(driver.window_handles[0])
        return fallback_email


def wait_for_email_link(max_wait=3600):
    """Poll mailbox for M3U link - handles both iframe and direct content"""
    print("[+] Waiting for M3U email...")
    # Switch to email tab (should be tab 1)
    driver.switch_to.window(driver.window_handles[1])
    
    start = time.time()
    while time.time() - start < max_wait:
        try:
            # Navigate to the email page
            driver.get("https://www.disposablemail.com/email/id/2")
            
            # Handle any consent popups on the email page
            try:
                consent_selectors = [
                    (By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'OK') or contains(text(), 'Agree') or contains(text(), 'Continue')]"),
                    (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]"),
                    (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'consent')]"),
                    (By.CSS_SELECTOR, "button[class*='consent']"),
                    (By.CSS_SELECTOR, "button[class*='accept']"),
                ]
                for by, selector in consent_selectors:
                    try:
                        consent_btn = WebDriverWait(driver, 2).until(EC.element_to_be_clickable((by, selector)))
                        js_click(consent_btn)
                        print("[+] Clicked consent/accept button")
                        time.sleep(1)
                        break
                    except TimeoutException:
                        continue
            except Exception:
                pass

            print(f"[{elapsed_time()}] Searching for M3U links on page...")
            
            # First, try to find M3U links directly on the page (without iframe)
            m3u_url = search_for_m3u_links()
            if m3u_url:
                return m3u_url
            
            # If no direct links found, try iframe approach
            print(f"[{elapsed_time()}] No direct links found, looking for iframe...")
            iframe_elem = None
            iframe_selectors = [
                (By.TAG_NAME, "iframe"),
                (By.CSS_SELECTOR, "iframe[src*='email']"),
                (By.XPATH, "//iframe"),
                (By.CSS_SELECTOR, "iframe[id*='email']"),
                (By.CSS_SELECTOR, "iframe[class*='email']"),
            ]
            
            for by, selector in iframe_selectors:
                try:
                    iframe_elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    print(f"[{elapsed_time()}] Found iframe with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if iframe_elem:
                print(f"[{elapsed_time()}] Found iframe, switching to it...")
                driver.switch_to.frame(iframe_elem)
                time.sleep(2)
                
                # Search for M3U links within the iframe
                m3u_url = search_for_m3u_links()
                
                # Switch back to default content
                driver.switch_to.default_content()
                
                if m3u_url:
                    return m3u_url
            else:
                print(f"[{elapsed_time()}] No iframe found on page")
                
                # Debug: Print page source snippet to see what's actually there
                try:
                    page_source = driver.page_source
                    print(f"[{elapsed_time()}] Page source length: {len(page_source)}")
                    
                    # Look for any M3U patterns in the full page source
                    m3u_patterns = [
                        r'https?://[^\s<>"\']+\.m3u[^\s<>"\']*',
                        r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u[^\s<>"\']*',
                        r'href=["\']([^"\']*(?:\.m3u|type=m3u)[^"\']*)["\']',
                    ]
                    
                    for pattern in m3u_patterns:
                        matches = re.findall(pattern, page_source, re.IGNORECASE)
                        for match in matches:
                            url = match if isinstance(match, str) else match[0] if match else ""
                            if url and ("m3u" in url.lower() or "get.php" in url.lower()):
                                print(f"[{elapsed_time()}] M3U URL found in page source: {url}")
                                return url
                    
                    # Show a sample of the page content for debugging
                    if "lemonrealm" in page_source.lower() or "m3u" in page_source.lower():
                        print(f"[{elapsed_time()}] Page contains LemonRealm content")
                        # Find the email content section
                        body_start = page_source.find("<body")
                        if body_start != -1:
                            body_content = page_source[body_start:body_start+2000]
                            print(f"[{elapsed_time()}] Body content sample: {body_content[:500]}...")
                    else:
                        print(f"[{elapsed_time()}] Page doesn't seem to contain expected email content")
                        
                except Exception as e:
                    print(f"[{elapsed_time()}] Error analyzing page source: {e}")

            print(f"[{elapsed_time()}] No M3U link found, retrying in 30s...")
            time.sleep(30)

        except Exception as e:
            print(f"[{elapsed_time()}] Error checking email: {e}")
            import traceback
            traceback.print_exc()
            # Make sure we're back to default content
            try:
                driver.switch_to.default_content()
            except:
                pass
            time.sleep(30)

    print(f"[{elapsed_time()}] Timed out waiting for M3U link")
    return None


def search_for_m3u_links():
    """Search for M3U links in current context (page or iframe)"""
    try:
        # Method 1: Look for direct M3U links
        m3u_selectors = [
            (By.XPATH, "//a[contains(@href, '.m3u')]"),
            (By.XPATH, "//a[contains(@href, 'get.php') and contains(@href, 'type=m3u')]"),
            (By.XPATH, "//a[contains(text(), '.m3u')]"),
            (By.XPATH, "//a[contains(@href, 'http') and contains(@href, 'm3u')]"),
            (By.CSS_SELECTOR, "a[href*='.m3u']"),
            (By.CSS_SELECTOR, "a[href*='get.php'][href*='type=m3u']"),
        ]
        
        for by, selector in m3u_selectors:
            try:
                m3u_elements = driver.find_elements(by, selector)
                for elem in m3u_elements:
                    href = elem.get_attribute("href")
                    if href and ("m3u" in href.lower() or "get.php" in href.lower()):
                        print(f"[{elapsed_time()}] M3U link found via selector: {href}")
                        return href
            except Exception:
                continue
        
        # Method 2: Look for text that looks like M3U URLs
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            page_html = driver.find_element(By.TAG_NAME, "body").get_attribute("innerHTML")
            
            print(f"[{elapsed_time()}] Body text length: {len(page_text)}")
            print(f"[{elapsed_time()}] Body HTML length: {len(page_html)}")
            
            # Search for M3U URLs in the content
            m3u_patterns = [
                r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u_plus[^\s<>"\']*',
                r'https?://[^\s<>"\']+\.m3u[^\s<>"\']*',
                r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u[^\s<>"\']*',
                r'href=["\']([^"\']*(?:get\.php[^"\']*type=m3u|\.m3u)[^"\']*)["\']',
            ]
            
            combined_content = page_html + " " + page_text
            
            for pattern in m3u_patterns:
                matches = re.findall(pattern, combined_content, re.IGNORECASE)
                for match in matches:
                    url = match if isinstance(match, str) else match[0] if match else ""
                    if url and ("m3u" in url.lower() or "get.php" in url.lower()):
                        # Clean up the URL (remove HTML entities, etc.)
                        url = url.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                        print(f"[{elapsed_time()}] M3U URL found via regex: {url}")
                        return url
            
            # Debug: Show sample content if it contains relevant keywords
            if any(keyword in combined_content.lower() for keyword in ["lemonrealm", "m3u", "get.php", "username", "password"]):
                print(f"[{elapsed_time()}] Content contains relevant keywords")
                # Find lines that might contain M3U info
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if any(keyword in line.lower() for keyword in ["m3u", "get.php", "http"]):
                        print(f"[{elapsed_time()}] Relevant line {i}: {line.strip()[:100]}...")
                        
        except Exception as e:
            print(f"[{elapsed_time()}] Error reading page content: {e}")
        
        return None
        
    except Exception as e:
        print(f"[{elapsed_time()}] Error in search_for_m3u_links: {e}")
        return None


def download_m3u_file(m3u_url, save_path, max_retries=3):
    """Download M3U file with proper headers and retry logic"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/plain, application/x-mpegURL, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for attempt in range(max_retries):
        try:
            print(f"[{elapsed_time()}] Download attempt {attempt + 1} of {max_retries}")
            print(f"[{elapsed_time()}] URL: {m3u_url}")
            
            # Create session for better connection handling
            session = requests.Session()
            session.headers.update(headers)
            
            # Set timeouts
            response = session.get(
                m3u_url, 
                timeout=(10, 30),  # (connection_timeout, read_timeout)
                allow_redirects=True,
                stream=True  # Stream download for large files
            )
            
            # Check if request was successful
            response.raise_for_status()
            
            print(f"[{elapsed_time()}] Response status: {response.status_code}")
            print(f"[{elapsed_time()}] Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
            print(f"[{elapsed_time()}] Content-Length: {response.headers.get('Content-Length', 'Unknown')}")
            
            # Check if response looks like an M3U file
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text' not in content_type and 'mpegurl' not in content_type and 'octet-stream' not in content_type:
                print(f"[!] Warning: Unexpected content type: {content_type}")
            
            # Write file in chunks
            total_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        f.write(chunk)
                        total_size += len(chunk)
            
            print(f"[{elapsed_time()}] Downloaded {total_size} bytes successfully")
            
            # Verify the file was created and has content
            if os.path.exists(save_path):
                file_size = os.path.getsize(save_path)
                print(f"[{elapsed_time()}] File saved: {save_path} ({file_size} bytes)")
                
                # Quick check if it looks like an M3U file
                try:
                    with open(save_path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_lines = f.read(500)
                        if '#EXTM3U' in first_lines or '#EXTINF' in first_lines or 'http' in first_lines:
                            print(f"[✓] File appears to be a valid M3U playlist")
                            return True
                        else:
                            print(f"[!] Warning: File doesn't look like an M3U playlist")
                            print(f"[!] First 200 chars: {first_lines[:200]}")
                except Exception as e:
                    print(f"[!] Could not verify file content: {e}")
                
                return True
            else:
                print(f"[!] File was not created successfully")
                return False
                
        except requests.exceptions.ConnectionError as e:
            print(f"[!] Connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5  # Progressive backoff
                print(f"[{elapsed_time()}] Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            
        except requests.exceptions.Timeout as e:
            print(f"[!] Timeout error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                print(f"[{elapsed_time()}] Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
        except requests.exceptions.HTTPError as e:
            print(f"[!] HTTP error on attempt {attempt + 1}: {e}")
            print(f"[!] Response status code: {e.response.status_code if e.response else 'Unknown'}")
            if e.response:
                print(f"[!] Response headers: {dict(e.response.headers)}")
                print(f"[!] Response content: {e.response.text[:500]}")
            
            # Don't retry on client errors (4xx), but retry on server errors (5xx)
            if e.response and e.response.status_code < 500:
                print(f"[!] Client error - not retrying")
                break
            elif attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"[{elapsed_time()}] Server error - waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"[!] Unexpected error on attempt {attempt + 1}: {e}")
            import traceback
            traceback.print_exc()
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"[{elapsed_time()}] Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    print(f"[!] Failed to download after {max_retries} attempts")
    return False


# Updated main download logic to use in your script
def download_and_save_m3u(m3u_url, save_path):
    """Main download function that tries multiple methods"""
    print(f"[+] Downloading M3U from: {m3u_url}")
    print(f"[+] Saving to: {save_path}")
    
    # Method 1: Try with requests
    if download_m3u_file(m3u_url, save_path):
        print("[✓] M3U downloaded successfully with requests")
        return True
    
    print("[!] All download methods failed")
    return False



# === Main Workflow ===
try:
    email = get_disposable_email()

    # Go to lemonrealm and fill out form
    driver.get("https://lemonrealm.com/24-hours/")
    handle_cookies_and_popups()
    
    # Wait a bit for page to fully load
    time.sleep(3)

    print("[+] Filling out form...")
    # Step 1: Email input
    email_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='b1-2-1']")))
    email_input.clear()
    email_input.send_keys(email)
    
    # Wait a moment for the email to be processed
    time.sleep(1)
    
    # Click Next button using exact XPath - FIXED: removed duplicate line
    print("[+] Clicking Next button for Step 1...")
    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[1]/div[2]/div/button[2]")))
    js_click(next_button)
    
    # Wait longer for next step to load and verify we moved to step 2
    print("[+] Waiting for Step 2 to load...")
    time.sleep(5)
    
    # Try to verify we're on step 2 by looking for the language dropdown
    try:
        language_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]"))
        )
        print("[+] Step 2 loaded successfully!")
    except TimeoutException:
        print("[!] Step 2 did not load - checking for validation errors...")
        # Check if there are any validation error messages
        try:
            error_elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'invalid') or contains(text(), 'required') or contains(text(), 'invalid')]")
            if error_elements:
                print(f"[!] Found {len(error_elements)} potential error messages:")
                for error in error_elements:
                    if error.is_displayed():
                        print(f"  Error: {error.text}")
            else:
                print("[!] No obvious error messages found")
        except Exception as e:
            print(f"[!] Error checking for validation messages: {e}")
        
        raise Exception("Failed to proceed to Step 2")

    # Step 2: Set language and adult content
    print("[+] Clicking language dropdown...")
    # Click language dropdown
    language_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]")))
    js_click(language_dropdown)
    
    # Wait for dropdown to open
    time.sleep(2)
    
    # Click English option
    print("[+] Selecting English...")
    english_option = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[6]")))
    js_click(english_option)
    
    # Click adult content OFF button (radio button)
    print("[+] Setting adult content to OFF...")
    try:
        # Primary method: Click the label associated with the radio button
        adult_off_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[@for='b1-4-1-chk-1']")))
        js_click(adult_off_label)
        print("[+] Clicked OFF label")
        
        # Give it a moment to register the selection
        time.sleep(1)
        
        # Verify it's selected (optional debug)
        try:
            adult_off_button = driver.find_element(By.XPATH, "//*[@id='b1-4-1-chk-1']")
            if adult_off_button.is_selected():
                print("[+] OFF option confirmed selected")
            else:
                print("[!] OFF option may not be selected, but continuing...")
        except:
            print("[+] Could not verify selection state, continuing...")
            
    except Exception as e:
        print(f"[!] Error with adult content label selection: {e}")
        # Fallback 1: Try clicking the radio button directly
        try:
            adult_off_button = driver.find_element(By.XPATH, "//*[@id='b1-4-1-chk-1']")
            js_click(adult_off_button)
            print("[+] Clicked OFF radio button as fallback")
        except NoSuchElementException:
            # Fallback 2: Try finding and clicking the parent container
            try:
                adult_off_container = driver.find_element(By.XPATH, "//*[@id='b1-4-1-chk-1']/parent::*")
                js_click(adult_off_container)
                print("[+] Clicked OFF container as fallback")
            except NoSuchElementException:
                # Last resort - look for text "Off" 
                try:
                    off_text_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'Off')]")
                    js_click(off_text_elem)
                    print("[+] Clicked OFF text element as fallback")
                except NoSuchElementException:
                    print("[!] Could not find OFF option with any method, continuing...")

    # Click Next button using exact XPath
    print("[+] Clicking Next button for Step 2...")
    next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[2]/div[2]/div/button[2]")))
    js_click(next_button)
    
    # Wait for next step
    time.sleep(2)
    print("[+] Step 2 completed, moving to Step 3...")

    # Step 3: Set devices and submit
    print("[+] Clicking devices dropdown...")
    # Click devices dropdown
    devices_dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[1]")))
    js_click(devices_dropdown)
    
    # Wait for dropdown to open
    time.sleep(2)
    
    # Click 4 Simultaneously option
    print("[+] Selecting 4 Simultaneously...")
    four_devices_option = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[1]/div/div[2]/div[1]/div/div[2]/div/ul[2]/li[4]")))
    js_click(four_devices_option)
    
    # Submit the form
    print("[+] Submitting form...")
    submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div[2]/div/div/div/div/div/form/div/div[2]/div[2]/div[3]/div[1]/div[2]/div/div/div/button")))
    js_click(submit_button)
    print("[+] Form submitted!")
    
    # Wait a moment to see if anything happens on the page
    time.sleep(5)
    
    # Check current page state after submission
    print(f"[+] Current URL after submission: {driver.current_url}")
    print(f"[+] Page title after submission: {driver.title}")
    
    # Look for any success/confirmation messages
    try:
        success_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'success') or contains(text(), 'Success') or contains(text(), 'sent') or contains(text(), 'Sent') or contains(text(), 'email')]")
        if success_elements:
            print("[+] Found potential success messages:")
            for elem in success_elements:
                if elem.is_displayed() and elem.text.strip():
                    print(f"  - {elem.text.strip()}")
    except Exception as e:
        print(f"[!] Error checking for success messages: {e}")


    # Wait for email and download
    m3u_url = wait_for_email_link()
    if m3u_url:
        if download_and_save_m3u(m3u_url, SAVE_FILE):
            print("[✓] M3U saved successfully.")
        else:
            print("[!] Failed to download M3U file.")
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