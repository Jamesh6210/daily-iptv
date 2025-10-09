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
from selenium.webdriver.common.action_chains import ActionChains

# === Settings ===
SAVE_FILE = "iptv_daily/iptv_daily_update.m3u"
EPG_SAVE_FILE = "iptv_daily/iptv_daily_update_epg.xml"
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

def get_disposable_email(driver):
    """Fetch a disposable email address - optimized"""
    print("[+] Fetching disposable email...")
    
    # Store original window
    original_window = driver.current_window_handle
    
    driver.execute_script("window.open('https://www.disposablemail.com/', '_blank');")
    driver.switch_to.window(driver.window_handles[1])
    
    
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
    """Search LayerSeven emails for IPTV details (M3U + EPG + Xtream fallback)."""
    try:
        # Grab page text + HTML
        page_html = driver.execute_script("return document.body.innerHTML;")
        page_text = driver.execute_script("return document.body.innerText;")
        combined_content = page_html + " " + page_text

        print(f"[{elapsed_time()}] Searching email content...")

        m3u_url, epg_url = None, None

        # === Direct HTML link search (existing method) ===
        try:
            m3u_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'get.php')]")
            for elem in m3u_elements:
                href = elem.get_attribute("href")
                if href and "get.php" in href:
                    m3u_url = href.replace("&amp;", "&")
                    print(f"[{elapsed_time()}] Found M3U link: {m3u_url}")
                    break
        except:
            pass

        try:
            epg_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'xmltv.php')]")
            for elem in epg_elements:
                href = elem.get_attribute("href")
                if href and "xmltv.php" in href:
                    epg_url = href.replace("&amp;", "&")
                    print(f"[{elapsed_time()}] Found EPG link: {epg_url}")
                    break
        except:
            pass

        # === Plain text fallback parsing ===
        if not m3u_url:
            match = re.search(r'M3U:\s*(https?://\S+)', combined_content, re.IGNORECASE)
            if match:
                m3u_url = match.group(1).strip()
                print(f"[{elapsed_time()}] Found M3U link in text: {m3u_url}")

        if not epg_url:
            match = re.search(r'EPG:\s*(https?://\S+)', combined_content, re.IGNORECASE)
            if match:
                epg_url = match.group(1).strip()
                print(f"[{elapsed_time()}] Found EPG link in text: {epg_url}")

        # === Xtream Codes fallback (server + user + pass) ===
        if not m3u_url:
            host = re.search(r'Hostname.*?:\s*(https?://[^\s]+)', combined_content, re.IGNORECASE)
            user = re.search(r'Username:\s*([A-Za-z0-9]+)', combined_content)
            passwd = re.search(r'Password:\s*([A-Za-z0-9]+)', combined_content)

            if host and user and passwd:
                server = host.group(1).strip()
                username = user.group(1).strip()
                password = passwd.group(1).strip()
                m3u_url = f"{server}/get.php?username={username}&password={password}&type=m3u_plus&output=ts"
                epg_url = f"{server}/xmltv.php?username={username}&password={password}"
                print(f"[{elapsed_time()}] Built M3U + EPG from Xtream details")

        return (m3u_url, epg_url) if m3u_url else None

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


def keep_only_and_merge_multi(source_dirs, output_file, keep_map):
    """
    Keep only specific .m3u files in each source_dir and merge them.
    
    source_dirs: list of folder paths (e.g. [live_m3u_dir, movie_m3u_dir])
    keep_map: dict { "folder_path": [list of filenames to keep] }
    """
    import os, glob

    merged_count = 0

    with open(output_file, "w", encoding="utf-8") as outfile:
        outfile.write('#EXTM3U url-tvg="https://raw.githubusercontent.com/Jamesh6210/daily-iptv/refs/heads/main/iptv_daily/iptv_daily_update_epg.xml"\n')

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



