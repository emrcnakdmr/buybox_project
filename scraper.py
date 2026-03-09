from curl_cffi import requests as cureq
from bs4 import BeautifulSoup
import re
import time
import random

session = cureq.Session(impersonate="chrome110")

def akakce_tekli_cek(url):
    try:
        # İnsan gibi davranmak için rastgele bir süre bekle
        time.sleep(random.uniform(1.5, 3.5)) 

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.akakce.com/",
            "DNT": "1"
        }
        
        response = session.get(url, headers=headers, timeout=15)
        
        # Hata Yönetimi
        if response.status_code == 429:
            return {"urun_adi": "IP Engeli (429)", "fiyat": "Engellendi", "satici": "-", "link": url}
        elif response.status_code == 410:
            return {"urun_adi": "Ürün Siteden Kaldırılmış", "fiyat": "Kaldırıldı", "satici": "-", "link": url}
        elif response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # 1. Ürün Adını Bul
        urun_adi_etiketi = soup.find("h1")
        urun_adi = urun_adi_etiketi.text.strip() if urun_adi_etiketi else "Ad Bulunamadı"
        
        # 2. KRİTİK KONTROL: FİYAT YOK veya STOK YOK DURUMU (Ölü Link Koruması)
        uyari_metni = soup.find(string=re.compile("Fiyat bulunamadı|Stokta kalmadı", re.I))
        if uyari_metni:
            return {"urun_adi": urun_adi, "fiyat": "Fiyat Yok", "satici": "-", "link": url}
        
        # 3. Fiyatı Bul
        fiyat = None
        fiyat_etiketi = soup.find("span", class_="pt_v8") 
        if not fiyat_etiketi:
            fiyat_etiketi = soup.find("span", class_="pt_v9") 
            
        if fiyat_etiketi:
            fiyat_metni = fiyat_etiketi.text.strip()
            temiz_fiyat = re.sub(r'[^\d,]', '', fiyat_metni).replace(',', '.')
            if temiz_fiyat:
                fiyat = float(temiz_fiyat)

        # 🚀 4. SATICIYI BULMA (RESİM/LOGO DESTEKLİ)
        satici = "Bulunamadı"
        satici_etiketi = soup.find("span", class_="v_v8")
        if not satici_etiketi:
            satici_etiketi = soup.find("a", class_="v_v8") 
            
        if satici_etiketi:
            # Önce satıcı alanının içinde bir resim (img) var mı diye kontrol et
            logo = satici_etiketi.find("img")
            
            if logo:
                # Logo varsa markanın adını 'alt' veya 'title' özelliklerinden çal
                if logo.get("alt"):
                    satici = logo.get("alt").strip()
                elif logo.get("title"):
                    satici = logo.get("title").strip()
                else:
                    satici = "Logo (İsimsiz)"
            else:
                # Logo yoksa, normal esnaf gibi yazıyla yazılmış demektir
                satici = satici_etiketi.text.replace("Satıcı:", "").strip()
            
        if fiyat is None:
            return {"urun_adi": urun_adi, "fiyat": "Fiyat Yok", "satici": "-", "link": url}

        return {"urun_adi": urun_adi, "fiyat": fiyat, "satici": satici, "link": url}
    
    except Exception as e:
        print(f"SİSTEM HATASI ({url}): {e}")
        return None