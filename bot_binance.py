# https://www.cryptomaton.org/2021/05/08/how-to-code-a-binance-trading-bot-that-detects-the-most-volatile-coins-on-binance/
# Para usar variables de entorno
import os
import socket
from signalsampledmod import PAIR_WITH

# Usado para crear hilos y dinámica cargar los modulos
import threading
import importlib

# Usado para manejar directorios
import glob

# from colorama import init
# init()

# Necesario para la API de binance y websockets / Manejo de Excepciones
from binance.client import Client
from binance.exceptions import BinanceAPIException
from requests.exceptions import ReadTimeout

# Usado para fechas
from datetime import date, datetime, timedelta
import time

# Usado para repetidamente ejecutar el codigo
from itertools import count

# Usado para almacenar trades y venta de activos
import json

# Cargar modulos auxiliares
from helpers.parameters import (
    parse_args, load_config
)

# Cargar modulos de credenciales
from helpers.handle_creds import (
    load_correct_creds, test_api_key
)

# Para un registro colorido en la consola
class txcolors:
    BUY = '\033[92m'
    WARNING = '\033[93m'
    SELL_LOSS = '\033[91m'
    SELL_PROFIT = '\033[32m'
    DEFAULT = '\033[39m'

# Registra ganancias/perdidas de cada sesion
global session_profit
session_profit = 0

def get_info():
    '''Devuelve informacion acerca de la moneda'''
    min_notional = {}
    info = client.get_exchange_info()['symbols']
        
    for coin in info:
        if CUSTOM_LIST:
            if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in FIATS):
                min_notional[coin['symbol']] = coin['filters'][3]['minNotional']
        else:
            if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
                min_notional[coin['symbol']] = coin['filters'][3]['minNotional']
                # print(coin['filters'][3]['minNotional'])

    return min_notional
    # coin = list(filter(lambda x:x['symbol'] == coin, info))
    # filters = coin[0]['filters'][3]
    # print(filters['minNotional'])
    

def get_price(add_to_historical=True):
    ''''Devuelve el precio actual para todas las monedas en Binance'''

    global historical_prices, hsp_head

    initial_price = {}
    prices = client.get_all_tickers()

    for coin in prices:

        # Solo devuelve pares USDT y excluye simbolos margin como BTCDOWNUSDT
        if CUSTOM_LIST:
            if any(item + PAIR_WITH == coin['symbol'] for item in tickers) and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = {'price': coin['price'], 'time': datetime.now()}
        else:
            if PAIR_WITH in coin['symbol'] and all(item not in coin['symbol'] for item in FIATS):
                initial_price[coin['symbol']] = {'price': coin['price'], 'time': datetime.now()}

    if add_to_historical:
        hsp_head += 1

        if hsp_head == RECHECK_INTERVAL:
            hsp_head = 0
        
        historical_prices[hsp_head] = initial_price

    return initial_price

