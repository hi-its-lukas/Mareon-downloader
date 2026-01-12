import os
import time
import glob
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from database import get_all_accounts, is_invoice_processed, add_to_history, add_log
from butler_api import upload_invoice

DOWNLOAD_DIR = os.path.abspath("downloads")
LOGIN_URL = "https://www.mareon.com/login"
INVOICES_URL = "https://www.mareon.com/portal/rechnungen"

def save_debug_screenshot(driver, prefix="error"):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        driver.save_screenshot(filepath)
        add_log("INFO", f"Debug screenshot saved: {filename}")
        return filepath
    except Exception as e:
        add_log("ERROR", f"Failed to save debug screenshot: {str(e)}")
        return None

def setup_driver():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        chrome_options.binary_location = chrome_bin
    
    chromedriver_paths = [
        os.environ.get("CHROMEDRIVER_PATH"),
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/nix/store/chromium-chromedriver/bin/chromedriver",
    ]
    
    driver = None
    last_error = None
    
    for path in chromedriver_paths:
        if path and os.path.exists(path):
            try:
                service = Service(path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                add_log("INFO", f"Using chromedriver at: {path}")
                break
            except Exception as e:
                last_error = e
                continue
    
    if driver is None:
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            add_log("INFO", "Using system default chromedriver")
        except Exception:
            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
                add_log("INFO", "Using webdriver-manager chromedriver")
            except Exception as e:
                add_log("ERROR", f"Failed to initialize WebDriver: {str(e)}")
                raise
    
    driver.implicitly_wait(10)
    return driver

def login(driver, username, password):
    add_log("INFO", f"Attempting login for user: {username}")
    
    try:
        driver.get(LOGIN_URL)
        time.sleep(2)
        
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "modlgn_username"))
        )
        username_field.clear()
        username_field.send_keys(username)
        
        password_field = driver.find_element(By.ID, "modlgn_passwd")
        password_field.clear()
        password_field.send_keys(password)
        
        submit_button = driver.find_element(By.NAME, "Submit")
        submit_button.click()
        
        time.sleep(3)
        
        if "login" not in driver.current_url.lower():
            add_log("INFO", f"Successfully logged in as: {username}")
            return True
        else:
            add_log("ERROR", f"Login failed for user: {username}")
            return False
            
    except TimeoutException:
        add_log("ERROR", f"Timeout during login for user: {username}")
        save_debug_screenshot(driver, "error_login_timeout")
        return False
    except Exception as e:
        add_log("ERROR", f"Login error for {username}: {str(e)}")
        save_debug_screenshot(driver, "error_login")
        return False

def switch_mandant(driver, mandant_text):
    if not mandant_text:
        return True
        
    add_log("INFO", f"Attempting to switch to mandant: {mandant_text}")
    
    try:
        time.sleep(2)
        
        dropdown_selectors = [
            "div.ui-selectonemenu-trigger",
            "label.ui-selectonemenu-label",
            "div.ui-selectonemenu",
            "//div[contains(@class, 'dropdown')]//a",
            "//nav//div[contains(@class, 'dropdown')]",
            "//ul[contains(@class, 'navbar')]//li[contains(@class, 'dropdown')]",
            "//header//div[contains(@class, 'dropdown')]"
        ]
        
        dropdown_clicked = False
        for selector in dropdown_selectors:
            try:
                if selector.startswith("//"):
                    dropdowns = driver.find_elements(By.XPATH, selector)
                else:
                    dropdowns = driver.find_elements(By.CSS_SELECTOR, selector)
                for dropdown in dropdowns:
                    if dropdown.is_displayed():
                        dropdown.click()
                        time.sleep(1)
                        dropdown_clicked = True
                        add_log("INFO", f"Clicked dropdown using selector: {selector}")
                        break
                if dropdown_clicked:
                    break
            except Exception:
                continue
        
        option_selectors = [
            f"//li[contains(@class, 'ui-selectonemenu-item') and contains(text(), '{mandant_text}')]",
            f"//li[contains(@class, 'ui-selectonemenu-item') and contains(., '{mandant_text}')]",
            f"//li[contains(text(), '{mandant_text}')]"
        ]
        
        mandant_li = None
        for option_selector in option_selectors:
            try:
                mandant_li = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, option_selector))
                )
                if mandant_li:
                    break
            except TimeoutException:
                continue
        
        if mandant_li:
            mandant_li.click()
            add_log("INFO", f"Successfully switched to mandant: {mandant_text}")
            time.sleep(2)
            return True
        else:
            add_log("ERROR", f"Could not find mandant option: {mandant_text}")
            save_debug_screenshot(driver, "error_mandant_notfound")
            return False
        
    except TimeoutException:
        add_log("ERROR", f"Could not find mandant: {mandant_text}")
        save_debug_screenshot(driver, "error_mandant_timeout")
        return False
    except Exception as e:
        add_log("ERROR", f"Error switching mandant: {str(e)}")
        save_debug_screenshot(driver, "error_mandant")
        return False

def wait_for_download(existing_files, timeout=30):
    end_time = time.time() + timeout
    while time.time() < end_time:
        current_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))
        new_files = current_files - existing_files
        completed_new_files = [f for f in new_files if not f.endswith('.crdownload')]
        if completed_new_files:
            newest = max(completed_new_files, key=os.path.getctime)
            return newest
        time.sleep(1)
    return None

def cleanup_downloads():
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")):
        try:
            os.remove(f)
        except Exception:
            pass

