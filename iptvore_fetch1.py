from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time, re, random, string, os, gc
import requests
from contextlib import contextmanager
import subprocess
from urllib.parse import urlparse, parse_qs

# === Settings ===
SAVE_FILE = "iptv_daily/iptvore_daily_update.m3u"
EPG_SAVE_FILE = "iptv_daily/iptvore_daily_update_epg.xml"
DRIVER_PATH = "/usr/bin/chromedriver"

# VPS-optimized Chrome options
def get_vps_optimized_options():
    """Return Chrome options optimized for small VPS"""
    options = webdriver.ChromeOptions()
    
    # Essential headless settings
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Memory optimization - crucial for small VPS
    options.add_argument("--memory-pressure-off")
    options.add_argument("--max-old-space-size=1024")  # Reduced from 4096
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--single-process")  # Use single process to save memory
    options.add_argument("--no-zygote")  # Disable zygote process
    
    # Disable resource-heavy features
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")  # Save bandwidth and memory
    options.add_argument("--disable-javascript")  # We'll enable only when needed
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor,AudioServiceOutOfProcess")
    
    # Minimal window size to save memory
    options.add_argument("--window-size=800,600")  # Smaller than original
    
    # Performance optimizations
    options.add_argument("--disable-logging")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    
    # Anti-detection (minimal)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Minimal preferences
    prefs = {
        "profile.default_content_setting_values": {
            "notifications": 2,
            "media_stream": 2,
            "geolocation": 2,
        },
        "profile.managed_default_content_settings": {
            "images": 2  # Block images
        }
    }
    options.add_experimental_option("prefs", prefs)
    
    return options

@contextmanager
def managed_driver():
    """Context manager for driver with proper cleanup and memory management"""
    driver = None
    try:
        options = get_vps_optimized_options()
        service = Service(DRIVER_PATH)
        service.start()
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(5)  # Reduced from 10
        driver.set_window_size(800, 600)  # Smaller window
        
        # Enable JavaScript only when needed
        driver.execute_script("navigator.webdriver = undefined;")
        
        yield driver
        
    finally:
        if driver:
            try:
                # Clear cache and cookies before closing
                driver.execute_script("window.localStorage.clear();")
                driver.execute_script("window.sessionStorage.clear();")
                driver.delete_all_cookies()
            except:
                pass
            driver.quit()
        
        # Force garbage collection
        gc.collect()

class VPSOptimizedWait:
    """Optimized wait class for VPS with shorter timeouts"""
    def __init__(self, driver, default_timeout=10):  # Reduced from 20
        self.driver = driver
        self.default_timeout = default_timeout
    
    def until(self, condition, timeout=None):
        timeout = timeout or self.default_timeout
        return WebDriverWait(self.driver, timeout).until(condition)

start_time = time.time()

def elapsed_time():
    """Return HH:MM:SS since start"""
    elapsed = int(time.time() - start_time)
    hrs, rem = divmod(elapsed, 3600)
    mins, secs = divmod(rem, 60)
    return f"{hrs:02}:{mins:02}:{secs:02}"

def memory_cleanup():
    """Force memory cleanup"""
    gc.collect()

