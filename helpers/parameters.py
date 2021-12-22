import yaml
import argparse

def load_config(file):
    try:
        with open(file) as file:
            return yaml.load(file, Loader=yaml.FullLoader)
    except FileNotFoundError as fe:
        exit(f'No pudo encontrar {file}')
    except Exception as e:
        exit(f'Encontró una exepcion...\n{e}')

def parse_args():
    x = argparse.ArgumentParser()
    x.add_argument('--debug', '-d', help="Registro adicional", action='store_true') #Store_true: si la opción es especificada, se asigna True
    x.add_argument('--config', '-c', help="Ruta al archivo config.yml")
    x.add_argument('--creds', '-u', help="Ruta al archivo creds")
    x.add_argument('--notimeout', help="No use el timeout en prod", action="store_true")
    return x.parse_args()


