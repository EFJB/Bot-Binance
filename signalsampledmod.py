from tradingview_ta import TA_Handler, Interval, Exchange
# Usar variables de entorno
import os
# Usar si necesita pasar argumentos a modulos externos
import sys
# Usado para manejar directorios
import glob

import time

MY_EXCHANGE = 'BINANCE'
MY_SCREENER = 'CRYPTO'
MY_FIRST_INTERVAL = Interval.INTERVAL_1_MINUTE
MY_SECOND_INTERVAL = Interval.INTERVAL_5_MINUTES
TA_BUY_THRESHOLD = 17 # Cuantos de los 26 indicadores indican una compra
PAIR_WITH = 'USDT'
TICKERS = "C:/Users/engel/Documents/Programar/Python/bot_binance/tickers_testnet.txt"
TIME_TO_WAIT = 4 # Minutos para esperar entre los análisis
FULL_LOG = False # Muestra el resultado del análisis en la consola

def analyze(pairs):

    taMax = 0
    taMaxCoin = 'none'
    signal_coins = {}
    first_handler = {}
    second_handler = {}
    first_analysis = {}
    second_analysis = {}

    if os.path.exists('signals/signalsample.exs'):
        os.remove('signals/signalsample.exs')


    for pair in pairs:
        first_handler[pair] = TA_Handler(
            symbol= pair,
            exchange= MY_EXCHANGE,
            screener= MY_SCREENER,
            interval= MY_FIRST_INTERVAL,
            timeout= 10
        )
        second_handler[pair] = TA_Handler(
            symbol= pair,
            exchange= MY_EXCHANGE,
            screener= MY_SCREENER,
            interval= MY_SECOND_INTERVAL,
            timeout= 10
        )

    for pair in pairs:
        try:
            first_analysis = first_handler[pair].get_analysis() # Para el primer período de tiempo
            second_analysis = second_handler[pair].get_analysis() # Para el segundo período de tiempo
        except Exception as e:
            print("Signalsample:")
            print("Exception:")
            print(e)
            print(f'Coin: {pair}')
            print(f'First handler: {first_handler[pair]}')
            print(f'Second handler: {second_handler[pair]}')
            

        first_tacheck = first_analysis.summary['BUY'] # Cantidad de indicadores para compra
        second_tacheck = second_analysis.summary['BUY']

        if FULL_LOG:
            # print(f'Primer Analisis: {first_analysis.__dict__}, Segundo Analisis: {second_analysis.__dict__}')
            print(f'Signalsample: {pair} Primer {first_tacheck} Segundo {second_tacheck}')
        else:
            print('.', end= '')

        if first_tacheck > taMax:
            taMax = first_tacheck
            taMaxCoin = pair
        # if 19 >= TA_BUY_THRESHOLD and 20 >= TA_BUY_THRESHOLD:
        if first_tacheck >= TA_BUY_THRESHOLD and second_tacheck >= TA_BUY_THRESHOLD:
            signal_coins[pair] = pair
            print("")
            print(f'Signalsample: Señal detectada en {pair}')

            if not os.path.exists('signals/'):
                os.mkdir('signals/')
            else:
                with open('signals/signalsample.exs', 'a+') as f:
                    f.write(pair + '\n')
    print("")
    print(f'Signalsample: Señal máxima para {taMaxCoin} en {taMax} en el timeframe mas corto')
    
    return signal_coins

def do_work():
    signal_coins = {}
    pairs = {}

    for line in open(TICKERS):
        pairs = [line.strip() + PAIR_WITH for line in open(TICKERS)]

    
    while True:
        print(f'Signalsample: Analizando {len(pairs)} monedas')
        signal_coins = analyze(pairs)
        
        if len(signal_coins) == 0:
            print(f'Signalsample: Sin monedas por encima del umbral de {TA_BUY_THRESHOLD}')
        else:
            print(f'Signalsample: {len(signal_coins)} monedas por en encima del umbral de {TA_BUY_THRESHOLD} en ambos períodos de tiempo')
        print(f'Signalsample: Esperando {TIME_TO_WAIT} minutos para el próximo análisis')
        time.sleep(TIME_TO_WAIT*60)
    # print(first_analysis.__dict__)
    # print(first_tacheck, second_tacheck)
    # print(signal_coins)