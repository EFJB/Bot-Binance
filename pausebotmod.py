from tradingview_ta import TA_Handler, Interval, Exchange
import os
import time
import threading

INTERVAL = Interval.INTERVAL_1_MINUTE # Marco de tiempo para el análisis

MY_EXCHANGE = 'BINANCE'
MY_SCREENER = 'CRYPTO'
SYMBOL = 'BTCUSDT'
THRESHOLD = 7 # 7 de 15 MA's indican venta
TIME_TO_WAIT = 1 # Minutos para esperar entre los análisis
FULL_LOG = False # Muestra el resultado del análisis en la consola

def analyze():
    analysis = {}
    handler = {}

    handler = TA_Handler(
        symbol= SYMBOL,
        exchange= MY_EXCHANGE,
        screener= MY_SCREENER,
        interval= INTERVAL,
        timeout= 10
    )

    try:
        analysis = handler.get_analysis()
    except Exception as e:
        print("pausebotmod:")
        print("Exception:")
        print(e)

    ma_sell = analysis.moving_averages['SELL'] # Cantidad de indicadores para venta

    if ma_sell >= THRESHOLD:
        paused = True
        print(f'pausebotmod: El mercado no se ve muy bien, el bot dejó de comprar {ma_sell}/{THRESHOLD} Esperando {TIME_TO_WAIT} minutos para el próximos checkeo del mercado')
    else:
        print(f'pausebotmod: Mercado se ve bien, bot esta corriendo nuevamente {ma_sell}/{THRESHOLD} Esperando {TIME_TO_WAIT} minutos para el próximo checkeo del mercado')
        paused = False

    return paused

def do_work():

    while True:
        if not threading.main_thread().is_alive(): exit()

        paused = analyze()
        
        if paused:
            with open ('signals/paused.exc', 'a+') as f:
                f.write('yes')
        else:
            if os.path.isfile('signals/paused.exc'):
                os.remove('signals/paused.exc')

        time.sleep(TIME_TO_WAIT*60)