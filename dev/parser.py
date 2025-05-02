from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import pandas as pd
import os
from datetime import datetime, timedelta
import json
import joblib
from sklearn.ensemble import RandomForestRegressor
import numpy as np
from datetime import datetime, timedelta

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

url = "https://rp5.ru/Погода_в_Иркутске"
driver.get(url)

wait = WebDriverWait(driver, 15)
button = wait.until(EC.element_to_be_clickable((By.ID, "ftab-0")))
button.click()

table = wait.until(EC.presence_of_element_located((By.ID, "forecastTable_1_3")))
rows = table.find_elements(By.TAG_NAME, "tr")

data = []

hours_raw = rows[1].find_elements(By.TAG_NAME, "td") or rows[1].find_elements(By.TAG_NAME, "th")
"""for i in hours_raw:
    print(i.text)"""
hours = [int(hour.text) for hour in hours_raw[1:-1]]

months_lib = {"января" : 1, "февраля" : 2, "марта" : 3, "апреля" : 4, "мая" : 5, "июня" : 6, 
          "июля" : 7, "августа" : 8, "сентября" : 9, "октября" : 10, "ноября" : 11, "декабря" : 12,}
cells = rows[0].find_elements(By.TAG_NAME, "td") or rows[0].find_elements(By.TAG_NAME, "th")
cells = [txt.text for txt in cells]
days = []
months = []
for cell in cells:
    date = re.search(r"(\d+)\s+([а-яА-Я]+)", cell)
    if date:
        day = int(date.group(1))
        month = months_lib[date.group(2)]
        days.append(day)
        months.append(month)
data.append(hours)

cells = rows[2].find_elements(By.TAG_NAME, "td") or rows[2].find_elements(By.TAG_NAME, "th")
cloud_cover = []
clouds = []
cloud_percentages = []

for cell in cells:
    try:
        cc_0 = cell.find_element(By.CLASS_NAME, "cc_0").get_attribute("innerHTML")

        teg_b = re.search(r"<b>(.*?)</b>", cc_0)
        cloud_cover.append(teg_b.group(1) if teg_b else '')

        teg_br = re.search(r"<br/>\((.*?)\)", cc_0)
        cloud_info = teg_br.group(1).strip('"') if teg_br else ''

        lower = re.search(r"нижнего яруса (\d+)%", cloud_info)
        middle = re.search(r"среднего яруса (\d+)%", cloud_info)

        if lower:
            cloud_percentages.append(int(lower.group(1)))
        elif middle:
            cloud_percentages.append(int(middle.group(1)))
        else:
            cloud_percentages.append(0)

        clouds.append(cloud_info)

    except:
        pass

data.append(cloud_cover[1:-1])
cloud_percentages[1:-1] = [x / 100 for x in cloud_percentages[1:-1]]
data.append(cloud_percentages[1:-1])

cells = rows[3].find_elements(By.TAG_NAME, "td") or rows[3].find_elements(By.TAG_NAME, "th")
rainfall = []
for cell in cells:
    try:
        pr_0 = cell.find_element(By.CLASS_NAME, "pr_0")
        pr_0 = pr_0.get_attribute("outerHTML")
        rf = re.search(r"tooltip\(this, '(.*?)'", pr_0)
        if rf:
            rainfall.append(rf.group(1))
        else:
            rainfall.append('')
    except:
        pass
data.append(rainfall[1:-1])

begin_parse = 4
end_parse = 11

if len(rows) == 14:
    begin_parse -= 1
    end_parse -= 1

for i in range(begin_parse, end_parse):
    raw_data = rows[i].find_elements(By.TAG_NAME, "td") or rows[i].find_elements(By.TAG_NAME, "th")
    raw_data = [raw.text for raw in raw_data]
    data.append(raw_data[1:-1])

hum_data = rows[end_parse].find_elements(By.TAG_NAME, "td") or rows[end_parse].find_elements(By.TAG_NAME, "th")
humidity = []
for cell in hum_data:
    digit = cell.get_attribute("innerHTML")
    teg_b = re.search(r"<b>(.*?)</b>", digit)
    if teg_b:
        humidity.append(teg_b.group(1))
    else:
        humidity.append(digit)
data.append(humidity[1:-1])

df = pd.DataFrame(data).T  

first_zero_hour_index = df[df[0] == 0].index[0]

current_date = datetime.today()

if df.iloc[0, 0] == 0:
    current_date += timedelta(days=1)

years, months, days = [], [], []

previous_hour = df.iloc[0, 0]
track_hour_decrease = False

for i in range(len(df)):
    current_hour = df.iloc[i, 0]

    if i == first_zero_hour_index:
        track_hour_decrease = True

    if track_hour_decrease and current_hour < previous_hour:
        current_date += timedelta(days=1)

    years.append(current_date.year)
    months.append(current_date.month)
    days.append(current_date.day)

    previous_hour = current_hour

df['YEAR'] = years
df['MO'] = months
df['DY'] = days

df = df[['YEAR', 'MO', 'DY'] + [col for col in df.columns if col not in ['YEAR', 'MO', 'DY']]]

df.columns = ['YEAR','MO','DY','HR','N','Nh','W1','F','T','Tt','Po','Ff','FF','f','U']
columns = ['F','Tt','FF','f']
df = df.drop(columns, axis=1)

json_dir = os.path.dirname(os.path.abspath(__file__))
json_file = os.path.join(json_dir, "data/weather_to_num.json") 
with open(json_file , 'r', encoding='utf-8') as f:
    replacement_rules = json.load(f)

def normalize_text(text):
    replacements = {
        'C': 'С',
        'c': 'с',
    }
    for latin, cyrillic in replacements.items():
        text = text.replace(latin, cyrillic)
    return text.strip()

