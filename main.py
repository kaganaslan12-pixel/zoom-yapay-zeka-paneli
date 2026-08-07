import json
import os
import sys
import time
import pyautogui

def rehberi_yukle():
    try:
        # rehber.json dosyasının tam yolunu al
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, "rehber.json")
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}

def toplantiya_katil(kisi_adi):
    rehber = rehberi_yukle()
    hedef = kisi_adi.lower().strip()

    if hedef not in rehber:
        print(f"❌ '{kisi_adi}' adinda bir kayit bulunamadi.")
        return

    bilgi = rehber[hedef]
    print(f"🚀 {hedef.capitalize()} toplantisina hizlica baglaniliyor...")

    # 1. Zoom'u doğrudan başlat
    clean_id = bilgi['id'].replace(' ', '')
    zoom_url = f"zoommtg://zoom.us/join?confno={clean_id}"
    os.system(f"start {zoom_url}")

    # 2. Şifre ekranının gelmesi için çok kısa bir bekleme
    time.sleep(1.5)

    # 3. Şifreyi anında yaz ve Enter'a bas
    if bilgi.get("sifre"):
        pyautogui.write(bilgi["sifre"], interval=0.01) # Işık hızında yazar
        pyautogui.press('enter')

    print("⚡ Giriş yapıldı!")

if __name__ == "__main__":
    # Eğer komut satırından parametre gelmişse (Örn: zoom kenanhoca)
    if len(sys.argv) > 1:
        toplantiya_katil(sys.argv[1])
    else:
        kisi = input("\nHangi kisisin toplantisina katilmak istiyorsun?: ")
        toplantiya_katil(kisi)