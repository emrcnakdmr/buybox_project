import sqlite3

def baglan():
    return sqlite3.connect('urunler.db')

def tablo_olustur():
    conn = baglan()
    cursor = conn.cursor()
    # link sütunundaki UNIQUE kelimesini kaldırdık
    cursor.execute('''CREATE TABLE IF NOT EXISTS urunler 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                       barkod TEXT, 
                       urun_adi TEXT, 
                       kategori TEXT,
                       link TEXT)''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    tablo_olustur()