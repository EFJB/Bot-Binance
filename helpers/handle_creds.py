def load_correct_creds(creds):
    try:
        return creds['prod']['access_key'], creds['prod']['secret_key']
    except TypeError as te:
        message = 'Tus credenciales estan formateadas incorrectamente\n'
        message += f'TypeError:Exception:\n\t{str(te)}'
        exit(message)
    except Exception as e:
        message = 'Ups, parece que hiciste algo realmente malo. Se ha detectado una excepcion...\n'
        message += f'Exception:\n\t{str(e)}'
        exit(message)

def test_api_key(client, BinanceAPIException):
    """Comprueba si las API keys proporcionadas devuelven errores
    
    Argumentos:
        client (class): clase binance client
        BinanceAPIException (class): clase binance exceptions
        
    Retorna:
        bool | msg: true/false según el éxito, y mensaje"""

    try:
        client.get_account()
        return True, "API key validada exitosamente"
    except BinanceAPIException as e:
        if e.code in [-2015,-2014]:
            bad_key = "Tu API key no tiene el formato correcto..."
            america = "Si estás en América, tendrás que actualizar la config AMERICAN_USER: True"
            ip_b = "Si estableciste un bloqueo de IP en sus keys, asegúrese de que esta direccón IP esté permitida. Comprobar ipinfo.io/ip"
            msg = f"Tu API key es tambien incorrecta, IP bloqueada, o incorrecta tld/permisos...\n más probable: {bad_key}\n{america}\n{ip_b}"
        elif e.code == -2021:
            desc = "Asegurate de que tu OS esté sincronizado con la hora del servidor."
            msg = f"Timestamp para esta solicitud estaba en 1000ms por delante de la hora del servidor.\n{desc}"
        
        else:
            msg = "Se encontró un código de error de la API que no se detecto correctamente, abra el problema"
            msg += str(e)

        return False, msg

    except Exception as e:
        return False, f"Ocurrió una excepción de respaldo:\n{e}"