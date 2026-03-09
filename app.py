from flask import Flask, render_template, request, redirect, send_file
import pandas as pd
from datetime import datetime
from database import baglan, tablo_olustur
from scraper import akakce_tekli_cek
import threading
import time
import random

app = Flask(__name__)
tablo_olustur()

KATEGORILER = [
    "Giyim & Ayakkabı", "Ev Tekstili", "Züccaciye", "Beyaz Eşya", 
    "Ev Elektroniği", "Küçük Ev Aletleri", "Halı", "Mobilya", 
    "Aksesuar", "Yatak Baza", "Diğer"
]

# --- AKILLI HAYALET BOT ---
bot_calisiyor_mu = False
durdur_sinyali = False # Yeni fren sinyalimiz

def arka_plan_kaziyici():
    global bot_calisiyor_mu, durdur_sinyali
    if bot_calisiyor_mu:
        return
    
    bot_calisiyor_mu = True
    durdur_sinyali = False
    
    while True:
        # 🛑 EĞER DURDUR BUTONUNA BASILDIYSA DÖNGÜYÜ KIR
        if durdur_sinyali:
            print("🛑 Bot durduruldu, beklemede.")
            break
            
        conn = baglan()
        cursor = conn.cursor()
        cursor.execute("SELECT id, link FROM urunler WHERE fiyat='Bekleniyor ⏳' LIMIT 1")
        bekleyen_urun = cursor.fetchone()
        
        if not bekleyen_urun:
            conn.close()
            break 
            
        urun_id, link = bekleyen_urun
        conn.close()
        
        veri = akakce_tekli_cek(link)
        
        if veri and veri.get("urun_adi") == "IP Engeli (429)":
            time.sleep(60) 
            continue 
            
        if veri:
            yeni_ad = veri["urun_adi"] if veri["urun_adi"] not in ["Ad Bulunamadı", "Ürün Siteden Kaldırılmış"] else "Geçersiz/Kaldırılmış Link"
            fiyat = str(veri["fiyat"]) if veri["fiyat"] else "Çekilemedi"
            satici = veri["satici"] if veri["satici"] else "Çekilemedi"
        else:
            yeni_ad = "Kırık Link / Sayfa Hatası"
            fiyat = "Çekilemedi"
            satici = "Çekilemedi"
        
        zaman_db = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        conn = baglan()
        cursor = conn.cursor()
        cursor.execute("UPDATE urunler SET urun_adi=?, fiyat=?, satici=?, son_guncelleme=? WHERE id=?", (yeni_ad, fiyat, satici, zaman_db, urun_id))
        conn.commit()
        conn.close()
        
        time.sleep(random.uniform(2.0, 4.0))
        
    # İşlem bittiğinde veya durdurulduğunda sistemi sıfırla
    bot_calisiyor_mu = False
    durdur_sinyali = False


# --- UYGULAMA ROTLARI ---

@app.route('/')
def index():
    global bot_calisiyor_mu, durdur_sinyali # Bu satırı ekledik
    
    conn = baglan()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM urunler")
    toplam = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM urunler WHERE fiyat='Bekleniyor ⏳'")
    bekleyen = cursor.fetchone()[0] or 0
    
    tamamlanan = toplam - bekleyen
    yuzde = int((tamamlanan / toplam) * 100) if toplam > 0 else 0
    
    kalan_saniye = bekleyen * 4.5
    if kalan_saniye > 60:
        kalan_sure_metin = f"{int(kalan_saniye // 60)} dk {int(kalan_saniye % 60)} sn"
    else:
        kalan_sure_metin = f"{int(kalan_saniye)} sn"
        
    if bekleyen == 0:
        kalan_sure_metin = "Tamamlandı"
    
    # SİSTEMDEKİ EN SON GÜNCELLEME ZAMANINI BULMA
    cursor.execute("SELECT MAX(son_guncelleme) FROM urunler WHERE son_guncelleme != 'Bekleniyor ⏳'")
    son_guncelleme_raw = cursor.fetchone()[0]
    if son_guncelleme_raw and son_guncelleme_raw != 'Bekleniyor ⏳':
        try:
            dt = datetime.strptime(son_guncelleme_raw, "%Y-%m-%d %H:%M:%S")
            son_guncelleme_genel = dt.strftime("%d.%m.%Y %H:%M") # Kullanıcıya gösterilecek güzel format
        except:
            son_guncelleme_genel = "Bilinmiyor"
    else:
        son_guncelleme_genel = "Henüz güncelleme yapılmadı"
    
    cursor.execute("SELECT * FROM urunler")
    urunler = cursor.fetchall()
    conn.close()
    
    # EĞER DURDUR SİNYALİ VERİLDİYSE BOT HENÜZ DURMAMIŞ OLSA BİLE EKRANI DURMUŞ GİBİ GÖSTER
    bot_aktif_durum = bot_calisiyor_mu and not durdur_sinyali
    
    return render_template('index.html', urunler=urunler, kategoriler=KATEGORILER, 
                           toplam=toplam, tamamlanan=tamamlanan, bekleyen=bekleyen, 
                           yuzde=yuzde, kalan_sure_metin=kalan_sure_metin, 
                           son_guncelleme_genel=son_guncelleme_genel,
                           bot_aktif=bot_aktif_durum) # Sadece bu değişkenin adını değiştirdik

