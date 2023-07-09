from requests_html import HTMLSession

from bs4 import BeautifulSoup


TEST_URL = 'https://health-diet.ru/diary/share/7758976496ec140b28a'
MACRO = ['calories', 'protein', 'fat', 'carb', 'water', 'fiber']
MICRO = ['cholesterin', 'calcium', 'potassium', 'ferrum', 'natrium', 'vitamin_d']


def get_response(session, url):
    response = session.get(url)
    response.html.render(sleep=3)
    return response.html.html


def parse_diet_diary(url):
    session = HTMLSession()
    response = get_response(session, url)
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
    results = {}
    for index in range(len(MACRO)):
        results[MACRO[index]] = float(macronutrients[index].text.split()[0])
        
    for index in range(len(MICRO)):
        results[MICRO[index]] = float(micronutrients[index].text.split()[0])
    return print(results)


if __name__ == '__main__':
    parse_diet_diary(TEST_URL)
