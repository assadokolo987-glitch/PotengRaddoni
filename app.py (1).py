import os
import json
import re
import urllib.request
import urllib.parse
import uuid
import sqlite3
import subprocess
import tempfile
from flask import Flask, request, render_template_string, abort, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# ========== إعدادات قاعدة البيانات ==========
DB_FILE = "bans.db"
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS banned_ips (ip TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()
init_db()

def is_ip_banned(ip):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT 1 FROM banned_ips WHERE ip=?", (ip,))
    result = c.fetchone()
    conn.close()
    return result is not None

def ban_ip(ip):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT OR IGNORE INTO banned_ips (ip) VALUES (?)", (ip,))
        conn.commit()
    except: pass
    conn.close()

# ========== إعدادات الحماية ==========
limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"], storage_uri="memory://")
users_db = {}

def is_vpn_or_proxy(ip):
    if ip.startswith("127.") or ip.startswith("192.168.") or ip.startswith("10."):
        return False
    try:
        req = urllib.request.urlopen(f"http://ip-api.com/json/{ip}?fields=proxy,hosting", timeout=3)
        data = json.loads(req.read().decode())
        return data.get("proxy", False) or data.get("hosting", False)
    except: return False

MAIN_BOT_TOKEN = "8986771864:AAEnQd4sjPpUxi7opLef5LikkNFDmnizs7c"
MAIN_CHAT_ID = "6314187699"

# ========== قوالب HTML ==========
HTML_INDEX = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Poteng Raddoni</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; text-align: center; padding: 50px; margin: 0; }
        .box { background: #1e293b; padding: 30px; border-radius: 10px; display: inline-block; width: 100%; max-width: 500px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h1 { color: #38bdf8; margin-bottom: 5px; }
        input { width: 100%; padding: 12px; margin: 10px 0; border-radius: 5px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #38bdf8; color: #0f172a; font-weight: bold; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 10px;}
        button:hover { background: #0ea5e9; }
        .link-box { background: #334155; padding: 15px; border-radius: 5px; margin-top: 20px; word-break: break-all; text-align: left; direction: ltr; }
        .footer { margin-top: 20px; font-size: 12px; color: #94a3b8; }
        .footer a { color: #38bdf8; text-decoration: none; }
        .nav-links { margin-top: 20px; }
        .nav-links a { display: inline-block; margin: 0 10px; color: #38bdf8; text-decoration: none; border-bottom: 1px dashed #38bdf8; }
        
        /* Consent Overlay */
        #consent-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0, 0, 0, 0.85); display: none; justify-content: center; align-items: center; z-index: 10000; backdrop-filter: blur(5px); }
        .consent-box { background: #1e293b; color: white; padding: 30px; border-radius: 10px; max-width: 600px; width: 90%; text-align: right; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; max-height: 90vh; overflow-y: auto; }
        .consent-box h2 { margin-top: 0; color: #38bdf8; font-size: 22px; border-bottom: 1px solid #334155; padding-bottom: 10px; }
        .consent-box p { font-size: 14px; line-height: 1.8; color: #cbd5e1; }
        .consent-box a { color: #38bdf8; text-decoration: underline; }
        .consent-buttons { display: flex; gap: 10px; margin-top: 20px; justify-content: flex-end; }
        .consent-buttons button { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 14px; width: auto;}
        .btn-accept { background: #38bdf8; color: #0f172a; }
        .btn-accept:hover { background: #0ea5e9; }
        .btn-reject { background: #ef4444; color: white; }
        .btn-reject:hover { background: #dc2626; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Poteng Raddoni</h1>
        <p style="color: #94a3b8; font-size: 14px; margin-bottom: 20px;">احصل على إشعارات فورية عند دخول الزوار لموقعك.</p>
        
        {% if generated_link %}
            <div style="background: #065f46; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                ✅ تم إنشاء الرابط بنجاح:
                <div class="link-box">{{ generated_link }}</div>
            </div>
        {% endif %}

        <form method="POST" action="/generate">
            <input type="text" name="token" placeholder="Bot Token" required>
            <input type="text" name="chat_id" placeholder="Chat ID" required>
            <button type="submit">توليد رابط التتبع</button>
        </form>
        
        <div class="nav-links">
            <a href="/link-site">🔗 ربط موقعك بالمنصة</a>
            <a href="/compiler">💻 محرر بايثون</a>
        </div>

        <div class="footer">باستخدامك الموقع، أنت توافق على <a href="/privacy" target="_blank">اتفاقية الخدمة وسياسة الخصوصية</a>.</div>
    </div>

    <!-- Consent Overlay -->
    <div id="consent-overlay">
        <div class="consent-box">
            <h2>مرحباً بك في Poteng Raddoni 🚀</h2>
            <p style="color: #38bdf8; font-weight: bold; margin-bottom: 15px;">للحصول على أفضل تجربة، نرجو منك الموافقة على الشروط التالية:</p>
            <div style="background: #0f172a; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #334155;">
                <h3 style="color: #10b981; margin-top: 0; font-size: 16px;">🌟 ماذا ستستفيد عند الموافقة؟</h3>
                <ul style="color: #cbd5e1; font-size: 14px; padding-right: 20px; margin-bottom: 0; line-height: 1.8;">
                    <li><strong>حماية متقدمة:</strong> تخصيص تجربتك وحماية حسابك من محاولات الاختراق.</li>
                    <li><strong>تحليلات دقيقة:</strong> مساعدتنا في تقديم إحصائيات دقيقة ومجانية لجميع المستخدمين.</li>
                    <li><strong>تجربة سلسة:</strong> تذكر خياراتك (مثل اللغة والإعدادات) دون الحاجة لإعادة ضبطها في كل زيارة.</li>
                    <li><strong>دعم فني أسرع:</strong> فهم احتياجاتك التقنية لتطوير الخدمة بشكل أفضل.</li>
                </ul>
            </div>
            <p style="font-size: 13px; color: #94a3b8;">
                <strong>ملاحظة قانونية:</strong> نحن نجمع فقط البيانات التقنية (IP، نوع الجهاز، دقة الشاشة) لأغراض إحصائية. 
                <strong>نحن لا نجمع كلمات المرور أو بياناتك البنكية أبداً.</strong> 
                يمكنك قراءة <a href="/privacy" target="_blank">اتفاقية الخدمة الكاملة</a>.
            </p>
            <div class="consent-buttons">
                <button class="btn-reject" onclick="rejectCookies()">لا شكراً</button>
                <button class="btn-accept" onclick="acceptCookies()">أوافق وأستفيد</button>
            </div>
        </div>
    </div>

    <script>
        document.addEventListener("DOMContentLoaded", function() {
            if (!localStorage.getItem('cookieConsent')) {
                document.getElementById('consent-overlay').style.display = 'flex';
            } else if (localStorage.getItem('cookieConsent') === 'true') {
                collectFingerprint();
            }
        });

        function acceptCookies() {
            localStorage.setItem('cookieConsent', 'true');
            document.getElementById('consent-overlay').style.display = 'none';
            collectFingerprint();
        }

        function rejectCookies() {
            localStorage.setItem('cookieConsent', 'false');
            document.getElementById('consent-overlay').style.display = 'none';
        }

        function collectFingerprint() {
            let fpData = {
                screen: window.screen.width + "x" + window.screen.height,
                colorDepth: window.screen.colorDepth,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                language: navigator.language,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                hardwareConcurrency: navigator.hardwareConcurrency || "Unknown"
            };
            fetch('/log_fingerprint', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fpData) });
        }
    </script>
</body>
</html>
"""

HTML_LINK_SITE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>ربط الموقع</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; text-align: center; padding: 50px; }
        .box { background: #1e293b; padding: 30px; border-radius: 10px; display: inline-block; width: 100%; max-width: 500px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); text-align: right;}
        h1 { color: #38bdf8; text-align: center;}
        label { font-size: 14px; color: #cbd5e1; margin-top: 10px; display: block;}
        input, textarea { width: 100%; padding: 12px; margin: 5px 0 15px 0; border-radius: 5px; border: 1px solid #334155; background: #0f172a; color: white; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #10b981; color: white; font-weight: bold; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #059669; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: #38bdf8; text-decoration: none; }
    </style>
</head>
<body>
    <div class="box">
        <h1>🔗 ربط موقعك بالمنصة</h1>
        <p style="text-align: center; color: #94a3b8; font-size: 14px;">سيتم إرسال طلب إلى الإدارة لمراجعة الموقع والموافقة عليه.</p>
        <form method="POST" action="/request_link">
            <label>رابط موقعك:</label>
            <input type="url" name="site_url" placeholder="https://example.com" required>
            
            <label>وصف الموقع / سبب الربط (إجباري):</label>
            <textarea name="description" rows="4" placeholder="اكتب وصفاً واضحاً لموقعك وسبب رغبتك في ربطه..." required></textarea>
            
            <button type="submit">إرسال طلب الربط</button>
        </form>
        <a href="/" class="back-link">العودة للرئيسية</a>
    </div>
</body>
</html>
"""

HTML_COMPILER = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>محرر بايثون - Poteng Raddoni</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: white; padding: 20px; margin: 0; }
        .container { max-width: 800px; margin: auto; background: #1e293b; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        h1 { color: #38bdf8; text-align: center; }
        textarea { width: 100%; height: 300px; background: #000; color: #00ff00; font-family: monospace; padding: 15px; border: 1px solid #334155; border-radius: 5px; box-sizing: border-box; resize: vertical; }
        .buttons { display: flex; gap: 10px; margin-top: 15px; }
        button { flex: 1; padding: 12px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; }
        .btn-run { background: #10b981; color: white; }
        .btn-run:hover { background: #059669; }
        .btn-download { background: #38bdf8; color: #0f172a; }
        .btn-download:hover { background: #0ea5e9; }
        .output-box { background: #000; color: #fff; padding: 15px; margin-top: 20px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; min-height: 100px; border: 1px solid #334155; }
        .back-link { display: block; text-align: center; margin-top: 20px; color: #38bdf8; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>💻 محرر بايثون</h1>
        <p style="text-align: center; color: #94a3b8; font-size: 14px;">اكتب كود بايثون، ونفذه، أو قم بتحميله كملف.</p>
        
        <form id="codeForm">
            <textarea id="codeArea" placeholder="# اكتب كود بايثون هنا...&#10;print('Hello, World!')"></textarea>
            <div class="buttons">
                <button type="button" class="btn-run" onclick="runCode()">▶️ تشغيل الكود</button>
                <button type="button" class="btn-download" onclick="downloadCode()">⬇️ تحميل كملف .py</button>
            </div>
        </form>
        
        <div class="output-box" id="output">النتيجة ستظهر هنا...</div>
        <a href="/" class="back-link">العودة للرئيسية</a>
    </div>

    <script>
        async function runCode() {
            const code = document.getElementById('codeArea').value;
            const outputDiv = document.getElementById('output');
            outputDiv.innerText = "جاري التشغيل...";

            try {
                const response = await fetch('/run_code', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ code: code })
                });
                const data = await response.json();
                
                if (data.error) {
                    outputDiv.style.color = '#ef4444';
                    outputDiv.innerText = "خطأ:\n" + data.error;
                } else {
                    outputDiv.style.color = '#00ff00';
                    outputDiv.innerText = data.output || "(لا يوجد مخرجات)";
                }
            } catch (e) {
                outputDiv.style.color = '#ef4444';
                outputDiv.innerText = "فشل الاتصال بالسيرفر.";
            }
        }

        function downloadCode() {
            const code = document.getElementById('codeArea').value;
            const blob = new Blob([code], { type: 'text/x-python' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'script.py';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>
"""

# ========== المسارات (Routes) ==========
@app.before_request
def check_ban_and_vpn():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if is_ip_banned(ip):
        abort(403, description="Your IP has been permanently banned.")
    if is_vpn_or_proxy(ip):
        ban_ip(ip)
        abort(403, description="VPN/Proxy usage detected. Your IP has been permanently banned.")

@app.route('/')
@limiter.limit("10 per minute")
def index():
    return render_template_string(HTML_INDEX)

@app.route('/link-site')
def link_site_page():
    return render_template_string(HTML_LINK_SITE)

@app.route('/compiler')
def compiler_page():
    return render_template_string(HTML_COMPILER)

@app.route('/request_link', methods=['POST'])
@limiter.limit("3 per minute")
def request_link():
    site_url = request.form.get('site_url', '').strip()
    description = request.form.get('description', '').strip()
    
    if not site_url or not description:
        abort(400)
        
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    
    msg = (f"🔗 طلب ربط موقع جديد:\n\n"
           f"🌐 الرابط: {site_url}\n"
           f"📝 الوصف: {description}\n"
           f"📍 IP الطالب: {ip}\n\n"
           f"للموافقة، يرجى التواصل مع صاحب الموقع أو قبول الطلب يدوياً.")
           
    url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/sendMessage"
    tg_data = urllib.parse.urlencode({"chat_id": MAIN_CHAT_ID, "text": msg}).encode("utf-8")
    
    try:
        urllib.request.urlopen(url, data=tg_data, timeout=5)
    except: pass

    return "<h2 style='text-align:center; font-family:sans-serif; margin-top:50px; color:green;'>✅ تم إرسال طلب الربط بنجاح! سيتم مراجعته قريباً.</h2><p style='text-align:center;'><a href='/'>العودة للرئيسية</a></p>"

@app.route('/privacy')
def privacy():
    return render_template_string(HTML_PRIVACY)

@app.route('/generate', methods=['POST'])
@limiter.limit("5 per minute")
def generate():
    token = request.form.get('token', '')
    chat_id = request.form.get('chat_id', '')

    if not re.match(r"^[0-9]+:[a-zA-Z0-9_-]+$", token):
        abort(400)
    if not re.match(r"^-?[0-9]+$", chat_id):
        abort(400)

    track_id = str(uuid.uuid4()).replace('-', '')[:12]
    users_db[track_id] = {"token": token, "chat_id": chat_id, "visits": 0}
    domain = request.host_url.rstrip('/')
    link = f"{domain}/track/{track_id}"
    return render_template_string(HTML_INDEX, generated_link=link)

@app.route('/track/<track_id>')
def track(track_id):
    if not re.match(r"^[a-zA-Z0-9]+$", track_id):
        abort(400)

    if track_id in users_db:
        user_data = users_db[track_id]
        user_data['visits'] += 1
        
        ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
        country = "Unknown"
        try:
            req = urllib.request.Request(f"http://ip-api.com/json/{ip}?fields=country", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                res = json.loads(response.read().decode())
                if res.get("country"): country = res.get("country")
        except: pass
        
        msg = f"🎉 نبض جديد!\n\n📍 الدولة: {country}\n📊 إجمالي الزوار: {user_data['visits']}"
        url = f"https://api.telegram.org/bot{user_data['token']}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": user_data['chat_id'], "text": msg}).encode("utf-8")
        
        try:
            tg_req = urllib.request.Request(url, data=data, method="POST")
            urllib.request.urlopen(tg_req, timeout=3)
        except: pass
            
    return b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b', 200, {'Content-Type': 'image/gif'}

@app.route('/log_fingerprint', methods=['POST'])
def log_fingerprint():
    data = request.get_json()
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    
    country = "Unknown"
    try:
        req = urllib.request.urlopen(f"http://ip-api.com/json/{ip}?fields=country", timeout=3)
        res = json.loads(req.read().decode())
        if res.get("country"): country = res.get("country")
    except: pass
    
    msg = (f"🔍 بصمة زائر جديدة:\n\n"
           f"🌐 IP: {ip}\n"
           f"📍 الدولة: {country}\n"
           f"🖥 الشاشة: {data.get('screen')}\n"
           f"🌍 المنطقة الزمنية: {data.get('timezone')}\n"
           f"🗣 اللغة: {data.get('language')}\n"
           f"📱 النظام: {data.get('platform')}\n"
           f"⚙️ المعالج (Threads): {data.get('hardwareConcurrency')}\n"
           f"💻 User-Agent: {data.get('userAgent')}")
           
    url = f"https://api.telegram.org/bot{MAIN_BOT_TOKEN}/sendMessage"
    tg_data = urllib.parse.urlencode({"chat_id": MAIN_CHAT_ID, "text": msg}).encode("utf-8")
    try:
        urllib.request.urlopen(url, data=tg_data, timeout=5)
    except: pass

    return jsonify({"status": "success"})

@app.route('/run_code', methods=['POST'])
@limiter.limit("5 per minute")
def run_code():
    data = request.get_json()
    code = data.get('code', '')
    if not code:
        return jsonify({"error": "No code provided"}), 400

    try:
        # كتابة الكود في ملف مؤقت وتنفيذه
        with tempfile.NamedTemporaryFile(delete=False, suffix='.py', mode='w', encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        # تنفيذ الكود باستخدام subprocess مع قيود الوقت (5 ثواني)
        result = subprocess.run(['python3', temp_file], capture_output=True, text=True, timeout=5)
        os.unlink(temp_file) # حذف الملف بعد التنفيذ

        if result.returncode != 0:
            return jsonify({"error": result.stderr})
        return jsonify({"output": result.stdout})
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Execution timed out (max 5 seconds)."})
    except Exception as e:
        return jsonify({"error": str(e)})

# صفحة سياسة الخصوصية
HTML_PRIVACY = """... (نفس محتوى سياسة الخصوصية السابق) ..."""

# معالجة الأخطاء
@app.errorhandler(400)
def bad_request(e): return "Bad Request", 400
@app.errorhandler(403)
def forbidden(e): return "Forbidden: Access Denied", 403
@app.errorhandler(404)
def not_found(e): return "Not Found", 404
@app.errorhandler(429)
def ratelimit_handler(e): return "Too Many Requests. Please try again later.", 429
@app.errorhandler(500)
def internal_error(e): return "Internal Server Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)