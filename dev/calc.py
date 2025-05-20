import joblib
import numpy as np
import pandas as pd
import os
from sklearn.ensemble import RandomForestRegressor

def calc_power(df, KPD, LENGHT, WIDTH, optim, beta = None, y = None):
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rad = os.path.join(script_dir, 'data/params.csv')
    df2 = pd.read_csv(rad, delimiter=',', encoding='utf-8', index_col=False)
    if not(optim):
        df = pd.merge(df, df2[['MO', 'DY', 'HR', 'SZA','ALB','NDAY','delta','sina']], on=['MO', 'DY', 'HR'], how='left')
        df['beta'] = df.apply(lambda row: beta, axis=1)
        df['y'] = df.apply(lambda row: y, axis=1)
    else:
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

    df['Wel'] = df.apply(lambda row: row['W']*KPD*LENGHT*WIDTH, axis=1)

    df.loc[df['Wel'] < 0, 'Wel'] = 0
    df.loc[df['sina'] < 0, 'Wel'] = 0

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file = os.path.join(script_dir, "test_data.csv")
    df.to_csv(file, index=False, encoding="utf-8")

    return df