def wait_for_price():
    '''Llama al precio inicial  y se asegura de que haya pasado la cantidad de tiempo correcta antes de volver a leer el precio actual'''

    global historical_prices, hsp_head, volatility_cooloff, bot_paused

    volatile_coins = {}
    externals = {}
    coins_up = 0
    coins_down = 0
    coins_unchanged = 0

    pause_bot()

    if historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'] > datetime.now() - timedelta(minutes=float(TIME_DIFFERENCE - RECHECK_INTERVAL)):
        # Duerme por exactamente la cantidad de tiempo requerido
        time.sleep((timedelta(minutes=float(TIME_DIFFERENCE / RECHECK_INTERVAL)) - (datetime.now() - historical_prices[hsp_head]['BNB' + PAIR_WITH]['time'])).total_seconds())

    print(f'Trabajando... Ganancia de la session: {session_profit:.2f}% Est: ${(QUANTITY * session_profit) / 100:.2f}')

    # Recupera los últimos precios
    get_price(add_to_historical=True)
    
    # Calcula la diferencia entre el primer y ultimo precio que lee
    for coin in historical_prices[hsp_head]:

        # Precios mínimos y máximos durante un período de tiempo
        min_price = min(historical_prices, key= lambda x: float('inf') if x is None else float(x[coin]['price']))
        max_price = max(historical_prices, key= lambda x: -1 if x is None else float(x[coin]['price']))
        
        threshold_check = (-1.0 if min_price[coin]['time'] > max_price[coin]['time'] else 1.0)

        # Cada moneda con ganancias más altas que nuestro CHANGE_IN_PRICE se agrega al diccionario de volatile_coins
        if threshold_check > CHANGE_IN_PRICE:
            coins_up += 1

            if coin not in volatility_cooloff:
                volatility_cooloff[coin] = datetime.now() - timedelta(minutes=TIME_DIFFERENCE)

            # Solo incluir monedas como volatiles si no se ha recogido ya en el último TIME_DIFFERENCE minutos
            if datetime.now() >= volatility_cooloff[coin] + timedelta(minutes=TIME_DIFFERENCE):
                volatility_cooloff[coin] = datetime.now()

                if len(coins_bought) + len(volatile_coins) < MAX_COINS or MAX_COINS == 0:
                    volatile_coins[coin] = round(threshold_check, 3)
                    print(f'{coin} ha ganado {volatile_coins[coin]}% en los últimos {TIME_DIFFERENCE} minutos, calculando volumen en {PAIR_WITH}')
                else:
                    print(f'{txcolors.WARNING}{coin} ha ganado {round(threshold_check, 3)}% en los ultimos {TIME_DIFFERENCE} minutos, pero tines la cantidad máxima de monedas{txcolors.DEFAULT}')
        elif threshold_check < CHANGE_IN_PRICE:
            coins_down += 1

        else:
            coins_unchanged += 1

    # Aqui va nuevo codigo para señales externas
    externals = external_signals()
    exnumber = 0

    for excoin in externals:
        if excoin not in volatile_coins and excoin not in coins_bought and (len(coins_bought) + exnumber + len(volatile_coins)) < MAX_COINS:
            volatile_coins[excoin] = 1
            exnumber += 1
            print(f'Señal externa recibida en {excoin}, calculando volumen en {PAIR_WITH}')

    return volatile_coins, len(volatile_coins), historical_prices[hsp_head]

def external_signals():
    external_list = {}
    signals = {}

    # Verifica el directorio y carga los archivos de los pares en external_list
    signals = glob.glob("signals/*.exs")
    for filename in signals:
        for line in open(filename):
            symbol = line.strip()
            external_list[symbol] = symbol
        try:
            os.remove(filename)
        except:
            if DEBUG: print(f'{txcolors.WARNING}No se pudo eliminar el archivo de señales externa{txcolors.DEFAULT}')

    return external_list

def pause_bot():
    '''Pausa el script cuando los indicadores externos detectan una tendencia bajista en el mercado'''
    global bot_paused, session_profit, hsp_head
    # Empieza a contar cuánto tiempo ha estado en pausa el bot
    start_time = time.perf_counter()

    while os.path.isfile('signals/paused.exc'):

        if bot_paused == False:
            print(f'{txcolors.WARNING}Pausando compras debido a cambio en las condiciones del mercado, stop loss y take profit continuarán trabajando...{txcolors.DEFAULT}')
            bot_paused = True

        # La función de vender necesita trabajar incluso mientras este pausado
        coins_sold = sell_coins()
        remove_from_portfolio(coins_sold)
        get_price(add_to_historical=True)

        # Pausando aqui
        if hsp_head == 1: print(f'Pausado... Beneficio de la Sesion: {session_profit:.2f}% Est: ${(QUANTITY * session_profit)/100:.2f}')
        time.sleep((TIME_DIFFERENCE * 60) / RECHECK_INTERVAL)
        
    else:
        # Deja de contar el tiempo pausado
        stop_time = time.perf_counter()
        time_elapsed = timedelta(seconds=int(stop_time-start_time))
        
        # Arreglar para que solo aparezca solo una vez despues de haber reanudado el bot
        # Resume el bot y pone el pause_bot en False
        # if bot_paused == True:
        #     print(f'{txcolors.WARNING}Reanudación de la compra debido a cambios en las condiciones del mercado, tiempo total detenido: {time_elapsed}{txcolors.DEFAULT}')
        #     bot_paused == False

    return

