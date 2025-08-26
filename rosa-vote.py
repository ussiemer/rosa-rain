import os
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromiumService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from io import StringIO
import traceback

def sanitize_filename(name):
    """
    Cleans a string to make it a valid filename by removing or replacing
    invalid characters.
    """
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.replace(' ', '_')
    return name.strip('_. ')

def process_url_and_get_title(driver, full_url, download_dir, base_filename):
    """
    Navigates to a specific URL, extracts the table data, and saves it.
    Uses the page title as the name and renames the columns.
    """
    try:
        print(f"\nProcessing URL: {full_url}")
        driver.get(full_url)

        # Get the page title and extract the name with regex
        title = driver.title
        match = re.search(r" in (.*)", title)
        name = match.group(1).strip() if match else title

        if not name:
            name = "Unknown"
            print("⚠️ Could not extract page title. Using 'Unknown'.")

        print(f"Page name: '{name}'")

        # Shorten the timeout to reduce waiting time
        WebDriverWait(driver, 0.77).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tablesaw.table-stimmen[data-tablejigsaw-downloadable]"))
        )

        table_selector = "table.tablesaw.table-stimmen[data-tablejigsaw-downloadable]"
        table_element = driver.find_element(By.CSS_SELECTOR, table_selector)
        table_html = table_element.get_attribute('outerHTML')
        df_list = pd.read_html(StringIO(table_html), header=[0, 1])

        if df_list:
            df = df_list[0]

            # Manually define the correct column names
            correct_headers = [
                'Merkmal_Unnamed:_0_level_1',
                'Erststimmen_Anzahl',
                'Erststimmen_Anteil',
                'Erststimmen_Gewinn',
                'Zweitstimmen_Anzahl',
                'Zweitstimmen_Anteil',
                'Zweitstimmen_Gewinn'
            ]

            # Since the number of columns can vary based on the number of parties,
            # we need to build the column list dynamically and then rename the first few.
            new_columns = []
            for col in df.columns:
                if isinstance(col, tuple):
                    # For Erst- and Zweitstimmen columns
                    if 'Erststimmen' in col[0]:
                        if 'Anzahl' in col[1]:
                            new_columns.append('Erststimmen_Anzahl')
                        elif 'Anteil' in col[1]:
                            new_columns.append('Erststimmen_Anteil')
                        elif 'Gewinn' in col[1]:
                            new_columns.append('Erststimmen_Gewinn')
                        else:
                            new_columns.append(f"Erststimmen_{col[1]}")
                    elif 'Zweitstimmen' in col[0]:
                        if 'Anzahl' in col[1]:
                            new_columns.append('Zweitstimmen_Anzahl')
                        elif 'Anteil' in col[1]:
                            new_columns.append('Zweitstimmen_Anteil')
                        elif 'Gewinn' in col[1]:
                            new_columns.append('Zweitstimmen_Gewinn')
                        else:
                            new_columns.append(f"Zweitstimmen_{col[1]}")
                    else:
                        new_columns.append(f"{col[0]}_{col[1]}")
                else:
                    # For the first column (Merkmal)
                    new_columns.append(f"{col}_Unnamed:_0_level_1")

            df.columns = new_columns

            # New filename format: [base_filename]_[place_name].csv
            filename = f"{base_filename}_{sanitize_filename(name)}.csv"
            file_path = os.path.join(download_dir, filename)
            df.to_csv(file_path, index=False, sep=';', encoding='utf-8')
            print(f"✅ Data successfully saved to: {file_path}")
        else:
            print(f"⚠️ No table found with pandas for '{name}'.")

        return driver.current_url
    except Exception as e:
        print(f"❌ An error occurred while processing '{full_url}': {e}")
        traceback.print_exc()
        time.sleep(1)
        return None

def main_scraper():
    """
    Main function to scrape election data for all 45 districts and their sub-links.
    """
    chromium_driver_path = "/usr/bin/chromedriver"
    if not os.path.exists(chromium_driver_path):
        print(f"Error: Chromium driver not found at {chromium_driver_path}")
        return

    download_dir = "./results"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        print(f"Directory created: {download_dir}")

    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")

        service = ChromiumService(executable_path=chromium_driver_path)
        driver = webdriver.Chrome(service=service, options=options)

        base_url_pattern = "https://wahlergebnisse.brandenburg.de/12/500/20240922/landtagswahl_land/ergebnisse_wahlkreis_{:02d}.html"

        for i in range(1, 46):  # Iterate from 01 to 45
            district_id = f"{i:02d}"
            base_url = base_url_pattern.format(i)

            url_stack = [base_url]
            processed_urls = set()

            while url_stack:
                full_url = url_stack.pop()

                if full_url in processed_urls:
                    continue

                processed_urls.add(full_url)

                # briefwahlbezirk
                # Get the filename from the URL to use as base for the sub-links
                url_filename_match = re.search(r'ergebnisse_wahlkreis_(\d+)\.html|ergebnisse_gemeinde_(\d+)\.html|ergebnisse_ortsteil_(\d+)\.html|ergebnisse_wahlbezirk_(\d+)\.html|ergebnisse_stimmbezirk_(\d+)\.html|ergebnisse_briefwahlbezirk_(\d+)\.html|ergebnisse_amt_(\d+)\.html', full_url)
                base_filename = "wahlkreis_" + district_id
                if url_filename_match:
                    if url_filename_match.group(1):
                        base_filename = "wahlkreis_" + district_id + "_" + url_filename_match.group(1)
                    elif url_filename_match.group(2):
                        base_filename = "gemeinde_" + district_id + "_" + url_filename_match.group(2)
                    elif url_filename_match.group(3):
                        base_filename = "ortsteil_" + district_id + "_" + url_filename_match.group(3)
                    elif url_filename_match.group(4):
                        base_filename = "wahlbezirk_" + district_id + "_" + url_filename_match.group(4)
                    elif url_filename_match.group(5):
                        base_filename = "stimmbezirk_" + district_id + "_" + url_filename_match.group(5)
                    elif url_filename_match.group(6):
                        base_filename = "briefwahlbezirk_" + district_id + "_" + url_filename_match.group(6)
                    elif url_filename_match.group(7):
                        base_filename = "amt_" + district_id + "_" + url_filename_match.group(7)

                process_url_and_get_title(driver, full_url, download_dir, base_filename)

                try:
                    WebDriverWait(driver, 0.14).until(
                        EC.presence_of_element_located((By.XPATH, "//h5[contains(text(), 'Untergeordnet')]/following-sibling::ul[contains(@class, 'linklist')]"))
                    )

                    sub_links_container = driver.find_element(By.XPATH, "//h5[contains(text(), 'Untergeordnet')]/following-sibling::ul[contains(@class, 'linklist')]")
                    sub_links = sub_links_container.find_elements(By.TAG_NAME, 'a')

                    if sub_links:
                        print(f"Found {len(sub_links)} nested links. Adding them to the stack.")
                        for link in sub_links:
                            new_link_href = link.get_attribute('href')
                            if new_link_href and new_link_href not in processed_urls:
                                url_stack.append(new_link_href)
                except Exception:
                    print("No further nested links found on this page. Continuing.")

    except Exception as e:
        print(f"A general error occurred: {e}")
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver closed.")

if __name__ == "__main__":
    main_scraper()