def js_click(driver, elem):
    """More reliable click using JavaScript with error handling"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", elem)
        time.sleep(0.3)  # Reduced wait time
        driver.execute_script("arguments[0].click();", elem)
        return True
    except Exception as e:
        print(f"[!] JS click failed: {e}")
        return False

def try_find_click(driver, selectors, timeout=3):  # Reduced timeout
    """Try multiple selectors to find and click an element"""
    wait = VPSOptimizedWait(driver, timeout)
    for by, selector in selectors:
        try:
            elem = wait.until(EC.element_to_be_clickable((by, selector)))
            if js_click(driver, elem):
                return True
        except TimeoutException:
            continue
    return False

def try_find_element(driver, selectors, timeout=5):  # Reduced timeout
    """Try multiple selectors to find an element"""
    wait = VPSOptimizedWait(driver, timeout)
    for by, selector in selectors:
        try:
            elem = wait.until(EC.presence_of_element_located((by, selector)))
            return elem
        except TimeoutException:
            continue
    return None

def handle_cookies_and_popups(driver):
    """Try to accept cookies or close modals - optimized"""
    print("[+] Handling cookies/popups...")
    selectors = [
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'accept')]"),
        (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'),'agree')]"),
        (By.XPATH, "//button[contains(text(),'OK')]"),
        (By.CSS_SELECTOR, "button#onetrust-accept-btn-handler"),
    ]
    try_find_click(driver, selectors, timeout=2)  # Reduced timeout
    
    # Simplified popup removal
    try:
        driver.execute_script("""
            var popups = document.querySelectorAll('div[class*="cookie"],div[class*="modal"],div[class*="overlay"]');
            popups.forEach(e => e.remove());
            document.body.style.overflow = 'auto';
        """)
    except:
        pass

def get_disposable_email(driver):
    """Fetch a disposable email address - optimized"""
    print("[+] Fetching disposable email...")
    
    # Store original window
    original_window = driver.current_window_handle
    
    driver.execute_script("window.open('https://www.disposablemail.com/', '_blank');")
    driver.switch_to.window(driver.window_handles[1])
    
    handle_cookies_and_popups(driver)
    
    try:
        wait = VPSOptimizedWait(driver, 15)
        # Get the email address with shorter timeout
        email_elem = wait.until(EC.visibility_of_element_located((By.ID, "email")))
        email = email_elem.get_attribute("value") or email_elem.text
        
        if not email or "@" not in email:
            raise Exception("Email not found")
            
        print(f"[+] Disposable email acquired: {email}")
        driver.switch_to.window(original_window)
        return email.strip()
        
    except Exception as e:
        print(f"[!] Error getting disposable email: {e}")
        fallback_email = f"{''.join(random.choices(string.ascii_lowercase, k=8))}@example.com"  # Shorter random string
        print(f"[!] Using fallback email: {fallback_email}")
        try:
            driver.switch_to.window(original_window)
        except:
            pass
        return fallback_email

def wait_for_email_link(driver, max_wait=1800):  # Reduced from 3600
    """Poll mailbox for M3U link - optimized for VPS"""
    print("[+] Waiting for M3U email...")
    driver.switch_to.window(driver.window_handles[1])
    
    start = time.time()
    check_interval = 45  # Increased interval to reduce resource usage
    
    while time.time() - start < max_wait:
        try:
            driver.get("https://www.disposablemail.com/email/id/2")
            
            # Quick consent handling
            consent_selectors = [
                (By.XPATH, "//button[contains(text(), 'Accept')]"),
                (By.XPATH, "//button[contains(text(), 'OK')]"),
            ]
            try_find_click(driver, consent_selectors, timeout=1)

            print(f"[{elapsed_time()}] Searching for M3U links...")
            
            # Search for M3U links
            result = search_for_m3u_links(driver)
            if result:
                return result
            
            print(f"[{elapsed_time()}] No M3U link found, retrying in {check_interval}s...")
            
            # Memory cleanup during wait
            memory_cleanup()
            time.sleep(check_interval)

        except Exception as e:
            print(f"[{elapsed_time()}] Error checking email: {e}")
            try:
                driver.switch_to.default_content()
            except:
                pass
            time.sleep(check_interval)

    print(f"[{elapsed_time()}] Timed out waiting for M3U link")
    return None

def search_for_m3u_links(driver):
    """Search for M3U links in current context - optimized"""
    try:
        # Get page content more efficiently
        try:
            page_html = driver.execute_script("return document.body.innerHTML;")
            page_text = driver.execute_script("return document.body.innerText;")
            combined_content = page_html + " " + page_text
        except Exception as e:
            print(f"[{elapsed_time()}] Error reading page content: {e}")
            return None
        
        print(f"[{elapsed_time()}] Searching email content...")
        
        m3u_url = None
        epg_url = None
        
        # Method 1: Direct HTML search (most efficient)
        m3u_selectors = [
            (By.XPATH, "//a[contains(@href, 'get.php') and contains(@href, 'type=m3u')]"),
            (By.CSS_SELECTOR, "a[href*='get.php'][href*='type=m3u']"),
        ]
        
        for by, selector in m3u_selectors:
            try:
                m3u_elements = driver.find_elements(by, selector)
                for elem in m3u_elements:
                    href = elem.get_attribute("href")
                    if href and ("get.php" in href and "type=m3u" in href):
                        m3u_url = href.replace("&amp;", "&")
                        print(f"[{elapsed_time()}] Found M3U link: {m3u_url}")
                        break
                if m3u_url:
                    break
            except Exception:
                continue
        
        # Method 2: EPG links
        if not epg_url:
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
                            print(f"[{elapsed_time()}] Found EPG link: {epg_url}")
                            break
                    if epg_url:
                        break
                except Exception:
                    continue
        
        # Method 3: Regex fallback (only if needed)
        if not m3u_url:
            print(f"[{elapsed_time()}] Using regex fallback...")
            m3u_patterns = [
                r'https?://[^\s<>"\']+/get\.php\?username=[^&\s<>"\']+&password=[^&\s<>"\']+&type=m3u_plus[^\s<>"\']*',
                r'https?://[^\s<>"\']+get\.php[^\s<>"\']*type=m3u[^\s<>"\']*',
            ]
            
            for pattern in m3u_patterns:
                matches = re.findall(pattern, combined_content, re.IGNORECASE)
                if matches:
                    m3u_url = matches[0].replace("&amp;", "&")
                    print(f"[{elapsed_time()}] Found M3U URL via regex: {m3u_url}")
                    break
        
        # Return results
        if m3u_url:
            return m3u_url, epg_url
        else:
            return None
        
    except Exception as e:
        print(f"[{elapsed_time()}] Error in search_for_m3u_links: {e}")
        return None

def download_m3u_file(url, save_path, max_retries=3, is_m3u=True):
    """Download file with adaptive timeout based on file type"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/plain, application/x-mpegURL, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Accept-Encoding': 'gzip, deflate',
    }
    
    # Adaptive timeout based on file type
    if is_m3u:
        connect_timeout = 10
        read_timeout = 120  # Much longer for large M3U files
        chunk_size = 8192   # Larger chunks for M3U
        print(f"[{elapsed_time()}] Using extended timeout for M3U file (120s read timeout)")
    else:
        connect_timeout = 5
        read_timeout = 30   # Shorter for EPG files
        chunk_size = 4096
        print(f"[{elapsed_time()}] Using standard timeout for EPG file (30s read timeout)")
    
    for attempt in range(max_retries):
        try:
            print(f"[{elapsed_time()}] Download attempt {attempt + 1}/{max_retries}")
            
            with requests.Session() as session:
                session.headers.update(headers)
                
                # Start the request
                response = session.get(
                    url, 
                    timeout=(connect_timeout, read_timeout), 
                    allow_redirects=True, 
                    stream=True
                )
                response.raise_for_status()
                
                print(f"[{elapsed_time()}] Response status: {response.status_code}")
                
                # Get content length if available
                content_length = response.headers.get('content-length')
                if content_length:
                    total_expected = int(content_length)
                    print(f"[{elapsed_time()}] Expected file size: {total_expected:,} bytes")
                else:
                    total_expected = None
                    print(f"[{elapsed_time()}] File size unknown, downloading...")
                
                total_downloaded = 0
                last_progress_time = time.time()
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            total_downloaded += len(chunk)
                            
                            # Progress reporting every 10 seconds for large files
                            current_time = time.time()
                            if current_time - last_progress_time >= 10:
                                if total_expected:
                                    progress = (total_downloaded / total_expected) * 100
                                    print(f"[{elapsed_time()}] Progress: {total_downloaded:,}/{total_expected:,} bytes ({progress:.1f}%)")
                                else:
                                    print(f"[{elapsed_time()}] Downloaded: {total_downloaded:,} bytes")
                                last_progress_time = current_time
                
                print(f"[{elapsed_time()}] Download completed: {total_downloaded:,} bytes")
                
                # Verify file was saved correctly
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    file_size = os.path.getsize(save_path)
                    print(f"[{elapsed_time()}] File saved successfully: {save_path} ({file_size:,} bytes)")
                    
                    # Additional verification for M3U files
                    if is_m3u:
                        try:
                            with open(save_path, 'r', encoding='utf-8') as f:
                                first_line = f.readline().strip()
                                if first_line.startswith('#EXTM3U'):
                                    print(f"[{elapsed_time()}] M3U file format verified")
                                else:
                                    print(f"[{elapsed_time()}] Warning: File may not be valid M3U format")
                        except Exception as e:
                            print(f"[{elapsed_time()}] Warning: Could not verify M3U format: {e}")
                    
                    return True
                else:
                    raise Exception("File was not saved or is empty")
                    
        except requests.exceptions.ReadTimeout as e:
            print(f"[!] Download attempt {attempt + 1} failed: Read timeout after {read_timeout}s")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                print(f"[{elapsed_time()}] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            
        except requests.exceptions.ConnectTimeout as e:
            print(f"[!] Download attempt {attempt + 1} failed: Connection timeout")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                print(f"[{elapsed_time()}] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                
        except Exception as e:
            print(f"[!] Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 3
                print(f"[{elapsed_time()}] Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        finally:
            # Cleanup
            memory_cleanup()
    
    print(f"[!] All download attempts failed for {url}")
    return False

def wait_for_element(driver, xpaths, wait_time=5, clickable=False):  # Reduced timeout
    """Try multiple XPaths and return the first one that works"""
    wait = VPSOptimizedWait(driver, wait_time)
    for xpath in xpaths:
        try:
            if clickable:
                elem = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            else:
                elem = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            print(f"[+] Found element with XPath: {xpath}")
            return elem
        except TimeoutException:
            continue
    raise Exception("[-] None of the XPaths worked for this element")

def truncate_m3u_file(file_path, max_lines=92025):
    """Truncate M3U file - memory efficient version"""
    print(f"[+] Truncating {file_path} to {max_lines} lines...")
    
    temp_path = file_path + ".tmp"
    
    try:
        with open(file_path, 'r', encoding='utf-8', buffering=8192) as infile:
            with open(temp_path, 'w', encoding='utf-8', buffering=8192) as outfile:
                for i, line in enumerate(infile):
                    if i >= max_lines:
                        break
                    outfile.write(line)
        
        os.replace(temp_path, file_path)
        print(f"[✓] File truncated to {max_lines} lines")
        return True
        
    except Exception as e:
        print(f"[!] Error truncating file: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False


def keep_only_and_merge_multi(source_dirs, output_file, keep_map):
    """
    Keep only specific .m3u files in each source_dir and merge them.
    
    source_dirs: list of folder paths (e.g. [live_m3u_dir, vod_m3u_dir])
    keep_map: dict { "folder_path": [list of filenames to keep] }
    """
    import os, glob

    merged_count = 0

    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write("#EXTM3U\n")

        for source_dir in source_dirs:
            keep_list = keep_map.get(source_dir, [])
            if not keep_list:
                continue

            # Delete unwanted files
            all_files = glob.glob(os.path.join(source_dir, "*.m3u"))
            for file_path in all_files:
                if os.path.basename(file_path) not in keep_list:
                    try:
                        os.remove(file_path)
                        print(f"[–] Deleted: {os.path.basename(file_path)}")
                    except Exception as e:
                        print(f"[!] Could not delete {file_path}: {e}")
                else:
                    print(f"[✓] Kept: {os.path.basename(file_path)}")

            # Merge kept files into final output
            kept_files = [
                os.path.join(source_dir, f)
                for f in keep_list
                if os.path.exists(os.path.join(source_dir, f))
            ]

            for file in kept_files:
                with open(file, "r", encoding="utf-8", errors="ignore") as infile:
                    for line in infile:
                        if not line.strip().startswith("#EXTM3U"):
                            outfile.write(line)
                merged_count += 1

    print(f"[✓] Merged {merged_count} files into {output_file}")
    return True





# === Main Workflow ===
def main():
    """Main execution function with proper resource management"""
    try:
        with managed_driver() as driver:
            # Get disposable email
            email = get_disposable_email(driver)
            
            # Navigate to IPTVore
            driver.get("https://iptvore.com/free-iptv-trial/#apply")
            handle_cookies_and_popups(driver)
            time.sleep(2)  # Reduced wait

            print("[+] Filling out IPTVore form...")

            # Email input
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
                    wait = VPSOptimizedWait(driver, 3)
                    email_input = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    print(f"[+] Found email field with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not email_input:
                email_input = wait_for_element(driver, ["//input[@type='text'][1]"])
            
            email_input.clear()
            email_input.send_keys(email)
            print(f"[+] Entered email: {email}")
            
            try:
                email_input.send_keys(Keys.TAB)
                time.sleep(0.5)
                driver.execute_script("document.activeElement.blur();")
            except:
                pass

            # Country field
            print("[+] Looking for country field...")
            try:
                wait = VPSOptimizedWait(driver, 5)
                country_field = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[1]/div/div/main/article/div/div/section[2]/div/div[1]/div/div[3]/div/div/form/div[2]/div[1]/div/div[2]/div/span")))
                
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'instant', block: 'center'});", country_field)
                time.sleep(1)
                
                country_field.click()
                time.sleep(2)
                
                search_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@class='select2-search__field']")))
                search_box.clear()
                search_box.send_keys("United Kingdom")
                time.sleep(1)
                search_box.send_keys(Keys.ENTER)
                
                print("[+] Successfully selected United Kingdom")
                
            except Exception as e:
                print(f"[!] Error with country selection: {e}")

            time.sleep(1)

            # Submit form
            print("[+] Submitting form...")
            submit_button = wait_for_element(driver, [
                "//*[@id='wpforms-submit-10636']",
                "//button[@type='submit']",
                "//input[@type='submit']",
                "//button[contains(text(), 'Submit')]"
            ], clickable=True)
            
            js_click(driver, submit_button)
            print("[+] Form submitted!")
            time.sleep(3)

            # Wait for email and download
            result = wait_for_email_link(driver)
            if result:
                if isinstance(result, tuple):
                    m3u_url, epg_url = result
                else:
                    m3u_url, epg_url = result, None
                
                # Download M3U with extended timeout
                if download_m3u_file(m3u_url, SAVE_FILE, max_retries=3, is_m3u=True):
                    truncate_m3u_file(SAVE_FILE, 92025)
                    print("[✓] M3U saved successfully.")
                else:
                    print("[!] Failed to download M3U file.")

                # === Extract Xtream Codes details from the M3U link ===
                try:
                    parsed_url = urlparse(m3u_url)
                    server = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    query_params = parse_qs(parsed_url.query)
                    username = query_params.get("username", [""])[0]
                    password = query_params.get("password", [""])[0]

                    if not server or not username or not password:
                        raise ValueError("Could not parse server/username/password from M3U link")

                    print(f"[+] Xtream Codes details extracted:")
                    print(f"    Server:   {server}")
                    print(f"    Username: {username}")
                    print(f"    Password: {password}")

                    # === Run xtream2m3u binary ===
                    output_dir = os.path.abspath("iptv_daily")
                    os.makedirs(output_dir, exist_ok=True)

                    cmd = [
                        "xtream2m3u",
                        "-s", server,
                        "-u", username,
                        "-p", password,
                        "-l",  # Live channels
                        "-v",  # VOD
                        "-m",  # Generate M3U
                        "-o", output_dir
                    ]

                    print(f"[+] Running xtream2m3u: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True)

                    if result.returncode == 0:
                        print("[✓] xtream2m3u completed successfully.")

                        live_m3u_dir = os.path.abspath("iptv_daily/live_m3u")
                        vod_m3u_dir  = os.path.abspath("iptv_daily/vod_m3u")
                        merged_file_path = os.path.abspath("iptv_daily/iptvore_daily_update.m3u")

                        keep_live = [
                            "UK_ GENERAL ᴴᴰ_ᴿᴬᵂ.m3u",
                            "UK_ SKY CINEMA ᴴᴰ_ᴿᴬᵂ.m3u",
                            "US_ ENTERTAINMENT ᴴᴰ_ᴿᴬᵂ ⁶⁰ᶠᵖˢ.m3u",
                            "US_ MOVIES ᴴᴰ_ᴿᴬᵂ ⁶⁰ᶠᵖˢ.m3u",
                            "UK_ SPORT ᴿᴬᵂ ⱽᴵᴾ ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                            "UK_ SPORT ᴴᴰ.m3u",
                            "UK_ TNT SPORT ᴴᴰ ⱽᴵᴾ.m3u",
                            "UK_ TNT SPORT EVENT.m3u",
                            "UK_ UEFA PPV.m3u",
                            "NZ_ NEW ZEALAND ᴴᴰ_ᴿᴬᵂ.m3u",
                            "IE_ IRELAND ᴴᴰ_ᴿᴬᵂ.m3u",
                            "UK_ MUSIC ᴴᴰ_ᴿᴬᵂ.m3u",
                            "UK_ DISCOVERY+ ᴴᴰ_ᴿᴬᵂ.m3u",
                            "UK_ DOCUMENTARY ᴴᴰ_ᴿᴬᵂ.m3u",
                            "UK_ EPL PREMIER LEAGUE PPV ⱽᴵᴾ ᴿᴬᵂ.m3u",
                            "UK_ FA PLAYER PPV.m3u",
                            "IE_ LOI PPV.m3u"
                        ]

                        keep_vod = [
                                "EN - NEW RELEASE.m3u",
                                "EN - IMDB TOP 250.m3u",
                                "AMAZON DOCU-MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "AMAZON DOCU-MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "AMAZON MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "AMAZON MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "APPLE+ MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "APPLE+ MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DISCOVERY+ MOVIES.m3u",
                                "DISNEY+ KIDS ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DISNEY+ MOVIES EU ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DREAMWORKS ANIMATION.m3u",
                                "MARVEL MOVIES (MULTI).m3u",
                                "MARVEL MOVIES 3840P (MULTI).m3u",
                                "NETFLIX ANIMI.m3u",
                                "NETFLIX DOCU-MOVIES.m3u",
                                "NETFLIX MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "NETFLIX MOVIES ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "NETFLIX MOVIES.m3u",
                                "EN - 2020 & OLD.m3u",
                                "EN - ACTION.m3u",
                                "EN - ADVENTURE.m3u",
                                "EN - CHRISTMAS.m3u",
                                "EN - COLLECTIONS.m3u",
                                "EN - COMEDY.m3u",
                                "EN - CONCERTS.m3u",
                                "EN - DOCUMENTARIES.m3u",
                                "EN - DRAMA.m3u",
                                "EN - HORROR.m3u",
                                "EN - KIDS ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "EN - KIDS.m3u",
                                "EN - MOVIES ⁴ᴷ ³⁸⁴⁰ᴾ.m3u",
                                "EN - MUSICAL.m3u",
                                "EN - ROMANCE.m3u",
                                "EN - SCIENCE FICTION.m3u",
                                "EN - THRILLER.m3u",
                                "EN - WESTERNS.m3u"
                            ]

                            keep_map = {
                                live_m3u_dir: keep_live,
                                vod_m3u_dir: keep_vod
                            }

                            keep_only_and_merge_multi(
                                source_dirs=[live_m3u_dir, vod_m3u_dir],
                                output_file=merged_file_path,
                                keep_map=keep_map
                            )
                        print(result.stdout)
                    else:
                        print("[!] xtream2m3u failed:")
                        print(result.stderr)

                except Exception as e:
                    print(f"[!] Error processing Xtream Codes credentials: {e}")


                
                # Download EPG if found
                if epg_url:
                    epg_file = SAVE_FILE.replace('.m3u', '_epg.xml')
                    if download_m3u_file(epg_url, epg_file, max_retries=2, is_m3u=False):
                        print("[✓] EPG saved successfully.")
                    else:
                        print("[!] Failed to download EPG file.")
            else:
                print("[!] Failed to retrieve M3U link.")

    except Exception as e:
        print(f"[!] Error occurred: {e}")
    finally:
        # Final cleanup
        memory_cleanup()
        print("[+] Script completed.")

if __name__ == "__main__":
    main()