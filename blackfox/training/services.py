from time import sleep

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


TEST_URL = 'https://health-diet.ru/diary/share/7758976496ec140b28a'
SLEEP = 3
FIELDS = {
    0: 'Калорийность (ккал)',
    1: 'Белки (г)',
    2: 'Жиры (г)',
    3: 'Углеводы (г)',
    6: 'Пищевые волокна (г)',
    7: 'Вода (г)',
    21: 'Витамин D, кальциферол (мкг)',
    29: 'Калий, K (мг)',
    30: 'Кальций, Ca (мг)',
    33: 'Натрий, Na (мг)',
    40: 'Железо, Fe (мг)',
    83: 'Холестерин (мг)',
}
DIET = [
    'calories', 'calories_rdr', 'calories_perc',
    'protein', 'protein_rdr', 'protein_perc',
    'fat', 'fat_rdr', 'fat_perc',
    'carb', 'carb_rdr', 'carb_perc',
    'fiber', 'fiber_rdr', 'fiber_perc',
    'water', 'water_rdr', 'water_perc',
    'vitamin_d', 'vitamin_d_rdr', 'vitamin_d_perc',
    'potassium', 'potassium_rdr', 'potassium_perc',
    'calcium', 'calcium_rdr', 'calcium_perc',
    'natrium', 'natrium_rdr', 'natrium_perc',
    'ferrum', 'ferrum_rdr', 'ferrum_perc',
    'cholesterin', 'cholesterin_rdr', 'cholesterin_perc',
]
CENTURY = '20'


def get_data(url):
    service = Service(executable_path=ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.get(url)
    sleep(SLEEP)

    # Возможные варианты для поиска:
    # ID, XPATH, LINK_TEXT, PARTIAL_LINK_TEXT,
    # NAME, TAG_NAME, CLASS_NAME, CSS_SELECTOR
    overflow_button = driver.find_element(
        By.CSS_SELECTOR,
        '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div:nth-child(5) > div > div.uk-flex-item-1.uk-margin-large-left > div > div.mzr-block-header-light.uk-flex.uk-flex-space-between.uk-flex-middle.mzr-font--body16sb > div.uk-flex.uk-flex-middle.uk-flex-item-none.mzr-no-print > svg:nth-child(1)'
    )
    overflow_button.click()
    sleep(SLEEP)

    date = driver.find_element(
        By.CSS_SELECTOR,
        '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div.mzr-block-header-light.uk-flex.uk-flex-space-between.uk-flex-middle.mzr-font--body18sb > div:nth-child(1)'
    ).text.split(' ')[-1]
    table = driver.find_element(
        By.CSS_SELECTOR,
        '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div:nth-child(5) > div > div.uk-flex-item-1.uk-margin-large-left > div > div.uk-overflow-container > table > tbody'
    )
    rows = table.find_elements(By.TAG_NAME, 'tr')
    results = []

    for r in rows:
        values = r.find_elements(By.TAG_NAME, 'td')
        row = []
        for v in values:
            row.append(v.text)
        results.append(row[1:])
    results.append(date)

    driver.quit()  # Закрытие веб-драйвера.
    return edit_data(results, date)


def edit_data(data, diet_date):
    results = {}
    dd, mm, yy = diet_date.split('.')
    results['diet_date'] = CENTURY + yy + '-' + mm + '-' + dd
    temp = []
    for n in FIELDS.keys():
        vavue, rdr, percentage = data[n]
        temp.append(vavue)
        temp.append(rdr.split('-')[-1].split(' ')[-1])
        temp.append(percentage.replace('%', ''))
    for i in range(len(DIET)):
        results[DIET[i]] = float(temp[i])

    return results
