from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import random
import string
import os
import requests
import re

# === Settings ===
SAVE_FILE = r"C:\Users\James\Documents\daily-iptv\iptv_daily_update.m3u"  # Change path if needed

# === Setup headless Chrome ===
options = webdriver.ChromeOptions()
# options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# Add adblock extension and other privacy settings
options.add_argument("--disable-notifications")
options.add_argument("--disable-popup-blocking")
options.add_argument("--blink-settings=imagesEnabled=false")
options.add_argument("--disable-javascript")


# Disable automation flags that trigger bot detection
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--disable-blink-features=AutomationControlled')


# Path to chromedriver.exe (update if needed)
driver_path = r"C:\Users\James\Downloads\chromedriver-win64\chromedriver-win64\chromedriver.exe"  # <-- PUT YOUR PATH HERE
service = Service(driver_path)

# Start WebDriver
driver = webdriver.Chrome(service=service, options=options)

def handle_popups(driver):
    try:
        # Try to close any popups
        driver.execute_script("""
            var popups = [
                'div[class*="popup"]',
                'div[class*="modal"]',
                'div[class*="overlay"]',
                'div[id*="cookie"]',
                'div[class*="cookie"]'
            ];
            popups.forEach(function(selector) {
                var elements = document.querySelectorAll(selector);
                elements.forEach(function(el) {
                    el.style.display = 'none';
                    el.remove();
                });
            });
            document.body.style.overflow = 'auto';
        """)
    except Exception as e:
        print(f"Popup handling error: {e}")

def accept_cookies_aggressively():
    """Try multiple methods to accept cookies/privacy consent"""
    print("[+] Attempting to handle consent popup...")
    try:
        # Try to find and click the consent button using multiple strategies
        consent_selectors = [
            ('css', "button.fc-cta-consent"),  # Common consent managers
            ('css', "button#onetrust-accept-btn-handler"),
            ('css', "button#cmpbntyestxt"),
            ('css', "button.sp_choice_type_11"),
            ('xpath', "//button[contains(., 'Accept')]"),
            ('xpath', "//button[contains(., 'AGREE')]"),
            ('xpath', "//button[contains(., 'Consent')]"),
            ('xpath', "//button[contains(., 'OK')]"),
            ('xpath', "//div[contains(@class,'cookie')]//button")
        ]
        
        for strategy, selector in consent_selectors:
            try:
                if strategy == 'css':
                    button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                else:
                    button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector)))
                
                # Scroll into view and click with JavaScript
                driver.execute_script("arguments[0].scrollIntoView(true);", button)
                driver.execute_script("arguments[0].click();", button)
                print(f"[+] Clicked consent button using {strategy}: {selector}")
                time.sleep(1)  # Allow time for the popup to disappear
                return True
            except:
                continue
        
        print("[-] No consent button found with standard methods, trying fallbacks...")
        
        # Fallback 1: Try to accept via iframe
        try:
            frames = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in frames:
                try:
                    driver.switch_to.frame(frame)
                    button = driver.find_element(By.XPATH, "//button[contains(., 'Accept')]")
                    button.click()
                    driver.switch_to.default_content()
                    print("[+] Clicked consent button in iframe")
                    return True
                except:
                    driver.switch_to.default_content()
                    continue
        except:
            pass
        
        # Fallback 2: Try to remove the popup element
        try:
            driver.execute_script("""
                var elements = document.querySelectorAll('div[class*="cookie"], div[id*="cookie"], div[class*="consent"], div[id*="consent"]');
                elements.forEach(function(el) {
                    el.parentNode.removeChild(el);
                });
                document.body.style.overflow = 'auto';
            """)
            print("[+] Removed consent elements with JavaScript")
            return True
        except:
            pass
        
        print("[-] Could not handle consent popup")
        return False
        
    except Exception as e:
        print(f"[!] Error handling consent: {e}")
        return False