def replace_weather_condition(text, condition_dict):
    text = normalize_text(text)
    for condition, value in condition_dict.items():
        if condition.lower() in text.lower():
            return value
    return text

df['W1'] = df['W1'].apply(lambda x: replace_weather_condition(str(x), replacement_rules["W1"]))
df['N'] = df['N'].apply(lambda x: replace_weather_condition(str(x), replacement_rules["N"]))

script_dir = os.path.dirname(os.path.abspath(__file__))
rad = os.path.join(script_dir, 'data/params.csv')
df2 = pd.read_csv(rad, delimiter=',', encoding='utf-8', index_col=False)
df = pd.merge(df, df2[['MO', 'DY', 'HR', 'SZA','ALB','NDAY','delta','sina','beta','y']], on=['MO', 'DY', 'HR'], how='left')

w = os.path.join(script_dir, 'data/w.csv')
df2 = pd.read_csv(w, delimiter=',', encoding='utf-8', index_col=False)
df = pd.merge(df, df2[['HR', 'w']], on=['HR'], how='left')

df['T'] = pd.to_numeric(df['T'], errors='coerce')
df['Ff'] = pd.to_numeric(df['Ff'], errors='coerce')

rf_model = os.path.join(script_dir, 'model.pkl')
rf_model = joblib.load(rf_model)

data_test = df.copy()

data_test['MO'] = data_test['MO'].astype(int)
data_test['DY'] = data_test['DY'].astype(int)

data_test['DayOfYear'] = pd.to_datetime(
    data_test[['YEAR', 'MO', 'DY']].astype(str).agg('-'.join, axis=1), errors='coerce'
).dt.dayofyear.fillna(0).astype(int)

data_test['sin_month'] = np.sin(2 * np.pi * data_test['MO'] / 12)
data_test['cos_month'] = np.cos(2 * np.pi * data_test['MO'] / 12)

data_test['sin_hour'] = np.sin(2 * np.pi * data_test['HR'].astype(int) / 24)
data_test['cos_hour'] = np.cos(2 * np.pi * data_test['HR'].astype(int) / 24)
data_test['sin_day_year'] = np.sin(2 * np.pi * data_test['DayOfYear'] / 365)
data_test['cos_day_year'] = np.cos(2 * np.pi * data_test['DayOfYear'] / 365)

features = ['sin_month', 'cos_month', 'sin_hour', 'cos_hour', 'sin_day_year', 'cos_day_year',
            'T', 'Po', 'U', 'Ff', 'SZA', 'N', 'W1', 'Nh']

X_test = data_test[features]
X_test.to_csv('test_data.csv', index=False, encoding="utf-8")

rf_pred = rf_model.predict(X_test)
rad_pred = pd.DataFrame(rf_pred, columns=['ALLSKY_SFC_SW_DIFF', 'ALLSKY_SFC_SW_DWN'])
times = ['YEAR', 'MO', 'DY', 'HR']
df_time = data_test[times]
df = pd.concat([df, rad_pred], axis=1)

LANTITUDE = 52.3

df['rad_pram'] = df.apply(lambda row: row['ALLSKY_SFC_SW_DWN']-row['ALLSKY_SFC_SW_DIFF'], axis=1)

df['cos'] = df.apply(lambda row: 
    np.sin(row['beta'] * np.pi/180) * (
        np.cos(row['delta'] * np.pi/180) * (
            np.sin(LANTITUDE * np.pi/180) * np.cos(row['y'] * np.pi/180) * np.cos(row['w'] * np.pi/180) + 
            np.sin(row['y'] * np.pi/180) * np.sin(row['w'] * np.pi/180)
        ) - 
        np.sin(row['delta'] * np.pi/180) * np.cos(LANTITUDE * np.pi/180) * np.cos(row['y'] * np.pi/180)
    ) + 
    np.cos(row['beta'] * np.pi/180) * (
        np.cos(row['delta'] * np.pi/180) * np.cos(LANTITUDE * np.pi/180) * np.cos(row['w'] * np.pi/180) + 
        np.sin(row['delta'] * np.pi/180) * np.sin(LANTITUDE * np.pi/180)
    ), axis=1)

df['Hnorm'] = df.apply(lambda row: row['rad_pram']/row['sina'], axis=1)

df['Hbt'] = df.apply(lambda row: row['Hnorm']*row['cos'], axis=1)

df['Hdt'] = df.apply(lambda row: row['ALLSKY_SFC_SW_DIFF']*(1+np.cos(row['beta']*np.pi/180))/2, axis=1)

df['Hrt'] = df.apply(lambda row: row['ALB']*row['ALLSKY_SFC_SW_DWN']*(1-np.cos(row['beta']*np.pi/180))/2, axis=1)

df['Hgt'] = df.apply(lambda row: row['Hbt']+row['Hdt']+row['Hrt'], axis=1)

df['Tmod'] = df.apply(lambda row: row['Hgt']*np.exp(-3.47-0.075*row['Ff'])+row['T'], axis=1)

df['Tyach'] = df.apply(lambda row: row['Tmod']+(row['Hgt']/1000)*2.5, axis=1)

df['W'] = df.apply(lambda row: row['Hgt']*(1-0.47*(row['Tyach']-25)/100), axis=1)

KPD = 0.12
LENGHT = 1.92
WIDTH = 1.02
df['Wel'] = df.apply(lambda row: row['W']*KPD*LENGHT*WIDTH, axis=1)

script_dir = os.path.dirname(os.path.abspath(__file__))
file = os.path.join(script_dir, "test_data.csv")
df.to_csv(file, index=False, encoding="utf-8")