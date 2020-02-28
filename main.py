from concurrent.futures import ThreadPoolExecutor as PoolExecutor
import requests
import ssl
import json
import datetime
import time
import logging
import socket
import yaml


def read_config():
    global config
    try:
        with open('config.yml') as file:
            try:
                config = yaml.load(file, Loader=yaml.FullLoader)
            except yaml.YAMLError as yaml_err:
                print(yaml_err)
                exit()
            except KeyError as key_err:
                print(key_err)
                exit()
    except FileNotFoundError as file_err:
        print(file_err)
        exit()


def get_config_value(key, param):
    try:
        config_value = config[key][param]
        return config_value
    except KeyError as key_err:
        print(key_err)
        exit()


def log_config():
    log_enable = get_config_value('log', 'enable')
    log_level = get_config_value('log', 'level')
    log_file = get_config_value('log', 'log_file')
    log_format = get_config_value('log', 'format')
    log_datefmt = get_config_value('log', 'datefmt')
    if log_enable:
        logging.basicConfig(
            filename=log_file,
            level=log_level,
            format=log_format,
            datefmt=log_datefmt
        )


def error_text_helper(service, error):
    dt = str(datetime.datetime.now().strftime('%d.%m.%Y %H:%M:%S'))
    return f'{dt} {service} Down\n Error: {error}'


def slack_users_id_to_str(users):
    return ' '.join([f'<@{user}>' for user in users if user is not None]) \
        if users is not None else ''


def send_alert(text):
    slack_webhook_url = get_config_value('slack', 'webhook_url')
    slack_channel = get_config_value('slack', 'channel')
    slack_app_name = get_config_value('slack', 'app_name')
    slack_app_icon = get_config_value('slack', 'app_icon')
    slack_users = get_config_value('slack', 'users')
    alert_text = f'{slack_users_id_to_str(slack_users)} {text}'
    data = ({
                'text': alert_text,
                'icon_emoji': slack_app_icon,
                'channel': slack_channel,
                'username': slack_app_name
            })
    try:
        requests.post(slack_webhook_url, json=data)
    except:
        pass


def check_server(target):
    server_name = target['name']
    server_ip = target['server']
    server_port = target['port']
    timeout = target['timeout_check_sec']
    logging.info(
        f'Call check_server with params: '
        f'server_name: {server_name}, server_ip: {server_ip}, '
        f'server_port: {server_port}, timeout: {timeout}')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex((server_ip, server_port))
    sock.close()
    if result == 0:
        logging.info(
            'Call check_server Result: OK; params: '
            f'server_name: {server_name}, server_ip: {server_ip}, '
            f'server_port: {server_port}, timeout: {timeout}')
    else:
        logging.error(f'Unable to connect {server_name}')
        error_text = error_text_helper(
            server_name, f'{server_ip}:{server_port} connection timeout')
        send_alert(error_text)


def check_api(target):
    api_name = target['name']
    api_url = target['url']
    api_payload = target['payload']
    try:
        logging.info(
            f'Call check_api with params: '
            f'api_name: {api_name}, api_url: {api_url}, '
            f'api_payload: {api_payload}')
        request = requests.post(api_url, json=api_payload)
        logging.info('Response: {}'.format(request.text.replace('\r\n', '')))
    except:
        logging.error(f'Unable to connect {api_url}')
        return
    if request.status_code != 200:
        logging.error('Response: {}'.format(request.text.replace('\r\n', '')))
        error_text = error_text_helper(api_name, request.status_code)
        send_alert(error_text)
    else:
        try:
            json.loads(request.text)
        except:
            logging.error(
                'Response: {}'.format(request.text.replace('\r\n', '')))
            error_text = error_text_helper(api_name, request.text)
            send_alert(error_text)


def check_targets(target):
    target_type = target['type']
    target_interval_check_sec = target['interval_check_sec']
    while True:
        if target_type == 'api':
            check_api(target)
        if target_type == 'server':
            check_server(target)
        time.sleep(target_interval_check_sec)


def main():
    read_config()
    log_config()
    targets = config['targets'].values()
    targets_count = len(targets)
    with PoolExecutor(max_workers=targets_count) as executor:
        for _ in executor.map(check_targets, targets):
            pass


if __name__ == "__main__":
    main()
