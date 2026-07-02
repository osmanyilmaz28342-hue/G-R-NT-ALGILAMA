╔══════════════════════════════════════════════════════════════╗
║          Shift + Sag Click Bot  v9.0                         ║
║          OpenCV + mss + Bezier + Win32 SendInput             ║
╚══════════════════════════════════════════════════════════════╝

■ HIZLI BASLANGIC
  1. calistir.bat dosyasina cift tıkla (veya sag tik → Yonetici)
  2. "Temel" sekmesinden referans gorsel(ler) ekle
  3. Hedef pencereyi sec (veya bos birak = tum ekran)
  4. ▶ Baslat (veya F9)

■ GEREKSINIMLER
  - Windows 10/11
  - Python 3.10+  (python.org → "Add to PATH" isaretli kur)
  - Internet baglantisi (ilk kurulumda pip paketleri indirir)

■ DOSYALAR
  main.py          → Ana uygulama + GUI
  detector.py      → Ekran eslestirme motoru (mss, CLAHE, NMS)
  clicker.py       → Win32 SendInput tiklama (7 mod)
  humanizer.py     → Bezier egri insan hareketi
  overlay.py       → Seffaf ekran overlay
  config.py        → Ayar kaliciligi
  session_log.py   → Log + CSV export
  profiler.py      → Profil yonetimi
  region_selector.py → Ekranda bolge seçici
  calistir.bat     → Baslatici (pip + python)

■ SEKMELER
  Temel       : Template, pencere, guven, tekrar/aralik
  Tiklama     : Mod secimi, insan hareketi, gecikme ayarlari
  Tarama      : Multi-scale, esleme yontemi, bölge, on-isleme
  Zamanlayici : Otomatik baslat/durdur, max tiklama, molalar
  Profiller   : Ayarlari isimle kaydet/yukle/dis aktar
  Istatistik  : Canli grafik, tiklama/dk, CSV export

■ TIKLAMA MODLARI
  Shift + Sag Tik   (varsayilan)
  Sol Tik
  Sag Tik
  Cift Sol Tik
  Ctrl + Sol Tik
  Ctrl + Sag Tik
  Shift + Sol Tik

■ HOTKEY
  F9   → Baslat
  F10  → Durdur
  F8   → Overlay gizle/goster
  (Yonetici olarak calistirilmazsa hotkey calismayabilir)

■ INSAN HAREKETI (ANTI-DETECTION)
  "Tiklama" sekmesinden aktif edilir.
  Bezier egri + overshoot + Gaussian jitter ile fare
  hareketini insan gibi simule eder.
  Hiz faktoru: 0.3 (cok yavas) → 4.0 (cok hizli)

■ MULTI-SCALE
  Varsayilan: 0.50x → 2.00x arasi 12 adim
  Uzak/kucuk hedefler icin min'i dusur (0.3x)
  Buyuk hedefler icin max'i artir (3.0x)

■ CLAHE (Kontrast Normalizasyon)
  Aydinlatma degisikliklerine karsi dayaniklilik saglar.
  Ozellikle gece/gunduz degisen oyun ekranlari icin onerilir.

■ PROFIL SISTEMI
  Farkli oyunlar/hedefler icin ayri profiller kaydet.
  JSON formatında disari/iceri aktar.

■ LOG / CSV
  Her oturum: logs/YYYY-MM-DD_HH-MM-SS.log
  CSV export: logs/YYYY-MM-DD_HH-MM-SS_stats.csv
  Istatistik sekmesinden manuel export da yapilabilir.

■ SORUN GIDERME
  "Python bulunamadi"    → python.org'dan kur, PATH isaretli
  "mss YOK"             → pip install mss
  Esleme bulunamıyor     → Guven'i 0.60-0.70'e dusurun
  Esleme cok fazla       → Guven'i artirin, CLAHE'i acin
  Tiklama calismıyor     → Yonetici olarak calistirin
  Overlay gorunmuyor     → F8 tusu veya "overlay etkin" isaretli mi?

══════════════════════════════════════════════════════════════
