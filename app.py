import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================================
# IMPORT FUNGSI NEON DARI FILE database.py
# ==========================================================
from database import (
    dapatkan_koneksi_neon,
    simpan_log_ke_neon,
    hitung_dan_ambil_log_db,     
    ambil_keyword_medsos_db,     
    tambah_keyword_medsos_db,
    ambil_status_storage_neon,
    
    # 🛠️ REFERENSI DATA MASTER (DISESUAIKAN)
    ambil_data_rujukan_hiv_positif,  
    ambil_set_reaktif_sebelumnya,       # ✨ Tambahkan ini untuk validasi is_reaktif_sebelumnya
    ambil_set_layanan_prep_valid,       # ✨ Tambahkan ini untuk validasi PrEP
    ambil_database_layanan,          
    
    # 🛠️ PROSES SIMPAN DATA REVIEWS
    simpan_agregasi_ke_neon,          # Untuk Penjangkauan
    simpan_agregasi_rujukan_db,       # Untuk Rujukan
    simpan_hasil_review_utama_db,     # Untuk Gabungan Utama
    
    # ⚡ BARU: TRANSAKSI MULTI-TABEL SEKALIGUS
    simpan_paket_validasi_ke_tiga_tabel, 
    
    # 📊 BARU: METRIK AKURASI KARTU SKOR GANDA
    simpan_metrik_akurasi_db,
    ambil_metrik_akurasi_terakhir,
    
    # 🔥 AMBIL DATA TERAKHIR SINKRON DENGAN APP STATE
    ambil_agregasi_penjangkauan_terakhir,  
    ambil_agregasi_rujukan_terakhir,       
    ambil_hasil_review_utama_terakhir      
)

# ==========================================================
# 0. KONFIGURASI UTAMA & TEMA GLASSMORPHISM
# ==========================================================
st.set_page_config(page_title="Executive Review - PKBI Jabar", page_icon="📊", layout="wide")