# === Captcha Solver (2Captcha) ===
def solve_recaptcha(api_key, site_url, site_key, max_wait=180):
    """
    Solve reCAPTCHA v2 (checkbox + image puzzle) using 2Captcha
    Returns the g-recaptcha-response token
    """
    import requests, time

    print("[+] Sending captcha to 2Captcha...")

    # Step 1: submit captcha
    r = requests.post("http://2captcha.com/in.php", data={
        "key": api_key,
        "method": "userrecaptcha",
        "googlekey": site_key,
        "pageurl": site_url,
        "json": 1
    })
    result = r.json()
    if result.get("status") != 1:
        raise Exception(f"2Captcha error: {result}")

    request_id = result["request"]

    # Step 2: poll for solution
    result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={request_id}&json=1"
    start = time.time()
    while time.time() - start < max_wait:
        res = requests.get(result_url).json()
        if res.get("status") == 1:
            print("[✓] Captcha solved by 2Captcha")
            return res.get("request")
        print("[...] Waiting for captcha solution...")
        time.sleep(5)

    raise TimeoutError("Timed out waiting for captcha solution")





# === Main Workflow ===
def main():
    """Main execution for LayerSeven signup"""
    try:
        with managed_driver() as driver:
            # Step 1: Get disposable email
            email = get_disposable_email(driver)

            # Step 2: Navigate to LayerSeven sign-up
            driver.get("https://panel.layerseven.ai/sign-up")
            time.sleep(2)

            print("[+] Filling out LayerSeven signup form...")

            # Step 3: Fill email
            email_input = wait_for_element(driver, ["//*[@id='email']"], wait_time=10)
            email_input.clear()
            email_input.send_keys(email)

            # Step 4: Fill password (random strong password)
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            password_input = wait_for_element(driver, ["//*[@id='password']"], wait_time=10)
            password_input.clear()
            password_input.send_keys(password)

            print(f"[+] Using password: {password}")

            # Step 5: Solve reCAPTCHA automatically with 2Captcha
            try:
                # Find sitekey from page
                iframe = driver.find_element(By.XPATH, "//iframe[contains(@src,'recaptcha')]")
                site_key = iframe.get_attribute("src").split("k=")[1].split("&")[0]

                API_KEY = os.getenv("TWOCAPTCHA_KEY", "YOUR_2CAPTCHA_API_KEY")
                token = solve_recaptcha(API_KEY, "https://panel.layerseven.ai/sign-up", site_key)

                # Inject token into the correct form field
                driver.execute_script("""
                    let form = document.querySelector("form"); 
                    let textarea = document.getElementById("g-recaptcha-response");
                    if (!textarea) {
                        textarea = document.createElement("textarea");
                        textarea.id = "g-recaptcha-response";
                        textarea.name = "g-recaptcha-response";
                        textarea.style.display = "none";
                        form.appendChild(textarea);  // attach inside form
                    }
                    textarea.value = arguments[0];
                """, token)

                print("[+] Injected captcha token successfully")

                # Give site time to register it
                time.sleep(5)


            except Exception as e:
                print(f"[!] reCAPTCHA solving failed: {e}")

            # Step 6: Click Create Account
            create_button = wait_for_element(
                driver,
                ["/html/body/div[1]/div[2]/div/div[2]/div/form/div[3]/button"],
                clickable=True
            )
            js_click(driver, create_button)
            print("[+] Submitted signup form.")

            time.sleep(5)

            # Step 7: Open side menu and click Request Free Trial
            try:
                # First, open the side menu
                menu_button = wait_for_element(
                    driver,
                    ["/html/body/div[3]/button"],  # target the <button>, not <svg>/<path>
                    clickable=True
                )
                js_click(driver, menu_button)
                print("[+] Side menu opened.")

                time.sleep(2)

                # Now click the Request Free Trial link inside the menu
                trial_link = wait_for_element(
                    driver,
                    [
                        "//a[contains(text(),'Request free trial')]",
                        "/html/body/div[1]/div[2]/div/div[2]/nav/ul/li[2]/ul/li[3]/a"
                    ],
                    clickable=True
                )
                js_click(driver, trial_link)
                print("[+] Navigated to Request Free Trial page.")

            except Exception as e:
                print(f"[!] Could not open side menu or free trial link: {e}")

            # Step 8: Wait for trial email
            result = wait_for_email_link(driver)
            if result:
                if isinstance(result, tuple):
                    m3u_url, epg_url = result
                else:
                    m3u_url, epg_url = result, None

                print(f"[✓] Got trial details: {m3u_url}, {epg_url}")

                # === Extract Xtream Codes details from the M3U link ===
                try:
                    parsed_url = urlparse(m3u_url)
                    server = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    query_params = parse_qs(parsed_url.query)
                    username = query_params.get("username", [""])[0]
                    password = query_params.get("password", [""])[0]

                    if not server or not username or not password:
                        raise ValueError("Could not parse server/username/password from M3U link")


                    print(f"[+] Xtream Codes details extracted from m3u:")
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
                        movie_m3u_dir  = os.path.abspath("iptv_daily/movie_m3u")
                        merged_file_path = os.path.abspath("iptv_daily/iptv_daily_update.m3u")

                        keep_map = {
                            live_m3u_dir: [
                                "UK_ GENERAL ᴴᴰ_ᴿᴬᵂ.m3u",
                                "IE_ IRELAND ᴴᴰ_ᴿᴬᵂ.m3u",
                                "UK_ SKY CINEMA ᴴᴰ_ᴿᴬᵂ.m3u",
                                "US_ MOVIES ᴴᴰ_ᴿᴬᵂ ⁶⁰ᶠᵖˢ.m3u",
                                "US_ ENTERTAINMENT ᴴᴰ_ᴿᴬᵂ ⁶⁰ᶠᵖˢ.m3u",
                                "UK_ SPORT ᴴᴰ ⱽᴵᴾ.m3u",
                                "UK_ SPORT ᴴᴰ.m3u",
                                "UK_ TNT SPORT ᴴᴰ ⱽᴵᴾ.m3u",
                                "UK_ TNT SPORT EVENT.m3u",
                                "UK_ EPL PREMIER LEAGUE PPV ᴿᴬᵂ.m3u",
                                "UK_ UEFA PPV.m3u",
                                "NZ_ NEW ZEALAND ᴴᴰ_ᴿᴬᵂ.m3u",
                                "UK_ MUSIC ᴴᴰ_ᴿᴬᵂ.m3u",
                                "UK_ FA PLAYER PPV.m3u",
                                "IE_ LOI PPV.m3u"
                            ],
                            movie_m3u_dir: [
                                "EN - NEW RELEASE.m3u",
                                "AMAZON MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "APPLE+ MOVIES ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DISCOVERY+ MOVIES.m3u",
                                "DISNEY+ KIDS ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DISNEY+ MOVIES EU ᴰᴼᴸᴮʸ ᴬᵁᴰᴵᴼ.m3u",
                                "DREAMWORKS ANIMATION.m3u",
                                "MARVEL MOVIES (MULTI).m3u",
                                "NETFLIX DOCU-MOVIES.m3u",
                                "NETFLIX KIDS.m3u",
                                "NETFLIX MOVIES.m3u",
                                "UNIVERSAL.m3u",
                                "EN - 2020 & OLD.m3u",
                                "EN - ACTION.m3u",
                                "EN - ADVENTURE.m3u",
                                "EN - COLLECTIONS.m3u",
                                "EN - COMEDY.m3u",
                                "EN - CONCERTS.m3u",
                                "EN - DOCUMENTARIES.m3u",
                                "EN - DRAMA.m3u",
                                "EN - HORROR.m3u",
                                "EN - IMDB TOP 250.m3u",
                                "EN - KIDS.m3u",
                                "EN - MUSICAL.m3u",
                                "EN - ROMANCE.m3u",
                                "EN - SCIENCE FICTION.m3u",
                                "EN - THRILLER.m3u",
                                "EN - WESTERNS.m3u"
                            ]
                        }

                        keep_only_and_merge_multi(
                            source_dirs=[live_m3u_dir, movie_m3u_dir],
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
        memory_cleanup()
        print("[+] Script completed.")


if __name__ == "__main__":
    main()