def save_to_local_path(filepath, save_path, invoice_nr):
    try:
        os.makedirs(save_path, exist_ok=True)
        
        filename = os.path.basename(filepath)
        base, ext = os.path.splitext(filename)
        dest_filename = f"{invoice_nr}{ext}" if invoice_nr else filename
        dest_path = os.path.join(save_path, dest_filename)
        
        counter = 1
        while os.path.exists(dest_path):
            dest_filename = f"{invoice_nr}_{counter}{ext}"
            dest_path = os.path.join(save_path, dest_filename)
            counter += 1
        
        import shutil
        shutil.move(filepath, dest_path)
        add_log("INFO", f"Saved invoice to: {dest_path}")
        return True
    except Exception as e:
        add_log("ERROR", f"Failed to save invoice locally: {str(e)}")
        return False

def process_invoices(driver, api_key, save_path):
    add_log("INFO", "Navigating to invoices page")
    
    try:
        driver.get(INVOICES_URL)
        time.sleep(3)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "tbody"))
        )
        
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        add_log("INFO", f"Found {len(rows)} invoice rows")
        
        processed_count = 0
        skipped_count = 0
        
        for i, row in enumerate(rows):
            try:
                row_text = row.text
                
                invoice_match = re.search(r'S-\d+', row_text)
                if not invoice_match:
                    continue
                    
                invoice_nr = invoice_match.group()
                
                if is_invoice_processed(invoice_nr):
                    add_log("INFO", f"Skipping already processed invoice: {invoice_nr}")
                    skipped_count += 1
                    continue
                
                add_log("INFO", f"Processing invoice: {invoice_nr}")
                
                try:
                    download_link = row.find_element(By.CSS_SELECTOR, 'a[title="Rechnungsdruck"]')
                except NoSuchElementException:
                    try:
                        download_link = row.find_element(By.XPATH, './/a[contains(@title, "Rechnung")]')
                    except NoSuchElementException:
                        add_log("ERROR", f"No download link found for invoice: {invoice_nr}")
                        continue
                
                existing_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))
                
                download_link.click()
                add_log("INFO", f"Clicked download for invoice: {invoice_nr}")
                time.sleep(1)
                
                downloaded_file = wait_for_download(existing_files)
                
                if downloaded_file:
                    add_log("INFO", f"Downloaded file: {downloaded_file}")
                    
                    success = False
                    
                    if api_key:
                        if upload_invoice(downloaded_file, api_key):
                            success = True
                            try:
                                os.remove(downloaded_file)
                                add_log("INFO", f"Deleted local file after upload: {downloaded_file}")
                            except Exception as e:
                                add_log("ERROR", f"Could not delete file: {str(e)}")
                        else:
                            add_log("ERROR", f"Upload failed for invoice: {invoice_nr}")
                    
                    elif save_path:
                        if save_to_local_path(downloaded_file, save_path, invoice_nr):
                            success = True
                        else:
                            add_log("ERROR", f"Save failed for invoice: {invoice_nr}")
                    
                    else:
                        add_log("ERROR", f"No API key or save path configured for invoice: {invoice_nr}")
                    
                    if success:
                        add_to_history(invoice_nr)
                        processed_count += 1
                    else:
                        try:
                            if os.path.exists(downloaded_file):
                                os.remove(downloaded_file)
                                add_log("INFO", f"Cleaned up failed file: {downloaded_file}")
                        except Exception:
                            pass
                else:
                    add_log("ERROR", f"Download timeout for invoice: {invoice_nr}")
                    
            except Exception as e:
                add_log("ERROR", f"Error processing row {i}: {str(e)}")
                continue
        
        add_log("INFO", f"Completed: {processed_count} processed, {skipped_count} skipped")
        return processed_count
        
    except TimeoutException:
        add_log("ERROR", "Timeout loading invoices page")
        save_debug_screenshot(driver, "error_invoices_timeout")
        return 0
    except Exception as e:
        add_log("ERROR", f"Error processing invoices: {str(e)}")
        save_debug_screenshot(driver, "error_invoices")
        return 0

def run_scraper():
    add_log("INFO", "=== Starting Mareon Invoice Scraper ===")
    
    cleanup_downloads()
    add_log("INFO", "Cleaned up any leftover download files")
    
    accounts = get_all_accounts()
    
    if not accounts:
        add_log("ERROR", "No accounts configured. Please add an account first.")
        return
    
    add_log("INFO", f"Found {len(accounts)} account(s) to process")
    
    driver = None
    
    try:
        driver = setup_driver()
        add_log("INFO", "WebDriver initialized successfully")
        
        for account in accounts:
            account_name = account['name']
            add_log("INFO", f"--- Processing account: {account_name} ---")
            
            if login(driver, account['username'], account['password']):
                if account['mandant_dropdown']:
                    switch_mandant(driver, account['mandant_dropdown'])
                
                api_key = account['butler_api_key'] if 'butler_api_key' in account.keys() else None
                save_path = account['save_path'] if 'save_path' in account.keys() else None
                process_invoices(driver, api_key, save_path)
            else:
                add_log("ERROR", f"Skipping account due to login failure: {account_name}")
            
            driver.delete_all_cookies()
            
    except Exception as e:
        add_log("ERROR", f"Scraper error: {str(e)}")
    finally:
        if driver:
            driver.quit()
            add_log("INFO", "WebDriver closed")
    
    add_log("INFO", "=== Scraper run completed ===")