def convert_volume():
    '''Convierte el volumen dado en QUANTITY de USDT al volumen de cada moneda'''
    global volatile_coins
    volatile_coins, number_of_coins, last_price = wait_for_price()
    lot_size = {}
    volume = {}

    for coin in volatile_coins:
        # Encuentra el step size correcto para cada moneda
        # Precisión máxima para BTC por ejemplo es de 6 puntos decimales
        # Mientras que XRP es de solo 1
        try:
            info = client.get_symbol_info(coin)
            step_size = info['filters'][2]['stepSize']
            lot_size[coin] = step_size.index('1') - 1 # Encuentra el 1 para encontrar cuantos pasos son

            if lot_size[coin] < 0:
                lot_size[coin] = 0

        except:
            pass

        # Calcula el volumen en moneda de QUANTITY en USDT (default)
        volume[coin] = float(QUANTITY / float(last_price[coin]['price']))

        # Define el volumen con el correcto step size
        if coin not in lot_size:
            volume[coin] = float('{:.1f}'.format(volume[coin])) # .1f un digito de precision número flotante
        else:
            # si el tamaño del lote tiene 0 punto decimal, hacer el volumen un entero
            if lot_size[coin] == 0:
                volume[coin] = int(volume[coin])
            else:
                volume[coin] = float('{:.{}f}'.format(volume[coin], lot_size[coin]))

    return volume, last_price

def buy():
    '''Coloca ordenes de compra de mercado para cada moneda volatil encontrada'''

    volume, last_price = convert_volume()
    orders = {}

    for coin in volume:
        # Sólo compra si no hay trades activos de la moneda
        if coin not in coins_bought:
            print(f'{txcolors.BUY}Preparando para comprar {volume[coin]} {coin}{txcolors.DEFAULT}')

            if TEST_MODE:
                orders[coin] = [{
                    'symbol': coin,
                    'orderId': 0,
                    'time': datetime.now().timestamp()
                }]

                # Log trade
                if LOG_TRADES:
                    write_log(f"Buy: {volume[coin]} {coin} - {last_price[coin]['price']}")
                continue

                # Crea orden de prueba antes de enviar una orden real
                test_order = client.create_test_order(symbol=coin, side='BUY', type='MARKET', quantity=volume[coin])

            # Intenta crear una orden real si la orden de prueba no genero una excepción
            try:
                buy_limit = client.create_order(
                    symbol=coin, 
                    side='BUY', 
                    type='MARKET', 
                    quantity=volume[coin]
                )

            # Lanza error aqui en caso de que no se pueda colocar la posición
            except Exception as e:
                print(e)

            # Corre el bloque else si la posición  ha sido colocada y devuelto la información del pedido
            else:
                orders[coin] = client.get_all_orders(symbol=coin, limit=1)

                # Binance algunas veces retorna una lista vacia, el codigo esperará aqui hasta que binance retorne la orden
                while orders[coin] == []:
                    print('Binance esta siendo lento en retornar la orden, llamando a la API otravez...')

                    orders[coin] = client.get_all_orders(symbol=coin, limit=1)
                    time.sleep(1)

                else:
                    print('Orden devuelta, guardando orden en el archivo')

                    # Log trade
                    if LOG_TRADES:
                        write_log(f"Compra: {volume[coin]} {coin} - {last_price[coin]['price']}")

        else:
            print(f'Señal detectada, pero ya hay un trade activo de {coin}')

    return orders, last_price, volume