# YENİ EKLENEN BUTON ROTALARI
@app.route('/durdur')
def durdur():
    global durdur_sinyali
    durdur_sinyali = True
    return redirect('/')

@app.route('/devam_et')
def devam_et():
    global durdur_sinyali
    durdur_sinyali = False
    threading.Thread(target=arka_plan_kaziyici).start()
    return redirect('/')



# YENİ ÖZELLİK: MANUEL OLARAK TÜMÜNÜ GÜNCELLEME BUTONU
@app.route('/tumunu_guncelle')
def tumunu_guncelle():
    global durdur_sinyali
    durdur_sinyali = False # Yeni işlem geldiği için freni kaldır
    conn = baglan()

    conn = baglan()
    cursor = conn.cursor()
    # Tüm verilerin fiyatını "Bekleniyor"a çekerek botun yeniden taramasını sağlıyoruz
    cursor.execute("UPDATE urunler SET fiyat='Bekleniyor ⏳', satici='Bekleniyor ⏳', son_guncelleme='Bekleniyor ⏳'")
    conn.commit()
    conn.close()
    
    # Botu uyandır
    threading.Thread(target=arka_plan_kaziyici).start()
    return redirect('/')

@app.route('/ekle', methods=['POST'])
def ekle():
    global durdur_sinyali
    durdur_sinyali = False # Freni kaldır

    barkod = request.form.get('barkod')
    kategori = request.form.get('kategori')
    link = request.form.get('link')
    onay = request.form.get('onay') 
    
    if barkod and link and kategori:
        conn = baglan()
        cursor = conn.cursor()

        # Eğer kullanıcıdan henüz "Yine de Ekle" onayı gelmediyse linki kontrol et
        if not onay:
            cursor.execute("SELECT urun_adi FROM urunler WHERE link=?", (link,))
            mevcut = cursor.fetchone()
            
            if mevcut:
                # 1. Pop-up için gereken uyarı paketini hazırla
                duplicate_data = {'barkod': barkod, 'kategori': kategori, 'link': link, 'mevcut_ad': mevcut[0]}
                
                # 2. Ana sayfanın çökmemesi için gerekli istatistikleri de mecburen hesapla
                cursor.execute("SELECT * FROM urunler")
                urunler = cursor.fetchall()
                
                cursor.execute("SELECT COUNT(*) FROM urunler")
                toplam = cursor.fetchone()[0] or 0
                
                cursor.execute("SELECT COUNT(*) FROM urunler WHERE fiyat='Bekleniyor ⏳'")
                bekleyen = cursor.fetchone()[0] or 0
                tamamlanan = toplam - bekleyen
                yuzde = int((tamamlanan / toplam) * 100) if toplam > 0 else 0
                
                kalan_saniye = bekleyen * 4.5
                kalan_sure_metin = f"{int(kalan_saniye // 60)} dk {int(kalan_saniye % 60)} sn" if kalan_saniye > 60 else f"{int(kalan_saniye)} sn"
                if bekleyen == 0: kalan_sure_metin = "Tamamlandı"
                
                cursor.execute("SELECT MAX(son_guncelleme) FROM urunler WHERE son_guncelleme != 'Bekleniyor ⏳'")
                son_guncelleme_raw = cursor.fetchone()[0]
                if son_guncelleme_raw and son_guncelleme_raw != 'Bekleniyor ⏳':
                    dt = datetime.strptime(son_guncelleme_raw, "%Y-%m-%d %H:%M:%S")
                    son_guncelleme_genel = dt.strftime("%d.%m.%Y %H:%M")
                else:
                    son_guncelleme_genel = "Henüz güncelleme yapılmadı"
                    
                conn.close()
                
                # 3. Sayfayı pop-up ile birlikte yeniden render et
                return render_template('index.html', urunler=urunler, kategoriler=KATEGORILER, 
                                       toplam=toplam, tamamlanan=tamamlanan, bekleyen=bekleyen, 
                                       yuzde=yuzde, kalan_sure_metin=kalan_sure_metin, 
                                       son_guncelleme_genel=son_guncelleme_genel,
                                       duplicate_data=duplicate_data)

        # Eğer link yeniyse veya kullanıcı pop-up'ta "Yine de Devam Et" butonuna bastıysa kaydı yap
        zaman_db = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute("INSERT INTO urunler (barkod, urun_adi, kategori, link, fiyat, satici, son_guncelleme) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                           (barkod, "Bekleniyor ⏳", kategori, link, "Bekleniyor ⏳", "Bekleniyor ⏳", zaman_db))
            conn.commit()
        except Exception as e:
            print(f"Ekleme hatası: {e}")
            
        conn.close()
        
        # Ekledikten sonra arka plan botunu uyandır
        threading.Thread(target=arka_plan_kaziyici).start()
        
    return redirect('/')

@app.route('/toplu_ekle', methods=['POST'])
def toplu_ekle():
    global durdur_sinyali
    durdur_sinyali = False # Freni kaldır
    
    if 'excel_dosya' not in request.files: return redirect('/')
    file = request.files['excel_dosya']
    if file:
        try:
            df = pd.read_excel(file)
            conn = baglan()
            cursor = conn.cursor()
            for index, row in df.iterrows():
                barkod, kategori, link = str(row.get('Barkod', '')).strip(), str(row.get('Kategori', '')).strip(), str(row.get('Link', '')).strip()
                if barkod != 'nan' and link != 'nan' and kategori != 'nan' and link:
                    cursor.execute("SELECT id FROM urunler WHERE link=?", (link,))
                    if not cursor.fetchone():
                        cursor.execute("INSERT INTO urunler (barkod, urun_adi, kategori, link, fiyat, satici, son_guncelleme) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                                       (barkod, "Bekleniyor ⏳", kategori, link, "Bekleniyor ⏳", "Bekleniyor ⏳", "Bekleniyor ⏳"))
            conn.commit()
            conn.close()
            threading.Thread(target=arka_plan_kaziyici).start()
        except: pass
    return redirect('/')

@app.route('/sil/<int:id>')
def sil(id):
    conn = baglan()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM urunler WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/duzenle/<int:id>', methods=['POST'])
def duzenle(id):
    y_barkod, y_kategori, y_link = request.form.get('barkod'), request.form.get('kategori'), request.form.get('link')
    if y_barkod and y_link and y_kategori:
        conn = baglan()
        cursor = conn.cursor()
        cursor.execute("UPDATE urunler SET barkod=?, urun_adi=?, kategori=?, link=?, fiyat=?, satici=?, son_guncelleme=? WHERE id=?", 
                       (y_barkod, "Bekleniyor ⏳", y_kategori, y_link, "Bekleniyor ⏳", "Bekleniyor ⏳", "Bekleniyor ⏳", id))
        conn.commit()
        conn.close()
        threading.Thread(target=arka_plan_kaziyici).start()
    return redirect('/')

@app.route('/excel_indir')
def excel_indir():
    conn = baglan()
    # Excel sütunlarına Son Güncelleme'yi de ekledik
    df = pd.read_sql_query("SELECT barkod as Barkod, kategori as Kategori, urun_adi as 'Ürün Adı', fiyat as Fiyat, satici as 'Satıcı', link as Link, son_guncelleme as 'Son Güncelleme Tarihi' FROM urunler", conn)
    conn.close()

    # Tarih formatını Excel'de güzel görünmesi için düzeltiyoruz
    df['Son Güncelleme Tarihi'] = df['Son Güncelleme Tarihi'].apply(lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M") if pd.notnull(x) and x != 'Bekleniyor ⏳' else x)

    if not df.empty:
        dosya_adi = f"analiz_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
        df.to_excel(dosya_adi, index=False)
        return send_file(dosya_adi, as_attachment=True)
    return "Veri bulunamadı."

if __name__ == "__main__":
    app.run(debug=True, port=5001)