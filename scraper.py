from curl_cffi import requests as cureq
from bs4 import BeautifulSoup
import re
import time

# 1. SİLAH: Oturum (Session) başlatıyoruz. Tüm istekler aynı tarayıcıdan gidiyormuş gibi olacak.
session = cureq.Session(impersonate="chrome110")

def akakce_tekli_cek(url):
    try:
        # 2. SİLAH: İnsan kimliği (Headers) ekliyoruz
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.akakce.com/",
            "DNT": "1" # Do Not Track (Gerçekçi bir tarayıcı ayarı)
        }
        
        # İstek atarken session kullanıyoruz
        response = session.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"HATA - IP Engeli veya Hatalı Link: {response.status_code} -> {url}")
            return None
            
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Ürün Adı
        urun_adi_etiketi = soup.find("h1")
        urun_adi = urun_adi_etiketi.text.strip() if urun_adi_etiketi else "Ad Bulunamadı"
        
        # 3. SİLAH: Fiyatı Bulma (Daha sağlam mantık, alternatif yerlere de bakar)
        fiyat = None
        fiyat_etiketi = soup.find("span", class_="pt_v8") 
        if not fiyat_etiketi:
            fiyat_etiketi = soup.find("span", class_="pt_v9") # Bazen indirimli fiyat class'ı farklı olur
            
        if fiyat_etiketi:
            fiyat_metni = fiyat_etiketi.text.strip()
            temiz_fiyat = re.sub(r'[^\d,]', '', fiyat_metni).replace(',', '.')
            if temiz_fiyat:
                fiyat = float(temiz_fiyat)

        # Satıcı İsmini Bulma
        satici = "Bulunamadı"
        satici_etiketi = soup.find("span", class_="v_v8")
        if not satici_etiketi:
            satici_etiketi = soup.find("a", class_="v_v8") # Bazen satıcı bir link(a) etiketi içindedir
            
        if satici_etiketi:
            satici = satici_etiketi.text.replace("Satıcı:", "").strip()
            
        # Eğer fiyat hala None ise stokta olmayabilir
        if fiyat is None:
            stok_kontrol = soup.find(string=re.compile("Stokta kalmadı", re.I))
            if stok_kontrol:
                fiyat = "Stokta Yok"
                satici = "-"

        return {"urun_adi": urun_adi, "fiyat": fiyat, "satici": satici, "link": url}
    
    except Exception as e:
        print(f"SİSTEM HATASI ({url}): {e}")
        return None