def get_disposable_email():
    """Get a disposable email from disposablemail.com"""
    print("[+] Getting disposable email address...")
    
    # Open disposablemail.com in a new tab
    driver.execute_script("window.open('');")
    driver.switch_to.window(driver.window_handles[1])
    driver.get("https://www.disposablemail.com/")
    time.sleep(2)  # Allow page to load
    accept_cookies_aggressively()
    handle_popups(driver)
    
    try:
        # Handle consent popup if it exists
        try:
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "sp-cc-iframe")))
            consent_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept')]")))
            consent_button.click()
            driver.switch_to.default_content()
            print("[+] Clicked consent button")
        except:
            print("[-] No consent popup found")
            pass
        
        # Wait for email to load - try multiple selectors
        email_selectors = [
            (By.ID, "email"),  # Primary selector
            (By.CSS_SELECTOR, ".email-address"),  # Alternative class
            (By.CSS_SELECTOR, "#email-address"),  # Another possible ID
            (By.XPATH, "//div[contains(@class, 'email') and contains(text(), '@')]")  # Generic fallback
        ]
        
        disposable_email = None
        for selector in email_selectors:
            try:
                email_element = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located(selector)
                )
                disposable_email = email_element.get_attribute("value") or email_element.text
                if "@" in disposable_email:  # Basic validation
                    break
            except:
                continue
        
        if not disposable_email or "@" not in disposable_email:
            # Try to extract from page text as last resort
            page_text = driver.page_source
            email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
            email_matches = re.findall(email_pattern, page_text)
            if email_matches:
                disposable_email = email_matches[0]
        
        if not disposable_email or "@" not in disposable_email:
            raise Exception("Could not extract valid email address")
        
        print(f"[+] Using disposable email: {disposable_email}")
        return disposable_email.strip()
        
    except Exception as e:
        print(f"[!] Error getting disposable email: {e}")
        # Fallback to temporary-mail.io as alternative
        try:
            print("[+] Trying temporary-mail.io as fallback...")
            driver.get("https://temp-mail.io/")
            email_element = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, "mail"))
            )
            disposable_email = email_element.get_attribute("value")
            if not disposable_email:
                disposable_email = email_element.text
            print(f"[+] Got fallback email: {disposable_email}")
            return disposable_email.strip()
        except Exception as fallback_e:
            print(f"[!] Fallback failed: {fallback_e}")
            username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            return f"{username}@example.com"

def check_for_email_with_m3u(max_wait_time=1200):
    """Check the disposable email for Tivimate M3U link"""
    print("[+] Checking disposable email for Tivimate M3U link...")
    
    # Switch to the disposablemail.com tab
    driver.switch_to.window(driver.window_handles[1])
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        try:
            # Refresh the inbox periodically
            if int(time.time() - start_time) % 30 == 0:  # Refresh every 30 seconds
                refresh_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "refresh"))
                )
                refresh_button.click()
                print("[+] Refreshed inbox")
                time.sleep(2)
            
            # Check for emails
            emails = driver.find_elements(By.CSS_SELECTOR, ".email-item, .mail-item, tr[onclick]")
            
            if emails:
                print(f"[+] Found {len(emails)} email(s), checking for Tivimate M3U link...")
                
                # Click on the first/latest email
                emails[0].click()
                time.sleep(3)  # Wait for email to load
                
                # Get email content
                email_content = driver.find_element(By.CSS_SELECTOR, "div.email-content, #email-content, div.mail-content")
                content_text = email_content.text
                content_html = email_content.get_attribute("innerHTML")
                
                # Specific pattern for Tivimate M3U URL
                tivimate_pattern = r"For Tivimate.*?🎛 M3U:\s*(https?://[^\s]+\.m3u[^\s]*)"
                
                # First try the specific Tivimate section
                tivimate_match = re.search(tivimate_pattern, content_text, re.DOTALL)
                if tivimate_match:
                    m3u_url = tivimate_match.group(1).strip()
                    print(f"[+] Found Tivimate M3U URL: {m3u_url}")
                    return m3u_url
                
                # Fallback to any M3U link if specific Tivimate one not found
                m3u_matches = re.findall(r"https?://[^\s]+\.m3u[^\s]*", content_text)
                if m3u_matches:
                    m3u_url = m3u_matches[0].strip()
                    print(f"[+] Found generic M3U URL: {m3u_url}")
                    return m3u_url
                
                print("[!] No M3U link found in this email")
            
            elapsed = int(time.time() - start_time)
            remaining = max_wait_time - elapsed
            print(f"[+] No emails yet, waiting... ({elapsed}s elapsed, {remaining}s remaining)")
            time.sleep(10)
            
        except Exception as e:
            print(f"[!] Error checking email: {e}")
            time.sleep(5)
    
    print("[!] Timeout waiting for email with M3U link")
    return None

