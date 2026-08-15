from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for, Response
import json
import os
import time
import threading
import webbrowser
import urllib.parse
import csv
import io
from datetime import datetime, timedelta

# PyAutoGUI ve Pyperclip kontrolleri
try:
    import pyautogui
    import pyperclip
    GUI_AUTOMATION_AVAILABLE = True
except ImportError:
    GUI_AUTOMATION_AVAILABLE = False

# PyCAW Ses Denetimi Kontrolü
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'zoom_admin_gizli_anahtar_999_v2')

ADMIN_USERNAME = "admin"
ESKI_SES_SEVIYESI = None
ESKI_MUTE_DURUMU = False

# Dosya okuma/yazma çakışmalarını önlemek için thread kilidi
FILE_LOCK = threading.Lock()

def veri_yukle(dosya):
    """JSON dosyasından veriyi güvenli şekilde okur."""
    with FILE_LOCK:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(script_dir, dosya)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[HATA] Veri yüklenemedi ({dosya}): {e}")
        return [] if "katilimlar" in dosya else {}

def veri_kaydet(dosya, data):
    """JSON dosyasına veriyi güvenli şekilde yazar."""
    with FILE_LOCK:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(script_dir, dosya)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[HATA] Veri kaydedilemedi ({dosya}): {e}")

def sistem_sesini_ayarla(fulle=True):
    """Sistem ses seviyesini ayarlar."""
    global ESKI_SES_SEVIYESI, ESKI_MUTE_DURUMU
    if not PYCAW_AVAILABLE:
        return
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        if fulle:
            if ESKI_SES_SEVIYESI is None:
                ESKI_SES_SEVIYESI = volume.GetMasterVolumeLevelScalar()
                ESKI_MUTE_DURUMU = volume.GetMute()
            
            volume.SetMute(0, None)
            volume.SetMasterVolumeLevelScalar(1.0, None)
        else:
            if ESKI_SES_SEVIYESI is not None:
                volume.SetMasterVolumeLevelScalar(ESKI_SES_SEVIYESI, None)
                volume.SetMute(ESKI_MUTE_DURUMU, None)
                ESKI_SES_SEVIYESI = None
    except Exception as e:
        print(f"[HATA] Ses ayarlanamadı: {e}")

