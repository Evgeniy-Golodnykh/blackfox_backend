from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


TEST_URL = 'https://health-diet.ru/diary/share/7758976496ec140b28a'
SLEEP = 3


def get_selenium(url):
    service = Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(url)
    sleep(SLEEP)

    # Возможные варианты для поиска:
    # ID, XPATH, LINK_TEXT, PARTIAL_LINK_TEXT,
    # NAME, TAG_NAME, CLASS_NAME, CSS_SELECTOR
    overflow_button = driver.find_element(By.CSS_SELECTOR, '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div:nth-child(5) > div > div.uk-flex-item-1.uk-margin-large-left > div > div.mzr-block-header-light.uk-flex.uk-flex-space-between.uk-flex-middle.mzr-font--body16sb > div.uk-flex.uk-flex-middle.uk-flex-item-none.mzr-no-print > svg:nth-child(1)')
    overflow_button.click()
    sleep(SLEEP)

    table = driver.find_element(By.CSS_SELECTOR, '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div:nth-child(5) > div > div.uk-flex-item-1.uk-margin-large-left > div > div.uk-overflow-container > table > tbody')
    rows = table.find_elements(By.TAG_NAME, 'tr')
    results = {}

    for r in rows:
        values = r.find_elements(By.TAG_NAME, 'td')
        row = []
        for v in values:
            row.append(v.text)
        results[row[0]] = float(row[1])

    driver.quit()  # Закрытие веб-драйвера.
    return results


if __name__ == '__main__':
    get_selenium(TEST_URL)
