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
    Reinigt einen String, um ihn zu einem gültigen Dateinamen zu machen, indem
    ungültige Zeichen entfernt oder ersetzt werden.
    """
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = name.replace(' ', '_')
    return name.strip('_. ')

def process_url_and_get_title(driver, full_url, download_dir):
    """
    Navigiert zu einer bestimmten URL, extrahiert die Tabellendaten und speichert sie.
    Verwendet den Seitentitel als Namen und benennt die Spalten um.
    """
    try:
        print(f"\nVerarbeite URL: {full_url}")
        driver.get(full_url)

        # Holen Sie den Seitentitel und extrahieren Sie den Namen mit Regex
        title = driver.title
        match = re.search(r" in (.*)", title)
        name = match.group(1).strip() if match else title

        if not name:
            name = "Unbekannt"
            print("⚠️ Seitentitel konnte nicht extrahiert werden. Verwende 'Unbekannt'.")

        print(f"Name der Seite: '{name}'")

        # Verkürzen Sie den Timeout, um die Wartezeit zu verringern
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.tablesaw.table-stimmen[data-tablejigsaw-downloadable]"))
        )

        table_selector = "table.tablesaw.table-stimmen[data-tablejigsaw-downloadable]"
        table_element = driver.find_element(By.CSS_SELECTOR, table_selector)

        table_html = table_element.get_attribute('outerHTML')

        df_list = pd.read_html(StringIO(table_html), header=[0, 1])

        if df_list:
            df = df_list[0]

            new_columns = []
            for col_tuple in df.columns:
                if 'Unnamed' in col_tuple[0] and col_tuple[1] == 'Unnamed: 0_level_1':
                    new_name = 'Merkmal'
                else:
                    new_name = f"{col_tuple[0]}_{col_tuple[1]}"

                new_columns.append(new_name)

            df.columns = new_columns

            # Regex-Bereinigung, um doppelte Namen, "more" und unnötige Symbole zu entfernen
            df.columns = [re.sub(r'(Erststimmenmore|Zweitstimmenmore)', '', col) for col in df.columns]
            df.columns = [re.sub(r'Gewinn.*', 'Gewinn', col) for col in df.columns]
            df.columns = [re.sub(r'more', '', col) for col in df.columns]

            # Entfernt die Duplikate (z.B. "ErststimmenErststimmen")
            df.columns = [re.sub(r'^(Erststimmen|Zweitstimmen)\1', r'\1', col) for col in df.columns]

            # Letzte Bereinigung für saubere CSV-Header
            df.columns = [col.replace(' ', '_').replace('__', '_').replace('-', '').replace('%', '') for col in df.columns]

            filename = f"{sanitize_filename(name)}.csv"
            file_path = os.path.join(download_dir, filename)

            final_df = df
            final_df.to_csv(file_path, index=False, sep=';', encoding='utf-8')
            print(f"✅ Daten erfolgreich gespeichert in: {file_path}")
        else:
            print(f"⚠️ Keine Tabelle gefunden mit pandas für '{name}'.")

        return driver.current_url
    except Exception as e:
        print(f"❌ Ein Fehler ist aufgetreten beim Verarbeiten von '{full_url}': {e}")
        traceback.print_exc()
        # Verkürzen Sie den Sleep-Timer, um schneller fortzufahren
        time.sleep(1)
        return None

def recursive_get_election_data():
    """
    Extrahiert rekursiv Wahldaten von wahlergebnisse.brandenburg.de.
    Diese Funktion navigiert durch verschachtelte Links, um alle verfügbaren
    Wahldaten herunterzuladen und als CSV-Dateien zu speichern.
    """
    chromium_driver_path = "/usr/bin/chromedriver"
    if not os.path.exists(chromium_driver_path):
        print(f"Fehler: Chromium-Treiber nicht gefunden unter {chromium_driver_path}")
        return

    download_dir = "./results"
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
        print(f"Verzeichnis erstellt: {download_dir}")

    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--ignore-certificate-errors")

        service = ChromiumService(executable_path=chromium_driver_path)
        driver = webdriver.Chrome(service=service, options=options)

        # Verwenden Sie einen Stack, um die zu besuchenden URLs zu verwalten.
        url_stack = ["https://wahlergebnisse.brandenburg.de/12/500/20240922/landtagswahl_land/ergebnisse_land_120.html"]
        processed_urls = set()

        while url_stack:
            full_url = url_stack.pop()

            if full_url in processed_urls:
                continue

            processed_urls.add(full_url)

            process_url_and_get_title(driver, full_url, download_dir)

            try:
                # Verkürzen Sie den Timeout, um die Wartezeit zu verringern
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//h5[contains(text(), 'Untergeordnet')]/following-sibling::ul[contains(@class, 'linklist')]"))
                )

                sub_links_container = driver.find_element(By.XPATH, "//h5[contains(text(), 'Untergeordnet')]/following-sibling::ul[contains(@class, 'linklist')]")
                sub_links = sub_links_container.find_elements(By.TAG_NAME, 'a')

                if sub_links:
                    print(f"Habe {len(sub_links)} verschachtelte Links gefunden. Füge sie dem Stack hinzu.")
                    for link in sub_links:
                        new_link_href = link.get_attribute('href')
                        if new_link_href not in processed_urls:
                            url_stack.append(new_link_href)
            except Exception:
                print("Keine weiteren verschachtelten Links auf dieser Seite gefunden. Fahre fort.")

    except Exception as e:
        print(f"Ein allgemeiner Fehler ist aufgetreten: {e}")
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            print("\nWebDriver geschlossen.")

if __name__ == "__main__":
    recursive_get_election_data()