def whatsapp_mesaj_gonder(telefon, mesaj):
    """WhatsApp Web üzerinden otomatik mesaj yönlendirmesi açar."""
    if not telefon:
        return
    temiz_tel = ''.join(filter(str.isdigit, str(telefon)))
    if not temiz_tel.startswith('90') and len(temiz_tel) == 10:
        temiz_tel = '90' + temiz_tel
    
    encoded_msg = urllib.parse.quote(mesaj)
    url = f"https://web.whatsapp.com/send?phone={temiz_tel}&text={encoded_msg}"
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"[HATA] WhatsApp açılamadı: {e}")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zoom Katılım & Takip Paneli PRO</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: #0f172a; color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
        .container { background-color: #1e293b; width: 100%; max-width: 1100px; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        .header { text-align: center; margin-bottom: 20px; border-bottom: 1px solid #334155; padding-bottom: 15px; }
        .header h1 { margin: 0; color: #38bdf8; font-size: 26px; }
        .clock { color: #94a3b8; font-size: 15px; margin-top: 6px; font-weight: bold; }
        
        .user-bar { display: flex; justify-content: space-between; align-items: center; background: #0f172a; padding: 12px 18px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #334155; }
        .user-info { font-size: 15px; color: #38bdf8; font-weight: bold; display: flex; align-items: center; gap: 8px; }
        .admin-badge { background-color: #ef4444; color: white; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
        .student-badge { background-color: #10b981; color: white; font-size: 11px; padding: 2px 6px; border-radius: 4px; }
        .nav-btns { display: flex; gap: 8px; }

        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }
        .stat-card { background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px; text-align: center; }
        .stat-card h3 { margin: 0; font-size: 24px; color: #38bdf8; }
        .stat-card p { margin: 4px 0 0 0; font-size: 12px; color: #94a3b8; text-transform: uppercase; font-weight: bold; }
        
        .search-bar { margin-bottom: 15px; }
        .search-input { width: 100%; padding: 12px; border-radius: 8px; background-color: #0f172a; border: 1px solid #334155; color: white; outline: none; font-size: 14px; }

        .tab-container { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #334155; padding-bottom: 10px; flex-wrap: wrap; }
        .tab-btn { background: #0f172a; border: 1px solid #334155; color: #94a3b8; padding: 10px 18px; border-radius: 8px; font-weight: bold; cursor: pointer; transition: 0.2s; }
        .tab-btn.active { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }

        .card-list { display: flex; flex-direction: column; gap: 14px; margin-bottom: 20px; }
        .kisi-card { background-color: #334155; border-radius: 12px; padding: 18px; display: flex; align-items: center; justify-content: space-between; border: 1px solid #475569; position: relative; transition: all 0.3s; }
        .kisi-card.alarm-active { border: 2px solid #ef4444; animation: pulse 1s infinite; background-color: #451a1a; }
        @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.8); } 70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); } 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } }

        .kisi-info h4 { margin: 0; font-size: 18px; color: #38bdf8; }
        .kisi-info .ogretmen-adi { font-size: 15px; color: #f8fafc; font-weight: 700; background: #0f172a; padding: 4px 8px; border-radius: 6px; display: inline-block; margin-top: 4px; }
        .kisi-info p { margin: 3px 0 0 0; font-size: 13px; color: #94a3b8; }
        .badge { background: #0f172a; border: 1px solid #475569; padding: 3px 8px; border-radius: 6px; color: #38bdf8; font-size: 11px; }
        
        .actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
        .btn { border: none; border-radius: 8px; padding: 8px 14px; font-weight: bold; cursor: pointer; transition: 0.2s; color: white; font-size: 13px; text-decoration: none; display: inline-flex; align-items: center; gap: 5px; }
        .btn-join { background-color: #2563eb; }
        .btn-join:hover { background-color: #1d4ed8; }
        .btn-copy { background-color: #64748b; }
        .btn-copy:hover { background-color: #475569; }
        .btn-edit { background-color: #d97706; }
        .btn-delete { background-color: #ef4444; }
        .btn-alarm { background-color: #dc2626; }
        .btn-alarm-off { background-color: #4b5563; }
        .btn-admin { background-color: #8b5cf6; }
        .btn-logout { background-color: #dc2626; }
        .btn-add { background-color: #10b981; width: 100%; padding: 12px; font-size: 15px; margin-top: 10px; justify-content: center; }
        .btn-chart { background-color: #06b6d4; }
        .btn-wa { background-color: #22c55e; }
        .btn-export { background-color: #059669; }

        .form-box { background: #0f172a; padding: 18px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #334155; }
        .form-row { display: flex; gap: 10px; margin-bottom: 10px; align-items: center; }
        input, select { width: 100%; background-color: #1e293b; border: 1px solid #475569; color: white; padding: 10px; border-radius: 8px; outline: none; }
        
        .log-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        .log-table th, .log-table td { border: 1px solid #334155; padding: 10px; text-align: left; }
        .log-table th { background-color: #0f172a; color: #38bdf8; }
        .log-table tr:nth-child(even) { background-color: #1e293b; }
        
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .online { background-color: #22c55e; box-shadow: 0 0 8px #22c55e; }
        .offline { background-color: #64748b; }

        .tag-devamsiz { background: #ef4444; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
        .tag-gec { background: #f59e0b; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }
        .tag-zamaninda { background: #10b981; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }

        .alarm-banner { display: none; position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #ef4444; color: white; padding: 16px 28px; border-radius: 12px; box-shadow: 0 10px 30px rgba(239, 68, 68, 0.6); z-index: 9999; font-weight: bold; font-size: 18px; align-items: center; gap: 12px; animation: bounce 0.8s infinite alternate; }
        @keyframes bounce { from { transform: translate(-50%, 0); } to { transform: translate(-50%, -10px); } }

        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.75); justify-content: center; align-items: center; z-index: 100; }
        .modal-content { background: #1e293b; border: 1px solid #475569; padding: 24px; border-radius: 16px; width: 90%; max-width: 550px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }

        #status { margin-top: 10px; text-align: center; font-weight: bold; font-size: 13px; min-height: 18px; }
        .login-box { width: 100%; max-width: 420px; }
    </style>
</head>
<body>

<div id="alarmBanner" class="alarm-banner">
    🚨 <span id="alarmBannerText">DERS ALARMI! DERSİN BAŞLAMASINA 5 DAKİKA KALDI! (10 sn)</span>
</div>

{% if not current_user %}
<div class="container login-box">
    <div class="header">
        <h1>🔐 Giriş Yap</h1>
        <p style="font-size: 13px; color: #94a3b8;">Lütfen kullanıcı adı ve şifrenizle giriş yapın.</p>
    </div>
    
    <form action="/login" method="POST">
        <input type="text" name="username" placeholder="Kullanıcı Adı" required style="margin-bottom:12px;">
        <input type="password" name="password" placeholder="Şifre" required style="margin-bottom:18px;">
        <button type="submit" class="btn btn-join" style="width:100%; padding:12px; justify-content: center;">Giriş Yap</button>
    </form>
</div>

{% else %}
<div class="container">
    <div class="header">
        <h1>🚀 Zoom Katılım & Öğrenci Takip Paneli PRO</h1>
        <div class="clock" id="liveClock">--:--:--</div>
    </div>

    <div class="user-bar">
        <span class="user-info">
            👤 {{ session.get('user_display', current_user.upper()) }}
            {% if is_admin %}
                <span class="admin-badge">ADMIN YÖNETİCİ</span>
            {% else %}
                <span class="student-badge">{{ user_sinif }} - {{ user_grup }}</span>
            {% endif %}
        </span>
        <div class="nav-btns">
            {% if is_admin %}
                <a href="#adminSection" class="btn btn-admin">⚙️ Admin Paneli</a>
            {% endif %}
            <a href="/logout" class="btn btn-logout">🚪 Çıkış Yap</a>
        </div>
    </div>

    {% if is_admin %}
    <div class="stats-grid">
        <div class="stat-card">
            <h3>{{ stats.toplam_ogrenci }}</h3>
            <p>Kayıtlı Öğrenci</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.online_ogrenci }}</h3>
            <p>Çevrimiçi Öğrenci</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.toplam_ders }}</h3>
            <p>Aktif Ders Programı</p>
        </div>
        <div class="stat-card">
            <h3>{{ stats.toplam_devamsizlik }}</h3>
            <p>Toplam Devamsızlık Kaydı</p>
        </div>
    </div>

    <div class="tab-container">
        <button class="tab-btn active" onclick="sekmeDegistir('hepsi', this)">🌐 Tüm Gruplar</button>
        <button class="tab-btn" onclick="sekmeDegistir('Dahiler', this)">🧠 Dahiler</button>
        <button class="tab-btn" onclick="sekmeDegistir('Efsaneler', this)">🔥 Efsaneler</button>
        <button class="tab-btn" onclick="sekmeDegistir('Şampiyonlar', this)">🏆 Şampiyonlar</button>
        <button class="tab-btn" onclick="sekmeDegistir('Hızlılar', this)">⚡ Hızlılar</button>
    </div>
    {% else %}
    <h3 style="color:#38bdf8; border-bottom: 2px solid #334155; padding-bottom: 10px; margin-top:0;">
        📌 Grubunuza Ait Aktif Dersler
    </h3>
    {% endif %}

    <div class="search-bar">
        <input type="text" id="kartAramaInput" class="search-input" placeholder="🔍 Ders adı, hoca adı veya grup ara..." onkeyup="kartFiltrele()">
    </div>

    <div class="card-list" id="cardList">
        {% set gosterilen_ders_sayisi = namespace(val=0) %}
        {% for kisi, bilgi in rehber.items() %}
            {% if is_admin or (bilgi.sinif == user_sinif and bilgi.grup == user_grup) %}
                {% set gosterilen_ders_sayisi.val = gosterilen_ders_sayisi.val + 1 %}
                <div id="card-{{ kisi }}" class="kisi-card ders-kart grup-{{ bilgi.grup }}" data-alarm="{{ bilgi.alarm }}" data-gun="{{ bilgi.gun }}" data-search="{{ bilgi.ders }} {{ bilgi.ogretmen }} {{ bilgi.grup }} {{ bilgi.sinif }}">
                    <div class="kisi-info">
                        <h4>
                            📘 {{ bilgi.ders|title }}
                            <span class="badge">{{ bilgi.sinif }} - {{ bilgi.grup }}</span>
                        </h4>
                        <div class="ogretmen-adi">👨‍🏫 {{ bilgi.ogretmen|title }}</div>
                        <p><b>Zoom ID:</b> {{ bilgi.id }}</p>
                        <p>⏰ <b>Gün:</b> {{ bilgi.gun|default('Her Gün') }} - <b>Saat:</b> {{ bilgi.alarm if bilgi.alarm else 'Ayar Yok' }} {% if bilgi.bitis_saati %}- {{ bilgi.bitis_saati }}{% endif %}</p>
                    </div>
                    <div class="actions">
                        <button type="button" class="btn btn-join" onclick="katil('{{ kisi }}')">🎥 Katıl</button>
                        <button type="button" class="btn btn-copy" title="ID ve Şifre Kopyala" onclick="bilgiKopyala('{{ bilgi.id }}', '{{ bilgi.sifre }}')">📋 Kopyala</button>
                        
                        {% if is_admin %}
                            <button type="button" class="btn {% if bilgi.manual_alarm %}btn-alarm-off{% else %}btn-alarm{% endif %}" 
                                    onclick="alarmTetikle('{{ kisi }}', {% if bilgi.manual_alarm %}false{% else %}true{% endif %})">
                                {% if bilgi.manual_alarm %}🔔 Alarmı Kapat{% else %}🔔 Alarm Ver{% endif %}
                            </button>
                            <button type="button" class="btn btn-edit" title="Düzenle" 
                                    onclick="duzenleModalAc('{{ kisi }}', '{{ bilgi.sinif }}', '{{ bilgi.grup }}', '{{ bilgi.ders }}', '{{ bilgi.ogretmen }}', '{{ bilgi.id }}', '{{ bilgi.sifre }}', '{{ bilgi.gun|default('Her Gün') }}', '{{ bilgi.alarm|default('') }}', '{{ bilgi.bitis_saati|default('') }}')">✏️</button>
                            <button type="button" class="btn btn-delete" title="Sil" onclick="sil('{{ kisi }}')">🗑️</button>
                        {% endif %}
                    </div>
                </div>
            {% endif %}
        {% endfor %}
    </div>

    {% if is_admin %}
    <div id="adminSection" style="margin-top: 35px; border-top: 2px dashed #334155; padding-top: 20px;">
        <div class="form-box" style="border-color: #10b981;">
            <h4 style="margin: 0 0 12px 0; color: #10b981;">👤 Admin Özel: Bireysel Öğrenci Hesabı Ekle</h4>
            <div class="form-row">
                <select id="ogrenci_sinif">
                    <option value="8. Sınıf" selected>8. Sınıf</option>
                    <option value="7. Sınıf">7. Sınıf</option>
                </select>

                <select id="ogrenci_grup">
                    <option value="Dahiler">Dahiler 🧠</option>
                    <option value="Efsaneler">Efsaneler 🔥</option>
                    <option value="Şampiyonlar">Şampiyonlar 🏆</option>
                    <option value="Hızlılar">Hızlılar ⚡</option>
                </select>
            </div>
            <div class="form-row">
                <input type="text" id="ogrenci_kullanici" placeholder="Öğrenci Kullanıcı Adı">
                <input type="password" id="ogrenci_sifre" placeholder="Öğrenci Şifresi">
                <input type="text" id="ogrenci_veli_tel" placeholder="Veli Tel (+905XXXXYYYY)">
            </div>
            <button type="button" class="btn btn-add" style="background-color:#10b981;" onclick="ogrenciEkle()">Öğrenciyi Kaydet</button>
        </div>

        <div class="form-box">
            <h4 style="margin: 0 0 12px 0; color: #38bdf8;">👥 Kayıtlı Öğrenci Yönetimi & Devamsızlık Grafikleri</h4>
            <table class="log-table">
                <thead>
                    <tr>
                        <th>Durum</th>
                        <th>Kullanıcı Adı</th>
                        <th>Sınıf / Grup</th>
                        <th>Veli Telefonu</th>
                        <th>Rapor & İşlem</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u_name, u_data in users.items() %}
                    {% if u_name != 'admin' %}
                    <tr class="ogrenci-row" data-grup="{{ u_data.grup }}">
                        <td>
                            {% if u_data.is_online %}
                                <span class="status-dot online"></span> <b style="color:#22c55e">Online</b>
                            {% else %}
                                <span class="status-dot offline"></span> <span style="color:#64748b">Offline</span>
                            {% endif %}
                        </td>
                        <td><b>{{ u_name.upper() }}</b></td>
                        <td><span class="badge" style="margin:0;">{{ u_data.sinif }} - {{ u_data.grup }}</span></td>
                        <td><code>{{ u_data.veli_telefon|default('Girilmedi') }}</code></td>
                        <td style="display:flex; gap:6px;">
                            <button class="btn btn-chart" style="padding: 5px 10px; font-size:12px;" onclick="grafikGoster('{{ u_name }}')">📊 Rapor</button>
                            {% if u_data.veli_telefon %}
                            <button class="btn btn-wa" style="padding: 5px 10px; font-size:12px;" onclick="manuelWaGonder('{{ u_data.veli_telefon }}', '{{ u_name }}')">💬 WA</button>
                            {% endif %}
                            <button class="btn btn-delete" style="padding: 5px 10px; font-size:12px;" onclick="ogrenciSil('{{ u_name }}')">Sil 🗑️</button>
                        </td>
                    </tr>
                    {% endif %}
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="form-box" style="border-color: #ef4444;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <h4 style="margin: 0; color: #ef4444;">📋 Tüm Devamsızlık ve Katılım Logları</h4>
                <div style="display:flex; gap:8px;">
                    <a href="/katilim_excel" class="btn btn-export" style="font-size:12px; padding:6px 12px;">📥 Excel / CSV İndir</a>
                    <button class="btn btn-delete" style="font-size:12px; padding:6px 12px;" onclick="katilimlariTemizle()">🗑️ Logları Temizle</button>
                </div>
            </div>
            <div style="max-height: 350px; overflow-y: auto;">
                <table class="log-table">
                    <thead>
                        <tr>
                            <th>Öğrenci</th>
                            <th>Sınıf / Grup</th>
                            <th>Tarih</th>
                            <th>Ders Saati</th>
                            <th>Giriş Saati</th>
                            <th>Ders</th>
                            <th>Öğretmen</th>
                            <th>Durum</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for k in katilimlar|reverse %}
                        <tr class="log-row" data-sinif-grup="{{ k.ogrenci_sinif_grup }}">
                            <td><b>{{ k.kullanici.upper() }}</b></td>
                            <td><span class="badge" style="margin:0;">{{ k.ogrenci_sinif_grup }}</span></td>
                            <td>{{ k.tarih }}</td>
                            <td><code>{{ k.ders_saati|default('--:--') }}</code></td>
                            <td><code>{{ k.saat }}</code></td>
                            <td>{{ k.ders }}</td>
                            <td>{{ k.ogretmen }}</td>
                            <td>
                                {% if k.durum == 'DEVAMSIZ' %}
                                    <span class="tag-devamsiz">DEVAMSIZ</span>
                                {% elif k.durum == 'GEC_KALDI' %}
                                    <span class="tag-gec">GEÇ KALDI</span>
                                {% else %}
                                    <span class="tag-zamaninda">ZAMANINDA</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="8" style="text-align:center; color:#94a3b8;">Henüz verilmiş bir devamsızlık veya katılım kaydı bulunmuyor.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="form-box">
            <h4 style="margin: 0 0 12px 0; color: #38bdf8;">📚 Admin Özel: Yeni Ders Programı Ekle</h4>
            <div class="form-row">
                <select id="yeni_sinif">
                    <option value="8. Sınıf" selected>8. Sınıf</option>
                    <option value="7. Sınıf">7. Sınıf</option>
                </select>
                <select id="yeni_grup">
                    <option value="Dahiler">Dahiler 🧠</option>
                    <option value="Efsaneler">Efsaneler 🔥</option>
                    <option value="Şampiyonlar">Şampiyonlar 🏆</option>
                    <option value="Hızlılar">Hızlılar ⚡</option>
                </select>
            </div>
            <div class="form-row">
                <input type="text" id="yeni_ders" placeholder="Ders Adı (Örn: Matematik)">
                <input type="text" id="yeni_ogretmen" placeholder="Hoca Adı">
            </div>
            <div class="form-row">
                <input type="text" id="yeni_id" placeholder="Zoom ID">
                <input type="text" id="yeni_sifre" placeholder="Passcode (Şifre)">
            </div>
            <div class="form-row">
                <select id="yeni_gun">
                    <option value="Her Gün">Her Gün 🔄</option>
                    <option value="Pazartesi">Pazartesi</option><option value="Salı">Salı</option>
                    <option value="Çarşamba">Çarşamba</option><option value="Perşembe">Perşembe</option>
                    <option value="Cuma">Cuma</option><option value="Cumartesi">Cumartesi</option><option value="Pazar">Pazar</option>
                </select>
            </div>
            <div class="form-row">
                <div style="width:50%;">
                    <span style="font-size:12px; color:#94a3b8;">Ders Başlangıç Saati:</span>
                    <input type="time" id="yeni_alarm">
                </div>
                <div style="width:50%;">
                    <span style="font-size:12px; color:#94a3b8;">Ders Bitiş Saati:</span>
                    <input type="time" id="yeni_bitis_saati">
                </div>
            </div>
            <button type="button" class="btn btn-add" onclick="ekle()">Ders Programına Ekle</button>
        </div>
    </div>
    {% endif %}

    <div id="status"></div>
</div>

<div id="chartModal" class="modal">
    <div class="modal-content">
        <h3 id="chartModalTitle" style="margin-top:0; color:#38bdf8; text-align:center;">📊 Öğrenci Katılım Raporu</h3>
        <div style="position: relative; height:220px; width:100%;">
            <canvas id="studentChart"></canvas>
        </div>
        <div id="chartDetails" style="margin-top:15px; text-align:center; font-size:14px; color:#94a3b8;"></div>
        <div style="margin-top:20px; text-align:center;">
            <button class="btn btn-delete" onclick="document.getElementById('chartModal').style.display='none'">Kapat</button>
        </div>
    </div>
</div>

<div id="editModal" class="modal">
    <div class="modal-content">
        <h3 style="margin-top:0; color:#38bdf8;">✏️ Ders Programını Düzenle</h3>
        <input type="hidden" id="edit_kisi_key">
        <div class="form-row">
            <select id="edit_sinif"><option value="8. Sınıf">8. Sınıf</option><option value="7. Sınıf">7. Sınıf</option></select>
            <select id="edit_grup"><option value="Dahiler">Dahiler</option><option value="Efsaneler">Efsaneler</option><option value="Şampiyonlar">Şampiyonlar</option><option value="Hızlılar">Hızlılar</option></select>
        </div>
        <div class="form-row">
            <input type="text" id="edit_ders" placeholder="Ders Adı">
            <input type="text" id="edit_ogretmen" placeholder="Hoca Adı">
        </div>
        <div class="form-row">
            <input type="text" id="edit_id" placeholder="Zoom ID">
            <input type="text" id="edit_sifre" placeholder="Passcode">
        </div>
        <div class="form-row">
            <select id="edit_gun">
                <option value="Her Gün">Her Gün 🔄</option>
                <option value="Pazartesi">Pazartesi</option><option value="Salı">Salı</option>
                <option value="Çarşamba">Çarşamba</option><option value="Perşembe">Perşembe</option>
                <option value="Cuma">Cuma</option><option value="Cumartesi">Cumartesi</option><option value="Pazar">Pazar</option>
            </select>
        </div>
        <div class="form-row">
            <div style="width:50%;">
                <span style="font-size:12px; color:#94a3b8;">Ders Başlangıç Saati:</span>
                <input type="time" id="edit_alarm">
            </div>
            <div style="width:50%;">
                <span style="font-size:12px; color:#94a3b8;">Ders Bitiş Saati:</span>
                <input type="time" id="edit_bitis_saati">
            </div>
        </div>
        <div style="display:flex; gap:10px; margin-top:15px;">
            <button class="btn btn-add" style="margin:0;" onclick="duzenleKaydet()">Güncelle ve Kaydet</button>
            <button class="btn btn-delete" onclick="document.getElementById('editModal').style.display='none'">İptal</button>
        </div>
    </div>
</div>

<script>
    let myChart = null;
    let aktifSekmeGrup = 'hepsi';
    let manualAlarmTetiklendi = false; 

    let alarmKalanSaniye = 0;
    let alarmCountdownTimer = null;
    let calmisAlarmlar = new Set();
    let audioCtx = null;
    let alarmInterval = null;

    function saatiGuncelle() {
        const now = new Date();
        const gunler = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
        const bugun = gunler[now.getDay()];
        const hrs = String(now.getHours()).padStart(2, '0');
        const mins = String(now.getMinutes()).padStart(2, '0');
        const secs = String(now.getSeconds()).padStart(2, '0');
        document.getElementById('liveClock').innerText = `${bugun} | ${hrs}:${mins}:${secs}`;
        
        otomatikAlarmVeDevamsizlikKontrol(bugun, hrs, mins, secs);
    }
    setInterval(saatiGuncelle, 1000);

    function alarmSesiCal() {
        try {
            if (!audioCtx) { audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
            if (audioCtx.state === 'suspended') { audioCtx.resume(); }
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'square';
            osc.frequency.setValueAtTime(880, audioCtx.currentTime);
            gain.gain.setValueAtTime(0.5, audioCtx.currentTime);
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.3);
        } catch(e){}
    }

    function otomatikAlarmVeDevamsizlikKontrol(bugun, hrs, mins, secs) {
        const simdiMins = parseInt(hrs) * 60 + parseInt(mins);
        const zamanKey = `${bugun}_${hrs}:${mins}`;

        document.querySelectorAll('.ders-kart').forEach(card => {
            const dersGun = card.getAttribute('data-gun');
            const dersSaatStr = card.getAttribute('data-alarm');
            const cardId = card.id;

            if (dersSaatStr && (dersGun === "Her Gün" || dersGun === bugun)) {
                const parts = dersSaatStr.split(':');
                if (parts.length === 2) {
                    const dersMins = parseInt(parts[0]) * 60 + parseInt(parts[1]);
                    
                    if (simdiMins === (dersMins - 5)) {
                        const alarmKey = `${cardId}_${zamanKey}`;
                        if (!calmisAlarmlar.has(alarmKey) && alarmKalanSaniye <= 0) {
                            calmisAlarmlar.add(alarmKey);
                            card.classList.add('alarm-active');
                            alarmBaslat10Sn();
                        }
                    }
                }
            }
        });
    }

    function alarmBaslat10Sn() {
        alarmKalanSaniye = 10;
        const banner = document.getElementById('alarmBanner');
        const bannerText = document.getElementById('alarmBannerText');
        banner.style.display = 'flex';

        if (!alarmInterval) {
            alarmInterval = setInterval(alarmSesiCal, 800);
        }

        if (alarmCountdownTimer) clearInterval(alarmCountdownTimer);

        bannerText.innerText = `🚨 DERS ALARMI! DERSİN BAŞLAMASINA 5 DAKİKA KALDI! (${alarmKalanSaniye} sn)`;

        alarmCountdownTimer = setInterval(() => {
            alarmKalanSaniye--;
            if (alarmKalanSaniye > 0) {
                bannerText.innerText = `🚨 DERS ALARMI! DERSİN BAŞLAMASINA 5 DAKİKA KALDI! (${alarmKalanSaniye} sn)`;
            } else {
                clearInterval(alarmCountdownTimer);
                alarmCountdownTimer = null;
                if (alarmInterval) {
                    clearInterval(alarmInterval);
                    alarmInterval = null;
                }
                if (!manualAlarmTetiklendi) {
                    banner.style.display = 'none';
                }
                
                document.querySelectorAll('.ders-kart').forEach(card => {
                    card.classList.remove('alarm-active');
                });
            }
        }, 1000);
    }

    function bilgiKopyala(zoomId, sifre) {
        const metin = `Zoom ID: ${zoomId}\nPasscode: ${sifre}`;
        navigator.clipboard.writeText(metin).then(() => {
            alert("Zoom bilgileri panoya kopyalandı!");
        });
    }

    function kartFiltrele() {
        const query = document.getElementById('kartAramaInput').value.toLowerCase().trim();
        
        document.querySelectorAll('.ders-kart').forEach(card => {
            const searchData = card.getAttribute('data-search').toLowerCase();
            const grupUygun = (aktifSekmeGrup === 'hepsi' || card.classList.contains('grup-' + aktifSekmeGrup));
            const metinUygun = searchData.includes(query);
            card.style.display = (grupUygun && metinUygun) ? 'flex' : 'none';
        });

        document.querySelectorAll('.ogrenci-row').forEach(row => {
            const grup = row.getAttribute('data-grup');
            const rowText = row.innerText.toLowerCase();
            const grupUygun = (aktifSekmeGrup === 'hepsi' || grup === aktifSekmeGrup);
            const metinUygun = rowText.includes(query);
            row.style.display = (grupUygun && metinUygun) ? '' : 'none';
        });

        document.querySelectorAll('.log-row').forEach(row => {
            const sinifGrup = row.getAttribute('data-sinif-grup') || '';
            const rowText = row.innerText.toLowerCase();
            const grupUygun = (aktifSekmeGrup === 'hepsi' || sinifGrup.includes(aktifSekmeGrup));
            const metinUygun = rowText.includes(query);
            row.style.display = (grupUygun && metinUygun) ? '' : 'none';
        });
    }

    function sekmeDegistir(grupAdi, btn) {
        aktifSekmeGrup = grupAdi;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        if(btn) btn.classList.add('active');
        kartFiltrele();
    }

    function grafikGoster(username) {
        fetch('/ogrenci_istatistik/' + encodeURIComponent(username))
            .then(r => r.json())
            .then(data => {
                document.getElementById('chartModalTitle').innerText = `📊 ${username.toUpperCase()} - Katılım Analizi`;
                document.getElementById('chartModal').style.display = 'flex';
                document.getElementById('chartDetails').innerHTML = `
                    <span style="color:#10b981;">Zamanında: <b>${data.zamaninda}</b></span> | 
                    <span style="color:#f59e0b;">Geç: <b>${data.gec}</b></span> | 
                    <span style="color:#ef4444;">Devamsız: <b>${data.devamsiz}</b></span>
                `;

                const ctx = document.getElementById('studentChart').getContext('2d');
                if (myChart) myChart.destroy();

                myChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Zamanında Girildi', 'Geç Girildi', 'Girilmedi (Devamsız)'],
                        datasets: [{
                            data: [data.zamaninda, data.gec, data.devamsiz],
                            backgroundColor: ['#10b981', '#f59e0b', '#ef4444']
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            });
    }

    function manuelWaGonder(tel, name) {
        const msg = encodeURIComponent(`Sayın Veli, ${name.toUpperCase()} isimli öğrencimizin ders katılım durumu hakkında bilgilendirme mesajıdır.`);
        window.open(`https://web.whatsapp.com/send?phone=${tel}&text=${msg}`, '_blank');
    }

    setInterval(() => { 
        fetch('/ping')
        .then(r => r.json())
        .then(data => {
            manualAlarmTetiklendi = data.alarm || false;
            const banner = document.getElementById('alarmBanner');
            const bannerText = document.getElementById('alarmBannerText');
            
            if (manualAlarmTetiklendi) {
                bannerText.innerText = "🚨 YÖNETİCİ ALARMI! LÜTFEN DERSE KATILIN!";
                banner.style.display = 'flex';
                if (!alarmInterval) alarmInterval = setInterval(alarmSesiCal, 800);
            } else if (alarmKalanSaniye <= 0 && banner.style.display === 'flex' && bannerText.innerText.includes('YÖNETİCİ')) {
                banner.style.display = 'none';
                if (alarmInterval) { clearInterval(alarmInterval); alarmInterval = null; }
            }
        });
    }, 3000); 

    function katil(kisi) {
        const statusDiv = document.getElementById('status');
        statusDiv.style.color = '#38bdf8';
        statusDiv.innerText = "Zoom açılıyor...";
        fetch('/katil/' + encodeURIComponent(kisi))
            .then(r => r.json())
            .then(d => {
                statusDiv.style.color = '#4ade80';
                statusDiv.innerText = d.message;
                setTimeout(() => location.reload(), 1500);
            });
    }

    {% if is_admin %}
    function ogrenciEkle() {
        const sinif = document.getElementById('ogrenci_sinif').value;
        const grup = document.getElementById('ogrenci_grup').value;
        const username = document.getElementById('ogrenci_kullanici').value.trim();
        const password = document.getElementById('ogrenci_sifre').value.trim();
        const veli_tel = document.getElementById('ogrenci_veli_tel').value.trim();

        if(!username || !password) { alert("Kullanıcı adı ve şifre zorunludur!"); return; }

        fetch('/ogrenci_ekle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sinif, grup, username, password, veli_telefon: veli_tel })
        }).then(() => location.reload());
    }

    function ogrenciSil(uname) {
        if(confirm(`${uname.toUpperCase()} adlı öğrenciyi silmek istediğinize emin misiniz?`)) {
            fetch('/ogrenci_sil/' + encodeURIComponent(uname), { method: 'DELETE' }).then(() => location.reload());
        }
    }

    function katilimlariTemizle() {
        if (confirm("Tüm katılım ve devamsızlık geçmişi silinecektir. Emin misiniz?")) {
            fetch('/katilim_temizle', { method: 'POST' }).then(() => location.reload());
        }
    }

    function ekle() {
        const sinif = document.getElementById('yeni_sinif').value;
        const grup = document.getElementById('yeni_grup').value;
        const ders = document.getElementById('yeni_ders').value.trim();
        let ogretmen = document.getElementById('yeni_ogretmen').value.trim();
        const id = document.getElementById('yeni_id').value.trim();
        const sifre = document.getElementById('yeni_sifre').value.trim();
        const gun = document.getElementById('yeni_gun').value;
        const alarm = document.getElementById('yeni_alarm').value;
        const bitis_saati = document.getElementById('yeni_bitis_saati').value;

        fetch('/ekle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sinif, grup, ders, ogretmen, id, sifre, gun, alarm, bitis_saati })
        }).then(() => location.reload());
    }

    function duzenleModalAc(key, sinif, grup, ders, ogretmen, id, sifre, gun, alarm, bitis_saati) {
        document.getElementById('edit_kisi_key').value = key;
        document.getElementById('edit_sinif').value = sinif;
        document.getElementById('edit_grup').value = grup;
        document.getElementById('edit_ders').value = ders;
        document.getElementById('edit_ogretmen').value = ogretmen;
        document.getElementById('edit_id').value = id;
        document.getElementById('edit_sifre').value = sifre;
        document.getElementById('edit_gun').value = gun;
        document.getElementById('edit_alarm').value = alarm;
        document.getElementById('edit_bitis_saati').value = bitis_saati;
        document.getElementById('editModal').style.display = 'flex';
    }

    function duzenleKaydet() {
        const key = document.getElementById('edit_kisi_key').value;
        const sinif = document.getElementById('edit_sinif').value;
        const grup = document.getElementById('edit_grup').value;
        const ders = document.getElementById('edit_ders').value;
        const ogretmen = document.getElementById('edit_ogretmen').value;
        const id = document.getElementById('edit_id').value;
        const sifre = document.getElementById('edit_sifre').value;
        const gun = document.getElementById('edit_gun').value;
        const alarm = document.getElementById('edit_alarm').value;
        const bitis_saati = document.getElementById('edit_bitis_saati').value;

        fetch('/duzenle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, sinif, grup, ders, ogretmen, id, sifre, gun, alarm, bitis_saati })
        }).then(() => location.reload());
    }

    function alarmTetikle(key, durum) {
        fetch('/manual_alarm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key, durum })
        }).then(() => location.reload());
    }

    function sil(kisi) {
        if (confirm(`Bu ders kaydını silmek istediğinize emin misiniz?`)) {
            fetch('/sil/' + encodeURIComponent(kisi), { method: 'DELETE' }).then(() => location.reload());
        }
    }
    {% endif %}
</script>
{% endif %}

</body>
</html>
"""

def arka_plan_devamsizlik_kontrol():
    """Arka planda periyodik olarak ders bitimlerini takip eden thread iş parçacığı."""
    while True:
        try:
            now = datetime.now()
            bugun = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"][now.weekday()]
            tarih_str = now.strftime("%d.%m.%Y")

            rehber = veri_yukle("rehber.json")
            users = veri_yukle("users.json")
            katilimlar = veri_yukle("katilimlar.json")
            if not isinstance(katilimlar, list):
                katilimlar = []

            degisiklik_var = False

            for key, ders in rehber.items():
                ders_gun = ders.get('gun', 'Her Gün')
                ders_saat_str = ders.get('alarm', '')

                if ders_saat_str and (ders_gun == 'Her Gün' or ders_gun == bugun):
                    p = ders_saat_str.split(':')
                    if len(p) == 2:
                        ders_saat = now.replace(hour=int(p[0]), minute=int(p[1]), second=0, microsecond=0)
                        
                        bitis_saat_str = ders.get('bitis_saati', '')
                        if bitis_saat_str and ':' in bitis_saat_str:
                            bp = bitis_saat_str.split(':')
                            sinir_saat = now.replace(hour=int(bp[0]), minute=int(bp[1]), second=0, microsecond=0)
                        else:
                            sinir_saat = ders_saat + timedelta(minutes=40)
                        
                        if now >= sinir_saat and now.date() == ders_saat.date():
                            ders_adi_std = (ders.get('ders') or key).strip().lower()
                            key_std = key.strip().lower()

                            for uname, udata in users.items():
                                if uname.lower() == ADMIN_USERNAME.lower() or not isinstance(udata, dict):
                                    continue
                                
                                if udata.get('sinif') == ders.get('sinif') and udata.get('grup') == ders.get('grup'):
                                    giris_var = any(
                                        k.get('kullanici', '').strip().lower() == uname.strip().lower() and 
                                        k.get('tarih') == tarih_str and 
                                        (k.get('ders', '').strip().lower() == ders_adi_std or k.get('ders', '').strip().lower() == key_std)
                                        for k in katilimlar
                                    )
                                    if not giris_var:
                                        katilimlar.append({
                                            "kullanici": uname,
                                            "ogrenci_sinif_grup": f"{udata.get('sinif')} {udata.get('grup')}",
                                            "ders": (ders.get('ders') or key).title(),
                                            "ogretmen": ders.get('ogretmen'),
                                            "tarih": tarih_str,
                                            "saat": now.strftime("%H:%M:%S"),
                                            "ders_saati": ders_saat_str,
                                            "durum": "DEVAMSIZ"
                                        })
                                        degisiklik_var = True
                                        
                                        vel_tel = udata.get('veli_telefon')
                                        if vel_tel:
                                            mesaj = f"Sayın Veli, öğrenciniz {uname.upper()}, bugün {ders_saat_str} saatindeki {ders.get('ders')} derse zamanında katılmadığı için devamsız yazılmıştır."
                                            threading.Thread(target=whatsapp_mesaj_gonder, args=(vel_tel, mesaj), daemon=True).start()

            if degisiklik_var:
                veri_kaydet("katilimlar.json", katilimlar)

        except Exception as e:
            print(f"[HATA] Arka plan devamsızlık kontrolü: {e}")
        
        time.sleep(20)

threading.Thread(target=arka_plan_devamsizlik_kontrol, daemon=True).start()

@app.route('/')
def ana_sayfa():
    rehber = veri_yukle("rehber.json")
    katilimlar = veri_yukle("katilimlar.json")
    users = veri_yukle("users.json")
    
    current_user = session.get('user', None)
    is_admin = False
    user_sinif, user_grup = "", ""

    if current_user:
        clean_u = current_user.lower().strip()
        if clean_u == ADMIN_USERNAME.lower():
            is_admin = True
        elif clean_u in users and isinstance(users[clean_u], dict):
            user_sinif = users[clean_u].get('sinif', '')
            user_grup = users[clean_u].get('grup', '')

    now_ts = time.time()
    online_count = 0
    student_count = 0
    for u, u_info in users.items():
        if u.lower() != ADMIN_USERNAME.lower() and isinstance(u_info, dict):
            student_count += 1
            is_on = (now_ts - u_info.get('last_seen', 0)) < 300
            u_info['is_online'] = is_on
            if is_on:
                online_count += 1

    stats = {
        "toplam_ogrenci": student_count,
        "online_ogrenci": online_count,
        "toplam_ders": len(rehber),
        "toplam_devamsizlik": sum(1 for k in katilimlar if k.get('durum') == 'DEVAMSIZ')
    }

    return render_template_string(HTML_TEMPLATE, 
                                  rehber=rehber, katilimlar=katilimlar, users=users, 
                                  current_user=current_user, is_admin=is_admin, 
                                  user_sinif=user_sinif, user_grup=user_grup, stats=stats)

@app.route('/ogrenci_istatistik/<uname>')
def ogrenci_istatistik(uname):
    katilimlar = veri_yukle("katilimlar.json")
    target = uname.lower().strip()
    
    zamaninda, gec, devamsiz = 0, 0, 0
    for k in katilimlar:
        if k.get('kullanici', '').lower() == target:
            durum = k.get('durum', 'ZAMANINDA')
            if durum == 'ZAMANINDA': zamaninda += 1
            elif durum == 'GEC_KALDI': gec += 1
            elif durum == 'DEVAMSIZ': devamsiz += 1

    return jsonify({"zamaninda": zamaninda, "gec": gec, "devamsiz": devamsiz})

@app.route('/katilim_excel')
def katilim_excel():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower():
        return redirect(url_for('ana_sayfa'))
    
    katilimlar = veri_yukle("katilimlar.json")
    gunler = {"Monday": "Pazartesi", "Tuesday": "Salı", "Wednesday": "Çarşamba", "Thursday": "Perşembe", "Friday": "Cuma", "Saturday": "Cumartesi", "Sunday": "Pazar"}
    
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Katılım Raporu"
        
        headers = ['Öğrenci', 'Sınıf / Grup', 'Gün', 'Tarih', 'Ders Saati', 'Giriş Saati', 'Ders', 'Öğretmen', 'Durum']
        ws.append(headers)
        
        for k in katilimlar:
            tarih_str = k.get('tarih', '')
            gun_adi = ""
            try:
                dt = datetime.strptime(tarih_str, "%d.%m.%Y")
                gun_adi = gunler.get(dt.strftime("%A"), "")
            except Exception:
                pass
                
            ws.append([
                k.get('kullanici', '').upper(),
                k.get('ogrenci_sinif_grup', ''),
                gun_adi,
                tarih_str,
                k.get('ders_saati', '--:--'),
                k.get('saat', ''),
                k.get('ders', ''),
                k.get('ogretmen', ''),
                k.get('durum', '')
            ])
            
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return Response(
            output.read(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": "attachment; filename=katilim_raporu.xlsx"}
        )
    except ImportError:
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        
        headers = ['Öğrenci', 'Sınıf / Grup', 'Gün', 'Tarih', 'Ders Saati', 'Giriş Saati', 'Ders', 'Öğretmen', 'Durum']
        writer.writerow(headers)
        
        for k in katilimlar:
            tarih_str = k.get('tarih', '')
            gun_adi = ""
            try:
                dt = datetime.strptime(tarih_str, "%d.%m.%Y")
                gun_adi = gunler.get(dt.strftime("%A"), "")
            except Exception:
                pass
                
            writer.writerow([
                k.get('kullanici', '').upper(),
                k.get('ogrenci_sinif_grup', ''),
                gun_adi,
                tarih_str,
                k.get('ders_saati', '--:--'),
                k.get('saat', ''),
                k.get('ders', ''),
                k.get('ogretmen', ''),
                k.get('durum', '')
            ])
            
        return Response(
            output.getvalue().encode('utf-8-sig'),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-disposition": "attachment; filename=katilim_raporu.csv"}
        )

@app.route('/katilim_temizle', methods=['POST'])
def katilim_temizle():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower():
        return jsonify({"status": "error"})
    veri_kaydet("katilimlar.json", [])
    return jsonify({"status": "success"})

@app.route('/alarm_durumlari')
def alarm_durumlari():
    rehber = veri_yukle("rehber.json")
    if any(info.get('manual_alarm', False) for info in rehber.values()):
        sistem_sesini_ayarla(fulle=True)
    else:
        sistem_sesini_ayarla(fulle=False)
    return jsonify(rehber)

@app.route('/ping')
def ping():
    alarm_tetiklendi = False
    if 'user' in session:
        users = veri_yukle("users.json")
        u = session['user'].lower().strip()
        is_admin = (u == ADMIN_USERNAME.lower())
        
        if u in users and isinstance(users[u], dict):
            users[u]['last_seen'] = time.time()
            veri_kaydet("users.json", users)
            
        rehber = veri_yukle("rehber.json")
        for k, ders in rehber.items():
            if ders.get('manual_alarm'):
                if is_admin or (not is_admin and u in users and isinstance(users[u], dict) and 
                                ders.get('sinif') == users[u].get('sinif') and 
                                ders.get('grup') == users[u].get('grup')):
                    alarm_tetiklendi = True
                    break

    return jsonify({"status": "ok", "alarm": alarm_tetiklendi})

@app.route('/login', methods=['POST'])
def login():
    users = veri_yukle("users.json")
    if ADMIN_USERNAME not in users:
        users[ADMIN_USERNAME] = {"pwd": "1234", "sinif": "Yönetim", "grup": "Admin"}
        veri_kaydet("users.json", users)

    uname = request.form.get('username', '').strip().lower()
    pwd = request.form.get('password', '').strip()

    if uname in users:
        u_pwd = users[uname]["pwd"] if isinstance(users[uname], dict) else users[uname]
        if u_pwd == pwd:
            session['user'] = uname
            session['user_display'] = "⚙️ YÖNETİCİ PANELİ" if uname == ADMIN_USERNAME else uname.title()
            if isinstance(users[uname], dict):
                users[uname]['last_seen'] = time.time()
                veri_kaydet("users.json", users)

    return redirect(url_for('ana_sayfa'))

@app.route('/ogrenci_ekle', methods=['POST'])
def ogrenci_ekle():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    data = request.json
    uname = data.get('username', '').strip().lower()
    pwd = data.get('password', '').strip()
    
    if uname and pwd and uname != ADMIN_USERNAME.lower():
        users = veri_yukle("users.json")
        users[uname] = {
            "pwd": pwd,
            "sinif": data.get('sinif', ''),
            "grup": data.get('grup', ''),
            "veli_telefon": data.get('veli_telefon', ''),
            "last_seen": 0
        }
        veri_kaydet("users.json", users)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"})

@app.route('/ogrenci_sil/<path:uname>', methods=['DELETE'])
def ogrenci_sil(uname):
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    users = veri_yukle("users.json")
    target = uname.lower().strip()
    if target in users and target != ADMIN_USERNAME.lower():
        del users[target]
        veri_kaydet("users.json", users)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('ana_sayfa'))

@app.route('/katil/<path:kisi>')
def toplantiya_katil(kisi):
    if 'user' not in session: 
        return jsonify({"status": "error", "message": "Giriş yapmalısınız!"})

    rehber = veri_yukle("rehber.json")
    users = veri_yukle("users.json")
    hedef = kisi.lower().strip()

    if hedef not in rehber: 
        return jsonify({"status": "error", "message": "Ders bulunamadı!"})

    bilgi = rehber[hedef]
    clean_id = bilgi.get('id', '').replace(' ', '')
    sifre = bilgi.get('sifre', '').strip()

    u_data = users.get(session['user'], {})
    ogrenci_sinif_grup = f"{u_data.get('sinif', '')} {u_data.get('grup', '')}" if isinstance(u_data, dict) else "Admin"

    now = datetime.now()
    ders_saat_str = bilgi.get('alarm', '')
    tarih_str = now.strftime("%d.%m.%Y")
    
    durum = "ZAMANINDA"
    if ders_saat_str:
        p = ders_saat_str.split(':')
        if len(p) == 2:
            ders_saat = now.replace(hour=int(p[0]), minute=int(p[1]), second=0, microsecond=0)
            zamaninda_sinir = ders_saat + timedelta(minutes=5)
            
            bitis_saat_str = bilgi.get('bitis_saati', '')
            if bitis_saat_str and ':' in bitis_saat_str:
                bp = bitis_saat_str.split(':')
                gec_sinir = now.replace(hour=int(bp[0]), minute=int(bp[1]), second=0, microsecond=0)
            else:
                gec_sinir = ders_saat + timedelta(minutes=40)
            
            if now <= zamaninda_sinir:
                durum = "ZAMANINDA"
            elif zamaninda_sinir < now <= gec_sinir:
                durum = "GEC_KALDI"
            else:
                durum = "DEVAMSIZ"

    katilimlar = veri_yukle("katilimlar.json")
    if not isinstance(katilimlar, list): 
        katilimlar = []

    # Standartlaştırılmış Ders ve Kullanıcı Karşılaştırması
    ders_adi_std = (bilgi.get('ders') or hedef).strip().lower()
    current_u = session['user'].strip().lower()

    existing_idx = None
    for idx, k in enumerate(katilimlar):
        k_user = k.get('kullanici', '').strip().lower()
        k_ders = k.get('ders', '').strip().lower()
        if k_user == current_u and k.get('tarih') == tarih_str and (k_ders == ders_adi_std or k_ders == hedef):
            existing_idx = idx
            break

    # Kayıt varsa mevcut kaydı güncelle, ALT ALTA MÜKERRER KAYIT EKLEME
    if existing_idx is not None:
        katilimlar[existing_idx]['durum'] = durum
        katilimlar[existing_idx]['saat'] = now.strftime("%H:%M:%S")
        katilimlar[existing_idx]['ogrenci_sinif_grup'] = ogrenci_sinif_grup
    else:
        log_kaydi = {
            "kullanici": session['user'],
            "ogrenci_sinif_grup": ogrenci_sinif_grup,
            "ders": (bilgi.get('ders') or hedef).title(),
            "ogretmen": bilgi.get('ogretmen', 'Öğretmen').title(),
            "tarih": tarih_str,
            "saat": now.strftime("%H:%M:%S"),
            "ders_saati": ders_saat_str if ders_saat_str else "--:--",
            "durum": durum
        }
        katilimlar.append(log_kaydi)

    veri_kaydet("katilimlar.json", katilimlar)

    zoom_url = f"zoommtg://zoom.us/join?confno={clean_id}&pwd={sifre}"
    try:
        webbrowser.open(zoom_url)
    except Exception as e:
        print(f"[HATA] Zoom URL açılamadı: {e}")

    if GUI_AUTOMATION_AVAILABLE and sifre:
        def otomatik_sifre_gir():
            try:
                pyperclip.copy(sifre)
                time.sleep(2.5)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.2)
                pyautogui.press('enter')
            except Exception as e:
                print(f"[HATA] Otomatik şifre girişi hatası: {e}")
        
        threading.Thread(target=otomatik_sifre_gir, daemon=True).start()

    return jsonify({"status": "success", "message": "Toplantıya bağlanıldı!"})

@app.route('/ekle', methods=['POST'])
def kisi_ekle():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    data = request.json
    sinif, grup = data.get('sinif', ''), data.get('grup', '')
    ders, ogretmen = data.get('ders', '').strip(), data.get('ogretmen', '').strip()
    id_num, sifre = data.get('id', '').strip(), data.get('sifre', '').strip()
    gun, alarm = data.get('gun', 'Her Gün'), data.get('alarm', '')
    bitis_saati = data.get('bitis_saati', '')

    anahtar = f"{sinif}_{grup}_{ders}_{ogretmen}".lower().replace(' ', '_')
    rehber = veri_yukle("rehber.json")
    rehber[anahtar] = {
        "sinif": sinif, "grup": grup, "ders": ders,
        "ogretmen": ogretmen if ogretmen else f"{ders} Öğretmeni",
        "id": id_num, "sifre": sifre, "gun": gun, "alarm": alarm, "bitis_saati": bitis_saati, "manual_alarm": False
    }
    veri_kaydet("rehber.json", rehber)
    return jsonify({"status": "success"})

@app.route('/duzenle', methods=['POST'])
def kisi_duzenle():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    data = request.json
    old_key = data.get('key', '')
    
    sinif, grup = data.get('sinif', ''), data.get('grup', '')
    ders, ogretmen = data.get('ders', '').strip(), data.get('ogretmen', '').strip()
    id_num, sifre = data.get('id', '').strip(), data.get('sifre', '').strip()
    gun, alarm = data.get('gun', 'Her Gün'), data.get('alarm', '')
    bitis_saati = data.get('bitis_saati', '')

    rehber = veri_yukle("rehber.json")
    if old_key in rehber: 
        del rehber[old_key]

    new_key = f"{sinif}_{grup}_{ders}_{ogretmen}".lower().replace(' ', '_')
    rehber[new_key] = {
        "sinif": sinif, "grup": grup, "ders": ders, "ogretmen": ogretmen,
        "id": id_num, "sifre": sifre, "gun": gun, "alarm": alarm, "bitis_saati": bitis_saati, "manual_alarm": False
    }
    veri_kaydet("rehber.json", rehber)
    return jsonify({"status": "success"})

@app.route('/manual_alarm', methods=['POST'])
def manual_alarm():
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    data = request.json
    key = data.get('key', '')
    durum = data.get('durum', False)

    rehber = veri_yukle("rehber.json")
    if key in rehber:
        rehber[key]['manual_alarm'] = durum
        veri_kaydet("rehber.json", rehber)
        sistem_sesini_ayarla(fulle=durum)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"})

@app.route('/sil/<path:kisi>', methods=['DELETE'])
def kisi_sil(kisi):
    if session.get('user', '').lower() != ADMIN_USERNAME.lower(): 
        return jsonify({"status": "error"})
    rehber = veri_yukle("rehber.json")
    hedef = kisi.lower().strip()
    if hedef in rehber:
        del rehber[hedef]
        veri_kaydet("rehber.json", rehber)
        return jsonify({"status": "success"})
    return jsonify({"status": "error"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)