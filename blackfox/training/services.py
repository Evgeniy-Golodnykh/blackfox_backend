from time import sleep
from requests_html import HTMLSession

from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


TEST_URL = 'https://health-diet.ru/diary/share/7758976496ec140b28a'
MACRO = ['calories', 'protein', 'fat', 'carb', 'water', 'fiber']
MICRO = ['cholesterin', 'calcium', 'potassium', 'ferrum', 'natrium', 'vitamin_d']
SLEEP = 3


def get_selenium(url):
    service = Service(executable_path=ChromeDriverManager().install())
    # Запуск веб-драйвера для Chrome.
    driver = webdriver.Chrome(service=service)

    # Открытие страницы по заданному адресу.
    driver.get(url)
    # Развёртывание окна на полный экран.
    driver.maximize_window()
    # Здесь и далее паузы, чтобы рассмотреть происходящее.
    sleep(SLEEP)

    # Поиск в содержимом страницы поля для логина.
    # Возможные варианты для поиска:
    # ID, XPATH, LINK_TEXT, PARTIAL_LINK_TEXT,
    # NAME, TAG_NAME, CLASS_NAME, CSS_SELECTOR
    overflow_button = driver.find_element(By.CSS_SELECTOR, '#js_app_root > div.uk-height-1-1 > div.mzr-grid-1-column > div > div > div > div:nth-child(5) > div > div.uk-flex-item-1.uk-margin-large-left > div > div.mzr-block-header-light.uk-flex.uk-flex-space-between.uk-flex-middle.mzr-font--body16sb > div.uk-flex.uk-flex-middle.uk-flex-item-none.mzr-no-print > svg:nth-child(1) > g > path:nth-child(1)')
    overflow_button.click()
    sleep(SLEEP)
    table = driver.find_element(By.XPATH, '//*[@id="js_app_root"]/div[1]/div[3]/div/div/div/div[5]/div/div[2]/div/div[2]/table/tbody')
    # Вывод текста найденного элемента в терминал.
    print(table)
    # Закрытие веб-драйвера.
    driver.quit()


def get_response(url):
    session = HTMLSession()
    response = session.get(url)
    response.html.render(sleep=SLEEP)
    return response.html.html


def parse_diet_diary(url):
    response = get_response(url)
    if response is None:
        return
    soup = BeautifulSoup(response, features='lxml')
    macronutrients = soup.find_all(
        'span',
        attrs={
            'class': 'mzr-macronutrients-item-header-value'
        }
    )
    micronutrients = soup.find_all(
        'div',
        attrs={'class': 'uk-flex el-micr-nutr-row uk-flex-middle'}
    )
    overflow = soup.find(
        'table',
        attrs={'class': 'uk-table uk-table-hover uk-table-condensed'}
    )
    results = {}
    for index in range(len(MACRO)):
        results[MACRO[index]] = float(macronutrients[index].text.split()[0])
    '''
    for index in range(len(MICRO)):
        results[MICRO[index]] = float(micronutrients[index].text.split()[0])
    '''
    return print(overflow.prettify())


if __name__ == '__main__':
    get_selenium(TEST_URL)