def set_modern_theme():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, .stApp { font-family: 'Inter', sans-serif; }
    i, .material-icons, .material-symbols-rounded, [class^="stIcon"], [class*="icon"] {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important; }
    [data-testid="stSidebar"] { background-color: #0f172a !important; }

    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }
    
    .stTabs [data-baseweb="tab-list"] { background-color: transparent !important; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; }
    .stTabs [aria-selected="true"] { color: #38bdf8 !important; border-bottom-color: #38bdf8 !important; }

    h1, h2, h3, h4, .main-title { color: #f8fafc !important; }
    p, span, label, .sub-title { color: #cbd5e1 !important; }
    
    .main-title { font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem; letter-spacing: -0.5px;}
    .sub-title { font-size: 1.1rem; color: #94a3b8 !important; margin-bottom: 2rem; font-weight: 400;}
    
    [data-testid="stMetricValue"] { color: #38bdf8 !important; font-weight: 700; }
    [data-testid="stMetricDelta"] { font-weight: 500; }

    /* --- JINAKKAN KOTAK HOVER PLOTLY SECARA TOTAL --- */
    div[data-testid="stPlotlyChart"] .hoverlayer path {
        fill: #1e293b !important;       /* Ubah latar belakang kotak menjadi slate gelap */
        stroke: #38bdf8 !important;     /* Beri garis tepi biru muda senada primaryColor Anda */
        fill-opacity: 0.95 !important;  /* Menjaga kotak tetap tegas dan tidak transparan */
    }
    
    div[data-testid="stPlotlyChart"] .hoverlayer text {
        fill: #f8fafc !important;       /* Paksa warna teks utama menjadi putih cerah sesuai textColor */
    }
    
    div[data-testid="stPlotlyChart"] .hoverlayer text tspan {
        fill: #f8fafc !important;       /* Kunci warna untuk sub-teks di dalam elemen grafik */
    }
</style>
    """, unsafe_allow_html=True)

set_modern_theme()

# ==========================================================
# 0. POPUP ABSENSI & INISIALISASI MASTER LEMBAGA (RBAC SYSTEM)
# ==========================================================
if "master_lembaga" not in st.session_state:
    st.session_state.master_lembaga = [
        {"Nama Lembaga": "BINA MUDA GEMILANG", "Status": "SSR"},
        {"Nama Lembaga": "PKBI JAWA BARAT", "Status": "SR"},
        {"Nama Lembaga": "GRAPIKS", "Status": "SSR"},
        {"Nama Lembaga": "LEMBAGA KASIH INDONESIA KITA", "Status": "SSR"},
        {"Nama Lembaga": "LENSA SUKABUMI", "Status": "SSR"},
        {"Nama Lembaga": "PESONA BUMI PASUNDAN", "Status": "SSR"},
        {"Nama Lembaga": "PETIK", "Status": "SSR"},
        {"Nama Lembaga": "PKBI CABANG SUBANG", "Status": "SSR"},
        {"Nama Lembaga": "PKBI CIREBON", "Status": "SSR"},
        {"Nama Lembaga": "PKBI GARUT", "Status": "SSR"},
        {"Nama Lembaga": "WAHANA CITA INDONESIA", "Status": "SSR"},
        {"Nama Lembaga": "YAYASAN PELANGI MALUKU", "Status": "SSR"},
        {"Nama Lembaga": "YAYASAN PONTIANAK PLUS - OUTREACH", "Status": "SSR"},
        {"Nama Lembaga": "YAYASAN SRIKANDI PASUNDAN", "Status": "SSR"},
        {"Nama Lembaga": "YAYASAN SRIKANDI PERINTIS", "Status": "SSR"},
        {"Nama Lembaga": "YAYASAN VESTA INDONESIA", "Status": "SSR"}
    ]

if "user_authenticated" not in st.session_state: st.session_state.user_authenticated = False
if "current_lembaga" not in st.session_state: st.session_state.current_lembaga = None
if "current_role" not in st.session_state: st.session_state.current_role = None

@st.dialog("📋 Login Aplikasi")
def popup_absensi():
    st.write("Silahkan pilih nama instansi/lembaga Anda untuk masuk ke sistem.")
    list_pilihan = [l["Nama Lembaga"] for l in st.session_state.master_lembaga]
    lembaga_pilihan = st.selectbox("Pilih Nama Lembaga:", ["-- Pilih Lembaga --"] + list_pilihan)
    
    if lembaga_pilihan != "-- Pilih Lembaga --":
        role_terdeteksi = next(l["Status"] for l in st.session_state.master_lembaga if l["Nama Lembaga"] == lembaga_pilihan)
        st.info(f"Sistem mendeteksi peran Anda sebagai: **{role_terdeteksi}**")
        if st.button("Konfirmasi & Masuk Aplikasi", use_container_width=True):
            st.session_state.current_lembaga = lembaga_pilihan
            st.session_state.current_role = role_terdeteksi
            st.session_state.user_authenticated = True
            st.rerun()

if not st.session_state.user_authenticated:
    popup_absensi()
    st.warning("🔒 Konten Utama Terkunci. Anda wajib mengisi absensi lembaga pada popup di atas.")
    st.stop()


# ==========================================================
# 0. MANAGEMENT DEFAULT STATE & INIT DATA (Tersinkron Neon DB)
# ==========================================================
if 'total_entri' not in st.session_state: st.session_state['total_entri'] = 0
if 'proses_selesai' not in st.session_state: st.session_state['proses_selesai'] = False
if 'aturan_kustom' not in st.session_state: st.session_state['aturan_kustom'] = []

# Pemicu untuk memaksa baca ulang data dari DB setelah tombol validasi selesai diproses
pemicu_baca_ulang = st.session_state.get('proses_selesai', False)

# 🎯 --- BAGIAN PERBAIKAN BARU: TARIK METRIK KARTU SKOR DARI DATABASE SAAT REFRESH ---
if ('total_entri_penjangkauan' not in st.session_state or pemicu_baca_ulang):
    # Set nilai default awal di session state
    st.session_state['total_entri_penjangkauan'] = 0
    st.session_state['total_entri_rujukan'] = 0
    st.session_state['temuan_penjangkauan'] = 0
    st.session_state['temuan_rujukan'] = 0
    st.session_state['akurasi_penjangkauan'] = 100.0
    st.session_state['akurasi_rujukan'] = 100.0
    
    try:
        from database import dapatkan_koneksi_neon
        conn = dapatkan_koneksi_neon()
        if conn:
            with conn.cursor() as cur:
                # Mengambil seluruh riwayat metrik akurasi dari yang paling baru
                # Sesuai dengan kolom di database Anda: total_data_diproses dan tingkat_akurasi
                cur.execute("""
                    SELECT kategori, total_data_diproses, total_baris_temuan, tingkat_akurasi 
                    FROM akurasi_review_data 
                    ORDER BY id DESC;
                """)
                rows = cur.fetchall()
                
                # Ambil 1 baris terbaru unik untuk masing-masing kategori
                kategori_terisi = set()
                for r in rows:
                    kat = str(r[0]).strip().lower()
                    if kat not in kategori_terisi:
                        if kat == 'penjangkauan':
                            st.session_state['total_entri_penjangkauan'] = int(r[1])
                            st.session_state['temuan_penjangkauan'] = int(r[2])
                            st.session_state['akurasi_penjangkauan'] = float(r[3])
                            kategori_terisi.add(kat)
                        elif kat == 'rujukan':
                            st.session_state['total_entri_rujukan'] = int(r[1])
                            st.session_state['temuan_rujukan'] = int(r[2])
                            st.session_state['akurasi_rujukan'] = float(r[3])
                            kategori_terisi.add(kat)
                    # Jika kedua kategori sudah mendapatkan data terbarunya, stop loop
                    if len(kategori_terisi) == 2:
                        break
            conn.close()
    except Exception as e:
        pass

# --- 1. REKAP HASIL REVIEW DATA PENJANGKAUAN SSR (Tabel 1) ---
if ('df_penjangkauan' not in st.session_state or st.session_state['df_penjangkauan'] is None or pemicu_baca_ulang):
    try:
        from database import ambil_agregasi_penjangkauan_terakhir
        df_pj, ts_pj = ambil_agregasi_penjangkauan_terakhir()
        if df_pj is not None and not df_pj.empty:
            st.session_state['df_penjangkauan'] = df_pj
            # ALIAS: Mengisi nama variabel lama agar dibaca oleh komponen UI lama
            st.session_state['df_tabel_atas'] = df_pj 
            st.session_state['df_tabel_penjangkauan'] = df_pj 
            st.session_state['ts_terakhir_penjangkauan'] = ts_pj
        else:
            st.session_state['df_penjangkauan'] = pd.DataFrame()
            st.session_state['df_tabel_atas'] = pd.DataFrame()
            st.session_state['ts_terakhir_penjangkauan'] = datetime.now()
    except Exception as e:
        st.session_state['df_penjangkauan'] = pd.DataFrame()
        st.session_state['df_tabel_atas'] = pd.DataFrame()
        st.session_state['ts_terakhir_penjangkauan'] = datetime.now()

# --- 2. REKAP HASIL REVIEW DATA RUJUKAN SSR (Tabel 2) ---
if ('df_rujukan' not in st.session_state or st.session_state['df_rujukan'] is None or pemicu_baca_ulang):
    try:
        from database import ambil_agregasi_rujukan_terakhir
        df_rj, ts_rj = ambil_agregasi_rujukan_terakhir()
        if df_rj is not None and not df_rj.empty:
            st.session_state['df_rujukan'] = df_rj
            st.session_state['df_tabel_rujukan'] = df_rj 
            st.session_state['ts_terakhir_rujukan'] = ts_rj
        else:
            st.session_state['df_rujukan'] = pd.DataFrame()
            st.session_state['ts_terakhir_rujukan'] = datetime.now()
    except Exception as e:
        st.session_state['df_rujukan'] = pd.DataFrame()
        st.session_state['ts_terakhir_rujukan'] = datetime.now()

# --- 3. HASIL REVIEW VALIDASI DATA GABUNGAN UTAMA (Tabel 3) ---
if ('df_review_utama' not in st.session_state or st.session_state['df_review_utama'] is None or pemicu_baca_ulang):
    try:
        from database import ambil_hasil_review_utama_terakhir
        df_ut, ts_ut = ambil_hasil_review_utama_terakhir()
        if df_ut is not None and not df_ut.empty:
            st.session_state['df_review_utama'] = df_ut
            # ALIAS UTAMA: Mengisi data ke variabel tabel bawah agar UI-nya tidak kosong
            st.session_state['df_tabel_bawah'] = df_ut 
            st.session_state['ts_terakhir_utama'] = ts_ut
        else:
            st.session_state['df_review_utama'] = pd.DataFrame()
            st.session_state['df_tabel_bawah'] = pd.DataFrame()
            st.session_state['ts_terakhir_utama'] = datetime.now()
    except Exception as e:
        st.session_state['df_review_utama'] = pd.DataFrame()
        st.session_state['df_tabel_bawah'] = pd.DataFrame()
        st.session_state['ts_terakhir_utama'] = datetime.now()

# --- B. INISIALISASI KEYWORD MEDSOS ---
if 'medsoc_keywords' not in st.session_state:
    try:
        from database import ambil_keyword_medsos_db
        st.session_state['medsoc_keywords'] = ambil_keyword_medsos_db()
    except Exception:
        st.session_state['medsoc_keywords'] = []

def ambil_keyword_medsos():
    keywords = st.session_state.get('medsoc_keywords', [])
    return sorted(keywords) if keywords else []

# --- C. TAMPILAN JUDUL UTAMA ---
st.markdown('<div class="main-title">📊 Tools Review Data PKBI Jawa Barat</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem Validasi Kualitas Data Penjangkauan & Rujukan</div>', unsafe_allow_html=True)


# ==========================================================
# FUNGSI HELPER
# ==========================================================
def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom) or str(teks_kolom).strip().lower() in ['', 'nan']: 
        return False
    clean_str = str(teks_kolom).replace("'", "").replace(" ", "")
    mentah_list = clean_str.split(",")
    list_kode = [kode.split('.')[0] for kode in mentah_list if kode != '']
    return str(kode_target) in list_kode

def buat_fungsi_validasi_kustom(target, kondisi, pembanding):
    if kondisi == "Panjang karakter tidak sama dengan (!=)":
        return lambda c: str(c.get(target, '')).strip() != '' and len(str(c.get(target, ''))) != int(pembanding)
    elif kondisi == "Panjang karakter kurang dari ( < )":
        return lambda c: str(c.get(target, '')).strip() != '' and len(str(c.get(target, ''))) < int(pembanding)
    elif kondisi == "Kosong / Blank":
        return lambda c: str(c.get(target, '')).strip() == '' or pd.isna(c.get(target)) or str(c.get(target)) == 'nan'
    elif kondisi == "Mengandung teks tertentu":
        return lambda c: pembanding.lower() in str(c.get(target, '')).lower()
    elif kondisi == "Sama dengan teks/angka tertentu":
        return lambda c: str(c.get(target, '')).strip().lower() == pembanding.strip().lower()
    return lambda c: False

# 🔥 REKOMENDASI: Tempat Penyimpanan Fungsi PrEP Valid
def ambil_set_layanan_prep_valid():
    """Mengambil kombinasi (Lembaga SSR, Nama Layanan) yang valid untuk PrEP dari database."""
    conn = dapatkan_koneksi_neon()
    set_prep_valid = set()
    
    if conn is None:
        return set_prep_valid
        
    try:
        with conn.cursor() as cur:
            # Menggunakan LOWER() dan LIKE '%prep%' agar pencarian teks bersifat fleksibel
            query = """
                SELECT LOWER(TRIM(lembaga_ssr_iu)), LOWER(TRIM(nama_layanan))
                FROM public.database_layanan
                WHERE LOWER(jenis) LIKE '%prep%';
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            # Simpan ke dalam Python set berupa tuple (lembaga, nama_layanan)
            for r in rows:
                if r[0] and r[1]:
                    set_prep_valid.add((r[0], r[1]))
                    
    except Exception as e:
        st.error(f"Gagal memuat referensi tabel database_layanan: {e}")
    finally:
        conn.close()
        
    return set_prep_valid

def hitung_dan_ambil_log_db():
    dict_revisi, dict_justifikasi = {}, {}
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT Kategori_Data, Lembaga_SSR, Tanggal, ID_Klien, Indikator_Kesalahan_Data, is_revisi, Justifikasi 
                    FROM log_hasil_review_data
                """)
                rows = cur.fetchall()
                
                for r in rows:
                    kat_data, ssr, tgl, id_klien, ind, is_rev, just = r
                    
                    # 🟢 STANDARISASI KAPITAL: WAJIB SINKRON 100% DENGAN ENGINE VALIDASI
                    v_kat = str(kat_data).strip().upper()  # Menjadi "RUJUKAN" / "PENJANGKAUAN"
                    v_ssr = str(ssr).strip().upper()
                    v_tgl = str(tgl).split(' ')[0].strip() # Hanya ambil YYYY-MM-DD
                    v_id  = str(id_klien).replace("'", "").strip().upper()
                    v_ind = str(ind).strip().upper()
                    
                    # Bentuk key gabungan unik
                    key = f"{v_kat}_{v_ssr}_{v_tgl}_{v_id}_{v_ind}"
                    
                    # 🎯 SOLUSI UTAMA: Simpan nilai boolean asli dari database (True/False) ke dictionary
                    is_rev_bool = True if (is_rev is True or str(is_rev).strip().lower() == 'true') else False
                    dict_revisi[key] = is_rev_bool
                    
                    # Simpan catatan justifikasi jika ada teksnya
                    if just and str(just).strip() not in ['', 'nan', 'None']: 
                        dict_justifikasi[key] = str(just).strip()
                        
        except Exception as e:
            pass
        finally:
            conn.close()
            
    return dict_revisi, dict_justifikasi

# ==========================================================
# 1. ATURAN VALIDASI BAWAAN (PENJANGKAUAN)
# ==========================================================
ATURAN_VALIDASI_BAWAAN = [
    {"nama": "Kode Petugas Kosong", "periksa": lambda c: pd.isna(c['row'].get('Kode Petugas')) or str(c['row'].get('Kode Petugas')).strip() in ['', 'nan', 'None']},
    {"nama": "Tahun dalam tanggal penjangkauan lebih besar/kecil dari tahun sekarang", "periksa": lambda c: pd.notna(c['tgl_p']) and c['tgl_p'].year != c['tahun_sekarang']},
    {"nama": "Tanggal lebih besar dari tanggal hari ini", "periksa": lambda c: pd.notna(c['tgl_p']) and c['tgl_p'] > c['hari_ini']},
    {"nama": "IDKD kurang/lebih dari 10 digit karakter", "periksa": lambda c: c['id_clean'] != '' and (len(c['id_clean']) != 10 or not c['id_clean'].isalnum())},
    {"nama": "Digit nama kurang/lebih dari 4 digit karakter", "periksa": lambda c: c['id_clean'] != '' and (len(c['id_clean']) < 4 or not (c['id_clean'][:4].isalpha() or (c['id_clean'][:3].isalpha() and c['id_clean'][3] == '0')))},
    {"nama": "Digit tanggal lahir lebih/kurang dari 6 digit angka", "periksa": lambda c: c['id_clean'] != '' and len(c['id_clean']) == 10 and not c['id_clean'][4:].isdigit()},
    {"nama": "Ada tanda titik (.) pada penulisan IDKD", "periksa": lambda c: '.' in str(c['row'].get('ID Klien', ''))},
    {"nama": "Ada spasi pada penulisan IDKD", "periksa": lambda c: ' ' in str(c['row'].get('ID Klien', ''))},
    {"nama": "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)", "periksa": lambda c: c['df_ref'] is not None and c['v_ssr'] and f"{c['v_ssr']}_{c['id_clean']}" in c['ref_ssr_id_to_nik'] and c['ref_ssr_id_to_nik'][f"{c['v_ssr']}_{c['id_clean']}"] != c['nik_clean']},
    {"nama": "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)", "periksa": lambda c: c['df_ref'] is not None and c['v_ssr'] and c['nik_clean'] != '' and f"{c['nik_clean']}_{c['v_ssr']}" in c['ref_nik_ssr_to_id'] and c['ref_nik_ssr_to_id'][f"{c['nik_clean']}_{c['v_ssr']}"] != c['id_clean']},
    {"nama": "Usia KD dibawah 16 tahun (konfirmasi)", "periksa": lambda c: pd.notna(c['umur']) and str(c['umur']).strip() != '' and float(c['umur']) < 17},
    {"nama": "Usia KD diatas 70 tahun (konfirmasi)", "periksa": lambda c: pd.notna(c['umur']) and str(c['umur']).strip() != '' and float(c['umur']) > 70},
    {"nama": "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)", "periksa": lambda c: c['id_clean'] != '' and len(c['id_clean']) == 10 and c['nik_clean'] != '' and len(c['nik_clean']) == 16 and c['id_clean'][4:6] != (str(c['row'].get('NIK', '')) if str(c['row'].get('NIK', '')).startswith("'") else "'" + c['nik_clean'])[11:13]},
    {"nama": "NIK kurang/lebih dari 16 digit (konfirmasi)", "periksa": lambda c: c['nik_clean'] not in ['', 'nan', 'none', 'NaN', "'"] and len(c['nik_clean']) != 16},
    {"nama": "Kesalahan dalam penulisan NIK (00) (konfirmasi)", "periksa": lambda c: c['nik_clean'] != '' and c['nik_clean'].endswith('00')},
    {"nama": "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)", "periksa": lambda c: len(c['nik_clean']) == 16 and c['jk'] == '1' and int(c['nik_clean'][6:8]) > 31 if c['nik_clean'].isdigit() and len(c['nik_clean'])>=8 else False},
    {"nama": "LSL/Waria tapi jenis kelamin perempuan", "periksa": lambda c: c['v_tipe_sasaran'] in ['1304', '1301'] and c['jk'] == '2'},
    {"nama": "Jenis kontak dengan Jenis Kegiatan tidak sesuai", "periksa": lambda c: (c['jns_kontak'] == '1' and c['jns_kegiatan'] not in ['1', '5']) or (c['jns_kontak'] == '2' and c['jns_kegiatan'] not in ['2', '3', '4', '6', '7']) or (c['jns_kontak'] == '3' and c['jns_kegiatan'] != '8')},
    {"nama": "Jenis kontak Individual/kelompok tapi kolom Virtual dan Tatap Muka (VC1) tidak diisi", "periksa": lambda c: c['jns_kontak'] in ['1', '2'] and (c['vc1'] == '' or c['vc1'] == 'nan')},
    {"nama": "VO tapi kolom Virtual dan Tatap Muka (VC1) diisi angka 1", "periksa": lambda c: c['is_vo'] and c['vc1'] == '1'},
    {"nama": "Penjangkauan tatap muka tapi lokasi outreach diindikasi ada nama medsos", "periksa": lambda c: str(c.get('jns_kontak', '')).split('.')[0].strip() in ['1', '2'] and c.get('pattern_medsos') is not None and str(c.get('pattern_medsos')).strip() != '' and bool(re.search(c['pattern_medsos'], str(c.get('lokasi', '')), re.IGNORECASE))},
    {"nama": "Lokasi outreach diisi IDKD", "periksa": lambda c: c['lokasi'] != '' and c['lokasi'] != 'nan' and len(c['lokasi']) == 10 and c['lokasi'][:4].isalpha() and c['lokasi'][4:].isdigit()},
    {"nama": "Lokasi outreach diindikasi kurang spesifik atau kurang detil (konfirmasi)", "periksa": lambda c: (str(c.get('lokasi', '')).strip() != '' and str(c.get('lokasi', '')).strip().lower() != 'nan' and not c.get('is_vo', False) and not (str(c.get('jns_kontak', '')).split('.')[0].strip() == '3' and str(c.get('jns_kegiatan', '')).split('.')[0].strip() == '8' and any(m in str(c.get('lokasi', '')).upper() for m in ['FB', 'FACEBOOK', 'IG', 'INSTAGRAM', 'WA', 'WHATSAPP', 'TELE', 'TELEGRAM', 'TIKTOK', 'TWITTER', 'X ', 'YOUTUBE', 'YT', 'GRUP', 'GROUP', 'ONLINE', 'MEDSOS', 'SOSMED'])) and len(str(c.get('lokasi', '')).strip()) < 17 and not any(k in str(c.get('lokasi', '')).upper() for k in ['ALUN', 'RSUD', 'RS ', 'PUSKESMAS', 'KLINIK', 'TERMINAL', 'STASIUN', 'TAMAN', 'PASAR', 'MALL', 'KAMPUS', 'UNIV', 'SEKOLAH', 'SMK', 'SMA', 'SMP', 'SD', 'MASJID', 'GEREJA', 'HOTEL', 'PANTI', 'AULA', 'BALAI']) and not (bool(re.search(r'\d', str(c.get('lokasi', '')))) or any(p in str(c.get('lokasi', '')).upper() for p in ['JL', 'JALAN', 'RT', 'RW', 'GANG', 'GG', 'KP', 'KAMPUNG', 'BLOK', 'DESA', 'KEC', 'KAB', 'SAMPING', 'DEPAN', 'DEKAT', 'SEBERANG'])))},
    {"nama": "Lokasi outreach indikasi diisi nomer HP", "periksa": lambda c: c['lokasi'] != '' and c['lokasi'] != 'nan' and __import__('re').search(r'(08\d{8,11})|(\+62\d{8,11})', str(c['lokasi']).replace('-', '').replace(' ', '')) and not (str(c['jns_kontak']).strip() == '3' and str(c['jns_kegiatan']).strip() == '8')},
    {"nama": "VO tapi lokasi outreach bukan nama medsos/kurang tepat mencatat nama aplikasi medsos", "periksa": lambda c: c['is_vo'] and str(c['lokasi']).strip() != '' and (c['pattern_medsos'] is None or not bool(re.search(c['pattern_medsos'], str(c['lokasi']), re.IGNORECASE)))},
    {"nama": "VO tapi nama akun /No. Hp tidak sesuai format medsos/telepon", "periksa": lambda c: c['is_vo'] and (c['no_hp'].replace("'", "").strip() in ['', 'nan', '-', '.', 'tidak ada'] or not re.match(r'^[a-zA-Z0-9_@.+- ]+$', c['no_hp'].replace("'", "").strip()))},
    {"nama": "Tidak ada informasi satupun yang diberikan / tidak diisi", "periksa": lambda c: str(c.get('info_diberikan', '')).strip() == '' or str(c.get('info_diberikan', '')).strip().lower() in ['nan', 'none', 'null']},
    {"nama": "Bukan PWID mendapatkan info 8 atau 9 (LASS, PTRM)", "periksa": lambda c: not c['is_pwid'] and (cek_kode(c['info_diberikan'], '8') or cek_kode(c['info_diberikan'], '9'))},
    {"nama": "LSL/TG/PWID menerima informasi PMTC (konfirmasi)", "periksa": lambda c: c['v_tipe_sasaran'] in ['1304', '1301', '1401'] and cek_kode(c['info_diberikan'], '6')},
    {"nama": "KD dikontak lebih dari 1x tapi tidak mendapat informasi HIV", "periksa": lambda c: c['id_clean'] != '' and c['id_counts'].get(c['id_clean'], 0) > 1 and not c['pernah_dapat_info_hiv']},
    {"nama": "KD telah menerima layanan CBS tapi tidak ada informasi CBS di penjangkauan", "periksa": lambda c: ('cbs' in str(c['row'].get('Nama Layanan', '')).lower() or str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6']) and not c.get('info_cbs_di_penjangkauan_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    {"nama": "KD telah menerima layanan VCT tapi tidak diberikan informasi VCT atau rujukan VCT di penjangkauan", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '2') and not c.get('edukasi_vct_di_penjangkauan_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    {"nama": "KD telah menerima layanan PrEP tapi tidak diberikan informasi PrEP atau rujukan PrEP di penjangkauan", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and not c.get('edukasi_prep_di_penjangkauan_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    {"nama": "KD ada rujukan PrEp di penjangkauan tapi tidak ada informasi PrEp", "periksa": lambda c: cek_kode(c['rujukan'], '5') and not cek_kode(c['info_diberikan'], '10')},
    {"nama": "Konfirmasi jumlah KIE yang diberikan adalah wajar (konfirmasi)", "periksa": lambda c: c['log_kie'] > 5},
    {"nama": "Konfirmasi jumlah kondom yang diberikan adalah wajar (konfirmasi)", "periksa": lambda c: c['log_kon'] > 144},
    {"nama": "Konfirmasi jumlah pelicin yang diberikan adalah wajar (konfirmasi)", "periksa": lambda c: c['log_pel'] > 50},
    {"nama": "Konfirmasi jumlah jarum yang diberikan adalah wajar (konfirmasi)", "periksa": lambda c: c['log_jar'] > 10},
    {"nama": "Konfirmasi jumlah alkohol SWAB yang diberikan adalah wajar (konfirmasi)", "periksa": lambda c: c['log_swab'] > 50},
    {"nama": "VO tapi menyerahkan jarum", "periksa": lambda c: c['is_vo'] and c['log_jar'] > 0},
    {"nama": "VO menerima logistik selain KIE", "periksa": lambda c: c['is_vo'] and (c['log_kon'] > 0 or c['log_pel'] > 0 or c['log_swab'] > 0)},
    {"nama": "Logistik kosong (Konfirmasi)", "periksa": lambda c: c['total_log_keseluruhan_klien'] == 0},
    {"nama": "Tipe klien PWID tapi tidak menerima jarum (konfirmasi)", "periksa": lambda c: c['is_pwid'] and c['log_jar'] == 0 and not c['is_vo']},
    {"nama": "Tipe klien PWID tapi tidak menerima alkohol SWAB (konfirmasi)", "periksa": lambda c: c['is_pwid'] and c['log_swab'] == 0 and not c['is_vo']},
    {"nama": "Popkun selain PWID menerima jarum suntik", "periksa": lambda c: not c['is_pwid'] and c['log_jar'] > 0},
    {"nama": "Popkun selain PWID menerima alkohol swab", "periksa": lambda c: not c['is_pwid'] and c['log_swab'] > 0},
    {"nama": "Popkun selain PWID menyerahkan jarum", "periksa": lambda c: not c['is_pwid'] and c['jarum_kembali'] > 0},
    {"nama": "Tidak ada rujukan yang diberikan satupun / tidak diisi", "periksa": lambda c: c['rujukan'] == '' or c['rujukan'] == 'nan'},
    {"nama": "KD dikontak lebih dari 1x tetapi tidak ada Rujukan Tes HIV (konfirmasi)", "periksa": lambda c: c['id_clean'] != '' and c['id_counts'].get(c['id_clean'], 0) > 1 and not c['pernah_dapat_rujuk_tes']},
    {"nama": "Bukan penasun rujukan 3,4", "periksa": lambda c: not c['is_pwid'] and (cek_kode(c['rujukan'], '3') or cek_kode(c['rujukan'], '4'))},
    {"nama": "KD telah menerima layanan PrEp tapi tidak ada rujukan PrEp di penjangkauan", "periksa": lambda c: c['pernah_prep_di_rujukan'] and not cek_kode(c['rujukan'], '5')}
]

# ==========================================================
# 2. ATURAN VALIDASI KHUSUS RUJUKAN (VERSI PENYELARASAN)
# ==========================================================
ATURAN_VALIDASI_RUJUKAN = [
    {"nama": "ID tidak terdaftar di penjangkauan", "periksa": lambda c: c.get('id_clean', '') not in ['', '-', 'nan', 'None'] and f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}" not in c.get('set_ssr_id_penjangkauan', set())},
    {"nama": "Data rujukan tapi tidak ada NIK (konfirmasi)", "periksa": lambda c: str(c['row'].get('ID Klien', '')).strip() != '' and str(c['row'].get('NIK', '')).replace("'", "").strip() in ['', 'nan', 'none']},
    {"nama": "ID sudah dinyatakan Reaktif di semester / tahun lalu (Konfirmasi)", "periksa": lambda c: c.get('is_reaktif_sebelumnya', False)},
    {"nama": "Jenis Layanan tidak sesuai", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).strip()[:1] not in ['5', '6']},
    {"nama": "Jenis Layanan dengan Metode CBS tidak sesuai", "periksa": lambda c: str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and str(c['row'].get('Metode CBS', '')).split('.')[0].strip() in ['', '0', '1', 'nan']},
    {"nama": "Bukan CBS tapi jenis layanan 5/6", "periksa": lambda c: 'cbs' not in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6']},
    
    # 📌 Penyesuaian aturan CBS: Memakai c['cek_kode'] untuk mengantisipasi jika kode '2' (VCT) digabung dengan kode lain (misal: '2,5')
    {"nama": "Layanan CBS ada rujukan selain VCT", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and (not c['cek_kode'](c['row'].get('Rujukan'), '2') or len(c.get('list_kode_rujukan', [])) > 1)},
    
    {"nama": "Tidak ada rujukan satupun/kolom rujukan tidak diisi", "periksa": lambda c: str(c['row'].get('Rujukan', '')).replace("'", "").strip() in ['', 'nan', 'None'] or len(c.get('list_kode_rujukan', [])) == 0},
    {"nama": "Bukan penasun rujukan 3,4", "periksa": lambda c: str(c['row'].get('Tipe Klien', '')).split('.')[0].strip() != '1401' and (c['cek_kode'](c['row'].get('Rujukan'), '3') or c['cek_kode'](c['row'].get('Rujukan'), '4'))},
    {"nama": "ID akses ke layanan lebih dari 1x tapi belum tes HIV (Konfirmasi)", "periksa": lambda c: c.get('id_counts_ruj', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", 0) > 1 and not c.get('rujukan_vct_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    
    # 📌 Validasi HIV / VCT
    {"nama": "Tidak menerima hasil tes HIV", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '2') and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', '2', 'nan']},
    {"nama": "Kolom menerima hasil tes HIV terisi tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['1', '2'] and not c['cek_kode'](c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and not c['cek_kode'](c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi kolom menerima hasil tidak terisi", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', 'nan']},
    
    # 📌 Validasi IMS
    {"nama": "Dirujuk IMS tapi tidak ada hasil IMS", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '1') and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil IMS tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and not c['cek_kode'](c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi hasil tes IMS Non Reaktif/ N/A", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['2', '3']},
    {"nama": "Hasil tes IMS reaktif tapi tidak menerima pengobatan IMS (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).strip() in ['1', '1.0'] and str(c['row'].get('Menerima Pengobatan IMS', '')).strip() in ['2', '2.0']},
    {"nama": "Kolom menerima pengobatan IMS terisi tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['1', '2'] and not c['cek_kode'](c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi tidak ada hasil tes IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil tes IMS tapi kolom menerima pengobatan IMS tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['', 'nan']},
    
    # 📌 Validasi PrEP
    {"nama": "DIrujuk PrEP tapi hasil skrining PrEP tidak diisi", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '5') and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Layanan PrEp tidak terdaftar, indikasi salah mengisi layanan atau belum update jenis layanan PrEP di SIMS (konfirmasi)", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '5') and not c.get('is_layanan_prep_valid', True)},
    {"nama": "Ada hasil skrining PrEP tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and not c['cek_kode'](c['row'].get('Rujukan'), '5')},
    {"nama": "Ada hasil skrining PrEP tapi kolom menerima obat PrEP tidak disi", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Menerima pengobatan PrEP diisi tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and not c['cek_kode'](c['row'].get('Rujukan'), '5')},
    {"nama": "KD sudah menerima obat PrEP tapi hasil skrining PrEP tidak memenuhi syarat", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '5') and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '2'},
    {"nama": "Hasil Skrining PrEP memenuhi syarat tapi KD tidak menerima obat PrEP (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '2'},
    
    # 📌 Validasi TB
    {"nama": "Dirujuk TB tapi tidak ada Hasil Tes TB", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '7') and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada Hasil TB tapi tidak ada rujukan TB", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['1', '2', '3'] and not c['cek_kode'](c['row'].get('Rujukan'), '7')},
    {"nama": "Menerima pengobatan TB tapi hasil tes TB Non Reaktif/ N/A/ tidak diisi", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['2', '3', '', 'nan']},
    {"nama": "Hasil tes TB reaktif tapi tidak menerima pengobatan TB (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '2'},
    {"nama": "Ada hasil tes TB tapi kolom pengobatan TB tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() in ['', 'nan']},
    
    # 📌 Validasi Hepatitis C (Hep-C)
    {"nama": "Dirujuk Hep-C tapi tidak ada Hasil Tes Hep-C", "periksa": lambda c: c['cek_kode'](c['row'].get('Rujukan'), '9') and str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada Hasil Hep-C tapi tidak ada rujukan Hep-C", "periksa": lambda c: str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['1', '2', '3'] and not c['cek_kode'](c['row'].get('Rujukan'), '9')},
    {"nama": "Menerima Pengobatan Hep-C tapi Hasil Tes Non Reaktif/ N/A / tidak diisi", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan HEPC/DAA', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['2', '3', '', 'nan']},
    {"nama": "Hasil tes Hep-C reaktif tapi tidak menerima pengobatan Hep-C (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan HEPC/DAA', '')).split('.')[0].strip() == '2'},
    {"nama": "Ada hasil tes Hep-C tapi kolom pengobatan Hep-C tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Pengobatan HEPC/DAA', '')).split('.')[0].strip() in ['', 'nan']}
]

# ==========================================================
# 2. PANEL SIDEBAR
# ==========================================================
with st.sidebar:
    st.markdown("""
        <div style="padding: 10px 0px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 15px;">
            <h3 style='margin: 0; color: #f8fafc; font-size: 1.35rem;'>🛠️ Control Panel</h3>
            <p style='margin: 5px 0 0 0; color: #94a3b8; font-size: 0.85rem;'>Sistem Navigasi & Manajemen</p>
        </div>
    """, unsafe_allow_html=True)
    
    # --- PENAMBAHAN MENU NAVIGASI (4 MENU SESUAI KONSEP) ---
    menu_pilihan = st.radio(
        "Navigasi Menu", 
        [
            "🎯 Dashboard Review Data", 
            "⚙️ Pengaturan Keyword Medsos",
            "📊 Tren Agregasi Data",          # Menu Konsep Baru 1
            "🔍 Riwayat & Log Validasi"       # Menu Konsep Baru 2
        ],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    
    # 💡 INSISIALISASI AWAL NILAI DEFAULT AGAR TIDAK NAMEERROR DI MENU LAIN
    tombol_proses = False
    file_master = None
    files_review = None
    
    # =================================================================
    # 1. HANYA TAMPILKAN ALAT REVIEW JIKA MENU "DASHBOARD" DIPILIH
    # =================================================================
    if menu_pilihan == "🎯 Dashboard Review Data":
        with st.container():
            st.markdown("<b style='color: #38bdf8; font-size: 0.95rem;'>📁 MANAJEMEN BERKAS</b>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- 1. UPLOADER PINTAR (SINGLE SLOT UNTUK SEMUA DATA REFERENSI) ---
            file_master = st.file_uploader(
                "Upload Berkas Database (.xlsx)", 
                type=["xlsx"], 
                help="Sistem akan otomatis mendeteksi apakah berkas ini berupa Data HIV+ Semester Lalu atau Database Master Layanan berdasarkan struktur kolomnya.",
                key="uploader_master_tunggal"
            )
            
            # Logika pemrosesan otomatis setelah berkas diunggah
            if file_master is not None:
                try:
                    df_check = pd.read_excel(file_master)
                    kolom_terdeteksi = [str(c).strip().lower() for c in df_check.columns]
                    
                    is_database_hiv = ("id klien" in kolom_terdeteksi) and ("tanggal" in kolom_terdeteksi)
                    ada_unsur_ssr = any("ssr" in c or "iu" in c or "lembaga" in c for c in kolom_terdeteksi)
                    is_data_layanan = ada_unsur_ssr and ("nama layanan" in kolom_terdeteksi)
                    
                    if is_database_hiv:
                        st.info("📋 **Terdeteksi:** Database HIV+")
                        if st.button("🔄 Update Database HIV+", use_container_width=False, key="btn_exec_hiv"):
                            with st.spinner("Sedang memproses data rujukan HIV..."):
                                from database import import_data_HIV
                                if import_data_HIV(df_check):
                                    st.success("✅ Database HIV+ telah diperbarui!")
                                else:
                                    st.error("❌ Gagal mengupdate database HIV+.")
                                    
                    elif is_data_layanan:
                        st.info("🏥 **Terdeteksi:** Database Fasyankes")
                        if st.button("🔄 Update Database Fasyankes", use_container_width=False, key="btn_exec_layanan"):
                            with st.spinner("Sedang memproses database fasyankes..."):
                                from database import import_database_layanan
                                sukses, pesan = import_database_layanan(df_check)
                                if sukses:
                                    st.success("✅ Database Fasyankes telah diperbarui!")
                                else:
                                    st.error(f"❌ Gagal mengupdate database fasyankes: {pesan}")
                                    
                    else:
                        st.warning("⚠️ **Format File Tidak Dikenali!** \n\n"
                                   "- Untuk **Database HIV+**, pastikan memiliki kolom: `ID Klien` dan `Tanggal`.\n"
                                   "- Untuk **Database Layanan**, pastikan memiliki kolom: `Lembaga SSR` (atau sejenisnya) dan `Nama Layanan`.")
                        
                except Exception as e:
                    st.error(f"⚠️ Gagal membaca struktur berkas Excel: {e}")
            
            st.markdown("<div style='margin-top: 10px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 10px;'></div>", unsafe_allow_html=True)
            
            # --- 2. UPLOADER RAW DATA PENJANGKAUAN ---
            st.markdown("<span style='font-weight: 500; font-size: 0.9rem;'>📂 Upload RD Penjangkauan & Rujukan</span>", unsafe_allow_html=True)
            files_review = st.file_uploader(
                "Raw Data Penjangkauan (Multi-File)", 
                type=["xlsx", "csv"], 
                accept_multiple_files=True, 
                help="Wajib: Anda bisa memilih lebih dari satu file operasional sekaligus untuk di-review",
                key="uploader_raw_penjangkauan"
            )
            
            if files_review:
                st.info(f"📁 {len(files_review)} file siap diproses.")
                
                # 🛠️ TOMBOL EKSEKUSI TERINTEGRASI ENGINE VALIDASI UTAMA
                if st.button("🔍 Jalankan Review Validasi Data", type="primary", key="btn_jalankan_review"):
                    with st.spinner("Sedang membaca dan menganalisis berkas sesuai aturan validasi..."):
                        list_df = []
                        for f in files_review:
                            try:
                                if f.name.endswith('.csv'):
                                    df_individual = pd.read_csv(f)
                                else:
                                    df_individual = pd.read_excel(f)
                                list_df.append(df_individual)
                            except Exception as e:
                                st.error(f"Gagal membaca file {f.name}: {e}")
                        
                        if list_df:
                            # 1. Gabungkan semua file mentah yang di-upload
                            df_gabungan_raw = pd.concat(list_df, ignore_index=True)
                            
                            # 2. Ambil parameter role user yang sedang login (Default ke 'SR' jika tidak ketemu)
                            role_aktif = st.session_state.get('peran', 'SR')
                            
                            # 3. PANGGIL ENGINE VALIDASI UTAMA ANDA DI SINI
                            # Semua parameter cross-check ditarik aman dari session_state bawaan sistem
                            df_hasil_kesalahan = jalankan_review_data(
                                df_asli=df_gabungan_raw,
                                df_ref=st.session_state.get('df_database_hiv', None),
                                nama_file=", ".join([f.name for f in files_review]),
                                set_ssr_id_penjangkauan=st.session_state.get('set_ssr_id_penjangkauan', None),
                                set_nik_reaktif=st.session_state.get('set_nik_reaktif', None),
                                set_ssr_id_reaktif=st.session_state.get('set_ssr_id_reaktif', None),
                                set_prep_valid=st.session_state.get('set_prep_valid', None),
                                df_log_review=st.session_state.get('df_log_review', None),
                                role_reviewer=role_aktif
                            )
                            
                            # 4. Hitung Scorecard Metrics dari DATA MENTAH (df_gabungan_raw)
                            # Mencari kolom kategori secara cerdas
                            kolom_kat = [c for c in df_gabungan_raw.columns if "kategori" in str(c).lower() or "tipe" in str(c).lower()]
                            if kolom_kat:
                                mask_penj = df_gabungan_raw[kolom_kat[0]].astype(str).str.lower().str.contains("penjangkauan")
                                tot_entri_penj = len(df_gabungan_raw[mask_penj])
                                tot_entri_ruj = len(df_gabungan_raw[~mask_penj])
                            else:
                                # Fallback jika kolom tidak spesifik
                                tot_entri_penj = len(df_gabungan_raw)
                                tot_entri_ruj = len(df_gabungan_raw)
                            
                            # 5. Simpan Hasil ke Session State agar langsung dibaca Tab 1 & Tab 2
                            st.session_state['df_review_utama'] = df_gabungan_raw # Simpan data mentah asli jika dibutuhkan
                            st.session_state['df_tabel_bawah'] = df_hasil_kesalahan # Hasil temuan anomali/kesalahan data
                            st.session_state['total_entri_penjangkauan'] = tot_entri_penj
                            st.session_state['total_entri_rujukan'] = tot_entri_ruj
                            
                            st.success(f"🎉 Validasi Selesai! Berhasil mendeteksi {len(df_hasil_kesalahan)} baris indikasi kesalahan data.")
                            
                            # Force refresh halaman agar data langsung menembus filter Tab 1 / Tab 2
                            import time
                            time.sleep(1.0)
                            st.rerun()
    
        st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)
        st.markdown("""<div style="margin-top: 35px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);"></div>""", unsafe_allow_html=True)
        tombol_proses = st.button("🚀 Jalankan Validasi", type="primary", use_container_width=True)
            
        st.markdown("### ⚙️ Manajemen Akhir Periode")
        st.warning("⚠️ Gunakan tombol di bawah ini untuk mengarsipkan database.")
        
        if st.button("🚀 Arsipkan Data", type="primary", use_container_width=True):
            with st.spinner("Sedang memproses pengarsipan data ke Neon Postgres..."):
                if jalankan_agregasi_tren():
                    st.success("🎉 Data berhasil diarsipkan ke tabel rekap bulanan!")
                    st.balloons()
                else:
                    st.error("Gagal memproses arsip ke database.")

    # =================================================================
    # 2. MENU PENGATURAN KEYWORD MEDSOS SELECTOR CONTROL
    # =================================================================
    elif menu_pilihan == "⚙️ Pengaturan Keyword Medsos":
        with st.container():
            st.markdown("<b style='color: #38bdf8; font-size: 0.95rem;'>🛠️ INFO MODUL MEDSOS</b>", unsafe_allow_html=True)
            st.caption("Gunakan area utama layar untuk melakukan penambahan, penghapusan, dan visualisasi kata kunci media sosial yang aktif.")

    # =================================================================
    # 3. MENU TREN AGREGASI DATA (KONSEP)
    # =================================================================
    elif menu_pilihan == "📊 Tren Agregasi Data":
        with st.container():
            st.markdown("<b style='color: #10b981; font-size: 0.95rem;'>📊 STATISTIK & TREN</b>", unsafe_allow_html=True)
            st.caption("Modul ini digunakan untuk memantau performa review data dari waktu ke waktu secara real-time.")

    # =================================================================
    # 4. MENU RIWAYAT & LOG VALIDASI (KONSEP)
    # =================================================================
    elif menu_pilihan == "🔍 Riwayat & Log Validasi":
        with st.container():
            st.markdown("<b style='color: #a855f7; font-size: 0.95rem;'>🔍 AUDIT LOG VALIDASI</b>", unsafe_allow_html=True)
            st.caption("Melihat berkas yang pernah di-upload sebelumnya serta daftar temuan *error* historis.")

    # ==========================================================
    # INDIKATOR STORAGE NEON DB (TAMPIL DI SEMUA MENU SEBAGAI FOOTER SIDEBAR)
    # ==========================================================
    st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-top: 25px;'></div>", unsafe_allow_html=True)
    storage_info = ambil_status_storage_neon()
    
    if storage_info:
        if storage_info['persen_terpakai'] > 85:
            kondisi_warna = "#ff4b4b"
        elif storage_info['persen_terpakai'] > 60:
            kondisi_warna = "#ffa500"
        else:
            kondisi_warna = "#38bdf8"
            
        html_storage = f"""
        <div style="
            background-color: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 12px 14px;
            margin-bottom: 10px;
            font-size: 0.82rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        ">
            <div style="display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 5px;">
                <span style="color: #cbd5e1; display: flex; align-items: center; gap: 5px;">💾 Storage</span>
                <span style="color: {kondisi_warna}; font-weight: 700;">{storage_info['persen_terpakai']}%</span>
            </div>
            <div style="color: #94a3b8; margin-bottom: 0px;">
                Tersisa: <strong style="color: #f8fafc;">{storage_info['sisa_mb']} MB</strong> dari {storage_info['total_mb']} MB
            </div>
        </div>
        """
        st.markdown(html_storage, unsafe_allow_html=True)
        st.progress(storage_info['persen_terpakai'] / 100.0)
    else:
        st.markdown("""
            <div style="color: #94a3b8; font-size: 0.8rem; margin-bottom: 15px; padding: 0 5px;">
                ⚠️ Gagal memuat status storage database.
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-top: 15px;'></div>", unsafe_allow_html=True)

# ==========================================================
# 3. ENGINE VALIDASI UTAMA (MENDUKUNG 2 FILE & CROSS-CHECK)
# ==========================================================
def jalankan_review_data(
    df_asli, 
    df_ref=None, 
    nama_file="",
    set_ssr_id_penjangkauan=None, 
    set_nik_reaktif=None, 
    set_ssr_id_reaktif=None, 
    set_prep_valid=None,
    df_log_review=None,  # Menerima data log_hasil_review_data dari Pre-Processing
    role_reviewer='SR'   # Penyesuaian Role Reviewer agar sinkron dengan database
):
    # Inisialisasi fallback pengaman Cross-Check Variables
    if set_ssr_id_penjangkauan is None: set_ssr_id_penjangkauan = set()
    if set_nik_reaktif is None: set_nik_reaktif = set()
    if set_ssr_id_reaktif is None: set_ssr_id_reaktif = set()
    if set_prep_valid is None: set_prep_valid = set()
        
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()

    # Penyeragam Tanggal agar format Excel (DD/MM/YYYY) sinkron dengan Database (YYYY-MM-DD)
    def normalisasi_tanggal(tgl_str):
        tgl_str = str(tgl_str).strip().split(' ')[0]
        if not tgl_str or tgl_str.lower() == 'none' or tgl_str == 'nan': return ""
        try:
            if '/' in tgl_str:
                parts = tgl_str.split('/')
                if len(parts) == 3:
                    if len(parts[2]) == 4: return f"{parts[2]}-{parts[1]}-{parts[0]}"
                    elif len(parts[0]) == 4: return f"{parts[0]}-{parts[1]}-{parts[2]}"
            elif '-' in tgl_str:
                parts = tgl_str.split('-')
                if len(parts) == 3 and len(parts[0]) == 4: return tgl_str
        except: pass
        return tgl_str.upper()

    # ==========================================================
    # LOGIKA PERBAIKAN HEADER BERTINGKAT (MERGED CELLS)
    # ==========================================================
    cek_sub_header = False
    if len(df) > 0:
        baris_pertama = str(df.iloc[0].values).upper()
        if any(k in baris_pertama for k in ['KIE', 'KONDOM', 'PELICIN', 'JARUM', 'SWAB']):
            cek_sub_header = True

    if cek_sub_header:
        columns_fixed = []
        main_headers = [str(c).strip() for c in df.columns]
        sub_headers = [str(x).strip() for x in df.iloc[0].values]
        
        current_main = ""
        for i in range(len(main_headers)):
            if main_headers[i] and 'UNNAMED' not in main_headers[i].upper():
                current_main = main_headers[i]
            sub = sub_headers[i] if (sub_headers[i] and str(sub_headers[i]).lower() != 'nan') else ""
            
            if current_main and sub and 'UNNAMED' not in sub.upper():
                columns_fixed.append(f"{current_main} - {sub}")
            elif sub and 'UNNAMED' not in sub.upper():
                columns_fixed.append(sub)
            else:
                columns_fixed.append(main_headers[i])
                
        df.columns = columns_fixed
        df = df.drop(0).reset_index(drop=True)
        start_row_idx = 0 
    else:
        df.columns = [str(c).strip() for c in df.columns]
        start_row_idx = 0
        if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values).lower() or 'laki-laki' in str(df.iloc[0].values).lower()):
            start_row_idx = 1
            
    # DETEKSI CERDAS: Mengecek substring, bukan exact match
    col_upper_all = [str(c).upper() for c in df.columns]
    is_file_rujukan = any(any(k in c for c in col_upper_all) for k in ['HASIL TES HIV', 'NAMA LAYANAN', 'METODE CBS'])
    
    v_kategori = "Rujukan" if is_file_rujukan else "Penjangkauan"
    tahun_sekarang = dt.datetime.now().year
    hari_ini = pd.Timestamp(dt.datetime.now().date())

    # PENGAMAN REGEX MEDSOS
    keywords_aktif = st.session_state.get('medsoc_keywords', []) if 'st' in globals() else []
    if keywords_aktif:
        pattern_medsos_dinamis = r'\b(' + '|'.join([re.escape(k) for k in keywords_aktif]) + r')\b'
    else:
        pattern_medsos_dinamis = r'\b(TIDAK_ADA_MEDSOS_TERDAFTAR_DI_SISTEM)\b'

    # Pengaman Database terintegrasi (Disesuaikan agar menerima parameter role_reviewer jika didukung oleh fungsinya)
    try:
        # Jika fungsi hitung_dan_ambil_log_db sudah Anda update untuk menerima role, teruskan parameter ini
        dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db(role_reviewer=role_reviewer)
    except Exception:
        try:
            dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()
        except Exception:
            dict_revisi, dict_justifikasi = {}, {}

    # Ekstrak log historis dari df_log_review jika dilempar dari Pre-Processing
    set_id_berulang_log = set()
    if df_log_review is not None and not df_log_review.empty:
        if 'TANGGAL' in df_log_review.columns:
            df_log_review['Tanggal_Clean'] = df_log_review['TANGGAL'].astype(str).str.split(' ').str[0].str.strip()
        else:
            df_log_review['Tanggal_Clean'] = ""

        # Menghasilkan key format unik yang disinkronkan dengan database dan menyertakan ROLE
        df_log_review['key_log'] = (
            df_log_review['KATEGORI DATA'].astype(str).str.strip().str.upper() + "_" +
            df_log_review['LEMBAGA SSR'].astype(str).str.strip().str.upper() + "_" +
            df_log_review['Tanggal_Clean'] + "_" +
            df_log_review['ID KLIEN'].astype(str).str.strip().str.upper() + "_" +
            df_log_review['INDIKATOR KESALAHAN DATA'].astype(str).str.strip().str.upper() + "_" +
            str(role_reviewer).strip().upper()
        )
        set_id_berulang_log = set(df_log_review['key_log'].unique())

    ref_ssr_id_to_nik, ref_nik_ssr_to_id = {}, {}
    dict_pernah_cbs, dict_pernah_prep_rujukan = {}, {}

    if not is_file_rujukan and df_ref is not None and not df_ref.empty:
        df_ref_cp = df_ref.copy()
        df_ref_cp.columns = [str(c).strip() for c in df_ref_cp.columns]
        
        col_id_ref = [c for c in df_ref_cp.columns if 'ID' in c or 'Klien' in c]
        col_nik_ref = [c for c in df_ref_cp.columns if 'NIK' in c]
        col_ssr_ref = [c for c in df_ref_cp.columns if 'SSR' in c or 'Lembaga' in c]
        col_layanan_ref = [c for c in df_ref_cp.columns if 'Jenis Layanan' in c or 'Layanan' in c]
        col_rujukan_ref = [c for c in df_ref_cp.columns if 'Rujukan' in c]

        if col_id_ref and col_ssr_ref:
            for _, r in df_ref_cp.iterrows():
                ssr_r = str(r[col_ssr_ref[0]]).strip().upper()
                id_r = str(r[col_id_ref[0]]).replace("'", "").strip()
                nik_r = str(r[col_nik_ref[0]]).replace("'", "").replace('.0', '').strip() if col_nik_ref else ''
                key_klien = f"{ssr_r}_{id_r}"

                if id_r and id_r != 'nan' and ssr_r and ssr_r != 'nan': 
                    ref_ssr_id_to_nik[key_klien] = nik_r
                if nik_r and nik_r not in ['nan', ''] and ssr_r and ssr_r != 'nan': 
                    ref_nik_ssr_to_id[f"{nik_r}_{ssr_r}"] = id_r
                
                if col_layanan_ref:
                    layanans = str(r[col_layanan_ref[0]]).replace("'", "").replace(" ", "").split(',')
                    if '5' in layanans or '6' in layanans: dict_pernah_cbs[key_klien] = True
                if col_rujukan_ref:
                    rujukans = str(r[col_rujukan_ref[0]]).replace("'", "").replace(" ", "").split(',')
                    if '5' in rujakans: dict_pernah_prep_rujukan[key_klien] = True

    # ==========================================================
    # DETEKSI KOLOM DINAMIS
    # ==========================================================
    col_id_klien = next((c for c in df.columns if "ID KLIEN" in str(c).upper() or "ID_KLIEN" in str(c).upper()), "ID Klien")
    col_ssr = next((c for c in df.columns if "LEMBAGA SSR" in str(c).upper() or "SSR" in str(c).upper()), "Lembaga SSR")
    col_nik = next((c for c in df.columns if "NIK" in str(c).upper()), "NIK")
    col_petugas = next((c for c in df.columns if "PETUGAS" in str(c).upper()), "Kode Petugas")
    col_kota = next((c for c in df.columns if "KOTA" in str(c).upper()), "Nama Kota")
    col_umur = next((c for c in df.columns if "UMUR" in str(c).upper() or "USIA" in str(c).upper()), "Umur")
    col_jk = next((c for c in df.columns if "JENIS KELAMIN" in str(c).upper() or "JK" in str(c).upper()), "Jenis Kelamin")

    col_info = next((c for c in df.columns if "INFORMASI" in str(c).upper() and "DIBERIKAN" in str(c).upper()), "")
    col_kegiatan = next((c for c in df.columns if "JENIS KEGIATAN" in str(c).upper()), "")
    col_kontak = next((c for c in df.columns if "JENIS KONTAK" in str(c).upper() or "JNS KONTAK" in str(c).upper()), "")
    col_lokasi = next((c for c in df.columns if "LOKASI" in str(c).upper()), "")
    col_ruj = next((c for c in df.columns if "RUJUKAN" in str(c).upper()), "")
    col_tanggal = next((c for c in df.columns if "TANGGAL" in str(c).upper()), "Tanggal")
    col_tipe_sasaran = next((c for c in df.columns if "TIPE SASARAN" in str(c).upper() or "TIPE KLIEN" in str(c).upper()), "Tipe Sasaran")
    col_vc1 = next((c for c in df.columns if "VIRTUAL" in str(c).upper() or "VC1" in str(c).upper() or "TATAP MUKA" in str(c).upper()), "")
    col_nama_layanan = next((c for c in df.columns if "NAMA LAYANAN" in str(c).upper()), "")
    
    # Pemetaan Identitas Klien
    df['id_mapped'] = df.get(col_id_klien, pd.Series(dtype=str)).astype(str).str.replace("'", "").str.strip().str.upper()
    df['ssr_id_key'] = df.get(col_ssr, pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + df['id_mapped']
    dict_ssr_id_counts = df.iloc[start_row_idx:]['ssr_id_key'].value_counts().to_dict()
    
    def periksa_hiv(x): return '1' in str(x).replace("'", "").replace(" ", "").split(',')
    def periksa_rujukan(x): 
        s = str(x).replace("'", "").replace(" ", "").replace(".0", "")
        if '.' in s and ',' not in s: s = s.replace('.', ',')
        return '2' in s.split(',')

    # PRE-KALKULASI KHUSUS RUJUKAN
    rujakan_vct_per_klien = {}
    if is_file_rujukan:
        col_ruj_temp = next((c for c in df.columns if "RUJUKAN" in str(c).upper()), None)
        if col_ruj_temp:
            for _, r in df.iloc[start_row_idx:].iterrows():
                k_ssr = str(r.get(col_ssr, '')).strip().upper()
                k_id = str(r.get(col_id_klien, '')).replace("'", "").strip().upper()
                if periksa_rujukan(r.get(col_ruj_temp)):
                    rujakan_vct_per_klien[f"{k_ssr}_{k_id}"] = True

    if col_info and col_kegiatan:
        df['is_info_hiv'] = df[col_info].apply(periksa_hiv) | df[col_kegiatan].apply(periksa_hiv)
    else:
        df['is_info_hiv'] = False
        
    if col_ruj: df['is_rujuk_tes'] = df[col_ruj].apply(periksa_rujukan)
    else: df['is_rujuk_tes'] = False

    dict_pernah_hiv = df.groupby('ssr_id_key')['is_info_hiv'].any().to_dict()
    dict_pernah_rujuk = df.groupby('ssr_id_key')['is_rujuk_tes'].any().to_dict()

    def _safe_float(val):
        try: return float(val) if pd.notna(val) and str(val).strip().lower() not in ['', 'nan'] else 0.0
        except: return 0.0

    col_kie_list = [c for c in df.columns if 'KIE' in str(c).upper()]
    col_kon_list = [c for c in df.columns if 'KONDOM' in str(c).upper()]
    col_pel_list = [c for c in df.columns if 'PELICIN' in str(c).upper()]
    col_jar_list = [c for c in df.columns if 'JARUM' in str(c).upper() and 'KEMBALI' not in str(c).upper()]
    col_swab_list = [c for c in df.columns if 'SWAB' in str(c).upper() or 'ALKOHOL' in str(c).upper()]
    
    semua_kolom_logistik = col_kie_list + col_kon_list + col_pel_list + col_jar_list + col_swab_list

    df['tmp_log'] = 0.0
    for col in semua_kolom_logistik: df['tmp_log'] += df[col].apply(_safe_float)
    dict_total_log_per_klien = df.groupby('ssr_id_key')['tmp_log'].sum().to_dict()

    info_cbs_di_penjangkauan_per_klien = {}
    edukasi_vct_di_penjangkauan_per_klien = {}
    edukasi_prep_di_penjangkauan_per_klien = {}

    df_pj_aktif = locals().get('df_penjangkauan', st.session_state.get('df_penjangkauan_aktif', None) if 'st' in globals() else None)

    # VALIDASI MURNI FILE-TO-FILE JIKA RUJUKAN DI-UPLOAD
    if is_file_rujukan:
        set_ssr_id_penjangkauan = set() 

        if df_pj_aktif is not None and not df_pj_aktif.empty:
            col_info_pj = next((c for c in df_pj_aktif.columns if "INFORMASI" in str(c).upper() and "DIBERIKAN" in str(c).upper()), "")
            col_ruj_pj = next((c for c in df_pj_aktif.columns if "RUJUKAN" in str(c).upper()), "")
            col_id_pj = next((c for c in df_pj_aktif.columns if "ID KLIEN" in str(c).upper() or "ID_KLIEN" in str(c).upper()), "ID Klien")
            col_ssr_pj = next((c for c in df_pj_aktif.columns if "LEMBAGA SSR" in str(c).upper() or "SSR" in str(c).upper()), "Lembaga SSR")
            
            for _, r_pj in df_pj_aktif.iterrows():
                ssr_pj = str(r_pj.get(col_ssr_pj, '')).strip().upper()
                id_pj = str(r_pj.get(col_id_pj, '')).replace("'", "").strip().upper() 
                kunci_pj = f"{ssr_pj}_{id_pj}"
                
                if id_pj and id_pj not in ['NAN', '', '-', 'NONE'] and ssr_pj and ssr_pj not in ['NAN', '']:
                    set_ssr_id_penjangkauan.add(kunci_pj)
                           
                txt_info = str(r_pj.get(col_info_pj, '')).strip() if col_info_pj else ""
                txt_ruj = str(r_pj.get(col_ruj_pj, '')).strip() if col_ruj_pj else ""
                
                list_info_pj = txt_info.replace("'", "").replace(" ", "").split(',')
                list_ruj_pj = txt_ruj.replace("'", "").replace(" ", "").replace(".0", "").split(',')
                
                if '12' in list_info_pj: info_cbs_di_penjangkauan_per_klien[kunci_pj] = True
                if '1' in list_info_pj and '2' in list_ruj_pj: edukasi_vct_di_penjangkauan_per_klien[kunci_pj] = True
                if '10' in list_info_pj and '5' in list_ruj_pj: edukasi_prep_di_penjangkauan_per_klien[kunci_pj] = True
            
            if 'st' in globals():
                st.write(f"✅ Sistem memproses {len(set_ssr_id_penjangkauan)} unik ID dari file Penjangkauan untuk validasi Rujukan.")
        else:
            if 'st' in globals():
                st.warning("⚠️ File Penjangkauan tidak ditemukan atau kosong. Validasi Rujukan tidak bisa dilakukan!")

    if is_file_rujukan:
        SEMUA_ATURAN_AKTIF = globals().get('ATURAN_VALIDASI_RUJUKAN', [])
    else:
        aturan_kustom = st.session_state.get('aturan_kustom', []) if 'st' in globals() else []
        SEMUA_ATURAN_AKTIF = globals().get('ATURAN_VALIDASI_BAWAAN', []) + aturan_kustom

    # LOOP BARIS DATA UNTUK EVALUASI
    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        
        v_ssr = str(row.get(col_ssr, '')).strip().upper() if pd.notna(row.get(col_ssr)) else ''
        v_petugas = str(row.get(col_petugas, '')).replace("'", "").strip() if pd.notna(row.get(col_petugas)) else ''
        v_kota = str(row.get(col_kota, '')).strip() if pd.notna(row.get(col_kota)) else ''
        v_tanggal = str(row.get(col_tanggal, '')).split(' ')[0] if pd.notna(row.get(col_tanggal)) else ''
        
        id_raw = str(row.get(col_id_klien, '')).strip()
        id_clean = id_raw.replace("'", "").strip().upper() 
        
        nik_raw = str(row.get(col_nik, '')).strip()
        nik_clean = nik_raw.replace("'", "").replace('.0', '').strip()

        v_tipe_sasaran = str(row.get(col_tipe_sasaran, '')).replace('.0', '').strip()
        umur = row.get(col_umur, None)
        jk = str(row.get(col_jk, '')).replace('.0', '').strip()
        
        jns_kontak = str(row.get(col_kontak, row.get('Jenis Kontak', ''))).replace('.0', '').strip()
        jns_kegiatan = str(row.get(col_kegiatan, row.get('Jenis Kegiatan', ''))).replace('.0', '').strip()
        lokasi = str(row.get(col_lokasi, row.get('Lokasi Outreach / Jenis Sosial Media', ''))).strip()
        
        info_diberikan = str(row.get(col_info, '')).strip() if col_info else ''
        rujakan = str(row.get(col_ruj, '')).strip() if col_ruj else ''
        no_hp = str(row.get('No. HP / Nama Akun', '')).strip()
        
        vc1 = str(row.get(col_vc1, row.get('Virtual & Tatap Muka', ''))).replace('.0', '').strip()

        log_kie = sum(_safe_float(row.get(c, 0)) for c in col_kie_list)
        log_kon = sum(_safe_float(row.get(c, 0)) for c in col_kon_list)
        log_pel = sum(_safe_float(row.get(c, 0)) for c in col_pel_list)
        log_jar = sum(_safe_float(row.get(c, 0)) for c in col_jar_list)
        log_swab = sum(_safe_float(row.get(c, 0)) for c in col_swab_list)
        jarum_kembali = _safe_float(row.get('Jumlah Jarum Suntik Kembali', 0))

        tgl_raw = row.get(col_tanggal, None)
        tgl_p = pd.to_datetime(tgl_raw, errors='coerce', format='%d/%m/%Y') if pd.notna(tgl_raw) and '/' in str(tgl_raw) else pd.to_datetime(tgl_raw, errors='coerce')

        kunci_klien_ref = f"{v_ssr}_{id_clean}"
        count_untuk_ssr_id = dict_ssr_id_counts.get(kunci_klien_ref, 0)
        local_id_counts = {id_clean: count_untuk_ssr_id} 

        pernah_dapat_info_hiv = dict_pernah_hiv.get(kunci_klien_ref, False) if id_clean else False
        pernah_dapat_rujuk_tes = dict_pernah_rujuk.get(kunci_klien_ref, False) if id_clean else False
        
        is_reaktif_db = False
        if nik_clean and nik_clean.lower() not in ['', 'nan', 'none'] and nik_clean in set_nik_reaktif: is_reaktif_db = True
        elif kunci_klien_ref in set_ssr_id_reaktif: is_reaktif_db = True
            
        layanan_clean = str(row.get(col_nama_layanan, '')).strip().lower() if col_nama_layanan else ""
        if not layanan_clean: is_layanan_prep_db = True
        else: is_layanan_prep_db = (v_ssr.lower(), layanan_clean) in set_prep_valid

        if is_file_rujukan and col_nama_layanan:
            v_nama_layanan = str(row.get(col_nama_layanan, '-')).strip()
            if v_nama_layanan.lower() in ['nan', 'none', '']: v_nama_layanan = '-'
        else: v_nama_layanan = '-'

        rujakan_clean_text = rujukan.replace("'", "").replace(".0", "").strip()
        if '.' in rujakan_clean_text and ',' not in rujakan_clean_text:
            rujakan_clean_text = rujakan_clean_text.replace('.', ',')
        
        list_kode_rujukan = [k.strip() for k in rujakan_clean_text.split(',') if k.strip() not in ['', 'nan', 'None']]

        def jembatan_cek_kode(nilai_input, kode_target):
            if nilai_input and kode_target: return str(kode_target).strip() in list_kode_rujukan
            return False

        context_data = {
            'row': row, 'id_clean': id_clean, 'nik_clean': nik_clean, 'v_ssr': v_ssr, 'v_tanggal': v_tanggal,
            'v_petugas': v_petugas, 'v_kota': v_kota, 'v_tipe_sasaran': v_tipe_sasaran, 'umur': umur, 'jk': jk,
            'jns_kontak': jns_kontak, 'jns_kegiatan': jns_kegiatan, 'lokasi': lokasi, 'info_diberikan': info_diberikan,
            'rujukan': rujukan, 'no_hp': no_hp, 'vc1': vc1, 'log_kie': log_kie, 'log_kon': log_kon, 'log_pel': log_pel,
            'log_jar': log_jar, 'log_swab': log_swab, 'jarum_kembali': jarum_kembali, 'tgl_p': tgl_p, 'hari_ini': hari_ini,
            'tahun_sekarang': tahun_sekarang, 'is_vo': (jns_kontak == '3'), 'is_pwid': (v_tipe_sasaran in ['1401', '1403']),
            'id_counts': local_id_counts, 'pernah_dapat_info_hiv': pernah_dapat_info_hiv, 'pernah_dapat_rujuk_tes': pernah_dapat_rujuk_tes,
            'is_file_rujukan': is_file_rujukan, 'df_ref': df_ref, 'ref_ssr_id_to_nik': ref_ssr_id_to_nik, 'ref_nik_ssr_to_id': ref_nik_ssr_to_id,
            'pernah_cbs_di_rujukan': dict_pernah_cbs.get(kunci_klien_ref, False),
            'pernah_prep_di_rujukan': dict_pernah_prep_rujukan.get(kunci_klien_ref, False),
            'total_log_keseluruhan_klien': dict_total_log_per_klien.get(kunci_klien_ref, 0.0),
            'pattern_medsos': pattern_medsos_dinamis,
            'set_ssr_id_penjangkauan': set_ssr_id_penjangkauan,
            'is_reaktif_sebelumnya': is_reaktif_db,
            'rujukan_vct_per_klien': rujakan_vct_per_klien,
            'id_counts_ruj': dict_ssr_id_counts,
            'is_layanan_prep_valid': is_layanan_prep_db,
            'list_kode_rujukan': list_kode_rujukan,
            'cek_kode': jembatan_cek_kode,
            'info_cbs_di_penjangkauan_per_klien': info_cbs_di_penjangkauan_per_klien,
            'edukasi_vct_di_penjangkauan_per_klien': edukasi_vct_di_penjangkauan_per_klien,
            'edukasi_prep_di_penjangkauan_per_klien': edukasi_prep_di_penjangkauan_per_klien
        }

        for rule in SEMUA_ATURAN_AKTIF:
            nama_ind = rule.get("nama", "Unknown Rule")
            try:
                if rule["periksa"](context_data):
                    v_tanggal_clean = normalisasi_tanggal(v_tanggal)
                    
                    # 🔥 PERBAIKAN KEY: Menyertakan role_reviewer di bagian akhir key_db
                    key_db = f"{v_kategori.strip().upper()}_{v_ssr.strip().upper()}_{v_tanggal_clean}_{id_clean.strip().upper()}_{nama_ind.strip().upper()}_{str(role_reviewer).strip().upper()}"
                    
                    ada_di_log_db = (key_db in dict_justification) if 'dict_justification' in locals() else False
                    if not ada_di_log_db:
                        ada_di_log_db = (key_db in dict_justifikasi) or (key_db in dict_revisi) or (key_db in set_id_berulang_log)
                    
                    if ada_di_log_db:
                        if "(konfirmasi)" in nama_ind.lower():
                            continue 
                        else:
                            is_rev_bool = dict_revisi.get(key_db, False)
                            if is_rev_bool:
                                status_validasi = "⚠️ Kesalahan Berulang (Revisi sebelumnya tidak valid!)"
                            else:
                                status_validasi = "Kesalahan pada ID yang berulang (belum direvisi)"
                            
                            checked_state = True
                            justif_val = dict_justifikasi.get(key_db, "")
                    else:
                        status_validasi = "-"
                        checked_state = False
                        justif_val = ""
    
                    list_kesalahan.append({
                        "Pilih": checked_state,
                        "Kategori Data": v_kategori,
                        "Lembaga SSR": v_ssr,
                        "Tanggal": v_tanggal_clean, 
                        "ID Klien": id_clean, 
                        "Kode Petugas": v_petugas, 
                        "Nama Kota": v_kota, 
                        "Nama Layanan": v_nama_layanan,
                        "NIK": nik_clean, 
                        "Tipe Sasaran": v_tipe_sasaran,
                        "INDIKATOR KESALAHAN DATA": nama_ind,
                        "Validasi Hasil Review": status_validasi, 
                        "Justifikasi": justif_val
                    })
            except Exception as e: 
                print(f"Error pada saat evaluasi Aturan [{nama_ind}] di Baris ke-{idx}: {e}")
                pass

    return pd.DataFrame(list_kesalahan)

    
# =========================================================================
# 4. LOGIKA TOMBOL EKSEKUSI (VERSI PENYELARASAN 3 TABEL + DUAL SCORECARD)
# =========================================================================
if tombol_proses:
    if not files_review:
        st.error("⚠️ Silakan unggah berkas Raw Data terlebih dahulu di sidebar!")
    else:
        with st.spinner("Sedang memproses validasi data & sinkronisasi database terintegrasi..."):
            
            # 🔥 AMBIL IDENTITAS LOGIN USER SAAT INI UNTUK PEMISAHAN DATA SR vs SSR
            role_aktif = st.session_state.get('peran_user', 'SR')
            lembaga_aktif = st.session_state.get('lembaga_user', None)
            
            # 🛠️ Tangkap uploader referensi dengan aman
            file_referensi_aman = st.session_state.get('uploader_master_tunggal', None)
            df_ref = None
            if file_referensi_aman is not None:
                try: 
                    file_referensi_aman.seek(0) # Pengaman pointer
                    df_ref = pd.read_excel(file_referensi_aman)
                except Exception: 
                    pass

            # -----------------------------------------------------------------
            # LANGKAH UTAMA: PRE-PROCESSING & KUMPULKAN PARAMETER CROSS-CHECK
            # -----------------------------------------------------------------
            set_penjangkauan = set()
            total_records = 0
            all_errs = []
            
            total_proses_pjj = 0
            total_proses_rjk = 0
            
            set_nik_rkt, set_ssr_id_rkt, set_prep_vld = set(), set(), set()
            set_error_historis = pd.DataFrame() 

            try:
                set_nik_rkt, set_ssr_id_rkt = ambil_set_reaktif_sebelumnya()
                set_prep_vld = ambil_set_layanan_prep_valid()
                set_error_historis = ambil_set_error_belum_direvisi() 
            except Exception as e:
                print(f"Gagal mengambil data historis log review: {e}")
                set_error_historis = pd.DataFrame()

            # =========================================================================
            # PERBAIKAN LOOP 1: BACA FILE 1 KALI SAJA UNTUK MENCEGAH BUG EOF
            # =========================================================================
            list_df_penj = []
            daftar_data_file = [] # Menyimpan tuple (nama_file, df_target, is_rujukan)

            for f in files_review:
                try:
                    f.seek(0) # Kembalikan kursor file ke baris pertama
                    temp_df = pd.read_csv(f, low_memory=False) if f.name.endswith('.csv') else pd.read_excel(f)
                    col_upper = [str(c).upper() for c in temp_df.columns]
                    
                    # Deteksi jenis file
                    is_ruj = any(k in col_upper for k in ['HASIL TES HIV', 'NAMA LAYANAN', 'METODE CBS'])
                    
                    # Simpan dataframe yang SUDAH DIBACA untuk dipakai di Loop 2
                    daftar_data_file.append((f.name, temp_df, is_ruj))
                    
                    # Jika ini file Penjangkauan, ekstrak ID-nya untuk set_penjangkauan
                    if not is_ruj:
                        list_df_penj.append(temp_df) 
                        
                        for _, row in temp_df.iterrows():
                            ssr = str(row.get('Lembaga SSR', '')).strip().upper()
                            idk = str(row.get('ID Klien', '')).replace("'", "").strip().upper()
                            if ssr and idk: set_penjangkauan.add(f"{ssr}_{idk}")
                except Exception as e:
                    print(f"Gagal membaca file {f.name}: {e}")
            
            # 💾 SIMPAN KE SESSION STATE
            if list_df_penj:
                st.session_state['df_penjangkauan_aktif'] = pd.concat(list_df_penj, ignore_index=True)
            else:
                st.session_state['df_penjangkauan_aktif'] = pd.DataFrame()

            # =========================================================================
            # PERBAIKAN LOOP 2: EKSEKUSI TANPA MEMBACA ULANG EXCEL
            # =========================================================================
            for nama_file, df_target, is_rujukan in daftar_data_file:
                try:
                    total_records += len(df_target)
                    
                    if is_rujukan: total_proses_rjk += len(df_target)
                    else: total_proses_pjj += len(df_target)
                    
                    # 🔥 PERUBAHAN: Sisipkan role_reviewer ke dalam engine validasi
                    df_res = jalankan_review_data(
                        df_target, df_ref, nama_file=nama_file,
                        set_ssr_id_penjangkauan=set_penjangkauan,
                        set_nik_reaktif=set_nik_rkt, set_ssr_id_reaktif=set_ssr_id_rkt, 
                        set_prep_valid=set_prep_vld,
                        df_log_review=set_error_historis,
                        role_reviewer=role_aktif
                    )
                    
                    if not df_res.empty:
                        all_errs.append(df_res)
                except Exception as e: 
                    print(f"Error saat validasi {nama_file}: {e}")

            # =========================================================================
            # PROSES RENAME KOLOM DAN SINKRONISASI DATABASE
            # =========================================================================
            df_bawah = pd.DataFrame()
            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                
                # RENAME KOLOM
                rename_map = {}
                for c in df_bawah.columns:
                    c_clean = str(c).strip().upper()
                    if 'KATEGORI' in c_clean: rename_map[c] = 'KATEGORI DATA'
                    elif 'LEMBAGA SSR' in c_clean or 'NAMA SSR' in c_clean: rename_map[c] = 'LEMBAGA SSR'
                    elif 'KODE PETUGAS' in c_clean: rename_map[c] = 'KODE PETUGAS'
                    elif 'NAMA KOTA' in c_clean or 'KOTA' in c_clean: rename_map[c] = 'NAMA KOTA'
                    elif 'NAMA LAYANAN' in c_clean or 'LAYANAN' in c_clean: rename_map[c] = 'NAMA LAYANAN'
                    elif 'TANGGAL' in c_clean: rename_map[c] = 'TANGGAL'
                    elif 'ID KLIEN' in c_clean or 'KLIEN' in c_clean: rename_map[c] = 'ID KLIEN'
                    elif 'NIK' in c_clean: rename_map[c] = 'NIK'
                    elif 'TIPE SASARAN' in c_clean or 'SASARAN' in c_clean: rename_map[c] = 'TIPE SASARAN'
                    elif 'INDIKATOR KESALAHAN' in c_clean: rename_map[c] = 'INDIKATOR KESALAHAN DATA'
                    elif 'VALIDASI' in c_clean: rename_map[c] = 'VALIDASI HASIL REVIEW'
                    elif 'JUSTIFIKASI' in c_clean: rename_map[c] = 'JUSTIFIKASI'
                
                df_bawah = df_bawah.rename(columns=rename_map)
                df_bawah = df_bawah.loc[:, ~df_bawah.columns.duplicated()].copy()

            # 🎯 Simpan total entri global ke memory Streamlit
            st.session_state['total_entri'] = total_records
            st.session_state['total_entri_penjangkauan'] = total_proses_pjj
            st.session_state['total_entri_rujukan'] = total_proses_rjk
            
            df_pjj_raw = pd.DataFrame()
            df_rjk_raw = pd.DataFrame()
            
            if df_bawah is None:
                df_bawah = pd.DataFrame()
                
            if 'KATEGORI DATA' not in df_bawah.columns:
                kolom_mirip = [c for c in df_bawah.columns if 'KATEGORI' in str(c).upper()]
                if kolom_mirip:
                    df_bawah = df_bawah.rename(columns={kolom_mirip[0]: 'KATEGORI DATA'})
                else:
                    df_bawah['KATEGORI DATA'] = '-'
            
            if not df_bawah.empty:
                df_pjj_raw = df_bawah[df_bawah['KATEGORI DATA'].astype(str).str.strip().str.upper() == 'PENJANGKAUAN'].copy()
                df_rjk_raw = df_bawah[df_bawah['KATEGORI DATA'].astype(str).str.strip().str.upper() == 'RUJUKAN'].copy()

            st.session_state['df_err_penj'] = df_pjj_raw
            st.session_state['df_err_ruj'] = df_rjk_raw
            
            total_temuan_pjj = len(df_pjj_raw)
            total_temuan_rjk = len(df_rjk_raw)
            
            akurasi_pjj = max(0.00, round(((total_proses_pjj - total_temuan_pjj) / total_proses_pjj) * 100, 2)) if total_proses_pjj > 0 else 100.00
            akurasi_rjk = max(0.00, round(((total_proses_rjk - total_temuan_rjk) / total_proses_rjk) * 100, 2)) if total_proses_rjk > 0 else 100.00
            
            st.session_state['akurasi_penjangkauan'] = akurasi_pjj
            st.session_state['akurasi_rujukan'] = akurasi_rjk
            st.session_state['temuan_penjangkauan'] = total_temuan_pjj
            st.session_state['temuan_rujukan'] = total_temuan_rjk
            
            st.session_state['db_tercatat_batch'] = False

            try:
                from database import simpan_metrik_akurasi_db
                # 🔥 PERUBAHAN: Sisipkan role_reviewer dan lembaga_ssr
                if total_proses_pjj > 0 or total_temuan_pjj > 0:
                    simpan_metrik_akurasi_db('penjangkauan', total_proses_pjj, total_temuan_pjj, akurasi_pjj, role_reviewer=role_aktif, lembaga_ssr=lembaga_aktif)
                if total_proses_rjk > 0 or total_temuan_rjk > 0:
                    simpan_metrik_akurasi_db('rujukan', total_proses_rjk, total_temuan_rjk, akurasi_rjk, role_reviewer=role_aktif, lembaga_ssr=lembaga_aktif)
                    
                st.toast("💾 Sinkronisasi metrik akurasi ke Database berhasil!", icon="✅")
                st.session_state['db_tercatat_batch'] = True
            except Exception as e:
                st.error(f"Gagal memproses pencatatan metrik ke database Neon: {e}")

            # CLEANSING DATA & FILTER DUPLIKAT SEBELUM MASUK TABEL DETAIL
            if not df_bawah.empty:
                kolom_wajib = [
                    'KATEGORI DATA', 'LEMBAGA SSR', 'TANGGAL', 'ID KLIEN', 'KODE PETUGAS', 
                    'NAMA KOTA', 'NAMA LAYANAN', 'NIK', 'TIPE SASARAN', 
                    'INDIKATOR KESALAHAN DATA', 'VALIDASI HASIL REVIEW', 'JUSTIFIKASI'
                ]
                for col in kolom_wajib:
                    if col not in df_bawah.columns: df_bawah[col] = "-"
                
                for col in kolom_wajib:
                    df_bawah[col] = df_bawah[col].fillna('-').astype(str).str.strip()
                    df_bawah[col] = df_bawah[col].replace({'nan': '-', 'None': '-', '': '-', 'NAN': '-'})
                
                df_bawah['TIPE SASARAN'] = df_bawah['TIPE SASARAN'].str.replace('.0', '', regex=False)
                
                def sesuaikan_nama_layanan(row_data):
                    kat = str(row_data['KATEGORI DATA']).strip().lower()
                    layanan = str(row_data['NAMA LAYANAN']).strip()
                    if 'rujukan' in kat:
                        return layanan if layanan not in ['', '-', 'nan', 'None'] else "-"
                    return "-"
                
                df_bawah['NAMA LAYANAN'] = df_bawah.apply(sesuaikan_nama_layanan, axis=1)

                # 🔥 PERUBAHAN: FILTER DUPLIKAT DARI DATABASE NEON DENGAN MEYEKAN KOLOM ROLE
                existing_master_keys = set()
                try:
                    from database import dapatkan_koneksi_neon
                    conn = dapatkan_koneksi_neon()
                    if conn:
                        with conn.cursor() as cur:
                            # Menambahkan COALESCE role_reviewer agar data lama tetap dikenali
                            cur.execute("SELECT LOWER(kategori_data), LOWER(lembaga_ssr), LOWER(tanggal), LOWER(id_klien), LOWER(indikator_kesalahan), LOWER(COALESCE(role_reviewer, 'SR')) FROM hasil_review_data;")
                            for r in cur.fetchall():
                                existing_master_keys.add((str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip(), str(r[4]).strip(), str(r[5]).strip()))
                        conn.close()
                except Exception: pass

                # 1. BUAT SALINAN FULL UNTUK TAMPILAN UI & AGREGASI
                df_full = df_bawah.copy()
                
                df_full['LEMBAGA SSR'] = df_full['LEMBAGA SSR'].fillna('-').astype(str).str.strip()
                df_full['INDIKATOR KESALAHAN DATA'] = df_full['INDIKATOR KESALAHAN DATA'].fillna('-').astype(str).str.strip()
                df_full['KATEGORI DATA'] = df_full['KATEGORI DATA'].fillna('-').astype(str).str.strip()
                
                # 2. PROSES FILTER HANYA UNTUK DATA YANG AKAN MASUK DB
                indices_to_drop = []
                for idx, row in df_bawah.iterrows():
                    kat = str(row.get('KATEGORI DATA', '')).strip().lower()
                    ssr = str(row.get('LEMBAGA SSR', '')).strip().lower()
                    tgl = str(row.get('TANGGAL', '')).strip().lower() 
                    id_klien = str(row.get('ID KLIEN', '')).strip().lower()
                    ind = str(row.get('INDIKATOR KESALAHAN DATA', '')).strip().lower()
                    role_key = role_aktif.strip().lower()
                    
                    # Cek 6 kombinasi parameter (termasuk Role)
                    if (kat, ssr, tgl, id_klien, ind, role_key) in existing_master_keys:
                        indices_to_drop.append(idx)
                
                if indices_to_drop:
                    df_bawah = df_bawah.drop(index=indices_to_drop).reset_index(drop=True)
                
                # 3. KIRIM DF_FULL KE UI (MENGANDUNG SEMUA BARIS)
                st.session_state['df_tabel_bawah'] = df_full
                
                # 4. SINKRONISASI KE 3 TABEL DETAIL AGREGASI
                try:
                    from database import simpan_paket_validasi_ke_tiga_tabel
                    
                    if not df_full.empty:
                        # AGREGASI MENGGUNAKAN DF_FULL
                        df_pjj_only = df_full[df_full['KATEGORI DATA'].str.title() == 'Penjangkauan']
                        
                        list_insert_tabel_1 = []
                        if not df_pjj_only.empty:
                            DAFTAR_INDIKATOR_AKTIF = [r["nama"] for r in (ATURAN_VALIDASI_BAWAAN + st.session_state.get('aturan_kustom', []))]
                            active_ssrs_pjj = sorted(list(df_pjj_only['LEMBAGA SSR'].unique()))
                            
                            for ind_err in DAFTAR_INDIKATOR_AKTIF:
                                for ssr_name in active_ssrs_pjj:
                                    hitung_kesalahan = len(df_pjj_only[(df_pjj_only['INDIKATOR KESALAHAN DATA'] == ind_err) & (df_pjj_only['LEMBAGA SSR'] == ssr_name)])
                                    if hitung_kesalahan > 0:
                                        list_insert_tabel_1.append((ssr_name, ind_err, hitung_kesalahan))
                        
                        df_rjk_only = df_full[df_full['KATEGORI DATA'].str.title() == 'Rujukan'].copy()
                        list_insert_tabel_2 = []
                        if not df_rjk_only.empty:
                            df_agregasi = df_rjk_only.groupby(['LEMBAGA SSR', 'INDIKATOR KESALAHAN DATA']).size().reset_index(name='JUMLAH KESALAHAN')
                            tanggal_skr = dt.date.today() if 'dt' in globals() else datetime.now().date()
                            for _, row_aggr in df_agregasi.iterrows():
                                list_insert_tabel_2.append((
                                    tanggal_skr,
                                    str(row_aggr.get('LEMBAGA SSR', '-')).strip(),
                                    str(row_aggr.get('INDIKATOR KESALAHAN DATA', '-')).strip(),
                                    int(row_aggr.get('JUMLAH KESALAHAN', 0))
                                ))
                        
                        # INSERT DETAIL MENGGUNAKAN DF_BAWAH
                        list_insert_tabel_3 = []

                        for _, row_all in df_bawah.iterrows():
                            pesan_validasi = str(row_all.get('VALIDASI HASIL REVIEW', '-')).strip()
                            
                            list_insert_tabel_3.append((
                                str(row_all.get('KATEGORI DATA', '-')), 
                                str(row_all.get('LEMBAGA SSR', '-')),
                                str(row_all.get('KODE PETUGAS', '-')), 
                                str(row_all.get('NAMA KOTA', '-')),
                                str(row_all.get('NAMA LAYANAN', '-')), 
                                str(row_all.get('TANGGAL', '-')),
                                str(row_all.get('ID KLIEN', '-')), 
                                str(row_all.get('NIK', '-')),
                                str(row_all.get('TIPE SASARAN', '-')), 
                                str(row_all.get('INDIKATOR KESALAHAN DATA', '-')),
                                pesan_validasi, 
                                str(row_all.get('JUSTIFIKASI', '-'))
                            ))
                        
                        # 🔥 PERUBAHAN: Teruskan peran (role_reviewer) ke fungsi simpan
                        sukses = simpan_paket_validasi_ke_tiga_tabel(list_insert_tabel_1, list_insert_tabel_2, list_insert_tabel_3, role_reviewer=role_aktif)
                        if sukses:
                            st.toast("💾 Sinkronisasi 3 tabel Agregasi dan detil per baris telah berhasil!", icon="✅")
                        else:
                            st.error("❌ Terjadi kesalahan teknis transaksi multi-tabel. Data gagal disimpan.")
                except Exception as e:
                    st.error(f"⚠️ Gagal mengeksekusi sinkronisasi database (Sistem Crash): {str(e)}")

            # =========================================================================
            # AUTO-REFRESH UI DENGAN DATA DARI DB (VERSI FINAL ROBUST SINKRON)
            # =========================================================================
            try:
                from database import (
                    ambil_agregasi_penjangkauan_terakhir, 
                    ambil_agregasi_rujukan_terakhir, 
                    ambil_hasil_review_utama_terakhir,
                    ambil_set_error_belum_direvisi  
                )
                
                # 🔥 PERUBAHAN: Tarik data dari database HANYA untuk peran aktif tersebut
                df_pjj_db, ts_pjj = ambil_agregasi_penjangkauan_terakhir(role_reviewer=role_aktif)
                df_rjk_db, ts_rjk = ambil_agregasi_rujukan_terakhir(role_reviewer=role_aktif)
                df_utama_db, ts_utama = ambil_hasil_review_utama_terakhir(role_reviewer=role_aktif)
                
                set_error_historis = ambil_set_error_belum_direvisi()
                
                st.session_state['df_tabel_atas'] = df_pjj_db 
                st.session_state['df_tabel_penjangkauan'] = df_pjj_db
                st.session_state['df_rujukan'] = df_rjk_db
                st.session_state['df_tabel_rujukan'] = df_rjk_db
                
                # 💡 LOGIKA DETEKSI KEPATUHAN REVISI (REPEAT ERROR DETECTION)
                if df_utama_db is not None and not df_utama_db.empty and set_error_historis is not None and not set_error_historis.empty:
                    
                    def normalisasi_tanggal(tgl_str):
                        tgl_str = str(tgl_str).strip().split(' ')[0] 
                        if not tgl_str or tgl_str.lower() == 'none' or tgl_str == 'nan':
                            return ""
                        try:
                            if '/' in tgl_str:
                                parts = tgl_str.split('/')
                                if len(parts) == 3:
                                    if len(parts[2]) == 4: return f"{parts[2]}-{parts[1]}-{parts[0]}"
                                    elif len(parts[0]) == 4: return f"{parts[0]}-{parts[1]}-{parts[2]}"
                            elif '-' in tgl_str:
                                parts = tgl_str.split('-')
                                if len(parts) == 3 and len(parts[0]) == 4: return tgl_str
                        except:
                            pass
                        return tgl_str.upper()
            
                    kamus_riwayat_revisi = {}
                    
                    for _, row_h in set_error_historis.iterrows():
                        def get_val(row, alternatives):
                            for alt in alternatives:
                                if alt in row: return str(row[alt]).strip().upper()
                            return ""
            
                        ind_h = get_val(row_h, ["INDIKATOR KESALAHAN DATA", "indikator_kesalahan_data"])
                        if "(KONFIRMASI)" in ind_h:
                            continue
                            
                        kat_h = get_val(row_h, ["KATEGORI DATA", "kategori_data"])
                        ssr_h = get_val(row_h, ["LEMBAGA SSR", "lembaga_ssr"])
                        id_h  = get_val(row_h, ["ID KLIEN", "id_klien"])
                        
                        tgl_raw = row_h.get("TANGGAL") if row_h.get("TANGGAL") is not None else row_h.get("tanggal", "")
                        tgl_h = normalisasi_tanggal(tgl_raw)
                        
                        status_rev = row_h.get("is_revisi")
                        is_rev_bool = True if (status_rev is True or str(status_rev).strip().lower() == 'true') else False
                        
                        kunci_gabung = f"{kat_h}_{ssr_h}_{tgl_h}_{id_h}_{ind_h}"
                        
                        if id_h and ind_h:
                            if kunci_gabung in kamus_riwayat_revisi:
                                if is_rev_bool: kamus_riwayat_revisi[kunci_gabung] = True
                            else:
                                kamus_riwayat_revisi[kunci_gabung] = is_rev_bool
                    
                    df_utama_db.columns = df_utama_db.columns.str.upper()
                    
                    for idx_db, row_db in df_utama_db.iterrows():
                        v_ind = str(row_db.get('INDIKATOR KESALAHAN DATA', '')).strip().upper()
                        if "(KONFIRMASI)" in v_ind: continue
                            
                        v_kat = str(row_db.get('KATEGORI DATA', '')).strip().upper()
                        v_ssr = str(row_db.get('LEMBAGA SSR', '')).strip().upper()
                        v_id  = str(row_db.get('ID KLIEN', '')).strip().upper()
                        v_tgl = normalisasi_tanggal(row_db.get('TANGGAL', ''))
                        
                        kunci_cek_db = f"{v_kat}_{v_ssr}_{v_tgl}_{v_id}_{v_ind}"
                        
                        if kunci_cek_db in kamus_riwayat_revisi:
                            was_revisied = kamus_riwayat_revisi[kunci_cek_db]
                            if was_revisied == True:
                                pesan = "⚠️ Kesalahan Berulang (Klaim revisi sebelumnya tidak valid!)"
                            else:
                                pesan = "Kesalahan pada ID yang berulang (belum direvisi)"
                                
                            df_utama_db.at[idx_db, 'VALIDASI HASIL REVIEW'] = pesan
                            df_utama_db.at[idx_db, 'Validasi Hasil Review'] = pesan
            
                if 'indeks_master_terpilih' in st.session_state and st.session_state['indeks_master_terpilih']:
                    idx_diapus = st.session_state['indeks_master_terpilih']
                    df_utama_db = df_utama_db.drop(index=idx_diapus, errors='ignore').reset_index(drop=True)
                    st.session_state['indeks_master_terpilih'] = []
            
                st.session_state['df_tabel_bawah'] = df_utama_db
                st.session_state['ts_terakhir_utama'] = ts_utama
                st.session_state['tanggal_terakhir_review'] = ts_pjj
                
                if ts_rjk:
                    st.session_state['tanggal_terakhir_rujukan_str'] = ts_rjk.strftime('%d-%m-%Y pukul %H:%M WIB') if hasattr(ts_rjk, 'strftime') else str(ts_rjk)
            
            except Exception as e:
                st.warning(f"⚠️ Berhasil simpan data, namun gagal me-refresh visualisasi dashboard UI ({e})")
            
            st.session_state['proses_selesai'] = True
            import time
            time.sleep(1.2) 
            st.rerun()

# ==========================================================================
# 5. RENDER LAYOUT UTAMA: DASHBOARD REVIEW DATA (URUTAN TABEL UI DISESUAIKAN)
# ==========================================================================
if menu_pilihan == "🎯 Dashboard Review Data":
    
    df_historis = st.session_state.get('df_tabel_atas', pd.DataFrame())
    peran = st.session_state.get('peran_user', 'SSR')  # Mengambil role dari session state hasil absensi popup
    
    if st.session_state.get('proses_selesai', False) or (df_historis is not None and not df_historis.empty):
        
        # Ambil data statistik ringkasan proses dari session state
        tot_data_penj = st.session_state.get('total_entri_penjangkauan', 0)
        tot_data_ruj = st.session_state.get('total_entri_rujukan', 0)
        tot_err_penj = st.session_state.get('temuan_penjangkauan', 0)
        tot_err_ruj = st.session_state.get('temuan_rujukan', 0)
        
        df_semua_error = st.session_state.get('df_tabel_bawah', st.session_state.get('df_review_utama', pd.DataFrame()))
        
        # Sinkronisasi parameter perhitungan awal jika bernilai kosong
        if (tot_err_penj == 0 and tot_err_ruj == 0) and (df_semua_error is not None and not df_semua_error.empty):
            df_semua_error = df_semua_error.copy()
            rename_dict_awal = {}
            for col in df_semua_error.columns:
                c_clean = str(col).strip().lower()
                if "indikator" in c_clean or "kesalahan" in c_clean or "error" in c_clean:
                    rename_dict_awal[col] = "INDIKATOR KESALAHAN DATA"
                elif "lembaga" in c_clean or "ssr" in c_clean:
                    rename_dict_awal[col] = "LEMBAGA SSR"
                elif "tanggal" in c_clean:
                    rename_dict_awal[col] = "TANGGAL"
                elif "id klien" in c_clean or "id_klien" in c_clean:
                    rename_dict_awal[col] = "ID KLIEN"
            
            if rename_dict_awal:
                df_semua_error = df_semua_error.rename(columns=rename_dict_awal)
            
            try:
                ind_rujukan = [str(r['nama']).strip().upper() for r in ATURAN_VALIDASI_RUJUKAN]
            except NameError:
                ind_rujukan = []
                
            df_semua_error.columns = [str(col).strip().upper() for col in df_semua_error.columns]
            mask_rujukan = df_semua_error['INDIKATOR KESALAHAN DATA'].str.strip().str.upper().isin(ind_rujukan)
            
            df_err_penj_asli = df_semua_error[~mask_rujukan]
            df_err_ruj_asli = df_semua_error[mask_rujukan]
            tot_err_penj = len(df_err_penj_asli)
            tot_err_ruj = len(df_err_ruj_asli)

        tot_err_penj = st.session_state.get('temuan_penjangkauan', tot_err_penj)
        tot_err_ruj = st.session_state.get('temuan_rujukan', tot_err_ruj)
        
        akurasi_penj = st.session_state.get('akurasi_penjangkauan', (100.0 if tot_data_penj == 0 else max(0.0, (tot_data_penj - tot_err_penj) / tot_data_penj * 100)))
        akurasi_ruj = st.session_state.get('akurasi_rujukan', (100.0 if tot_data_ruj == 0 else max(0.0, (tot_data_ruj - tot_err_ruj) / tot_data_ruj * 100)))
        
        teks_akurasi_penj = f"{akurasi_penj:.2f}%" if tot_data_penj > 0 else "100.00%"
        teks_akurasi_ruj = f"{akurasi_ruj:.2f}%" if tot_data_ruj > 0 else "100.00%"
        
        # =========================================================================
        # DEKLARASI TAB LAYOUT UTAMA
        # =========================================================================
        tab1, tab2, tab3 = st.tabs(["📋 Hasil Review Validasi Data", "📋 Hasil Review Validasi Data SSR","🕸️ Analisis Tren & Histori"])

        # -------------------------------------------------------------------------
        # TAB 1: AREA LAYOUT URUTAN TABEL SESUAI PERMINTAAN USER
        # -------------------------------------------------------------------------
        with tab1:
            # --- RENDER UI KARTU SKOR MENGGUNAKAN GLASSMORPHISM ---
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            tanggal_hari_ini = datetime.now(ZoneInfo('Asia/Jakarta')).strftime('%d %B %Y')
            st.markdown(f"""
                <p style='color: #94a3b8; font-size: 0.9rem; margin-bottom: 15px;'>
                    📅 <b>Executive Review Dashboard</b> | Tanggal Sesi: {tanggal_hari_ini} | Akses: <span style='color:#38bdf8; font-weight:700;'>{peran}</span>
                </p>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            with c1: st.metric(label="Total Data Penjangkauan", value=f"{tot_data_penj:,}")
            with c2: st.metric(label="Temuan Penjangkauan", value=f"{tot_err_penj:,}", delta="Perlu Perhatian", delta_color="inverse")
            with c3: st.metric(label="Akurasi Penjangkauan", value=teks_akurasi_penj)
            
            st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 15px 0;'>", unsafe_allow_html=True)
            
            c4, c5, c6 = st.columns(3)
            with c4: st.metric(label="Total Data Rujukan", value=f"{tot_data_ruj:,}")
            with c5: st.metric(label="Temuan Rujukan", value=f"{tot_err_ruj:,}", delta="Perlu Perhatian", delta_color="inverse")
            with c6: st.metric(label="Akurasi Rujukan", value=teks_akurasi_ruj)
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Style Kustom Ukuran Huruf Tab
            st.markdown("""
                <style>
                .stTabs [data-baseweb="tab"] p { font-size: 1.2rem !important; font-weight: 600 !important; color: #ffffff !important; }
                .stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 10px; }
                </style>
            """, unsafe_allow_html=True)
            
            # ---------------------------------------------------------------------
            # Urutan 1: TABEL AGREGASI PENJANGKAUAN
            # ---------------------------------------------------------------------
            st.markdown("#### 1️⃣ Tabel Agregasi Ringkasan Kesalahan - Data Penjangkauan")
            df_atas_view = st.session_state.get('df_tabel_atas', pd.DataFrame())
            try: ind_rujukan = [r['nama'] for r in ATURAN_VALIDASI_RUJUKAN]
            except NameError: ind_rujukan = []
            
            if df_atas_view is not None and not df_atas_view.empty:
                df_render = df_atas_view.copy()
                if df_render.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render.columns:
                    df_render = df_render.reset_index()
                df_render = df_render[~df_render['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan)].copy()
                
                if not df_render.empty:
                    kolom_indikator = 'INDIKATOR KESALAHAN DATA'
                    kolom_ssr = [c for c in df_render.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
                    for col in kolom_ssr: df_render[col] = pd.to_numeric(df_render[col], errors='coerce').fillna(0).astype(int)
                    ssr_aktif = [col for col in kolom_ssr if df_render[col].sum() > 0]
                    kolom_final = [kolom_indikator] + ssr_aktif + ['Jumlah per indikator', '%']
                    df_final = df_render[[c for c in kolom_final if c in df_render.columns]].copy()
                    total_error_penjangkauan = df_final['Jumlah per indikator'].sum()
                    if total_error_penjangkauan > 0: df_final['%'] = (df_final['Jumlah per indikator'] / total_error_penjangkauan) * 100
                    df_display = df_final.copy()
                    for col in ssr_aktif:
                        if col in df_display.columns: df_display[col] = df_display[col].astype(str).replace({'0': '-', '0.0': '-'})
                    
                    column_config = {
                        kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                        "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                        "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                    }
                    for col in ssr_aktif: column_config[col] = st.column_config.TextColumn(col, width="small")
                    st.dataframe(df_display, use_container_width=True, column_config=column_config, hide_index=True)
                else: st.info("✅ Tidak ada temuan kesalahan untuk Data Penjangkauan.")
            else: st.info("✨ Belum ada data review penjangkauan.")
            
            st.markdown("<br>", unsafe_allow_html=True)

            # ---------------------------------------------------------------------
            # Urutan 2: TABEL AGREGASI RUJUKAN
            # ---------------------------------------------------------------------
            st.markdown("#### 2️⃣ Tabel Agregasi Ringkasan Kesalahan - Data Rujukan")
            df_sumber = st.session_state.get('df_rujukan', pd.DataFrame())
            if df_sumber.empty and df_atas_view is not None: df_sumber = df_atas_view.copy()
            
            if df_sumber is not None and not df_sumber.empty:
                df_render_ruj = df_sumber.copy()
                if df_render_ruj.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render_ruj.columns: df_render_ruj = df_render_ruj.reset_index()
                if 'indikator_kesalahan_data' in df_render_ruj.columns: df_render_ruj = df_render_ruj.rename(columns={'indikator_kesalahan_data': 'INDIKATOR KESALAHAN DATA'})
                df_render_ruj = df_render_ruj[df_render_ruj['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan)].copy()
                
                if not df_render_ruj.empty:
                    kolom_indikator = 'INDIKATOR KESALAHAN DATA'
                    if 'Jumlah per indikator' not in df_render_ruj.columns and 'LEMBAGA SSR' in df_render_ruj.columns:
                        kolom_target_jumlah = 'JUMLAH KESALAHAN'
                        if kolom_target_jumlah not in df_render_ruj.columns:
                            opsi_kolom = [c for c in df_render_ruj.columns if 'JUMLAH' in str(c).upper() or 'KESALAHAN' in str(c).upper()]
                            if opsi_kolom: kolom_target_jumlah = opsi_kolom[0]
                        if kolom_target_jumlah in df_render_ruj.columns: df_render_ruj = df_render_ruj.groupby([kolom_indikator, 'LEMBAGA SSR'])[kolom_target_jumlah].sum().unstack(fill_value=0)
                        else: df_render_ruj = df_render_ruj.groupby([kolom_indikator, 'LEMBAGA SSR']).size().unstack(fill_value=0)
                        df_render_ruj['Jumlah per indikator'] = df_render_ruj.sum(axis=1)
                        df_render_ruj = df_render_ruj.reset_index()
                    
                    kolom_ssr_ruj = [c for c in df_render_ruj.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
                    for col in kolom_ssr_ruj: df_render_ruj[col] = pd.to_numeric(df_render_ruj[col], errors='coerce').fillna(0).astype(int)
                    ssr_aktif_ruj = [col for col in kolom_ssr_ruj if df_render_ruj[col].sum() > 0]
                    kolom_final_ruj = [kolom_indikator] + ssr_aktif_ruj + ['Jumlah per indikator', '%']
                    df_final_ruj = df_render_ruj[[c for c in kolom_final_ruj if c in df_render_ruj.columns]].copy()
                    total_error_rujukan = df_final_ruj['Jumlah per indikator'].sum() if 'Jumlah per indikator' in df_final_ruj.columns else 0
                    df_final_ruj['%'] = (df_final_ruj['Jumlah per indikator'] / total_error_rujukan) * 100 if total_error_rujukan > 0 else 0.0
                    df_display_ruj = df_final_ruj.copy()
                    for col in ssr_aktif_ruj:
                        if col in df_display_ruj.columns: df_display_ruj[col] = df_display_ruj[col].astype(str).replace({'0': '-', '0.0': '-'})
                    
                    column_config_ruj = {
                        kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                        "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                        "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                    }
                    for col in ssr_aktif_ruj: column_config_ruj[col] = st.column_config.TextColumn(str(col).upper(), width="small")
                    st.dataframe(df_display_ruj, use_container_width=True, column_config=column_config_ruj, hide_index=True)
                else: st.info("✅ Tidak ada temuan kesalahan untuk Data Rujukan.")
            else: st.info("✨ Belum ada data review rujukan.")
            
            st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.15); margin: 35px 0;'>", unsafe_allow_html=True)

            # ---------------------------------------------------------------------
            # Urutan 3: TABEL GABUNGAN UTAMA (ONE-TABLE INTEGRATED EDITOR)
            # ---------------------------------------------------------------------
            st.markdown("#### 3️⃣ Tabel Gabungan Hasil Review Validasi Data (Penjangkauan & Rujukan)")
            
            if peran == "SSR":
                st.info("💡 **Mode Terproteksi SSR**: Anda hanya diizinkan memberikan centang `Pilih` dan mengedit kolom `Justifikasi` pada baris konfirmasi.")
            else:
                st.success("🔓 **Mode Akses Penuh SR**: Anda berwenang mengelola seluruh instrumen instansi.")
            
            df_master_source = st.session_state.get('df_tabel_bawah', st.session_state.get('df_review_utama', pd.DataFrame()))
            
            if df_master_source is not None and not df_master_source.empty:
                df_master = df_master_source.copy()
                df_master["_indeks_asli_master"] = df_master.index
                df_master.columns = [str(c).strip() for c in df_master.columns]
                
                # Normalisasi Nama Kolom sesuai susunan baku Anda
                rename_dict = {}
                for col in df_master.columns:
                    c_clean = str(col).strip().lower()
                    if "indikator" in c_clean or "kesalahan" in c_clean or "error" in c_clean: rename_dict[col] = "Indikator Kesalahan Data"
                    elif "validasi" in c_clean or "review" in c_clean: rename_dict[col] = "Validasi Hasil Review"
                    elif "justifikasi" in c_clean: rename_dict[col] = "Justifikasi"
                    elif "lembaga" in c_clean or "ssr" in c_clean: rename_dict[col] = "Lembaga SSR"
                    elif "layanan" in c_clean: rename_dict[col] = "Nama Layanan"
                    elif "petugas" in c_clean: rename_dict[col] = "Kode Petugas"
                    elif "kota" in c_clean or "kabupaten" in c_clean: rename_dict[col] = "Nama Kota"
                    elif "tanggal" in c_clean: rename_dict[col] = "Tanggal"
                    elif "id klien" in c_clean or "id_klien" in c_clean: rename_dict[col] = "ID Klien"
                    elif "nik" == c_clean: rename_dict[col] = "NIK"
                    elif "sasaran" in c_clean: rename_dict[col] = "Tipe Sasaran"
                        
                if rename_dict:
                    df_master = df_master.rename(columns=rename_dict)
            
                if "Kategori Data" not in df_master.columns:
                    if "Indikator Kesalahan Data" in df_master.columns:
                        try: ind_rujukan_caps = [str(r['nama']).strip().upper() for r in ATURAN_VALIDASI_RUJUKAN]
                        except: ind_rujukan_caps = []
                        df_master["Kategori Data"] = df_master["Indikator Kesalahan Data"].apply(
                            lambda x: "Rujukan" if str(x).strip().upper() in ind_rujukan_caps else "Penjangkauan"
                        )
                    else:
                        df_master["Kategori Data"] = "Penjangkauan"
            
                # SUSUNAN KOLOM DI KUNCI (TIDAK BERUBAH)
                kolom_susunan_gabungan = [
                    "Pilih", "Kategori Data", "Lembaga SSR", "Kode Petugas", "Nama Kota", "Nama Layanan", 
                    "Tanggal", "ID Klien", "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", "Validasi Hasil Review", "Justifikasi"
                ]
            
                for col in kolom_susunan_gabungan:
                    if col not in df_master.columns:
                        df_master[col] = False if col == "Pilih" else "-"
            
                # Dropdown filter di atas tabel gabungan
                list_ssr_unik = sorted(df_master["Lembaga SSR"].dropna().unique().tolist())
                col_ssr, col_kat, col_spacer = st.columns([1.2, 1.2, 2.6])
                with col_ssr: pilihan_ssr = st.selectbox("🎯 Saring Lembaga SSR:", options=["Semua"] + list_ssr_unik, index=0)
                with col_kat: pilihan_kategori = st.selectbox("📂 Saring Kategori Data:", options=["Semua", "Penjangkauan", "Rujukan"], index=0)
                
                if pilihan_ssr != "Semua": df_master = df_master[df_master["Lembaga SSR"] == pilihan_ssr]
                if pilihan_kategori != "Semua": df_master = df_master[df_master["Kategori Data"] == pilihan_kategori]
                    
                df_view_gabungan = df_master[kolom_susunan_gabungan + ["_indeks_asli_master"]].copy()
            
                # Gembok kolom Justifikasi pada baris Non-Konfirmasi
                for idx, row in df_view_gabungan.iterrows():
                    if "konfirmasi" not in str(row['Indikator Kesalahan Data']).lower():
                        df_view_gabungan.at[idx, 'Justifikasi'] = "🔒 Terkunci (Bukan Konfirmasi)"
            
                if df_view_gabungan.empty:
                    st.info(f"✨ Tidak ada data kesalahan untuk filter tersebut.")
                else:
                    # Aturan Proteksi Hak Akses Peran
                    if peran == "SSR":
                        kolom_dikunci = [c for c in kolom_susunan_gabungan if c not in ["Pilih", "Justifikasi"]]
                    else:
                        kolom_dikunci = [c for c in kolom_susunan_gabungan if c not in ["Pilih", "Justifikasi", "Validasi Hasil Review"]]
                        
                    df_hasil_edit = st.data_editor(
                        df_view_gabungan[kolom_susunan_gabungan],
                        use_container_width=True,
                        hide_index=True, 
                        key="editor_validasi_tunggal_tab1",
                        column_config={
                            "Pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                            "Indikator Kesalahan Data": st.column_config.TextColumn("Indikator Kesalahan Data", width=300),
                            "Justifikasi": st.column_config.TextColumn("Justifikasi", width=260),
                        },
                        disabled=kolom_dikunci
                    )
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_save, _ = st.columns([1, 2])
                    with col_save:
                        if st.button("💾 Simpan Perubahan Validasi (Tabel Gabungan)", type="primary"):
                            with st.spinner("Menyimpan progres validasi..."):
                                list_log_db = []
                                indeks_master_terpilih = []
                                for idx, row_edit in df_hasil_edit.iterrows():
                                    ind_text = str(row_edit.get('Indikator Kesalahan Data', ''))
                                    text_justifikasi = str(row_edit.get('Justifikasi', '')).strip()
                                    is_konfirmasi = "konfirmasi" in ind_text.lower()
                                    status_revisi = bool(row_edit.get('Pilih', False))
                                    
                                    if not is_konfirmasi or "🔒 Terkunci" in text_justifikasi:
                                        text_justifikasi = ""
                                        
                                    if status_revisi or (is_konfirmasi and text_justifikasi != ""):
                                        list_log_db.append((
                                            str(row_edit.get('Kategori Data', '-')), str(row_edit.get('Lembaga SSR', '-')),
                                            str(row_edit.get('Tanggal', '-')), str(row_edit.get('ID Klien', '-')), 
                                            ind_text, status_revisi, text_justifikasi
                                        ))
                                        if idx in df_view_gabungan.index:
                                            indeks_master_terpilih.append(df_view_gabungan.at[idx, "_indeks_asli_master"])
                                
                                if len(list_log_db) > 0:
                                    if simpan_log_ke_neon(list_log_db):
                                        if 'df_tabel_bawah' in st.session_state and st.session_state['df_tabel_bawah'] is not None:
                                            st.session_state['df_tabel_bawah'] = st.session_state['df_tabel_bawah'].drop(index=indeks_master_terpilih, errors='ignore').reset_index(drop=True)
                                        if 'df_review_utama' in st.session_state and st.session_state['df_review_utama'] is not None:
                                            st.session_state['df_review_utama'] = st.session_state['df_review_utama'].drop(index=indeks_master_terpilih, errors='ignore').reset_index(drop=True)
                                        st.success(f"🎉 Sukses menyinkronkan {len(list_log_db)} data ke log database!")
                                        import time
                                        time.sleep(1.0)
                                        st.rerun()
                                    else: st.error("❌ Gagal menyimpan perubahan ke server database.")
                                else: st.info("ℹ️ Tidak ada baris perubahan data yang dipilih untuk disimpan.")
            else:
                st.info("✨ Belum ada data review gabungan yang tersedia.")

        
        # -------------------------------------------------------------------------
# TAB 2: KHUSUS VALIDASI DATA SSR (MURNI FILTER LEMBAGA LOGIN / FILTER SR)
# -------------------------------------------------------------------------
with tab2:
    # =========================================================================
    # 1. JUDUL DINAMIS & FILTER BERDASARKAN LEVEL USER BERDASARKAN POPUP LOGIN
    # =========================================================================
    
    # Mengambil status role dan nama lembaga dari session state hasil popup login
    role_aktif = st.session_state.get('current_role', 'SSR')
    lembaga_aktif = st.session_state.get('current_lembaga', '')
    
    if role_aktif == "SR":
        # ---------------------------------------------------------------------
        # TAMPILKAN LEVEL SR (Judul Tetap + Filter Dropdown Seluruh SSR)
        # ---------------------------------------------------------------------
        st.markdown(f"### 🏛️ {lembaga_aktif}") # Output: SR PKBI JAWA BARAT
        
        # Ambil daftar seluruh nama lembaga yang berstatus 'SSR' dari master_lembaga secara dinamis
        daftar_seluruh_ssr = [
            l["Nama Lembaga"] for l in st.session_state.master_lembaga if l["Status"] == "SSR"
        ]
        daftar_seluruh_ssr = sorted(daftar_seluruh_ssr) # Urutkan alfabetis A-Z
        
        # Buat susunan kolom (Layout) berdampingan agar filter berada di samping kanan judul
        col_judul, col_filter = st.columns([1.2, 1])
        
        with col_judul:
            st.write("") # Memberi ruang kosong agar sejajar vertikal dengan selectbox
            st.caption("🌐 **Mode Pemantauan Provinsi:** Anda dapat menyaring data per lembaga di bawah ini.")
            
        with col_filter:
            # Pilihan default di paling atas
            pilihan_ssr = ["✨ Semua SSR"] + daftar_seluruh_ssr
            
            # Inilah variabel 'ssr_terpilih' yang Anda butuhkan
            ssr_terpilih = st.selectbox(
                "Saring Tampilan Data Berdasarkan Lembaga SSR:",
                options=pilihan_ssr,
                index=0,
                key="filter_ssr_level_sr",
                label_visibility="collapsed" # Menyembunyikan label bawaan agar rapi berdampingan
            )
            
    else:
        # ---------------------------------------------------------------------
        # TAMPILKAN LEVEL SSR (Judul otomatis fleksibel mengunci nama yang login)
        # ---------------------------------------------------------------------
        nama_ssr_caps = f"SSR {lembaga_aktif}" if not str(lembaga_aktif).startswith("SSR") else lembaga_aktif
        st.markdown(f"### 🏢 {nama_ssr_caps}")
        
        # Jika yang login adalah SSR, maka 'ssr_terpilih' otomatis terkunci ke lembaga mereka sendiri
        ssr_terpilih = lembaga_aktif
    
    # Ambil data master untuk Tab 2
    df_master_source_tab2 = st.session_state.get('df_tabel_bawah', st.session_state.get('df_review_utama', pd.DataFrame()))
    df_atas_view_tab2 = st.session_state.get('df_tabel_atas', pd.DataFrame())
    
    # Ambil aturan rujukan untuk pengelompokan indikator
    try: 
        ind_rujukan_tab2 = [r['nama'] for r in ATURAN_VALIDASI_RUJUKAN]
    except NameError: 
        ind_rujukan_tab2 = []

    # --- 🛠️ PROSES FILTER DATA BERDASARKAN USER LOGIN ATAU FILTER DROP DOWN SR ---
    if df_master_source_tab2 is not None and not df_master_source_tab2.empty:
        df_master_tab2 = df_master_source_tab2.copy()
        kolom_ssr_bawah = [c for c in df_master_tab2.columns if "lembaga" in str(c).lower() or "ssr" in str(c).lower()]
        
        if kolom_ssr_bawah:
            # Jika user adalah SSR, kunci data murni miliknya
            if role_aktif != "SR":
                df_master_tab2 = df_master_tab2[df_master_tab2[kolom_ssr_bawah[0]].astype(str).str.upper() == str(ssr_terpilih).upper()].copy()
            # Jika user adalah SR dan memilih SSR tertentu (bukan "✨ Semua SSR")
            elif role_aktif == "SR" and ssr_terpilih != "✨ Semua SSR":
                df_master_tab2 = df_master_tab2[df_master_tab2[kolom_ssr_bawah[0]].astype(str).str.upper() == str(ssr_terpilih).upper()].copy()
    else:
        df_master_tab2 = pd.DataFrame()

    # --- KUALIFIKASI STATISTIK KARTU SKOR KHUSUS LEMBAGA SSR TERKAIT ---
    if not df_master_tab2.empty:
        col_ind_clean = [c for c in df_master_tab2.columns if "indikator" in str(c).lower() or "kesalahan" in str(c).lower() or "error" in str(c).lower()]
        if col_ind_clean:
            try: ind_ruj_caps = [str(r).strip().upper() for r in ind_rujukan_tab2]
            except: ind_ruj_caps = []
            mask_ruj_tab2 = df_master_tab2[col_ind_clean[0]].astype(str).str.strip().str.upper().isin(ind_ruj_caps)
            
            tot_err_penj_tab2 = len(df_master_tab2[~mask_ruj_tab2])
            tot_err_ruj_tab2 = len(df_master_tab2[mask_ruj_tab2])
        else:
            tot_err_penj_tab2 = 0
            tot_err_ruj_tab2 = 0
    else:
        tot_err_penj_tab2 = 0
        tot_err_ruj_tab2 = 0

    # Ambil data metrik akurasi terakhir dari DB (MUTLAK MENGGUNAKAN STATUS SSR)
    try:
        metrik_db, _ = ambil_metrik_akurasi_terakhir(
            role_reviewer="SSR", 
            lembaga_ssr=None if (role_aktif == "SR" and ssr_terpilih == "✨ Semua SSR") else ssr_terpilih
        )
        if not isinstance(metrik_db, dict): metrik_db = {}
    except Exception:
        metrik_db = {}

    tot_data_penj_tab2 = st.session_state.get('total_entri_penjangkauan', metrik_db.get('total_penjangkauan', 0 if role_aktif == "SR" else 100))
    tot_data_ruj_tab2 = st.session_state.get('total_entri_rujukan', metrik_db.get('total_rujukan', 0 if role_aktif == "SR" else 100))
    
    akurasi_penj_tab2 = (100.0 if tot_data_penj_tab2 == 0 else max(0.0, (tot_data_penj_tab2 - tot_err_penj_tab2) / tot_data_penj_tab2 * 100))
    akurasi_ruj_tab2 = (100.0 if tot_data_ruj_tab2 == 0 else max(0.0, (tot_data_ruj_tab2 - tot_err_ruj_tab2) / tot_data_ruj_tab2 * 100))
    
    teks_akurasi_penj_tab2 = f"{akurasi_penj_tab2:.2f}%" if tot_data_penj_tab2 > 0 else "100.00%"
    teks_akurasi_ruj_tab2 = f"{akurasi_ruj_tab2:.2f}%" if tot_data_ruj_tab2 > 0 else "100.00%"

    # Render Kartu Skor Lokal SSR (Glassmorphism)
    st.markdown('<div class="glass-card" style="background: rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1);">', unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns(3)
    with cc1: st.metric(label="Data Penjangkauan Terproses", value=f"{tot_data_penj_tab2:,}")
    with cc2: st.metric(label="Temuan Penjangkauan (Lembaga)", value=f"{tot_err_penj_tab2:,}", delta="Perlu Tindakan", delta_color="inverse")
    with cc3: st.metric(label="Akurasi Penjangkauan Lokal", value=teks_akurasi_penj_tab2)
    
    st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 15px 0;'>", unsafe_allow_html=True)
    
    cc4, cc5, cc6 = st.columns(3)
    with cc4: st.metric(label="Data Rujukan Terproses", value=f"{tot_data_ruj_tab2:,}")
    with cc5: st.metric(label="Temuan Rujukan (Lembaga)", value=f"{tot_err_ruj_tab2:,}", delta="Perlu Tindakan", delta_color="inverse")
    with cc6: st.metric(label="Akurasi Rujukan Lokal", value=teks_akurasi_ruj_tab2)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ---------------------------------------------------------------------
    # Urutan 1: TABEL AGREGASI PENJANGKAUAN (KONSISTEN PARAMETER/KOLOM SSR)
    # ---------------------------------------------------------------------
    st.markdown("#### 1️⃣ Tabel Agregasi Ringkasan Kesalahan - Data Penjangkauan")
    if df_atas_view_tab2 is not None and not df_atas_view_tab2.empty:
        df_render_tab2 = df_atas_view_tab2.copy()
        if df_render_tab2.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render_tab2.columns:
            df_render_tab2 = df_render_tab2.reset_index()
        
        df_render_tab2 = df_render_tab2[~df_render_tab2['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan_tab2)].copy()
        
        if not df_render_tab2.empty:
            kolom_indikator = 'INDIKATOR KESALAHAN DATA'
            
            # Deteksi apakah menyaring satu lembaga tunggal atau semua SSR
            is_lembaga_tunggal = (ssr_terpilih != "✨ Semua SSR")
            
            if is_lembaga_tunggal and ssr_terpilih in df_render_tab2.columns:
                df_render_tab2[ssr_terpilih] = pd.to_numeric(df_render_tab2[ssr_terpilih], errors='coerce').fillna(0).astype(int)
                df_render_tab2['Jumlah per indikator'] = df_render_tab2[ssr_terpilih]
                total_error_lokal = df_render_tab2['Jumlah per indikator'].sum()
                df_render_tab2['%'] = (df_render_tab2['Jumlah per indikator'] / total_error_lokal * 100) if total_error_lokal > 0 else 0.0
                
                kolom_final_tab2 = [kolom_indikator, ssr_terpilih, 'Jumlah per indikator', '%']
                df_display_tab2 = df_render_tab2[[c for c in kolom_final_tab2 if c in df_render_tab2.columns]].copy()
                df_display_tab2[ssr_terpilih] = df_display_tab2[ssr_terpilih].astype(str).replace({'0': '-', '0.0': '-'})
                
                config_t2_penj = {
                    kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                    ssr_terpilih: st.column_config.TextColumn(f"Jumlah ({ssr_terpilih})", width="small"),
                    "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                    "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                }
                st.dataframe(df_display_tab2, use_container_width=True, column_config=config_t2_penj, hide_index=True)
            else:
                # JIKA PILIH "✨ SEMUA SSR" -> Tarik seluruh kolom berstatus lembaga SSR dari master data
                list_nama_ssr_master = [l["Nama Lembaga"] for l in st.session_state.master_lembaga if l["Status"] == "SSR"]
                kolom_ssr_ada = [c for c in df_render_tab2.columns if c in list_nama_ssr_master]
                
                if kolom_ssr_ada:
                    for c in kolom_ssr_ada:
                        df_render_tab2[c] = pd.to_numeric(df_render_tab2[c], errors='coerce').fillna(0).astype(int)
                    
                    df_render_tab2['Jumlah per indikator'] = df_render_tab2[kolom_ssr_ada].sum(axis=1)
                    total_error_all = df_render_tab2['Jumlah per indikator'].sum()
                    df_render_tab2['%'] = (df_render_tab2['Jumlah per indikator'] / total_error_all * 100) if total_error_all > 0 else 0.0
                    
                    config_t2_penj = {
                        kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                        "Jumlah per indikator": st.column_config.NumberColumn("Total Gabungan SSR", width="small", format="%d"),
                        "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                    }
                    st.dataframe(df_render_tab2[[kolom_indikator] + kolom_ssr_ada + ['Jumlah per indikator', '%']], use_container_width=True, column_config=config_t2_penj, hide_index=True)
                else:
                    st.info(f"✅ Tidak ada temuan kesalahan data Penjangkauan tercatat untuk lembaga {ssr_terpilih}.")
        else:
            st.info("✅ Tidak ada temuan kesalahan untuk Data Penjangkauan.")
    else:
        st.info("✨ Belum ada data review penjangkauan.")
        
    st.markdown("<br>", unsafe_allow_html=True)

    # ---------------------------------------------------------------------
    # Urutan 2: TABEL AGREGASI RUJUKAN (KONSISTEN PARAMETER/KOLOM SSR)
    # ---------------------------------------------------------------------
    st.markdown("#### 2️⃣ Tabel Agregasi Ringkasan Kesalahan - Data Rujukan")
    df_sumber_tab2 = st.session_state.get('df_rujukan', pd.DataFrame())
    if df_sumber_tab2.empty and df_atas_view_tab2 is not None: 
        df_sumber_tab2 = df_atas_view_tab2.copy()
    
    if df_sumber_tab2 is not None and not df_sumber_tab2.empty:
        df_render_ruj_t2 = df_sumber_tab2.copy()
        if df_render_ruj_t2.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render_ruj_t2.columns: 
            df_render_ruj_t2 = df_render_ruj_t2.reset_index()
        if 'indikator_kesalahan_data' in df_render_ruj_t2.columns: 
            df_render_ruj_t2 = df_render_ruj_t2.rename(columns={'indikator_kesalahan_data': 'INDIKATOR KESALAHAN DATA'})
        
        df_render_ruj_t2 = df_render_ruj_t2[df_render_ruj_t2['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan_tab2)].copy()
        
        if not df_render_ruj_t2.empty:
            kolom_indikator = 'INDIKATOR KESALAHAN DATA'
            
            if 'Jumlah per indikator' not in df_render_ruj_t2.columns and 'LEMBAGA SSR' in df_render_ruj_t2.columns:
                kolom_target_jumlah = 'JUMLAH KESALAHAN'
                if kolom_target_jumlah not in df_render_ruj_t2.columns:
                    opsi_kolom = [c for c in df_render_ruj_t2.columns if 'JUMLAH' in str(c).upper() or 'KESALAHAN' in str(c).upper()]
                    if opsi_kolom: kolom_target_jumlah = opsi_kolom[0]
                if kolom_target_jumlah in df_render_ruj_t2.columns: 
                    df_render_ruj_t2 = df_render_ruj_t2.groupby([kolom_indikator, 'LEMBAGA SSR'])[kolom_target_jumlah].sum().unstack(fill_value=0)
                else: 
                    df_render_ruj_t2 = df_render_ruj_t2.groupby([kolom_indikator, 'LEMBAGA SSR']).size().unstack(fill_value=0)
                df_render_ruj_t2 = df_render_ruj_t2.reset_index()

            # Selalu arahkan filter aktif murni ke nama SSR resmi dari master data
            list_nama_ssr_master = [l["Nama Lembaga"] for l in st.session_state.master_lembaga if l["Status"] == "SSR"]
            
            if ssr_terpilih != "✨ Semua SSR":
                kolom_aktif_t2 = [ssr_terpilih] if ssr_terpilih in df_render_ruj_t2.columns else []
            else:
                kolom_aktif_t2 = [c for c in df_render_ruj_t2.columns if c in list_nama_ssr_master]
                
            if kolom_aktif_t2:
                for col in kolom_aktif_t2: 
                    df_render_ruj_t2[col] = pd.to_numeric(df_render_ruj_t2[col], errors='coerce').fillna(0).astype(int)
                
                df_render_ruj_t2['Jumlah per indikator'] = df_render_ruj_t2[kolom_aktif_t2].sum(axis=1)
                total_error_ruj_lokal = df_render_ruj_t2['Jumlah per indikator'].sum()
                df_render_ruj_t2['%'] = (df_render_ruj_t2['Jumlah per indikator'] / total_error_ruj_lokal * 100) if total_error_ruj_lokal > 0 else 0.0
                
                kolom_final_ruj_t2 = [kolom_indikator] + kolom_aktif_t2 + ['Jumlah per indikator', '%']
                df_display_ruj_t2 = df_render_ruj_t2[[c for c in kolom_final_ruj_t2 if c in df_render_ruj_t2.columns]].copy()
                
                config_t2_ruj = {
                    kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                    "Jumlah per indikator": st.column_config.NumberColumn("Total SSR", width="small", format="%d"),
                    "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                }
                for col in kolom_aktif_t2: 
                    config_t2_ruj[col] = st.column_config.NumberColumn(str(col).upper(), width="small", format="%d")
                st.dataframe(df_display_ruj_t2, use_container_width=True, column_config=config_t2_ruj, hide_index=True)
            else:
                st.info(f"✅ Tidak ada temuan kesalahan data Rujukan tercatat untuk lembaga {ssr_terpilih}.")
        else:
            st.info("✅ Tidak ada temuan kesalahan untuk Data Rujukan.")
    else:
        st.info("✨ Belum ada data review rujukan.")
        
    st.markdown("<hr style='border: 1px solid rgba(255,255,255,0.15); margin: 35px 0;'>", unsafe_allow_html=True)
        
    # ---------------------------------------------------------------------
    # Urutan 3: TABEL GABUNGAN UTAMA SSR (ONE-TABLE INTEGRATED EDITOR)
    # ---------------------------------------------------------------------
    st.markdown("#### 3️⃣ Tabel Gabungan Hasil Review Validasi Data (Penjangkauan & Rujukan)")
    
    # Label nama dinamis sesuai filter yang sedang aktif
    nama_lembaga_tampil = ssr_terpilih if (role_aktif != "SR" or ssr_terpilih != "✨ Semua SSR") else "Semua Lembaga SSR"
    st.info(f"💡 **Mode Terproteksi Lembaga**: Menampilkan data review murni yang menjadi hak jawab **{nama_lembaga_tampil}**.")
    
    if not df_master_tab2.empty:
        df_master_t2_gab = df_master_tab2.copy()
        df_master_t2_gab["_indeks_asli_master"] = df_master_t2_gab.index
        df_master_t2_gab.columns = [str(c).strip() for c in df_master_t2_gab.columns]
        
        # Normalisasi Nama Kolom Gabungan
        rename_dict_t2 = {}
        for col in df_master_t2_gab.columns:
            c_clean = str(col).strip().lower()
            if "indikator" in c_clean or "kesalahan" in c_clean or "error" in c_clean: rename_dict_t2[col] = "Indikator Kesalahan Data"
            elif "validasi" in c_clean or "review" in c_clean: rename_dict_t2[col] = "Validasi Hasil Review"
            elif "justifikasi" in c_clean: rename_dict_t2[col] = "Justifikasi"
            elif "lembaga" in c_clean or "ssr" in c_clean: rename_dict_t2[col] = "Lembaga SSR"
            elif "layanan" in c_clean: rename_dict_t2[col] = "Nama Layanan"
            elif "petugas" in c_clean: rename_dict_t2[col] = "Kode Petugas"
            elif "kota" in c_clean or "kabupaten" in c_clean: rename_dict_t2[col] = "Nama Kota"
            elif "tanggal" in c_clean: rename_dict_t2[col] = "Tanggal"
            elif "id klien" in c_clean or "id_klien" in c_clean: rename_dict_t2[col] = "ID Klien"
            elif "nik" == c_clean: rename_dict_t2[col] = "NIK"
            elif "sasaran" in c_clean: rename_dict_t2[col] = "Tipe Sasaran"
        
        if rename_dict_t2:
            df_master_t2_gab = df_master_t2_gab.rename(columns=rename_dict_t2)
        
        if "Kategori Data" not in df_master_t2_gab.columns:
            if "Indikator Kesalahan Data" in df_master_t2_gab.columns:
                df_master_t2_gab["Kategori Data"] = df_master_t2_gab["Indikator Kesalahan Data"].apply(
                    lambda x: "Rujukan" if str(x).strip().upper() in [str(r).strip().upper() for r in ind_rujukan_tab2] else "Penjangkauan"
                )
            else:
                df_master_t2_gab["Kategori Data"] = "Penjangkauan"
        
        # Susunan Baku Kolom Tabel Gabungan
        kolom_susunan_gabungan_t2 = [
            "Pilih", "Kategori Data", "Lembaga SSR", "Kode Petugas", "Nama Kota", "Nama Layanan", 
            "Tanggal", "ID Klien", "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", "Validasi Hasil Review", "Justifikasi"
        ]
        
        for col in kolom_susunan_gabungan_t2:
            if col not in df_master_t2_gab.columns:
                df_master_t2_gab[col] = False if col == "Pilih" else "-"
                
        # Terapkan gembok proteksi Justifikasi non-konfirmasi untuk keamanan internal SSR
        for idx, row in df_master_t2_gab.iterrows():
            if "konfirmasi" not in str(row['Indikator Kesalahan Data']).lower():
                df_master_t2_gab.at[idx, 'Justifikasi'] = "🔒 Terkunci (Bukan Konfirmasi)"
                
        df_view_gabungan_t2 = df_master_t2_gab[kolom_susunan_gabungan_t2 + ["_indeks_asli_master"]].copy()
        
        # Render Data Editor khusus Tab 2
        kolom_dikunci_t2 = [c for c in kolom_susunan_gabungan_t2 if c not in ["Pilih", "Justifikasi"]]
        
        df_hasil_edit_t2 = st.data_editor(
            df_view_gabungan_t2[kolom_susunan_gabungan_t2],
            use_container_width=True,
            hide_index=True, 
            key="editor_validasi_tunggal_tab2",
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", default=False),
                "Indikator Kesalahan Data": st.column_config.TextColumn("Indikator Kesalahan Data", width=300),
                "Justifikasi": st.column_config.TextColumn("Justifikasi", width=260),
            },
            disabled=kolom_dikunci_t2
        )
        
        # Tombol Simpan Perubahan khusus Tab 2
        st.markdown("<br>", unsafe_allow_html=True)
        col_save_t2, _ = st.columns([1, 2])
        with col_save_t2:
            # Mengubah teks tombol simpan secara dinamis mengikuti context user
            label_tombol_simpan = "💾 Simpan Perubahan Validasi SR" if role_aktif == "SR" else "💾 Simpan Perubahan Validasi SSR"
            if st.button(label_tombol_simpan, type="primary", key="btn_save_tab2"):
                with st.spinner("Menyimpan log verifikasi lembaga..."):
                    list_log_db_t2 = []
                    indeks_master_terpilih_t2 = []
                    
                    for idx, row_edit in df_hasil_edit_t2.iterrows():
                        ind_text = str(row_edit.get('Indikator Kesalahan Data', ''))
                        text_justifikasi = str(row_edit.get('Justifikasi', '')).strip()
                        is_konfirmasi = "konfirmasi" in ind_text.lower()
                        status_revisi = bool(row_edit.get('Pilih', False))
                        
                        if not is_konfirmasi or "🔒 Terkunci" in text_justifikasi:
                            text_justifikasi = ""
                            
                        if status_revisi or (is_konfirmasi and text_justifikasi != ""):
                            list_log_db_t2.append((
                                str(row_edit.get('Kategori Data', '-')),
                                str(row_edit.get('Lembaga SSR', '-')),
                                str(row_edit.get('Kode Petugas', '-')),
                                str(row_edit.get('Nama Kota', '-')),
                                str(row_edit.get('Nama Layanan', '-')),
                                str(row_edit.get('Tanggal', '-')),
                                str(row_edit.get('ID Klien', '-')),
                                str(row_edit.get('NIK', '-')),
                                str(row_edit.get('Tipe Sasaran', '-')),
                                ind_text,
                                str(row_edit.get('Validasi Hasil Review', '-')),
                                text_justifikasi,
                                bool(status_revisi)
                            ))
                            if idx in df_view_gabungan_t2.index:
                                indeks_master_terpilih_t2.append(df_view_gabungan_t2.at[idx, "_indeks_asli_master"])
                    
                    if len(list_log_db_t2) > 0:
                        if simpan_log_ke_neon(list_log_db_t2):
                            # Hapus baris yang berhasil disimpan dari session state utama agar sinkron
                            if 'df_tabel_bawah' in st.session_state and st.session_state['df_tabel_bawah'] is not None:
                                st.session_state['df_tabel_bawah'] = st.session_state['df_tabel_bawah'].drop(index=indeks_master_terpilih_t2, errors='ignore').reset_index(drop=True)
                            if 'df_review_utama' in st.session_state and st.session_state['df_review_utama'] is not None:
                                st.session_state['df_review_utama'] = st.session_state['df_review_utama'].drop(index=indeks_master_terpilih_t2, errors='ignore').reset_index(drop=True)
                            
                            st.success(f"🎉 Sukses menyinkronkan {len(list_log_db_t2)} data koreksi ke database Neon!")
                            import time
                            time.sleep(1.0)
                            st.rerun()
                        else:
                            st.error("❌ Gagal menyimpan data ke server database.")
                    else:
                        st.info("ℹ️ Tidak ada data verifikasi yang Anda centang atau lengkapi.")
    else:
        st.info(f"✨ Tidak ada data review gabungan yang tersedia untuk lembaga {nama_lembaga_tampil}.")
            
        
        # -------------------------------------------------------------------------
        # TAB 3: GRAFIK SPIDER WEB DAN HISTORI ABSENSI (4 GRAFIK DENGAN TRUNCATE LABEL)
        # -------------------------------------------------------------------------
        with tab3:
            st.subheader("📜 Histori Riwayat Tindakan Absensi Review")
            if 'log_histori_absensi_review' not in st.session_state:
                st.session_state['log_histori_absensi_review'] = [
                    {"Lembaga SSR": "BINA MUDA GEMILANG", "Tanggal Sesi": datetime.now().strftime("%d-%m-%Y"), "Akurasi Akhir": teks_akurasi_penj},
                    {"Lembaga SSR": "PKBI JAWA BARAT", "Tanggal Sesi": datetime.now().strftime("%d-%m-%Y"), "Akurasi Akhir": teks_akurasi_ruj}
                ]
            st.table(pd.DataFrame(st.session_state['log_histori_absensi_review']))
            
            st.markdown("---")
            st.subheader("🕸️ Analisis Profil Klaster Temuan (Grafik Sarang Laba-Laba)")
            
            # ---------------------------------------------------------------------
            # FUNGSI LOKAL: MEMOTONG TEKS LABEL AGAR TIDAK MEMANJANG
            # ---------------------------------------------------------------------
            def potong_label(teks, max_char=25):
                teks_str = str(teks).strip()
                if len(teks_str) > max_char:
                    return teks_str[:max_char] + "..."
                return teks_str

            # ---------------------------------------------------------------------
            # QUERY 1: AMBIL DAFTAR BULAN UNIK FROM DATABASE
            # ---------------------------------------------------------------------
            list_bulan = []
            conn_bulan = dapatkan_koneksi_neon()
            if conn_bulan:
                try:
                    query_bulan = """
                        SELECT DISTINCT TO_CHAR(tanggal_dibuat, 'YYYY-MM') as bulan 
                        FROM agregasi_hasil_review_penjangkauan
                        WHERE tanggal_dibuat IS NOT NULL
                        UNION
                        SELECT DISTINCT TO_CHAR(tanggal_dibuat, 'YYYY-MM') as bulan 
                        FROM agregasi_hasil_review_rujukan
                        WHERE tanggal_dibuat IS NOT NULL
                        ORDER BY bulan ASC
                    """
                    df_bulan_db = pd.read_sql_query(query_bulan, conn_bulan)
                    if not df_bulan_db.empty:
                        list_bulan = [str(b).strip() for b in df_bulan_db['bulan'].tolist() if b]
                except Exception as e:
                    st.warning(f"Gagal mengambil daftar rentang bulan dari database: {e}")
                finally:
                    conn_bulan.close()
                    
            # Validasi & Fallback Range Slider
            list_bulan = sorted(list(set(list_bulan)))
            if len(list_bulan) < 2:
                sekarang = datetime.now()
                bulan_lalu = (sekarang - timedelta(days=30)).strftime('%Y-%m')
                bulan_ini = sekarang.strftime('%Y-%m')
                if len(list_bulan) == 1:
                    if list_bulan[0] != bulan_ini: list_bulan.append(bulan_ini)
                    else: list_bulan.insert(0, bulan_lalu)
                else: list_bulan = [bulan_lalu, bulan_ini]
            
            # ---------------------------------------------------------------------
            # KOMPONEN FILTER KOTAK PROPORSIONAL
            # ---------------------------------------------------------------------
            c_filter1, c_filter2, c_filter3, c_spacer = st.columns([1.5, 1.0, 1.5, 0.8])
            
            with c_filter1:
                list_ssr_g = sorted(df_view_gabungan["Lembaga SSR"].dropna().unique().tolist()) if 'df_view_gabungan' in locals() else []
                filter_ssr = st.selectbox("🎯 Saring Lembaga SSR:", ["Semua Lembaga SSR"] + list_ssr_g, key="sb_grafik_ssr")
                
            with c_filter2:
                top_n = st.number_input("🔝 Rangking Teratas (N):", min_value=3, max_value=20, value=5, step=1, key="num_top_n")
                
            with c_filter3:
                filter_bulan = st.select_slider(
                    "📅 Pilih Rentang Bulan:",
                    options=list_bulan,
                    value=list_bulan[-1],
                    key="slider_bulan_grafik"
                )
            
            # ---------------------------------------------------------------------
            # PREPARASI CLAUSE QUERY & PENGAMBILAN DATA (REGULER vs KONFIRMASI)
            # ---------------------------------------------------------------------
            base_where_pjj = f"WHERE TO_CHAR(tanggal_dibuat, 'YYYY-MM') = '{filter_bulan}'"
            base_where_rjk = f"WHERE TO_CHAR(tanggal_dibuat, 'YYYY-MM') = '{filter_bulan}'"
            
            if filter_ssr != "Semua Lembaga SSR":
                base_where_pjj += f" AND nama_ssr = '{filter_ssr}'"
                base_where_rjk += f" AND nama_ssr = '{filter_ssr}'"
            
            # Query Pembagian Data Berdasarkan Kata '(konfirmasi)'
            query_pjj_reguler = f"SELECT indikator_kesalahan, SUM(jumlah_kesalahan) as total FROM agregasi_hasil_review_penjangkauan {base_where_pjj} AND LOWER(indikator_kesalahan) NOT LIKE '%(konfirmasi)%' GROUP BY indikator_kesalahan ORDER BY total DESC LIMIT {top_n}"
            query_pjj_konfirmasi = f"SELECT indikator_kesalahan, SUM(jumlah_kesalahan) as total FROM agregasi_hasil_review_penjangkauan {base_where_pjj} AND LOWER(indikator_kesalahan) LIKE '%(konfirmasi)%' GROUP BY indikator_kesalahan ORDER BY total DESC LIMIT {top_n}"
            
            query_rjk_reguler = f"SELECT indikator_kesalahan, SUM(jumlah_kesalahan) as total FROM agregasi_hasil_review_rujukan {base_where_rjk} AND LOWER(indikator_kesalahan) NOT LIKE '%(konfirmasi)%' GROUP BY indikator_kesalahan ORDER BY total DESC LIMIT {top_n}"
            query_rjk_konfirmasi = f"SELECT indikator_kesalahan, SUM(jumlah_kesalahan) as total FROM agregasi_hasil_review_rujukan {base_where_rjk} AND LOWER(indikator_kesalahan) LIKE '%(konfirmasi)%' GROUP BY indikator_kesalahan ORDER BY total DESC LIMIT {top_n}"
            
            df_pjj_reg = df_pjj_kon = df_rjk_reg = df_rjk_kon = pd.DataFrame()
            
            conn_grafik = dapatkan_koneksi_neon()
            if conn_grafik:
                try:
                    df_pjj_reg = pd.read_sql_query(query_pjj_reguler, conn_grafik)
                    df_pjj_kon = pd.read_sql_query(query_pjj_konfirmasi, conn_grafik)
                    df_rjk_reg = pd.read_sql_query(query_rjk_reguler, conn_grafik)
                    df_rjk_kon = pd.read_sql_query(query_rjk_konfirmasi, conn_grafik)
                except Exception as e:
                    st.error(f"Gagal memproses query grafik: {e}")
                finally:
                    conn_grafik.close()

            # ---------------------------------------------------------------------
            # INTERNAL HELPER UNTUK MAPPING KOTAK GRAFIK (Menerapkan Potong Label)
            # ---------------------------------------------------------------------
            def dapatkan_format_grafik(df):
                if not df.empty and df['total'].sum() > 0:
                    labels = [potong_label(x) for x in df['indikator_kesalahan'].tolist()]
                    r_values = df['total'].tolist()
                    labels.append(labels[0])
                    r_values.append(r_values[0])
                    return labels, r_values
                return ['Tidak Ada Temuan'] * 3, [0, 0, 0]

            lbl_pjj_reg, r_pjj_reg = dapatkan_format_grafik(df_pjj_reg)
            lbl_pjj_kon, r_pjj_kon = dapatkan_format_grafik(df_pjj_kon)
            lbl_rjk_reg, r_rjk_reg = dapatkan_format_grafik(df_rjk_reg)
            lbl_rjk_kon, r_rjk_kon = dapatkan_format_grafik(df_rjk_kon)

            import plotly.graph_objects as go
            
            # =====================================================================
            # BAGIAN A: RENDER GRAFIK KLASTER REGULER (TIDAK ADA KAT_KONFIRMASI)
            # =====================================================================
            st.markdown("#### 📊 1. Ranking Temuan Kesalahan Data Murni")
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown(f"<p style='text-align: center; font-weight: bold; color:#38bdf8;'> Penjangkauan ({filter_bulan})</p>", unsafe_allow_html=True)
                fig_pjj = go.Figure(data=go.Scatterpolar(r=r_pjj_reg, theta=lbl_pjj_reg, fill='toself', name='Penjangkauan', fillcolor='rgba(56, 189, 248, 0.15)', line=dict(color='#38bdf8', width=2)))
                fig_pjj.update_layout(polar=dict(radialaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.08)'), angularaxis=dict(gridcolor='rgba(255,255,255,0.08)')), showlegend=False, height=290, margin=dict(t=20, b=20, l=40, r=40), paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
                st.plotly_chart(fig_pjj, use_container_width=True)
                
            with col_g2:
                st.markdown(f"<p style='text-align: center; font-weight: bold; color:#10B981;'> Rujukan ({filter_bulan})</p>", unsafe_allow_html=True)
                fig_rjk = go.Figure(data=go.Scatterpolar(r=r_rjk_reg, theta=lbl_rjk_reg, fill='toself', name='Rujukan', fillcolor='rgba(16, 185, 129, 0.15)', line=dict(color='#10B981', width=2)))
                fig_rjk.update_layout(polar=dict(radialaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.08)'), angularaxis=dict(gridcolor='rgba(255,255,255,0.08)')), showlegend=False, height=290, margin=dict(t=20, b=20, l=40, r=40), paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
                st.plotly_chart(fig_rjk, use_container_width=True)
                
            st.markdown("<br>", unsafe_allow_html=True)

            # =====================================================================
            # BAGIAN B: RENDER GRAFIK KLASTER DATA KONFIRMASI (ADA KAT_KONFIRMASI)
            # =====================================================================
            st.markdown("#### 🔍 2. Ranking Validasi Khusus Data Perlu Konfirmasi")
            col_k1, col_k2 = st.columns(2)
            
            with col_k1:
                st.markdown(f"<p style='text-align: center; font-weight: bold; color:#f59e0b;'> Penjangkauan (Konfirmasi) ({filter_bulan})</p>", unsafe_allow_html=True)
                fig_pjj_k = go.Figure(data=go.Scatterpolar(r=r_pjj_kon, theta=lbl_pjj_kon, fill='toself', name='PJJ Konfirmasi', fillcolor='rgba(245, 158, 11, 0.15)', line=dict(color='#f59e0b', width=2)))
                fig_pjj_k.update_layout(polar=dict(radialaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.08)'), angularaxis=dict(gridcolor='rgba(255,255,255,0.08)')), showlegend=False, height=290, margin=dict(t=20, b=20, l=40, r=40), paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
                st.plotly_chart(fig_pjj_k, use_container_width=True)
                
            with col_k2:
                st.markdown(f"<p style='text-align: center; font-weight: bold; color:#ec4899;'> Rujukan (Konfirmasi) ({filter_bulan})</p>", unsafe_allow_html=True)
                fig_rjk_k = go.Figure(data=go.Scatterpolar(r=r_rjk_kon, theta=lbl_rjk_kon, fill='toself', name='Ruj Konfirmasi', fillcolor='rgba(236, 72, 153, 0.15)', line=dict(color='#ec4899', width=2)))
                fig_rjk_k.update_layout(polar=dict(radialaxis=dict(visible=True, gridcolor='rgba(255,255,255,0.08)'), angularaxis=dict(gridcolor='rgba(255,255,255,0.08)')), showlegend=False, height=290, margin=dict(t=20, b=20, l=40, r=40), paper_bgcolor='rgba(0,0,0,0)', font_color='#E0E0E0')
                st.plotly_chart(fig_rjk_k, use_container_width=True)
                

# ----------------------------------------------------------
# MENU 2: PENGATURAN MEDSOS 
# ----------------------------------------------------------
elif menu_pilihan == "⚙️ Pengaturan Keyword Medsos":
    st.title("⚙️ Pengaturan Keyword Media Sosial")
    st.markdown("Gunakan menu ini untuk menambahkan atau melihat daftar nama media sosial yang digunakan sebagai filter pada pencarian **Lokasi Outreach / Penjangkauan Online**.")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_kiri, col_kanan = st.columns([1, 1.5])
    
    with col_kiri:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("➕ Tambah Medsos Baru")
        with st.form("form_tambah_medsos", clear_on_submit=True):
            medsos_baru = st.text_input("Masukkan Nama Medsos:", placeholder="Contoh: grindr, michat, wechat")
            tombol_simpan = st.form_submit_button("Simpan Keyword", use_container_width=True)
            
            if tombol_simpan:
                keyword_clean = medsos_baru.strip().lower()
                if keyword_clean:
                    # 1. Simpan ke database
                    sukses = tambah_keyword_medsos_db(keyword_clean)
                    
                    if sukses:
                        # 2. Update session_state agar tampil langsung tanpa refresh database
                        st.session_state['medsoc_keywords'].append(keyword_clean)
                        st.session_state['medsoc_keywords'].sort()
                        st.success(f"Berhasil menambahkan '{keyword_clean}' ke database!")
                        
                        import time
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.warning(f"Keyword '{keyword_clean}' sudah ada di dalam database.")
                else:
                    st.warning("Kolom tidak boleh kosong!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_kanan:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        # Ambil langsung dari session state yang sudah tersinkron database
        list_medsos = st.session_state.get('medsoc_keywords', [])
        st.subheader(f"📋 Daftar Keyword Aktif ({len(list_medsos)})")
        
        if list_medsos:
            html_badges = ""
            for m in list_medsos:
                html_badges += f"""
                <span style="
                    background-color: rgba(56, 189, 248, 0.15); 
                    color: #38bdf8; 
                    border: 1px solid rgba(56, 189, 248, 0.3);
                    padding: 6px 12px; 
                    border-radius: 20px; 
                    font-family: inherit; 
                    font-size: 0.85rem;
                    font-weight: 500;
                    white-space: nowrap;
                    display: flex;
                    align-items: center;
                    gap: 5px;
                ">
                    🔹 {m}
                </span>
                """
            
            st.markdown(f"""
                <div style="
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    padding: 15px; 
                    border: 1px solid rgba(255,255,255,0.1); 
                    border-radius: 8px; 
                    background-color: rgba(0,0,0,0.2);
                ">
                    {html_badges}
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Belum ada data medsos di database.")
            
        st.markdown('</div>', unsafe_allow_html=True)