def sell_coins():
    '''Vende las monedas que han alcanzado el umbral de STOP LOSS o el TAKE PROFIT'''

    global hsp_head, session_profit

    last_price = get_price(add_to_historical=False)
    min_notional = get_info()
    coins_sold = {}

    for coin in list(coins_bought):
        LastPrice = float(last_price[coin]['price'])
        BuyPrice = float(coins_bought[coin]['bought_at'])
        PriceChange = float(((LastPrice - BuyPrice) / BuyPrice) * 100)

        # Define el STOP LOSS y TAKE PROFIT
        TP = BuyPrice + (BuyPrice * float(coins_bought[coin]['take_profit'])) / 100
        SL = BuyPrice + (BuyPrice * float(coins_bought[coin]['stop_loss'])) / 100
        # print(f"{coin}: {TP} {SL}")

        # Revisa que el precio este sobre el TAKE PROFIT y reajusta el SL y TP en consecuencia si se utiliza el trailing stop
        if LastPrice > TP or LastPrice < SL and USE_TRAILING_STOP_LOSS:
            # Incrementa TP por TRAILING_TAKE_PROFIT (esencialmente la próxima vez para reajustar SL)
            coins_bought[coin]['take_profit'] = PriceChange + TRAILING_TAKE_PROFIT
            coins_bought[coin]['stop_loss'] = coins_bought[coin]['take_profit'] - TRAILING_STOP_LOSS

            if DEBUG: 
                print(f"{coin} TP alcanzado, ajustando TP {coins_bought[coin]['take_profit']:.2f}% y SL {coins_bought[coin]['stop_loss']:.2f}% de acuerdo con el beneficio asegurado")

            if LastPrice <= SL:
                print(f"{txcolors.SELL_PROFIT if PriceChange >= 0.15 else txcolors.SELL_LOSS}TP or SL alcanzado, vendiendo {coins_bought[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} : {PriceChange-(TRADING_FEE*2):.2F}% Est: ${(QUANTITY*(PriceChange-(TRADING_FEE*2))/100):.2f}{txcolors.DEFAULT}")
                try:
                    sell_coins_limit = client.create_order(
                        symbol=coin,
                        side='SELL', 
                        timeInForce='GTC', 
                        type='TAKE_PROFIT_LIMIT', 
                        quantity=coins_bought[coin]['volume'], 
                        stopPrice=round(LastPrice - ((PriceChange - TRAILING_TAKE_PROFIT)/100) * LastPrice, 2), 
                        price=round(LastPrice - ((PriceChange - TRAILING_TAKE_PROFIT)/100) * LastPrice, 2)
                    )
                except BinanceAPIException as e:
                    if e.code == -1013:
                        print(f"El total debe ser mayor a {min_notional[coin]}")
                        exit()

                except Exception as e:
                    print(e)

                else:
                    coins_sold[coin] = coins_bought[coin]

                    volatility_cooloff[coin] = datetime.now()

                    if LOG_TRADES:
                        profit = ((LastPrice - BuyPrice) * coins_sold[coin]['volume']) * (1-(TRADING_FEE*2)) # ajusta la tarifa del trade aqui
                        write_log(f"Vender: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Ganancia: {profit:.2f} {PriceChange-(TRADING_FEE*2):.2f}%")
                        session_profit = session_profit + (PriceChange-(TRADING_FEE*2))

                continue
        # Revisa que el precio este por debajo del stop loss o por encima del take profit (si el trailing stop loss no se usa) y vender si este es el caso
        if LastPrice > TP or LastPrice < SL and not USE_TRAILING_STOP_LOSS:
            print(f"{txcolors.SELL_PROFIT if PriceChange >= 0.15 else txcolors.SELL_LOSS}TP or SL alcanzado, vendiendo {coins_bought[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} : {PriceChange-(TRADING_FEE*2):.2F}% Est: ${(QUANTITY*(PriceChange-(TRADING_FEE*2)))/100:.2f}{txcolors.DEFAULT}")

            # Intenta crear una orden real
            try:
                sell_coins_limit = client.create_order(
                    symbol=coin, 
                    side='SELL', 
                    type='MARKET', 
                    quantity=coins_bought[coin]['volume']
                )

            # Lanza error aqui en caso de que no se pueda colocar la posición
            except Exception as e:
                print(e)

            except BinanceAPIException as e:
                    if e.code == -1013:
                        print("El total debe ser mayor a 10")
                        exit()
            # Ejecuta el bloque else si se ha vendido la moneda y crea un diccionario para cada moneda vendida
            else:
                coins_sold[coin] = coins_bought[coin]

                # Evita que el sistema compre esta moneda durante los próximos TIME_DIFFERENCE minutos
                volatility_cooloff[coin] = datetime.now()

                # Registro de trade
                if LOG_TRADES:
                    profit = ((LastPrice - BuyPrice) * coins_sold[coin]['volume']) * (1-(TRADING_FEE*2)) # ajusta la tarifa del trade aqui
                    write_log(f"Vender: {coins_sold[coin]['volume']} {coin} - {BuyPrice} - {LastPrice} Ganancia: {profit:.2f} {PriceChange-(TRADING_FEE*2):.2f}%")
                    session_profit = session_profit + (PriceChange-(TRADING_FEE*2))
            continue

        # Ninguna accion; imprimir una vez cada TIME_DIFFERENCE
        if hsp_head == 1:
            if len(coins_bought) > 0:
                print(f'TP or SL no ha sido alcanzado todavia, sin vender {coin} por ahora {BuyPrice} - {LastPrice} : {txcolors.SELL_PROFIT if PriceChange >=0.15 else txcolors.SELL_LOSS}{PriceChange-(TRADING_FEE*2):.2f}% Est: ${(QUANTITY*(PriceChange-(TRADING_FEE*2)))/100:.2f}{txcolors.DEFAULT}')
    
    if hsp_head == 1 and len(coins_bought) == 0: print(f'No holding ninguna moneda')

    return coins_sold