try:
    # Get disposable email first
    disposable_email = get_disposable_email()
    
    # Switch back to the main lemonrealm tab
    driver.switch_to.window(driver.window_handles[0])
    
    print("[+] Opening lemonrealm...")
    driver.get("https://lemonrealm.com/24-hours/")

    wait = WebDriverWait(driver, 10)

    # Step 1: Enter disposable email and next
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email-1-2")))
    email_input.send_keys(disposable_email)
    driver.find_element(By.XPATH, "//button[contains(text(),'Next')]").click()
    print("[+] Step 1 complete")

    # Step 2: Set language and turn adult content OFF
    dropdown_trigger = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "div[role='combobox'][aria-label='Dropdown']")
    ))
    dropdown_trigger.click()

    # Small delay to ensure dropdown is fully open
    time.sleep(0.5)

    # Find and click the English option
    english_option = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//span[@class='opt-lbl' and normalize-space()='English']")
    ))
    english_option.click()

    # Wait a moment for the dropdown to close
    time.sleep(0.5)

    # Adult content toggle - try multiple approaches
    print("[+] Setting adult content to OFF...")
    
    # Method 1: Direct click with JavaScript
    off_radio = wait.until(EC.presence_of_element_located(
        (By.CSS_SELECTOR, "input[value='Off'][name='radio-1-4']")
    ))
    driver.execute_script("""
        arguments[0].click();
        arguments[0].dispatchEvent(new Event('change'));
        arguments[0].dispatchEvent(new Event('input'));
    """, off_radio)
    
    # Additional wait and verification
    time.sleep(1)
    
    # Verify the radio button is actually selected
    if off_radio.is_selected():
        print("[+] Adult content set to OFF successfully")
    else:
        print("[!] Retrying adult content selection...")
        # Try clicking the label instead
        off_label = driver.find_element(By.XPATH, "//label[contains(@for, 'radio-1-4') and contains(text(), 'Off')]")
        driver.execute_script("arguments[0].click();", off_label)
        time.sleep(0.5)

    # Now try multiple strategies to click the Next button
    print("[+] Attempting to click Next button...")
    
    # Strategy 1: Wait for element to be clickable
    try:
        next_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Next')]"))
        )
        next_button.click()
        print("[+] Step 2 complete - Next button clicked (Strategy 1)")
    except:
        print("[!] Strategy 1 failed, trying Strategy 2...")
        
        # Strategy 2: Force click with JavaScript
        try:
            next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
            driver.execute_script("arguments[0].click();", next_button)
            print("[+] Step 2 complete - Next button clicked (Strategy 2)")
        except:
            print("[!] Strategy 2 failed, trying Strategy 3...")
            
            # Strategy 3: Try different selectors
            try:
                # Look for button by type
                next_button = driver.find_element(By.XPATH, "//button[@type='button' and contains(text(), 'Next')]")
                driver.execute_script("arguments[0].click();", next_button)
                print("[+] Step 2 complete - Next button clicked (Strategy 3)")
            except:
                print("[!] Strategy 3 failed, trying Strategy 4...")
                
                # Strategy 4: ActionChains click
                try:
                    next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
                    ActionChains(driver).move_to_element(next_button).click().perform()
                    print("[+] Step 2 complete - Next button clicked (Strategy 4)")
                except:
                    print("[!] Strategy 4 failed, trying Strategy 5...")
                    
                    # Strategy 5: Send Enter key to the form
                    try:
                        form = driver.find_element(By.TAG_NAME, "form")
                        form.send_keys(Keys.ENTER)
                        print("[+] Step 2 complete - Form submitted with Enter key (Strategy 5)")
                    except:
                        print("[!] All strategies failed. Waiting longer and trying once more...")
                        time.sleep(3)
                        next_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Next')]")
                        driver.execute_script("arguments[0].click();", next_button)

    # Wait a moment before proceeding to Step 3
    time.sleep(2)

    # Step 3: Set devices to 4 and submit
    print("[+] Moving to Step 3...")
    
    # Debug: Print all available dropdowns
    try:
        dropdowns = driver.find_elements(By.CSS_SELECTOR, "div[role='combobox']")
        print(f"[DEBUG] Found {len(dropdowns)} dropdown(s)")
        for i, dropdown in enumerate(dropdowns):
            print(f"[DEBUG] Dropdown {i}: {dropdown.get_attribute('outerHTML')[:200]}...")
    except Exception as e:
        print(f"[DEBUG] Error finding dropdowns: {e}")
    
    # Try multiple approaches to find the devices dropdown
    devices_dropdown_trigger = None
    
    # Method 1: Look for the second dropdown (first was language)
    try:
        dropdowns = driver.find_elements(By.CSS_SELECTOR, "div[role='combobox']")
        if len(dropdowns) >= 2:
            devices_dropdown_trigger = dropdowns[1]  # Second dropdown should be devices
            print("[+] Found devices dropdown using index method")
    except:
        pass
    
    # Method 2: Look for dropdown near "devices" text or form field
    if not devices_dropdown_trigger:
        try:
            # Try to find by nearby text or container
            devices_dropdown_trigger = driver.find_element(By.XPATH, 
                "//div[contains(@class, 'form') or contains(@class, 'field')]//div[@role='combobox']")
            print("[+] Found devices dropdown using form field method")
        except:
            pass
    
    # Method 3: Look for any remaining dropdown with aria-label
    if not devices_dropdown_trigger:
        try:
            devices_dropdown_trigger = driver.find_element(By.CSS_SELECTOR, 
                "div[role='combobox'][aria-label='Dropdown']:not([style*='display: none'])")
            print("[+] Found devices dropdown using visible dropdown method")
        except:
            pass
    
    # Method 4: Try a more generic approach
    if not devices_dropdown_trigger:
        try:
            # Wait a bit longer and try again
            time.sleep(2)
            devices_dropdown_trigger = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div[role='combobox']"))
            )
            print("[+] Found devices dropdown using generic method")
        except:
            pass
    
    if not devices_dropdown_trigger:
        print("[!] Could not find devices dropdown, trying alternative approach...")
        # Try to find by looking for the actual select element or input
        try:
            # Look for any select or input related to devices
            device_input = driver.find_element(By.XPATH, "//input[contains(@name, 'device') or contains(@id, 'device')]")
            device_input.click()
            print("[+] Found device input field")
        except:
            print("[!] No device input found either")
            raise Exception("Could not find devices dropdown or input")
    else:
        # Click the dropdown trigger
        devices_dropdown_trigger.click()
        print("[+] Clicked devices dropdown")
    
    # Wait for dropdown to open
    time.sleep(1)
    
    # Try to click on "4 Simultaneously" option
    try:
        four_devices_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//span[@class='opt-lbl' and normalize-space()='4 Simultaneously']")
        ))
        four_devices_option.click()
        print("[+] Selected '4 Simultaneously'")
    except:
        # Try alternative text variations
        try:
            four_devices_option = driver.find_element(By.XPATH, "//span[contains(text(), '4 Simultaneously')]")
            four_devices_option.click()
            print("[+] Selected '4 Simultaneously' (alternative method)")
        except:
            # Try just looking for "4"
            four_devices_option = driver.find_element(By.XPATH, "//span[contains(text(), '4')]")
            four_devices_option.click()
            print("[+] Selected option containing '4'")
    
    # Wait for dropdown to close
    time.sleep(0.5)
    
    # Click Submit button
    submit_button = wait.until(EC.element_to_be_clickable(
        (By.XPATH, "//button[contains(text(),'Submit')]")
    ))
    submit_button.click()
    print("[+] Step 3 complete - Form submitted!")
    
    # Now check the disposable email for the M3U link
    m3u_url = check_for_email_with_m3u(max_wait_time=1200)  # Wait up to 5 minutes
    
    if m3u_url:
        # Download the file
        print(f"[+] Downloading M3U file from: {m3u_url}")
        try:
            r = requests.get(m3u_url)
            r.raise_for_status()  # Raise an exception for bad status codes
            with open(SAVE_FILE, "wb") as f:
                f.write(r.content)
            print(f"✅ IPTV playlist saved to {SAVE_FILE}")
        except Exception as e:
            print(f"[!] Error downloading file: {e}")
            # Try to download with browser session
            try:
                print("[+] Trying to download with browser session...")
                cookies = driver.get_cookies()
                session = requests.Session()
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
                
                r = session.get(m3u_url)
                r.raise_for_status()
                with open(SAVE_FILE, "wb") as f:
                    f.write(r.content)
                print(f"✅ IPTV playlist saved to {SAVE_FILE}")
            except Exception as e2:
                print(f"[!] Error downloading with session: {e2}")
                raise
    else:
        print("[!] Could not find M3U link in email")

finally:
    driver.quit()