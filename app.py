from flask import Flask, render_template, request, redirect, send_file
import pandas as pd
import time
from datetime import datetime
from database import baglan, tablo_olustur
from scraper import akakce_tekli_cek

app = Flask(__name__)
tablo_olustur()

# Kategorileri her yerde kullanabilmek için en başa aldık
KATEGORILER = [
    "Giyim & Ayakkabı", "Ev Tekstili", "Züccaciye", "Beyaz Eşya", 
    "Ev Elektroniği", "Küçük Ev Aletleri", "Halı", "Mobilya", 
    "Aksesuar", "Yatak Baza", "Cep Telefonu", "Diğer"
]

@app.route('/')
def index():
    conn = baglan()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM urunler")
    urunler = cursor.fetchall()
    conn.close()
    return render_template('index.html', urunler=urunler, kategoriler=KATEGORILER)

@app.route('/ekle', methods=['POST'])
def ekle():
    barkod = request.form.get('barkod')
    kategori = request.form.get('kategori')
    link = request.form.get('link')
    onay = request.form.get('onay') 
    
    if barkod and link and kategori:
        conn = baglan()
        cursor = conn.cursor()

        if not onay:
            cursor.execute("SELECT urun_adi FROM urunler WHERE link=?", (link,))
            mevcut = cursor.fetchone()
            if mevcut:
                # Link varsa, ana sayfayı "duplicate_data" (kopya uyarısı) ile yeniden açıyoruz
                cursor.execute("SELECT * FROM urunler")
                urunler = cursor.fetchall()
                conn.close()
                duplicate_data = {
                    'barkod': barkod,
                    'kategori': kategori,
                    'link': link,
                    'mevcut_ad': mevcut[0]
                }
                return render_template('index.html', urunler=urunler, kategoriler=KATEGORILER, duplicate_data=duplicate_data)

        # Kullanıcı pop-up'ta onay verdiyse burası çalışır
        veri = akakce_tekli_cek(link)
        urun_adi = veri["urun_adi"] if veri else "Ad Çekilemedi, Linki Kontrol Edin"
        
        try:
            cursor.execute("INSERT INTO urunler (barkod, urun_adi, kategori, link) VALUES (?, ?, ?, ?)", 
                           (barkod, urun_adi, kategori, link))
            conn.commit()
        except Exception as e:
            print(f"Ekleme hatası: {e}")
            
        conn.close()
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
    yeni_barkod = request.form.get('barkod')
    yeni_kategori = request.form.get('kategori')
    yeni_link = request.form.get('link')
    
    if yeni_barkod and yeni_link and yeni_kategori:
        veri = akakce_tekli_cek(yeni_link)
        yeni_ad = veri["urun_adi"] if veri else "Ad Çekilemedi"

        conn = baglan()
        cursor = conn.cursor()
        cursor.execute("UPDATE urunler SET barkod=?, urun_adi=?, kategori=?, link=? WHERE id=?", 
                       (yeni_barkod, yeni_ad, yeni_kategori, yeni_link, id))
        conn.commit()
        conn.close()
        
    return redirect('/')

@app.route('/toplu_ekle', methods=['POST'])
def toplu_ekle():
    if 'excel_dosya' not in request.files:
        return redirect('/')
    file = request.files['excel_dosya']
    if file.filename == '':
        return redirect('/')

    if file:
        try:
            df = pd.read_excel(file)
            conn = baglan()
            cursor = conn.cursor()
            
            for index, row in df.iterrows():
                barkod = str(row.get('Barkod', '')).strip()
                kategori = str(row.get('Kategori', '')).strip()
                link = str(row.get('Link', '')).strip()
                
                if barkod != 'nan' and link != 'nan' and kategori != 'nan' and link:
                    cursor.execute("SELECT id FROM urunler WHERE link=?", (link,))
                    if not cursor.fetchone():
                        veri = akakce_tekli_cek(link)
                        urun_adi = veri["urun_adi"] if veri else "Ad Çekilemedi"
                        cursor.execute("INSERT INTO urunler (barkod, urun_adi, kategori, link) VALUES (?, ?, ?, ?)", 
                                       (barkod, urun_adi, kategori, link))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Excel yükleme hatası: {e}")
            
    return redirect('/')

@app.route('/excel_indir')
def excel_indir():
    conn = baglan()
    cursor = conn.cursor()
    # Hata durumunda boş kalmasın diye veritabanındaki ürün adını da çekiyoruz
    cursor.execute("SELECT barkod, kategori, urun_adi, link FROM urunler")
    urunler_db = cursor.fetchall()
    conn.close()

    tum_veriler = []
    for barkod, kategori, db_urun_adi, link in urunler_db:
        sonuc = akakce_tekli_cek(link)
        
        if sonuc:
            duzenli_veri = {
                "Barkod": barkod,
                "Kategori": kategori,
                "Ürün Adı": sonuc["urun_adi"],
                "Fiyat": sonuc["fiyat"],
                "Satıcı": sonuc["satici"],
                "Link": sonuc["link"]
            }
        else:
            # Siteden veri çekilemezse satırı silmek yerine "Çekilemedi" yazarak Excel'e ekliyoruz
            duzenli_veri = {
                "Barkod": barkod,
                "Kategori": kategori,
                "Ürün Adı": db_urun_adi, # Veritabanındaki eski adını kullan
                "Fiyat": "Çekilemedi",
                "Satıcı": "Çekilemedi",
                "Link": link
            }
            
        tum_veriler.append(duzenli_veri)
        
        # Karşı siteyi yormamak ve ban yememek için her ürün arası 1 saniye bekletiyoruz
        time.sleep(1) 

    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        dosya_adi = f"analiz_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
        df.to_excel(dosya_adi, index=False)
        return send_file(dosya_adi, as_attachment=True)
    return "Veri bulunamadı."

    if tum_veriler:
        df = pd.DataFrame(tum_veriler)
        dosya_adi = f"analiz_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
        df.to_excel(dosya_adi, index=False)
        return send_file(dosya_adi, as_attachment=True)
    return "Veri bulunamadı."

if __name__ == "__main__":
    app.run(debug=True, port=5001)