def update_portfolio(orders, last_price, volume):
    '''Agrega cada moneda comprada a nuestro portafolio para rastrear/vender más tarde'''
    if DEBUG: print(orders)

    for coin in orders:
        coins_bought[coin] = {
            'symbol': orders[coin][0]['symbol'],
            'orderid': orders[coin][0]['orderId'],
            'timestamp': orders[coin][0]['time'],
            'bought_at': last_price[coin]['price'],
            'volume': volume[coin],
            'stop_loss': -STOP_LOSS,
            'take_profit': TAKE_PROFIT
        }

        # Guarda las monedas en un archivo json en el mismo directorio
        with open(coins_bought_file_path, 'w') as file:
            json.dump(coins_bought, file, indent=4)

        print(f'Orden con id {orders[coin][0]["orderId"]} colocado y guardado en el archivo')

def remove_from_portfolio(coins_sold):
    '''Remover monedas vendidas debido al SL o TP del portafolio'''
    for coin in coins_sold:
        coins_bought.pop(coin)

    with open(coins_bought_file_path, 'w') as file:
        json.dump(coins_bought, file, indent=4)

def write_log(logline):
    timestamp = datetime.now().strftime("%d/%m %H:%M:%S")
    with open(LOG_FILE, 'a+') as f:
        f.write(timestamp + ' ' + logline + '\n')

if __name__ == '__main__':
    # Cargar argumentos y luego analizar la configuración
    args = parse_args()
    mymodule = {}

    # Establecer a False al comienzo
    global bot_paused
    bot_paused = False

    DEFAULT_CONFIG_FILE = 'C:/Users/engel/Documents/Programar/Python/bot_binance/configs/config.yml'
    DEFAULT_CREDS_FILE = 'C:/Users/engel/Documents/Programar/Python/bot_binance/configs/test.yml'

    config_file = args.config if args.config else DEFAULT_CONFIG_FILE
    creds_file = args.creds if args.creds else DEFAULT_CREDS_FILE
    parsed_config = load_config(config_file)
    parsed_creds = load_config(creds_file)

    # Predeterminado sin depurar
    DEBUG = False

    # Cargar variables del sistema
    TEST_MODE = parsed_config['script_options']['TEST_MODE']
    LOG_TRADES = parsed_config['script_options'].get('LOG_TRADES')
    LOG_FILE = parsed_config['script_options'].get('LOG_FILE')
    DEBUG_SETTING = parsed_config['script_options'].get('DEBUG')


    # Cargar variables de trading
    PAIR_WITH = parsed_config['trading_options']['PAIR_WITH']
    CUSTOM_LIST = parsed_config['trading_options']['CUSTOM_LIST']
    SIGNALLING_MODULES = parsed_config['trading_options']['SIGNALLING_MODULES']
    TICKERS_LIST = parsed_config['trading_options']['TICKERS_LIST']
    FIATS = parsed_config['trading_options']['FIATS']
    RECHECK_INTERVAL = parsed_config['trading_options']['RECHECK_INTERVAL']
    TIME_DIFFERENCE = parsed_config['trading_options']['TIME_DIFFERENCE']
    QUANTITY = parsed_config['trading_options']['QUANTITY']
    CHANGE_IN_PRICE = parsed_config['trading_options']['CHANGE_IN_PRICE']
    MAX_COINS = parsed_config['trading_options']['MAX_COINS']
    USE_TRAILING_STOP_LOSS = parsed_config['trading_options']['USE_TRAILING_STOP_LOSS']
    TRAILING_TAKE_PROFIT = parsed_config['trading_options']['TRAILING_TAKE_PROFIT']
    TRAILING_STOP_LOSS = parsed_config['trading_options']['TRAILING_STOP_LOSS']
    STOP_LOSS = parsed_config['trading_options']['STOP_LOSS']
    TAKE_PROFIT = parsed_config['trading_options']['TAKE_PROFIT']
    TRADING_FEE = parsed_config['trading_options']['TRADING_FEE']
    if DEBUG_SETTING or args.debug:
        DEBUG = True

    if DEBUG:
        print(f'Configuración cargada a continuación\n{json.dumps(parsed_config, indent=4)}')
        print(f'Tus credenciales han sido cargadas desde {creds_file}')

    # Usar Lista personalizada de simbolos si CUSTOM_LIST esta configurado en True
    if CUSTOM_LIST:
        tickers_full = [line.strip() for line in open(TICKERS_LIST)]
        tickers_test = [line.strip() for line in open('tickers_testnet.txt')]
        tickers = list(set(tickers_full) & set(tickers_test))

    # Intentar cargar todas las monedas compradas por el bot si el archivo existe y si no esta vacio
    coins_bought = {}

    #  Cargar credenciales para el entorno correcto
    acces_key, secret_key = load_correct_creds(parsed_creds)

    # Aunteticarse con el cliente
    client = Client(acces_key, secret_key)

    # Ruta para el archivo de coins_bought
    coins_bought_file_path = 'coins_bought.json' # Revisar mas adelante si se puede colocar con un else en el statmant if

    # Ventana móvil de precios; cola ciclica
    historical_prices = [None] * (TIME_DIFFERENCE * RECHECK_INTERVAL)
    hsp_head = -1

    # Previene incluir una moneda en volatile_coins si ya apareció alli hace menos de TIME_DIFFERENCE minutos
    volatility_cooloff = {}

    if TEST_MODE:
        # La API URL necesita ser manualmente cambiada in la libreria para que funcione en la TESTNET
        client.API_URL = 'https://testnet.binance.vision/api'
        coins_bought_file_path = 'test_' + coins_bought_file_path
    else:
        print('ADVERTENCIA: Usted esta usando la Mainnet y con Fondos Reales. Esperando 30 segundos como una medida de seguridad')
        time.sleep(30)

    api_ready, msg = test_api_key(client, BinanceAPIException)
    if api_ready is not True:
        exit(f'{txcolors.SELL_LOSS}{msg}{txcolors.DEFAULT}')

    if not TEST_MODE:
        if not args.notimeout: # si no se especificó notimeout saltar esto (Rápido para pruebas de desarrollo)
            print('Advertencia: Estás usando la Mainnet y fondos reales. Esperando 30 segundos como una medida de seguridad')
            time.sleep(30)
        

    # Si esta guardado el archivo coins_bought y si no esta vacio entonces cargarlo
    if os.path.isfile(coins_bought_file_path) and os.stat(coins_bought_file_path).st_size!= 0:
        with open(coins_bought_file_path) as file:
            coins_bought = json.load(file)

    signals = glob.glob("signals/*.exs")
    for filename in signals:
        for lin in open(filename):
            try:
                os.remove(filename)
            except:
                if DEBUG: print(f'{txcolors.WARNING}No pudo remover el archivo de señales externo {filename}{txcolors.DEFAULT}')

    if os.path.isfile("signals/paused.exc"):
        try:
            os.remove("signals/paused.exc")
        except:
            if DEBUG: print(f'{txcolors.WARNING}No pudo remover el archivo de señales externo {filename}{txcolors.DEFAULT}')

    # Cargar módulos de señales
    try:
        if len(SIGNALLING_MODULES) > 0:
            for module in SIGNALLING_MODULES:
                print(f'Comenzando {module}')
                mymodule[module] = importlib.import_module(module)
                t = threading.Thread(target=mymodule[module].do_work, args=())
                t.deamon = True
                t.start()
                time.sleep(2)
        else:
            print(f'No hay modulos para cargar {SIGNALLING_MODULES}')
    except Exception as e:
        print(e)
    
    print('Presiona Ctrl-C para detener el BOT')

    get_price()
    READ_TIMEOUT_COUNT = 0
    CONNECTION_ERROR_COUNT = 0
    while True:
        try:
            orders, last_price, volume = buy()
            update_portfolio(orders, last_price, volume)
            coins_sold = sell_coins()
            remove_from_portfolio(coins_sold)
        except ReadTimeout as rt:
            READ_TIMEOUT_COUNT += 1
            print(f'{txcolors.WARNING}Recibimos un error de tiempo de espera de Binance. Ejecutando nuevamente... Contador actual: {READ_TIMEOUT_COUNT}\n{rt}{txcolors.DEFAULT}')
            time.sleep(2)
        except ConnectionError as ce:
            CONNECTION_ERROR_COUNT += 1
            print(f'{txcolors.WARNING}Recibimos un error de tiempo de espera de Binance. Ejecutando nuevamente... Contador actual: {CONNECTION_ERROR_COUNT}\n{ce}{txcolors.DEFAULT}')
            time.sleep(2)
        except socket.gaierror as ge:
            print(f"Este es un error de gaierror")
            print(ge)
            time.sleep(2)