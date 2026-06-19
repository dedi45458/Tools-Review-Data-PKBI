import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime  

# ==========================================================
# IMPORT FUNGSI NEON DARI FILE database.py
# ==========================================================
from database import (
    dapatkan_koneksi_neon,
    simpan_log_ke_neon,
    jalankan_agregasi_tren,
    ambil_rekap_tren,
    hitung_dan_ambil_log_db,     
    ambil_keyword_medsos_db,     
    tambah_keyword_medsos_db,
    ambil_status_storage_neon,
    
    # 🛠️ REFERENSI DATA MASTER
    ambil_data_rujukan_hiv_positif,  
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
# 0. MANAGEMENT DEFAULT STATE & INIT DATA (Tersinkron Neon DB)
# ==========================================================
if 'total_entri' not in st.session_state: st.session_state['total_entri'] = 0
if 'proses_selesai' not in st.session_state: st.session_state['proses_selesai'] = False
if 'aturan_kustom' not in st.session_state: st.session_state['aturan_kustom'] = []

# --- 1. REKAP HASIL REVIEW DATA PENJANGKAUAN SSR (Tabel 1) ---
if 'df_penjangkauan' not in st.session_state or st.session_state['df_penjangkauan'] is None:
    try:
        df_pj, ts_pj = ambil_agregasi_penjangkauan_terakhir()
        if df_pj is not None and not df_pj.empty:
            st.session_state['df_penjangkauan'] = df_pj
            st.session_state['ts_terakhir_penjangkauan'] = ts_pj
        else:
            st.session_state['df_penjangkauan'] = pd.DataFrame()
            st.session_state['ts_terakhir_penjangkauan'] = datetime.now()
    except Exception as e:
        st.session_state['df_penjangkauan'] = pd.DataFrame()
        st.session_state['ts_terakhir_penjangkauan'] = datetime.now()

# --- 2. REKAP HASIL REVIEW DATA RUJUKAN SSR (Tabel 2) ---
if 'df_rujukan' not in st.session_state or st.session_state['df_rujukan'] is None:
    try:
        df_rj, ts_rj = ambil_agregasi_rujukan_terakhir()
        if df_rj is not None and not df_rj.empty:
            st.session_state['df_rujukan'] = df_rj
            st.session_state['ts_terakhir_rujukan'] = ts_rj
        else:
            st.session_state['df_rujukan'] = pd.DataFrame()
            st.session_state['ts_terakhir_rujukan'] = datetime.now()
    except Exception as e:
        st.session_state['df_rujukan'] = pd.DataFrame()
        st.session_state['ts_terakhir_rujukan'] = datetime.now()

# --- 3. HASIL REVIEW VALIDASI DATA GABUNGAN UTAMA (Tabel 3) ---
if 'df_review_utama' not in st.session_state or st.session_state['df_review_utama'] is None:
    try:
        df_ut, ts_ut = ambil_hasil_review_utama_terakhir()
        if df_ut is not None and not df_ut.empty:
            st.session_state['df_review_utama'] = df_ut
            st.session_state['ts_terakhir_utama'] = ts_ut
        else:
            st.session_state['df_review_utama'] = pd.DataFrame()
            st.session_state['ts_terakhir_utama'] = datetime.now()
    except Exception as e:
        st.session_state['df_review_utama'] = pd.DataFrame()
        st.session_state['ts_terakhir_utama'] = datetime.now()

# --- B. INISIALISASI KEYWORD MEDSOS ---
if 'medsoc_keywords' not in st.session_state:
    st.session_state['medsoc_keywords'] = ambil_keyword_medsos_db()

def ambil_keyword_medsos():
    """Mengambil daftar keyword medsos aktif dari session state"""
    keywords = st.session_state.get('medsoc_keywords', [])
    return sorted(keywords) if keywords else []

# --- C. TAMPILAN JUDUL UTAMA ---
st.markdown('<div class="main-title">📊 Tools Review Data PKBI Jawa Barat</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem Penelaahan Kualitas Data Penjangkauan & Rujukan Terpadu (Neon DB)</div>', unsafe_allow_html=True)

# ==========================================================
# FUNGSI HELPER
# ==========================================================
def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom) or str(teks_kolom).strip().lower() in ['', 'nan']: return False
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

def hitung_dan_ambil_log_db():
    dict_revisi, dict_justifikasi = {}, {}
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                # Ambil data langsung menggunakan query Postgres
                cur.execute("SELECT Lembaga_SSR, Tanggal, ID_Klien, Indikator_Kesalahan_Data, is_revisi, Justifikasi FROM log_validasi_review")
                rows = cur.fetchall()
                for r in rows:
                    ssr, tgl, id_klien, ind, is_rev, just = r
                    key = f"{str(ssr).upper()}_{str(tgl)}_{str(id_klien)}_{str(ind)}"
                    dict_revisi[key] = is_rev
                    if just: dict_justifikasi[key] = just
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
    {"nama": "KD telah menerima layanan CBS tapi tidak ada informasi CBS", "periksa": lambda c: c['pernah_cbs_di_rujukan'] and not cek_kode(c['info_diberikan'], '13')},
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
# 2. ATURAN VALIDASI KHUSUS RUJUKAN
# ==========================================================
ATURAN_VALIDASI_RUJUKAN = [
    {"nama": "ID tidak terdaftar di penjangkauan", "periksa": lambda c: f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}" not in c.get('set_ssr_id_penjangkauan', set())},
    {"nama": "Data rujukan tapi tidak ada NIK (konfirmasi)", "periksa": lambda c: str(c['row'].get('ID Klien', '')).strip() != '' and str(c['row'].get('NIK', '')).replace("'", "").strip() in ['', 'nan', 'none']},
    {"nama": "ID sudah dinyatakan Reaktif di semester / tahun lalu (Konfirmasi)", "periksa": lambda c: c.get('is_reaktif_sebelumnya', False)},
    {"nama": "Jenis Layanan tidak sesuai", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() not in ['5', '6']},
    {"nama": "Jenis Layanan dengan Metode CBS tidak sesuai", "periksa": lambda c: str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and str(c['row'].get('Metode CBS', '')).split('.')[0].strip() in ['', '0', '1', 'nan']},
    {"nama": "Bukan CBS tapi jenis layanan 5/6", "periksa": lambda c: 'cbs' not in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6']},
    {"nama": "Layanan CBS ada rujukan IMS", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Layanan CBS ada rujukan PrEp", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and cek_kode(c['row'].get('Rujukan'), '51')},
    {"nama": "Layanan CBS ada rujukan selain VCT", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Rujukan', '')).replace("'", "").strip() != '2'},
    {"nama": "Tidak ada rujukan satupun/tidak diisi", "periksa": lambda c: str(c['row'].get('Rujukan', '')).replace("'", "").strip() in ['', 'nan', 'None']},
    {"nama": "Bukan penasun rujukan 3,4", "periksa": lambda c: str(c['row'].get('Tipe Klien', '')).split('.')[0].strip() != '1401' and (cek_kode(c['row'].get('Rujukan'), '3') or cek_kode(c['row'].get('Rujukan'), '4'))},
    {"nama": "ID akses ke layanan lebih dari 1x tapi belum tes HIV (Konfirmasi)", "periksa": lambda c: c.get('id_counts_ruj', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", 0) > 1 and not c.get('rujukan_vct_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    {"nama": "Tidak menerima hasil tes HIV", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '2') and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', '2', 'nan']},
    {"nama": "Kolom menerima hasil tes HIV terisi tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi kolom menerima hasil tidak terisi", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Dirujuk IMS tapi tidak ada hasil IMS", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '1') and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil IMS tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi hasil tes IMS Non Reaktif/ N/A", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['2', '3']},
    {"nama": "Hasil tes IMS reaktif tapi tidak menerima pengobatan IMS (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '2'},
    {"nama": "Kolom menerima pengobatan IMS terisi tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi tidak ada hasil tes IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil tes IMS tapi kolom menerima pengobatan IMS tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "DIrujuk PrEP tapi hasil skrining PrEP tidak diisi", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Layanan PrEp tidak terdaftar, indikasi salah mengisi layanan atau belum update jenis layanan PrEP di SIMS (konfirmasi)", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and not c.get('is_layanan_prep_valid', True)},
    {"nama": "Ada hasil skrining PrEP tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '5')},
    {"nama": "Ada hasil skrining PrEP tapi kolom menerima obat PrEP tidak disi", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Menerima pengobatan PrEP diisi tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and not cek_kode(c['row'].get('Rujukan'), '5')},
    {"nama": "KD sudah menerima obat PrEP tapi hasil skrining PrEP tidak memenuhi syarat", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '2'},
    {"nama": "Hasil Skrining PrEP memenuhi syarat tapi KD tidak menerima obat PrEP (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '2'},
    {"nama": "Dirujuk TB tapi tidak ada Hasil Tes TB", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '8') and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada Hasil TB tapi tidak ada rujukan TB", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '8')},
    {"nama": "Menerima pengobatan TB tapi hasil tes TB Non Reaktif/ N/A/ tidak diisi", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['2', '3', '', 'nan']},
    {"nama": "Hasil tes TB reaktif tapi tidak menerima pengobatan TB (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '2'},
    {"nama": "Ada hasil tes TB tapi kolom pengobatan TB tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['2', '3'] and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Dirujuk Hep-C tapi tidak ada Hasil Tes Hep-C", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '9') and str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada Hasil Hep-C tapi tidak ada rujukan Hep-C", "periksa": lambda c: str(c['row'].get('Hasil Tes HEPC', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '9')},
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
    
    # --- PENAMBAHAN MENU NAVIGASI ---
    menu_pilihan = st.radio(
        "Navigasi Menu", 
        ["🎯 Dashboard Review Data", "⚙️ Pengaturan Keyword Medsos"],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    
    # 💡 SOLUSI NYA DI SINI: Inisialisasi awal nilai default agar tidak NameError di menu lain
    tombol_proses = False
    
    # =================================================================
    # HANYA TAMPILKAN ALAT REVIEW JIKA MENU "DASHBOARD" DIPILIH
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
                    # Normalisasi nama kolom untuk pengecekan tipe data secara aman
                    kolom_terdeteksi = [str(c).strip().lower() for c in df_check.columns]
                    
                    # Deteksi Tipe A: Apakah ini Database Layanan?
                    is_data_layanan = any("lembaga" in c or "ssr" in c for c in kolom_terdeteksi) and any("layanan" in c for c in kolom_terdeteksi)
                    
                    if is_data_layanan:
                        st.info("🏥 **Terdeteksi:** Database Fasyankes / SSR")
                        if st.button("🔄 Update Database Fasyankes", use_container_width=False, key="btn_exec_layanan"):
                            with st.spinner("Sedang memproses database fasyankes..."):
                                from database import import_database_layanan
                                sukses, pesan = import_database_layanan(df_check)
                                if sukses:
                                    st.success("✅ Database Fasyankes telah diperbarui!")
                                else:
                                    st.error("❌ Gagal mengupdate database fasyankes")
                    
                    # Deteksi Tipe B: Berarti ini Data HIV+ Semester Lalu
                    else:
                        st.info("📋 **Terdeteksi:** Berkas Database HIV+")
                        if st.button("🔄 Update Database HIV+", use_container_width=False, key="btn_exec_hiv"):
                            with st.spinner("Sedang memproses data rujukan HIV..."):
                                from database import import_data_HIV
                                if import_data_HIV(df_check):
                                    st.success("✅ Database HIV+ telah diperbarui!")
                                else:
                                    st.error("❌ Gagal mengupdate database HIV+.")
                                    
                except Exception as e:
                    st.error(f"⚠️ Gagal membaca struktur berkas Excel: {e}")
            
            # Pembatas vertikal pemisah antar uploader
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
    
        st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)
        
        # =================================================================
        # PARAMETER VALIDASI
        # =================================================================
        with st.container():
            st.markdown("<b style='color: #38bdf8; font-size: 0.95rem;'>⚙️ PARAMETER VALIDASI</b>", unsafe_allow_html=True)
            
            with st.expander("✨ Buat Aturan Kustom Baru", expanded=False):
                with st.form("form_tambah_aturan", clear_on_submit=True):
                    input_nama_ind = st.text_input("Nama Indikator", placeholder="Misal: Digit NIK wajib 16")
                    pilihan_kolom = st.selectbox("Kolom Target", ["NIK", "ID Klien", "Umur", "Lembaga SSR", "Kode Petugas", "Lokasi Outreach / Jenis Sosial Media", "Informasi Yang diberikan", "Rujukan"])
                    pilihan_kondisi = st.selectbox("Kondisi Error Jika:", ["Panjang karakter tidak sama dengan (!=)", "Panjang karakter kurang dari ( < )", "Kosong / Blank", "Mengandung teks tertentu", "Sama dengan teks/angka tertentu"])
                    input_pembanding = st.text_input("Nilai Pembanding", placeholder="Contoh: 16 atau Teks tertentu")
                    
                    submit_rule = st.form_submit_button("➕ Daftarkan Aturan", use_container_width=True)
                    
                    if submit_rule:
                        if not input_nama_ind: st.error("Nama wajib diisi!")
                        elif "Kosong" not in pilihan_kondisi and not input_pembanding: st.error("Nilai pembanding wajib diisi!")
                        else:
                            mapping_kunci = {"NIK": "nik_clean", "ID Klien": "id_clean", "Umur": "umur", "Lembaga SSR": "v_ssr", "Kode Petugas": "v_petugas", "Lokasi Outreach / Jenis Sosial Media": "lokasi", "Informasi Yang diberikan": "info_diberikan", "Rujukan": "rujukan"}
                            kunci_target = mapping_kunci[pilihan_kolom]
                            fungsi_validasi = buat_fungsi_validasi_kustom(kunci_target, pilihan_kondisi, input_pembanding)
                            st.session_state['aturan_kustom'].append({"nama": input_nama_ind, "periksa": fungsi_validasi})
                            st.success(f"Berhasil didaftarkan!")
                            st.rerun()
            
            if st.session_state['aturan_kustom']:
                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                with st.expander(f"📋 Aturan Aktif ({len(st.session_state['aturan_kustom'])} Terdaftar)", expanded=True):
                    for idx, r_kustom in enumerate(st.session_state['aturan_kustom']):
                        st.markdown(f"<div style='font-size: 0.85rem; color: #cbd5e1; padding: 4px 0;'>📌 {r_kustom['nama']}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️ Bersihkan Semua Aturan", use_container_width=True, type="secondary"):
                        st.session_state['aturan_kustom'] = []
                        st.rerun()
    
        st.markdown("""<div style="margin-top: 35px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);"></div>""", unsafe_allow_html=True)
        tombol_proses = st.button("🚀 Jalankan Validasi", type="primary", use_container_width=True)

        # ==========================================================
        # INDIKATOR STORAGE NEON DB (PAKET FREE TIER)
        # ==========================================================
        storage_info = ambil_status_storage_neon()
        
        if storage_info:
            # Menentukan warna teks & indikator berdasarkan tingkat kepenuhan storage
            if storage_info['persen_terpakai'] > 85:
                kondisi_warna = "#ff4b4b"  # Merah jika hampir penuh
            elif storage_info['persen_terpakai'] > 60:
                kondisi_warna = "#ffa500"  # Kuning jika mulai terisi banyak
            else:
                kondisi_warna = "#38bdf8"  # Biru langit modern jika aman
                
            # Tampilan card informasi storage ala glassmorphism
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
            # Menampilkan progress bar bawaan Streamlit
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
    set_prep_valid=None
):
    # Inisialisasi fallback pengaman Cross-Check Variables
    if set_ssr_id_penjangkauan is None: set_ssr_id_penjangkauan = set()
    if set_nik_reaktif is None: set_nik_reaktif = set()
    if set_ssr_id_reaktif is None: set_ssr_id_reaktif = set()
    if set_prep_valid is None: set_prep_valid = set()
        
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    
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
            
    # 🔥 DETEKSI CERDAS: Apakah ini file rujukan atau penjangkauan?
    col_upper_all = [str(c).upper() for c in df.columns]
    is_file_rujukan = any(k in col_upper_all for k in ['HASIL TES HIV', 'NAMA LAYANAN', 'METODE CBS'])
    
    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())

    # PENGAMAN REGEX MEDSOS
    keywords_aktif = st.session_state.get('medsoc_keywords', [])
    if keywords_aktif:
        pattern_medsos_dinamis = r'\b(' + '|'.join([re.escape(k) for k in keywords_aktif]) + r')\b'
    else:
        pattern_medsos_dinamis = r'\b(TIDAK_ADA_MEDSOS_TERDAFTAR_DI_SISTEM)\b'

    # Pengaman Database terintegrasi (Membaca riwayat konfirmasi & revisi terdahulu)
    try:
        dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()
    except Exception:
        dict_revisi, dict_justifikasi = {}, {}

    ref_ssr_id_to_nik, ref_nik_ssr_to_id = {}, {}
    dict_pernah_cbs, dict_pernah_prep_rujukan = {}, {}

    # PENYUSUNAN DICTIONARY REFERENSI HISTORIS (Jika df_ref diupload)
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
                if nik_r and nik_r != 'nan' and nik_r != '' and ssr_r and ssr_r != 'nan': 
                    ref_nik_ssr_to_id[f"{nik_r}_{ssr_r}"] = id_r
                
                if col_layanan_ref:
                    layanans = str(r[col_layanan_ref[0]]).replace("'", "").replace(" ", "").split(',')
                    if '5' in layanans or '6' in layanans:
                        dict_pernah_cbs[key_klien] = True
                
                if col_rujukan_ref:
                    rujukans = str(r[col_rujukan_ref[0]]).replace("'", "").replace(" ", "").split(',')
                    if '5' in rujukans:
                        dict_pernah_prep_rujukan[key_klien] = True

    df['id_mapped'] = df.get('ID Klien', pd.Series(dtype=str)).astype(str).str.replace("'", "").str.strip()
    df['ssr_id_key'] = df.get('Lembaga SSR', pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + df['id_mapped']
    
    dict_ssr_id_counts = df.iloc[start_row_idx:]['ssr_id_key'].value_counts().to_dict()
    
    def periksa_hiv(x): return '1' in str(x).replace("'", "").replace(" ", "").split(',')
    def periksa_rujukan(x): 
        s = str(x).replace("'", "").replace(" ", "").replace(".0", "")
        if '.' in s and ',' not in s: 
            s = s.replace('.', ',')
        return '2' in s.split(',')

    # PRE-KALKULASI KHUSUS RUJUKAN (Apakah ID rujuk VCT > 1x)
    rujukan_vct_per_klien = {}
    if is_file_rujukan:
        col_ruj_temp = next((c for c in df.columns if "RUJUKAN" in str(c).upper()), None)
        if col_ruj_temp:
            for _, r in df.iloc[start_row_idx:].iterrows():
                k_ssr = str(r.get('Lembaga SSR', '')).strip().upper()
                k_id = str(r.get('ID Klien', '')).replace("'", "").strip()
                if cek_kode(r.get(col_ruj_temp), '2'):
                    rujukan_vct_per_klien[f"{k_ssr}_{k_id}"] = True

    # ==========================================================
    # DETEKSI KOLOM DINAMIS
    # ==========================================================
    col_info = next((c for c in df.columns if "INFORMASI" in str(c).upper() and "DIBERIKAN" in str(c).upper()), "")
    col_kegiatan = next((c for c in df.columns if "JENIS KEGIATAN" in str(c).upper()), "")
    col_kontak = next((c for c in df.columns if "JENIS KONTAK" in str(c).upper() or "JNS KONTAK" in str(c).upper()), "")
    col_lokasi = next((c for c in df.columns if "LOKASI" in str(c).upper()), "")
    col_ruj = next((c for c in df.columns if "RUJUKAN" in str(c).upper()), "")
    col_tanggal = next((c for c in df.columns if "TANGGAL" in str(c).upper()), "Tanggal")
    col_tipe_sasaran = next((c for c in df.columns if "TIPE SASARAN" in str(c).upper() or "TIPE KLIEN" in str(c).upper()), "Tipe Sasaran")
    col_vc1 = next((c for c in df.columns if "VIRTUAL" in str(c).upper() or "VC1" in str(c).upper() or "TATAP MUKA" in str(c).upper()), "")
    col_nama_layanan = next((c for c in df.columns if "NAMA LAYANAN" in str(c).upper()), "")
    
    if col_info and col_kegiatan:
        df['is_info_hiv'] = df[col_info].apply(periksa_hiv) | df[col_kegiatan].apply(periksa_hiv)
    else:
        df['is_info_hiv'] = False
        
    if col_ruj: 
        df['is_rujuk_tes'] = df[col_ruj].apply(periksa_rujukan)
    else: 
        df['is_rujuk_tes'] = False

    dict_pernah_hiv = df.groupby('ssr_id_key')['is_info_hiv'].any().to_dict()
    dict_pernah_rujuk = df.groupby('ssr_id_key')['is_rujuk_tes'].any().to_dict()

    def _safe_float(val):
        try:
            return float(val) if pd.notna(val) and str(val).strip().lower() not in ['', 'nan'] else 0.0
        except:
            return 0.0

    col_kie_list = [c for c in df.columns if 'KIE' in str(c).upper()]
    col_kon_list = [c for c in df.columns if 'KONDOM' in str(c).upper()]
    col_pel_list = [c for c in df.columns if 'PELICIN' in str(c).upper()]
    col_jar_list = [c for c in df.columns if 'JARUM' in str(c).upper() and 'KEMBALI' not in str(c).upper()]
    col_swab_list = [c for c in df.columns if 'SWAB' in str(c).upper() or 'ALKOHOL' in str(c).upper()]
    
    semua_kolom_logistik = col_kie_list + col_kon_list + col_pel_list + col_jar_list + col_swab_list

    df['tmp_log'] = 0.0
    for col in semua_kolom_logistik:
        df['tmp_log'] += df[col].apply(_safe_float)

    df['kunci_klien_ref_log'] = df.get('Lembaga SSR', pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + df['id_mapped']
    dict_total_log_per_klien = df.groupby('kunci_klien_ref_log')['tmp_log'].sum().to_dict()

    # PILIH ATURAN VALIDASI BERDASARKAN JENIS FILE
    if is_file_rujukan:
        SEMUA_ATURAN_AKTIF = ATURAN_VALIDASI_RUJUKAN
    else:
        aturan_kustom = st.session_state.get('aturan_kustom', [])
        SEMUA_ATURAN_AKTIF = ATURAN_VALIDASI_BAWAAN + aturan_kustom

    # LOOP BARIS DATA UNTUK EVALUASI
    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        
        v_ssr = str(row.get('Lembaga SSR', '')).strip().upper() if pd.notna(row.get('Lembaga SSR')) else ''
        v_petugas = str(row.get('Kode Petugas', '')).replace("'", "").strip() if pd.notna(row.get('Kode Petugas')) else ''
        v_kota = str(row.get('Nama Kota', '')).strip() if pd.notna(row.get('Nama Kota')) else ''
        v_tanggal = str(row.get(col_tanggal, '')).split(' ')[0] if pd.notna(row.get(col_tanggal)) else ''
        
        id_raw = str(row.get('ID Klien', '')).strip()
        id_clean = id_raw.replace("'", "").strip()
        nik_raw = str(row.get('NIK', '')).strip()
        nik_clean = nik_raw.replace("'", "").replace('.0', '').strip()

        v_tipe_sasaran = str(row.get(col_tipe_sasaran, '')).replace('.0', '').strip()
        umur = row.get('Umur', None)
        jk = str(row.get('Jenis Kelamin', '')).replace('.0', '').strip()
        
        jns_kontak = str(row.get(col_kontak, row.get('Jenis Kontak', ''))).replace('.0', '').strip()
        jns_kegiatan = str(row.get(col_kegiatan, row.get('Jenis Kegiatan', ''))).replace('.0', '').strip()
        lokasi = str(row.get(col_lokasi, row.get('Lokasi Outreach / Jenis Sosial Media', ''))).strip()
        
        info_diberikan = str(row.get(col_info, '')).strip() if col_info else ''
        rujukan = str(row.get(col_ruj, '')).strip() if col_ruj else ''
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
        
        # Validasi Database Khusus Rujukan (Is Reaktif & Validasi PrEP)
        is_reaktif_db = False
        if nik_clean and nik_clean.lower() not in ['', 'nan', 'none'] and nik_clean in set_nik_reaktif:
            is_reaktif_db = True
        elif kunci_klien_ref in set_ssr_id_reaktif:
            is_reaktif_db = True
            
        layanan_clean = str(row.get(col_nama_layanan, '')).strip().lower() if col_nama_layanan else ""
        is_layanan_prep_db = True if not layanan_clean else f"{v_ssr.lower()}_{layanan_clean}" in set_prep_valid

        # KONTEKS DATA (Mencakup variabel untuk kedua jenis file)
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
            
            # --- PARAMETER CROSS CHECK RUJUKAN ---
            'set_ssr_id_penjangkauan': set_ssr_id_penjangkauan,
            'is_reaktif_sebelumnya': is_reaktif_db,
            'rujukan_vct_per_klien': rujukan_vct_per_klien,
            'id_counts_ruj': dict_ssr_id_counts,
            'is_layanan_prep_valid': is_layanan_prep_db
        }

        # LOOP ATURAN VALIDASI
        for rule in SEMUA_ATURAN_AKTIF:
            nama_ind = rule["nama"]
            try:
                if rule["periksa"](context_data):
                    # Kunci unik pencocokan database
                    key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{nama_ind}"
                    
                    status_validasi = "-"
                    checked_state = False
                    justif_val = dict_justifikasi.get(key_db, "")
                    
                    if key_db in dict_justifikasi:
                        status_validasi = f"⚠️ Terdeteksi Kembali (Riwayat Justifikasi: {justif_val})"
                        
                    if key_db in dict_revisi:
                        status_validasi = "kesalahan pada ID yang berulang (belum dilakukan revisi)"
                        checked_state = True

                    list_kesalahan.append({
                        "Pilih": checked_state,
                        "Lembaga SSR": v_ssr,
                        "Tanggal": v_tanggal, 
                        "ID Klien": id_clean, 
                        "Kode Petugas": v_petugas, 
                        "Nama Kota": v_kota, 
                        "NIK": nik_clean, 
                        "Tipe Sasaran": v_tipe_sasaran,
                        "INDIKATOR KESALAHAN DATA": nama_ind,
                        "validasi hasil review": status_validasi, 
                        "Justifikasi": justif_val
                    })
            except Exception: 
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
            
            # 🛠️ Tangkap uploader referensi dengan aman
            file_referensi_aman = st.session_state.get('uploader_master_tunggal', None)
            df_ref = None
            if file_referensi_aman is not None:
                try: 
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
            try:
                from database import ambil_set_reaktif_sebelumnya, ambil_set_layanan_prep_valid
                set_nik_rkt, set_ssr_id_rkt = ambil_set_reaktif_sebelumnya()
                set_prep_vld = ambil_set_layanan_prep_valid()
            except Exception as e:
                pass # Abaikan jika data historis belum ada

            # Loop 1: Kumpulkan set ID Penjangkauan
            for f in files_review:
                try:
                    temp_df = pd.read_csv(f, low_memory=False) if f.name.endswith('.csv') else pd.read_excel(f)
                    col_upper = [str(c).upper() for c in temp_df.columns]
                    if not any(k in col_upper for k in ['HASIL TES HIV', 'NAMA LAYANAN', 'METODE CBS']):
                        for _, row in temp_df.iterrows():
                            ssr = str(row.get('Lembaga SSR', '')).strip().upper()
                            idk = str(row.get('ID Klien', '')).replace("'", "").strip()
                            if ssr and idk: set_penjangkauan.add(f"{ssr}_{idk}")
                except Exception: pass

            # Loop 2: Eksekusi Validasi
            for f in files_review:
                try:
                    df_target = pd.read_csv(f, low_memory=False) if f.name.endswith('.csv') else pd.read_excel(f)
                    total_records += len(df_target)
                    
                    col_upper = [str(c).upper() for c in df_target.columns]
                    is_rujukan = any(k in col_upper for k in ['HASIL TES HIV', 'NAMA LAYANAN', 'METODE CBS'])
                    
                    if is_rujukan: total_proses_rjk += len(df_target)
                    else: total_proses_pjj += len(df_target)
                    
                    df_res = jalankan_review_data(
                        df_target, df_ref, nama_file=f.name,
                        set_ssr_id_penjangkauan=set_penjangkauan,
                        set_nik_reaktif=set_nik_rkt, set_ssr_id_reaktif=set_ssr_id_rkt, set_prep_valid=set_prep_vld
                    )
                    
                    if not df_res.empty:
                        df_res['Kategori Data'] = 'Rujukan' if is_rujukan else 'Penjangkauan'
                        all_errs.append(df_res)
                except Exception: pass

            # 🎯 INJEKSI UNTUK KARTU SKOR GANDA: Simpan total entri ke memory Streamlit
            st.session_state['total_entri'] = total_records
            st.session_state['total_entri_penjangkauan'] = total_proses_pjj
            st.session_state['total_entri_rujukan'] = total_proses_rjk

            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                
                # SIMPAN LOG AKURASI
                df_pjj_raw = df_bawah[df_bawah['Kategori Data'] == 'Penjangkauan'] if not df_bawah.empty else pd.DataFrame()
                df_rjk_raw = df_bawah[df_bawah['Kategori Data'] == 'Rujukan'] if not df_bawah.empty else pd.DataFrame()
                
                # 🎯 INJEKSI UNTUK KARTU SKOR GANDA: Simpan tabel temuan spesifik ke memory Streamlit
                st.session_state['df_err_penj'] = df_pjj_raw
                st.session_state['df_err_ruj'] = df_rjk_raw
                
                total_temuan_pjj = len(df_pjj_raw)
                total_temuan_rjk = len(df_rjk_raw)
                akurasi_pjj = max(0.00, round(((total_proses_pjj - total_temuan_pjj) / total_proses_pjj) * 100, 2)) if total_proses_pjj > 0 else 100.00
                akurasi_rjk = max(0.00, round(((total_proses_rjk - total_temuan_rjk) / total_proses_rjk) * 100, 2)) if total_proses_rjk > 0 else 100.00
                
                try:
                    from database import simpan_metrik_akurasi_db
                    if total_proses_pjj > 0: simpan_metrik_akurasi_db('penjangkauan', total_proses_pjj, total_temuan_pjj, akurasi_pjj)
                    if total_proses_rjk > 0: simpan_metrik_akurasi_db('rujukan', total_proses_rjk, total_temuan_rjk, akurasi_rjk)
                except Exception: pass

                # STANDARISASI NAMA KOLOM UI
                rename_map = {}
                for c in df_bawah.columns:
                    c_clean = str(c).strip().upper()
                    if 'LEMBAGA SSR' in c_clean or 'NAMA SSR' in c_clean: rename_map[c] = 'Lembaga SSR'
                    elif 'KODE PETUGAS' in c_clean: rename_map[c] = 'Kode Petugas'
                    elif 'NAMA KOTA' in c_clean or 'KOTA' in c_clean: rename_map[c] = 'Nama Kota'
                    elif 'NAMA LAYANAN' in c_clean or 'LAYANAN' in c_clean: rename_map[c] = 'Nama Layanan'
                    elif 'TANGGAL' in c_clean: rename_map[c] = 'Tanggal'
                    elif 'ID KLIEN' in c_clean: rename_map[c] = 'ID Klien'
                    elif 'NIK' in c_clean: rename_map[c] = 'NIK'
                    elif 'TIPE SASARAN' in c_clean: rename_map[c] = 'Tipe Sasaran'
                    elif 'INDIKATOR KESALAHAN' in c_clean: rename_map[c] = 'Indikator Kesalahan Data'
                    elif 'VALIDASI' in c_clean: rename_map[c] = 'Validasi Hasil Review'
                    elif 'JUSTIFIKASI' in c_clean: rename_map[c] = 'Justifikasi'
                df_bawah = df_bawah.rename(columns=rename_map)
                
                for col in ['Kode Petugas', 'Nama Kota', 'Nama Layanan', 'NIK', 'Tipe Sasaran', 'Validasi Hasil Review', 'Justifikasi']:
                    if col not in df_bawah.columns: df_bawah[col] = "-"

                # FILTER DUPLIKAT DARI DATABASE NEON
                existing_master_keys = set()
                try:
                    from database import dapatkan_koneksi_neon
                    conn = dapatkan_koneksi_neon()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT LOWER(kategori_data), LOWER(lembaga_ssr), LOWER(tanggal), LOWER(id_klien), LOWER(indikator_kesalahan) FROM hasil_review_data;")
                            for r in cur.fetchall():
                                existing_master_keys.add((str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip(), str(r[4]).strip()))
                        conn.close()
                except Exception: pass

                indices_to_drop = []
                for idx, row in df_bawah.iterrows():
                    kat = str(row.get('Kategori Data', '')).strip().lower()
                    ssr = str(row.get('Lembaga SSR', '')).strip().lower()
                    tgl = str(row.get('Tanggal', '')).strip().lower() 
                    id_klien = str(row.get('ID Klien', '')).strip().lower()
                    ind = str(row.get('Indikator Kesalahan Data', '')).strip().lower()
                    if (kat, ssr, tgl, id_klien, ind) in existing_master_keys:
                        indices_to_drop.append(idx)
                
                if indices_to_drop:
                    df_bawah = df_bawah.drop(index=indices_to_drop).reset_index(drop=True)

                # SINKRONISASI KE 3 TABEL (EKSTRAKSI TUPLE MANUAL YANG AMAN DARI ERROR PANDAS)
                try:
                    from database import simpan_paket_validasi_ke_tiga_tabel
                    
                    if df_bawah.empty:
                        st.info("ℹ️ Seluruh data kesalahan yang diupload sudah tersimpan di database Neon sebelumnya.", icon="ℹ️")
                    else:
                        # 1. TABEL PENJANGKAUAN (Hanya agregasi)
                        df_pjj_only = df_bawah[df_bawah['Kategori Data'] == 'Penjangkauan']
                        list_insert_tabel_1 = []
                        if not df_pjj_only.empty:
                            DAFTAR_INDIKATOR_AKTIF = [r["nama"] for r in (ATURAN_VALIDASI_BAWAAN + st.session_state.get('aturan_kustom', []))]
                            active_ssrs_pjj = sorted(list(df_pjj_only['Lembaga SSR'].dropna().unique()))
                            for ind_err in DAFTAR_INDIKATOR_AKTIF:
                                for ssr_name in active_ssrs_pjj:
                                    hitung_kesalahan = len(df_pjj_only[(df_pjj_only['Indikator Kesalahan Data'] == ind_err) & (df_pjj_only['Lembaga SSR'] == ssr_name)])
                                    if hitung_kesalahan > 0:
                                        list_insert_tabel_1.append((ssr_name, ind_err, hitung_kesalahan))

                        # 2. TABEL RUJUKAN
                        df_rjk_only = df_bawah[df_bawah['Kategori Data'] == 'Rujukan']
                        list_insert_tabel_2 = []
                        for _, row_rjk in df_rjk_only.iterrows():
                            tgl_raw = str(row_rjk.get('Tanggal', '')).strip()
                            tgl_clean = tgl_raw if tgl_raw != '-' else None
                            val_review = str(row_rjk.get('Validasi Hasil Review', '')).strip().lower()
                            is_valid = True if val_review in ['true', 'yes', '1', 'ya'] else False

                            list_insert_tabel_2.append((
                                str(row_rjk.get('Lembaga SSR', '-')), str(row_rjk.get('Kode Petugas', '-')),
                                str(row_rjk.get('Nama Kota', '-')), str(row_rjk.get('Nama Layanan', '-')),
                                tgl_clean, str(row_rjk.get('ID Klien', '-')), str(row_rjk.get('NIK', '-')),
                                str(row_rjk.get('Tipe Sasaran', '-')), str(row_rjk.get('Indikator Kesalahan Data', '-')),
                                is_valid, str(row_rjk.get('Justifikasi', '-'))
                            ))

                        # 3. TABEL UTAMA MASTER
                        list_insert_tabel_3 = []
                        for _, row_all in df_bawah.iterrows():
                            list_insert_tabel_3.append((
                                str(row_all.get('Kategori Data', '-')), str(row_all.get('Lembaga SSR', '-')),
                                str(row_all.get('Kode Petugas', '-')), str(row_all.get('Nama Kota', '-')),
                                str(row_all.get('Nama Layanan', '-')), str(row_all.get('Tanggal', '-')),
                                str(row_all.get('ID Klien', '-')), str(row_all.get('NIK', '-')),
                                str(row_all.get('Tipe Sasaran', '-')), str(row_all.get('Indikator Kesalahan Data', '-')),
                                str(row_all.get('Validasi Hasil Review', '-')), str(row_all.get('Justifikasi', '-'))
                            ))

                        # EKSEKUSI PENYIMPANAN
                        sukses = simpan_paket_validasi_ke_tiga_tabel(list_insert_tabel_1, list_insert_tabel_2, list_insert_tabel_3)
                        if sukses:
                            st.toast("💾 Sinkronisasi aman ke 3 tabel Cloud Neon Database berhasil!", icon="✅")
                        else:
                            st.error("❌ Terjadi kesalahan teknis transaksi multi-tabel. Data gagal disimpan.")

                except Exception as e:
                    st.error(f"⚠️ Gagal mengeksekusi sinkronisasi database (Sistem Crash): {str(e)}")
            
            else:
                st.session_state['df_tabel_atas'] = pd.DataFrame()
                st.session_state['df_tabel_bawah'] = pd.DataFrame()
                
                # 🎯 INJEKSI UNTUK KARTU SKOR GANDA: Reset jika tidak ada error
                st.session_state['df_err_penj'] = pd.DataFrame()
                st.session_state['df_err_ruj'] = pd.DataFrame()
                
                st.info("✨ Proses selesai: Tidak ditemukan indikator kesalahan data pada file yang Anda unggah.")

            # AUTO-REFRESH UI DENGAN DATA DARI DB
            try:
                from database import ambil_agregasi_penjangkauan_terakhir, ambil_agregasi_rujukan_terakhir, ambil_hasil_review_utama_terakhir, ambil_metrik_akurasi_terakhir
                metrik_db, ts_metrik = ambil_metrik_akurasi_terakhir()
                st.session_state['metrik_akurasi'] = metrik_db
                st.session_state['ts_metrik_terakhir'] = ts_metrik
                
                df_pjj_db, ts_pjj = ambil_agregasi_penjangkauan_terakhir()
                df_rjk_db, ts_rjk = ambil_agregasi_rujukan_terakhir()
                df_utama_db, ts_utama = ambil_hasil_review_utama_terakhir()
                
                st.session_state['df_tabel_atas'] = df_pjj_db 
                st.session_state['df_tabel_penjangkauan'] = df_pjj_db
                st.session_state['df_tabel_rujukan'] = df_rjk_db
                st.session_state['df_tabel_bawah'] = df_utama_db
                st.session_state['tanggal_terakhir_review'] = ts_utama
                st.session_state['tanggal_terakhir_bawah'] = ts_utama

            except Exception as e:
                st.warning(f"⚠️ Berhasil simpan data, namun gagal me-refresh visualisasi dashboard UI ({e})")

            st.session_state['proses_selesai'] = True
            import time
            time.sleep(1.2) 
            st.rerun()
            
# ==========================================================
# 5. RENDER LAYOUT UTAMA (BERDASARKAN PILIHAN MENU)
# ==========================================================

# ----------------------------------------------------------
# MENU 1: DASHBOARD REVIEW DATA (VERSI REVISI AKURASI BARIS MULTI-FILE)
# ----------------------------------------------------------
if menu_pilihan == "🎯 Dashboard Review Data":
    
    # 1. BUKA KUNCI DASHBOARD: Tampilkan jika proses validasi selesai ATAU ada data historis dari DB
    df_historis = st.session_state.get('df_tabel_atas', pd.DataFrame())
    
    if st.session_state.get('proses_selesai', False) or (df_historis is not None and not df_historis.empty):
        
        # ==========================================================
        # 🔥 INTEGRASI BARU: KARTU SKOR GANDA (PENJANGKAUAN & RUJUKAN)
        # ==========================================================
        # Ambil total data awal dari session state
        tot_data_penj = st.session_state.get('total_entri_penjangkauan', 0)
        tot_data_ruj = st.session_state.get('total_entri_rujukan', 0)
        
        tot_err_penj = 0
        tot_err_ruj = 0
        
        # Hitung baris temuan secara dinamis jika data hasil review tersedia
        if st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
            df_semua_error = st.session_state['df_tabel_bawah'].copy()
            
            # 🛡️ PROTEKSI KEYERROR: Sinkronisasi nama kolom seandainya sudah di-rename sebelumnya
            if 'Indikator Kesalahan Data' in df_semua_error.columns and 'INDIKATOR KESALAHAN DATA' not in df_semua_error.columns:
                df_semua_error = df_semua_error.rename(columns={'Indikator Kesalahan Data': 'INDIKATOR KESALAHAN DATA'})
            
            # Memisahkan error berdasarkan jenis file (Bisa dicek dari aturan mana yang terpicu)
            # Menggunakan try-except sebagai fallback jika ATURAN_VALIDASI_RUJUKAN belum di-declare secara global
            try:
                ind_rujukan = [r['nama'] for r in ATURAN_VALIDASI_RUJUKAN]
            except NameError:
                ind_rujukan = [] # Fallback aman jika list aturan rujukan tidak terbaca
                
            mask_rujukan = df_semua_error['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan)
            
            # Eliminasi duplikasi baris fisik agar akurasi dihitung per entri data (bukan per jenis error)
            df_err_penj_unik = df_semua_error[~mask_rujukan].drop_duplicates(subset=["LEMBAGA SSR", "TANGGAL", "ID KLIEN"])
            df_err_ruj_unik = df_semua_error[mask_rujukan].drop_duplicates(subset=["LEMBAGA SSR", "TANGGAL", "ID KLIEN"])
            
            tot_err_penj = len(df_err_penj_unik)
            tot_err_ruj = len(df_err_ruj_unik)

        # Perhitungan Akurasi masing-masing entri
        akurasi_penj = 100.0 if tot_data_penj == 0 else max(0, 100 - (tot_err_penj / tot_data_penj * 100))
        akurasi_ruj = 100.0 if tot_data_ruj == 0 else max(0, 100 - (tot_err_ruj / tot_data_ruj * 100))
        
        teks_akurasi_penj = f"{akurasi_penj:.1f}%" if tot_data_penj > 0 else "N/A"
        teks_akurasi_ruj = f"{akurasi_ruj:.1f}%" if tot_data_ruj > 0 else "N/A"

        # --- RENDER UI KARTU SKOR MENGGUNAKAN GLASSMORPHISM ---
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        
        tanggal_hari_ini = datetime.now().strftime('%d %B %Y')
        st.markdown(f"""
            <p style='color: #94a3b8; font-size: 0.9rem; margin-bottom: 15px;'>
                📅 <b>Executive Review Dashboard</b> | Tanggal: {tanggal_hari_ini}
            </p>
        """, unsafe_allow_html=True)
        
        # Seksi 1: Penjangkauan
        st.markdown("<b style='color: #38bdf8; font-size: 1.05rem;'>🎯 Data Penjangkauan</b>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: 
            st.metric(label="Total Data Diproses", value=f"{tot_data_penj:,}")
        with c2: 
            st.metric(label="Total Baris Temuan", value=f"{tot_err_penj:,}", delta="Perlu Perhatian", delta_color="inverse")
        with c3: 
            st.metric(label="Tingkat Akurasi", value=teks_akurasi_penj, delta="Akurasi Penjangkauan")
        
        st.markdown("<hr style='border-color: rgba(255,255,255,0.1); margin: 15px 0;'>", unsafe_allow_html=True)
        
        # Seksi 2: Rujukan
        st.markdown("<b style='color: #10B981; font-size: 1.05rem;'>🎯 Data Rujukan</b>", unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        with c4: 
            st.metric(label="Total Data Diproses", value=f"{tot_data_ruj:,}")
        with c5: 
            st.metric(label="Total Baris Temuan", value=f"{tot_err_ruj:,}", delta="Perlu Perhatian", delta_color="inverse")
        with c6: 
            st.metric(label="Tingkat Akurasi", value=teks_akurasi_ruj, delta="Akurasi Rujukan")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # =========================================================================
        # KUSTOMISASI UKURAN HURUF TAB (Agar Seimbang dengan Sub-Tabel)
        # =========================================================================
        st.markdown("""
            <style>
            /* Menargetkan teks paragraf di dalam komponen Tab Streamlit */
            .stTabs [data-baseweb="tab"] p {
                font-size: 1.5rem !important;    /* Mengubah ukuran huruf (Default: ~0.875rem) */
                font-weight: 600 !important;      /* Membuat teks menjadi lebih tebal/tegas */
                color: #ffffff !important;        /* Memastikan warna teks tetap kontras */
            }
            
            /* Otomatis memberikan sedikit ruang vertikal agar tidak terlalu rapat dengan konten bawah */
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
                margin-bottom: 10px;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # =========================================================================
        # DEKLARASI TAB ANDA
        # =========================================================================
        tab1, tab2 = st.tabs(["📋 Hasil Review Data SR", "📈 Analisis Tren Temuan"])

        with tab1:
            # Ambil list indikator rujukan terlebih dahulu untuk keperluan filter di kedua seksi
            try:
                ind_rujukan = [r['nama'] for r in ATURAN_VALIDASI_RUJUKAN]
            except NameError:
                ind_rujukan = [] # Fallback aman jika variabel belum terdefinisi
                
            df_atas_view = st.session_state.get('df_tabel_atas', pd.DataFrame())
            tanggal_terakhir = st.session_state.get('tanggal_terakhir_review', None)
        
            # =========================================================================
            # 🟢 SEKSI 1: RENDER HASIL REVIEW DATA PENJANGKAUAN (SUDAH DI-FILTER)
            # =========================================================================
            st.markdown("#### 📋 Rekap Hasil Review Data Penjangkauan SSR")
            
            if tanggal_terakhir:
                if hasattr(tanggal_terakhir, 'strftime'):
                    tgl_format = tanggal_terakhir.strftime("%d-%m-%Y pukul %H:%M WIB")
                else:
                    tgl_format = str(tanggal_terakhir)
                    
                badge_html = f"""
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background-color: rgba(28, 131, 225, 0.12);
                    color: #1c83e1;
                    padding: 6px 14px;
                    border-radius: 20px;
                    border: 1px solid rgba(28, 131, 225, 0.25);
                    font-size: 0.88rem;
                    font-weight: 500;
                    margin-bottom: 18px;
                ">
                    ℹ️ Review Data Penjangkauan SR terakhir tanggal : <span style="font-weight: 700;">{tgl_format}</span>
                </div>
                """
                st.markdown(badge_html, unsafe_allow_html=True)
                
            if df_atas_view is not None and not df_atas_view.empty:
                df_render = df_atas_view.copy()
                
                if df_render.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render.columns:
                    df_render = df_render.reset_index()
                    
                # 🔥 PERBAIKAN LOGIKA: Saring agar HANYA menampilkan indikator Penjangkauan (Bukan Rujukan)
                df_render = df_render[~df_render['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan)].copy()
                
                if not df_render.empty:
                    kolom_indikator = 'INDIKATOR KESALAHAN DATA'
                    kolom_ssr = [c for c in df_render.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
                    
                    for col in kolom_ssr:
                        df_render[col] = pd.to_numeric(df_render[col], errors='coerce').fillna(0).astype(int)
                    
                    ssr_aktif = [col for col in kolom_ssr if df_render[col].sum() > 0]
                    kolom_final = [kolom_indikator] + ssr_aktif + ['Jumlah per indikator', '%']
                    df_final = df_render[[c for c in kolom_final if c in df_render.columns]].copy()
                    
                    # Recalculate % dan Total jika diperlukan agar akurat per kategori
                    total_error_penjangkauan = df_final['Jumlah per indikator'].sum()
                    if total_error_penjangkauan > 0:
                        df_final['%'] = (df_final['Jumlah per indikator'] / total_error_penjangkauan) * 100
                    
                    df_display = df_final.copy()
                    for col in ssr_aktif:
                        if col in df_display.columns:
                            df_display[col] = df_display[col].astype(str).replace({'0': '-', '0.0': '-'})
                    
                    column_config = {
                        kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                        "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                        "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                    }
                    for col in ssr_aktif:
                        column_config[col] = st.column_config.TextColumn(col, width="small")
                
                    st.dataframe(df_display, use_container_width=True, column_config=column_config, hide_index=True)
                else:
                    st.info("✅ Tidak ada temuan kesalahan untuk Data Penjangkauan.")
            else:
                st.info("✨ Belum ada data review dalam database Neon.")
        
        
            # =========================================================================
            # 🔵 SEKSI 2: RENDER HASIL REVIEW DATA RUJUKAN (SUDAH BENAR)
            # =========================================================================
            st.markdown("<hr style='border: 1px solid #e2e8f0; margin: 40px 0;'>", unsafe_allow_html=True)
            st.markdown("#### 📋 Rekap Hasil Review Data Rujukan SSR")
            
            if tanggal_terakhir:
                badge_rujukan_html = f"""
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background-color: rgba(16, 185, 129, 0.12); /* Warna Emerald/Hijau */
                    color: #10B981;
                    padding: 6px 14px;
                    border-radius: 20px;
                    border: 1px solid rgba(16, 185, 129, 0.25);
                    font-size: 0.88rem;
                    font-weight: 500;
                    margin-bottom: 18px;
                ">
                    🔗 Review Data Rujukan SR terakhir tanggal : <span style="font-weight: 700;">{tgl_format}</span>
                </div>
                """
                st.markdown(badge_rujukan_html, unsafe_allow_html=True)
                
            if df_atas_view is not None and not df_atas_view.empty:
                df_render_ruj = df_atas_view.copy()
                
                if df_render_ruj.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render_ruj.columns:
                    df_render_ruj = df_render_ruj.reset_index()
                
                # Filter HANYA untuk indikator rujukan
                df_render_ruj = df_render_ruj[df_render_ruj['INDIKATOR KESALAHAN DATA'].isin(ind_rujukan)].copy()
                
                if not df_render_ruj.empty:
                    kolom_indikator = 'INDIKATOR KESALAHAN DATA'
                    kolom_ssr_ruj = [c for c in df_render_ruj.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
                    
                    for col in kolom_ssr_ruj:
                        df_render_ruj[col] = pd.to_numeric(df_render_ruj[col], errors='coerce').fillna(0).astype(int)
                    
                    ssr_aktif_ruj = [col for col in kolom_ssr_ruj if df_render_ruj[col].sum() > 0]
                    kolom_final_ruj = [kolom_indikator] + ssr_aktif_ruj + ['Jumlah per indikator', '%']
                    df_final_ruj = df_render_ruj[[c for c in kolom_final_ruj if c in df_render_ruj.columns]].copy()
                    
                    # Recalculate % khusus kelompok rujukan agar total porsinya pas 100%
                    total_error_rujukan = df_final_ruj['Jumlah per indikator'].sum()
                    if total_error_rujukan > 0:
                        df_final_ruj['%'] = (df_final_ruj['Jumlah per indikator'] / total_error_rujukan) * 100
                    
                    df_display_ruj = df_final_ruj.copy()
                    for col in ssr_aktif_ruj:
                        if col in df_display_ruj.columns:
                            df_display_ruj[col] = df_display_ruj[col].astype(str).replace({'0': '-', '0.0': '-'})
                    
                    column_config_ruj = {
                        kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                        "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                        "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                    }
                    for col in ssr_aktif_ruj:
                        column_config_ruj[col] = st.column_config.TextColumn(col, width="small")
                
                    st.dataframe(df_display_ruj, use_container_width=True, column_config=column_config_ruj, hide_index=True)
                else:
                    st.info("✅ Tidak ada temuan kesalahan untuk Data Rujukan.")
            else:
                st.info("✨ Belum ada data review dalam database Neon.")


            # =========================================================================
            # TABEL GABUNGAN: HASIL REVIEW PENJANGKAUAN & RUJUKAN (ONE-TABLE EDITOR)
            # =========================================================================
            st.markdown("### 🔍 Hasil Review Validasi Data (Penjangkauan & Rujukan)")
            st.markdown(
                "<small style='color: #888;'>💡 Kolom Justifikasi hanya dapat diisi jika indikator kesalahan mengandung kata 'konfirmasi'. Kolom lain dikunci secara otomatis.</small>", 
                unsafe_allow_html=True
            )
            
            # 1. Validasi Awal Keberadaan Data
            tanggal_terakhir_bawah = st.session_state.get('tanggal_terakhir_bawah', None)
            
            if tanggal_terakhir_bawah and st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
                
                # Ambil format tanggal untuk Badge Informasi
                if hasattr(tanggal_terakhir_bawah, 'strftime'):
                    tgl_format_bawah = tanggal_terakhir_bawah.strftime("%d-%m-%Y pukul %H:%M WIB")
                else:
                    tgl_format_bawah = str(tanggal_terakhir_bawah)
                    
                badge_gabungan_html = f"""
                <div style="
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    background-color: rgba(124, 58, 237, 0.12);
                    color: #7c3aed;
                    padding: 6px 14px;
                    border-radius: 20px;
                    border: 1px solid rgba(124, 58, 237, 0.25);
                    font-size: 0.88rem;
                    font-weight: 500;
                    margin-bottom: 15px;
                ">
                    🔮 Total Data Review Terintegrasi (SR) terakhir tanggal: <span style="font-weight: 700; margin-left: 3px;">{tgl_format_bawah}</span>
                </div>
                """
                st.markdown(badge_gabungan_html, unsafe_allow_html=True)
            
                # 2. Duplikasi & Normalisasi Kolom secara Global
                df_master = st.session_state['df_tabel_bawah'].copy()
                
                rename_dict = {}
                for col in df_master.columns:
                    c_clean = str(col).strip().lower()
                    if "indikator" in c_clean or "kesalahan" in c_clean or "error" in c_clean:
                        rename_dict[col] = "Indikator Kesalahan Data"
                    elif "validasi" in c_clean or "review" in c_clean:
                        rename_dict[col] = "Validasi Hasil Review"
                    elif "justifikasi" in c_clean:
                        rename_dict[col] = "Justifikasi"
                    elif "lembaga" in c_clean or "ssr" in c_clean:
                        rename_dict[col] = "Lembaga SSR"
                    elif "layanan" in c_clean:
                        rename_dict[col] = "Nama Layanan"
                    elif "petugas" in c_clean:
                        rename_dict[col] = "Kode Petugas"
                    elif "kota" in c_clean or "kabupaten" in c_clean:
                        rename_dict[col] = "Nama Kota"
                        
                if rename_dict:
                    df_master = df_master.rename(columns=rename_dict)
            
                # 3. 🔥 IMPLEMENTASI BARU: Penentuan Kategori Data Otomatis 🔥
                # (Pastikan variabel list `ind_rujukan` sudah terdefinisi di bagian atas aplikasi Anda)
                df_master["Kategori Data"] = df_master["Indikator Kesalahan Data"].apply(
                    lambda x: "Rujukan" if str(x) in ind_rujukan else "Penjangkauan"
                )
            
                # 4. Susunan Struktur Kolom Universal Baru
                kolom_susunan_gabungan = [
                    "Pilih", "Kategori Data", "Lembaga SSR", "Kode Petugas", "Nama Kota", "Nama Layanan", 
                    "Tanggal", "ID Klien", "NIK", "Tipe Sasaran", 
                    "Indikator Kesalahan Data", "Validasi Hasil Review", "Justifikasi"
                ]
            
                # Safety Check: Isi nilai default jika ada kolom struktural yang absen dari file sumber
                for col in kolom_susunan_gabungan:
                    if col not in df_master.columns:
                        if col == "Pilih":
                            df_master["Pilih"] = False
                        else:
                            df_master[col] = "-"
            
                # 5. Filter Komponen Tunggal Berdasarkan Lembaga SSR
                pilihan_ssr = "Semua"
                list_ssr_unik = sorted(df_master["Lembaga SSR"].dropna().unique().tolist())
                
                col_filter, _ = st.columns([1, 2])
                with col_filter:
                    pilihan_ssr = st.selectbox(
                        "🎯 Pilih Lembaga SSR (Semua Kategori):",
                        options=["Semua"] + list_ssr_unik,
                        index=0,
                        help="Menyaring seluruh data Penjangkauan dan Rujukan berdasarkan Lembaga SSR yang dipilih."
                    )
                    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
            
                # Jalankan filter selectbox jika bukan "Semua"
                if pilihan_ssr != "Semua":
                    df_master = df_master[df_master["Lembaga SSR"] == pilihan_ssr]
            
                # Ambil view kolom sesuai urutan susunan global
                df_view_gabungan = df_master[kolom_susunan_gabungan].copy()
            
                # 6. Intersepsi Tampilan: Bersihkan Justifikasi jika bukan tipe 'konfirmasi'
                for idx, row in df_view_gabungan.iterrows():
                    if "konfirmasi" not in str(row['Indikator Kesalahan Data']).lower():
                        df_view_gabungan.at[idx, 'Justifikasi'] = ""
            
                # 7. Render Data Editor Tunggal
                if df_view_gabungan.empty:
                    st.info(f"✨ Tidak ada data kesalahan yang perlu divalidasi untuk Lembaga SSR: **{pilihan_ssr}**")
                else:
                    df_hasil_edit = st.data_editor(
                        df_view_gabungan,
                        use_container_width=True,
                        hide_index=False,  # 🔥 WAJIB FALSE: Diperlukan agar indeks asli dataframe master tetap terjaga saat penghapusan baris
                        key="editor_validasi_tunggal",
                        column_config={
                            "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang jika data telah direvisi/diperbaiki", default=False),
                            "Kategori Data": st.column_config.TextColumn("Kategori Data", width=110),
                            "Lembaga SSR": st.column_config.TextColumn("Lembaga SSR", width=120),
                            "Kode Petugas": st.column_config.TextColumn("Kode Petugas", width=100),
                            "Nama Kota": st.column_config.TextColumn("Nama Kota", width=110),
                            "Nama Layanan": st.column_config.TextColumn("Nama Layanan", width=120),
                            "Tanggal": st.column_config.TextColumn("Tanggal", width=100),
                            "ID Klien": st.column_config.TextColumn("ID Klien", width=110),
                            "NIK": st.column_config.TextColumn("NIK", width=130),
                            "Tipe Sasaran": st.column_config.TextColumn("Tipe Sasaran", width=110),
                            "Indikator Kesalahan Data": st.column_config.TextColumn("Indikator Kesalahan Data", width=300),
                            "Validasi Hasil Review": st.column_config.TextColumn("Validasi Hasil Review", width=200),
                            "Justifikasi": st.column_config.TextColumn("Justifikasi", help="Hanya diisi jika kolom indikator mengandung unsur kata 'konfirmasi'", width=260),
                        },
                        disabled=[c for c in kolom_susunan_gabungan if c not in ["Pilih", "Justifikasi"]]
                    )
            
                    # 8. Tombol Eksekusi Penyimpanan Tunggal
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_save, _ = st.columns([1, 2])
                    with col_save:
                        if st.button("💾 Simpan Semua Progres Validasi", type="primary", use_container_width=False):
                            
                            with st.spinner("Memproses penyelarasan data ke database..."):
                                list_log_db = []
                                indeks_baris_terpilih = []
                                peringatan_justifikasi = False
            
                                # Iterasi baris hasil edit dari interface tunggal
                                for idx, row_edit in df_hasil_edit.iterrows():
                                    ind_text = str(row_edit['Indikator Kesalahan Data'])
                                    text_justifikasi = str(row_edit['Justifikasi']).strip()
                                    
                                    is_konfirmasi = "konfirmasi" in ind_text.lower()
                                    
                                    # Proteksi: Abaikan input justifikasi jika baris tersebut bukan tipe konfirmasi
                                    if not is_konfirmasi:
                                        if text_justifikasi not in ["", "None", "-", "nan"]:
                                            peringatan_justifikasi = True
                                        text_justifikasi = ""
                                    else:
                                        if text_justifikasi in ["None", "-", "nan"]:
                                            text_justifikasi = ""
            
                                    # Trigger simpan: jika kotak 'Pilih' dicentang ATAU justifikasi konfirmasi terisi
                                    if bool(row_edit['Pilih']) or (is_konfirmasi and text_justifikasi != ""):
                                        status_revisi = bool(row_edit['Pilih'])
                                        
                                        # Susun parameter tuple sesuai kebutuhan fungsi simpan_log_ke_neon
                                        list_log_db.append((
                                            str(row_edit.get('Lembaga SSR', '-')),
                                            str(row_edit.get('Tanggal', '-')),
                                            str(row_edit.get('ID Klien', '-')),
                                            ind_text,
                                            status_revisi,      # BOOLEAN
                                            text_justifikasi    # TEXT
                                        ))
                                        # Catat indeks dataframe asli untuk dipotong dari session state jika sukses
                                        indeks_baris_terpilih.append(idx)
            
                                # Kirim ke Neon Database jika ada baris yang memenuhi kriteria simpan
                                if len(list_log_db) > 0:
                                    if simpan_log_ke_neon(list_log_db):
                                        
                                        # Potong baris yang sukses disimpan berdasarkan indeks asli session_state
                                        df_sekarang = st.session_state['df_tabel_bawah']
                                        df_sisa = df_sekarang.drop(indeks_baris_terpilih).reset_index(drop=True)
                                        st.session_state['df_tabel_bawah'] = df_sisa
                                        
                                        st.success(f"🎉 Sukses memindahkan {len(list_log_db)} baris data ke tabel log_validasi_review!")
                                        
                                        if peringatan_justifikasi:
                                            st.warning("⚠️ Catatan: Teks Justifikasi pada baris non-konfirmasi otomatis diabaikan oleh sistem.")
                                            
                                        import time
                                        time.sleep(1.2)
                                        st.rerun()
                                    else:
                                        st.error("❌ Terjadi kegagalan saat menyimpan ke Neon Database. Cek koneksi Anda.")
                                else:
                                    st.info("ℹ️ Tidak ada data yang diproses. Silakan centang 'Pilih' atau ketik teks 'Justifikasi' sebelum menekan tombol simpan.")
            else:
                st.info("✨ Belum ada data tabel review atau session state kosong.")

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("---")
            
            st.markdown("### ⚙️ Manajemen Akhir Periode")
            st.warning("⚠️ Gunakan tombol di bawah ini HANYA JIKA periode bulanan sudah selesai dan semua data sudah diverifikasi.")
            
            if st.button("🚀 Tutup Periode & Arsipkan Tren Bulanan", type="primary", use_container_width=True):
                with st.spinner("Sedang memproses pengarsipan data ke Neon Postgres..."):
                    if jalankan_agregasi_tren():
                        st.success("🎉 Data berhasil diarsipkan ke tabel rekap bulanan!")
                        st.balloons()
                    else:
                        st.error("Gagal memproses arsip ke database.")

        with tab2:
            st.markdown("### 📈 Pusat Analisis & Wawasan Data")
            st.markdown("<br>", unsafe_allow_html=True)
            
            import plotly.express as px
            
            # =========================================================================
            # 1. BAGIAN A: VISUALISASI CLEVELAND DOT PLOT (PENGGANTI TOTAL BAR)
            # =========================================================================
            if st.session_state.get('proses_selesai', False) and st.session_state.get('df_tabel_bawah') is not None:
                df_bawah = st.session_state['df_tabel_bawah'].copy()
                
                if not df_bawah.empty:
                    st.markdown("#### 📊 Sebaran Titik Kesalahan Berdasarkan Kelompok Sasaran")
                    
                    # Standarisasi Tipe Sasaran & Mapping Label
                    df_bawah['Tipe Sasaran'] = df_bawah['Tipe Sasaran'].astype(str).str.replace('.0', '', regex=False).str.strip()
                    map_sasaran = {
                        '1304': '1304 (MSM)',
                        '1301': '1301 (TG)',
                        '1401': '1401 (PWID)'
                    }
                    df_bawah['Kelompok Sasaran'] = df_bawah['Tipe Sasaran'].map(map_sasaran).fillna(df_bawah['Tipe Sasaran'])
                    
                    # Pengaman Duplikat
                    df_bawah = df_bawah.drop_duplicates(subset=["Lembaga SSR", "Tanggal", "ID Klien", "INDIKATOR KESALAHAN DATA"])
                    
                    # Memisahkan Kategori (Mutlak vs Konfirmasi)
                    is_konfirmasi = df_bawah['INDIKATOR KESALAHAN DATA'].str.contains(r'\(konfirmasi\)', case=False, na=False)
                    df_mutlak_all = df_bawah[~is_konfirmasi]
                    df_konf_all = df_bawah[is_konfirmasi]
                    
                    # --- VISUALISASI KATEGORI 1: TEMUAN MUTLAK (DOT PLOT) ---
                    st.markdown("##### 🟥 A. Top 5 Temuan Mutlak (Perlu Koreksi / Non-Konfirmasi)")
                    if not df_mutlak_all.empty:
                        # Ambil top 5 indikator
                        top_5_mutlak_idx = df_mutlak_all['INDIKATOR KESALAHAN DATA'].value_counts().head(5).index
                        df_top_5_mutlak = df_mutlak_all[df_mutlak_all['INDIKATOR KESALAHAN DATA'].isin(top_5_mutlak_idx)]
                        
                        # Hitung jumlah per kombinasi Indikator + Kelompok Sasaran
                        df_dot_mutlak = df_top_5_mutlak.groupby(['INDIKATOR KESALAHAN DATA', 'Kelompok Sasaran']).size().reset_index(name='Jumlah Kasus')
                        
                        # Membuat Cleveland Dot Plot menggunakan px.scatter
                        fig_mutlak = px.scatter(
                            df_dot_mutlak,
                            x='Jumlah Kasus',
                            y='INDIKATOR KESALAHAN DATA',
                            color='Kelompok Sasaran',
                            template="plotly_dark",
                            color_discrete_map={'1304 (MSM)': '#EF4444', '1301 (TG)': '#3B82F6', '1401 (PWID)': '#10B981'}
                        )
                        
                        fig_mutlak.update_traces(
                            marker=dict(size=14, opacity=0.85, line=dict(width=1, color='#FFFFFF')),
                            hovertemplate="<b>%{hovertext}</b><br>Jumlah: %{x} Kasus<extra></extra>",
                            hovertext=df_dot_mutlak['Kelompok Sasaran']
                        )
                        
                        # Pengaturan Layout & Anti-Kotak Putih (Sudah Disatukan)
                        fig_mutlak.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10),
                            paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color='#E0E0E0', 
                            xaxis_title="Jumlah Kasus Kesalahan", 
                            yaxis_title="",
                            legend_title_text="Sasaran", 
                            height=280, 
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            yaxis={'categoryorder':'total ascending'},
                            hoverlabel=dict(bgcolor="#0f172a", font_size=12, font_color="#f8fafc") # Menggunakan skema warna gelap Anda
                        )
                        fig_mutlak.update_xaxes(showgrid=True, gridcolor='#333333')
                        fig_mutlak.update_yaxes(showgrid=True, gridcolor='#222222')
                        
                        st.plotly_chart(fig_mutlak, use_container_width=True, theme=None)
                    else:
                        st.info("✨ Bersih! Tidak ada temuan mutlak terdeteksi.")
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                
                    # --- VISUALISASI KATEGORI 2: TEMUAN BUTUH KONFIRMASI (DOT PLOT) ---
                    st.markdown("##### 🟨 B. Top 5 Temuan Butuh Klarifikasi (Ada Unsur Justifikasi / Konfirmasi)")
                    if not df_konf_all.empty:
                        # Ambil top 5 indikator
                        top_5_konf_idx = df_konf_all['INDIKATOR KESALAHAN DATA'].value_counts().head(5).index
                        df_top_5_konf = df_konf_all[df_konf_all['INDIKATOR KESALAHAN DATA'].isin(top_5_konf_idx)]
                        
                        # Hitung jumlah per kombinasi
                        df_dot_konf = df_top_5_konf.groupby(['INDIKATOR KESALAHAN DATA', 'Kelompok Sasaran']).size().reset_index(name='Jumlah Kasus')
                        
                        # Membuat Cleveland Dot Plot
                        fig_konf = px.scatter(
                            df_dot_konf,
                            x='Jumlah Kasus',
                            y='INDIKATOR KESALAHAN DATA',
                            color='Kelompok Sasaran',
                            template="plotly_dark",
                            color_discrete_map={'1304 (MSM)': '#EF4444', '1301 (TG)': '#3B82F6', '1401 (PWID)': '#10B981'}
                        )
                        
                        fig_konf.update_traces(
                            marker=dict(size=14, opacity=0.85, line=dict(width=1, color='#FFFFFF')),
                            hovertemplate="<b>%{hovertext}</b><br>Jumlah: %{x} Kasus<extra></extra>",
                            hovertext=df_dot_konf['Kelompok Sasaran']
                        )
                        
                        fig_konf.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10),
                            paper_bgcolor='rgba(0,0,0,0)', 
                            plot_bgcolor='rgba(0,0,0,0)',
                            font_color='#E0E0E0', 
                            xaxis_title="Jumlah Kasus Kesalahan", 
                            yaxis_title="",
                            legend_title_text="Sasaran", 
                            height=280, 
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            yaxis={'categoryorder':'total ascending'},
                            hoverlabel=dict(bgcolor="#0f172a", font_size=12, font_color="#f8fafc")
                        )
                        fig_konf.update_xaxes(showgrid=True, gridcolor='#333333')
                        fig_konf.update_yaxes(showgrid=True, gridcolor='#222222')
                        
                        st.plotly_chart(fig_konf, use_container_width=True, theme=None)
                    else:
                        st.info("✨ Aman! Tidak ada data yang membutuhkan konfirmasi tambahan.")
                else:
                    st.info("✨ Tidak ada rincian data kesalahan untuk dianalisa berdasarkan target.")
                    
            # =========================================================================
            # LINE BREAK / PEMBATAS ELEGAN ANTARA DATA SEKARANG VS DATA HISTORIS
            # =========================================================================
            st.markdown("---")
            st.markdown("<br>", unsafe_allow_html=True)
            
            # =========================================================================
            # 2. BAGIAN B: ANALISIS TREN SEMESTER (AREA CHART)
            # =========================================================================
            st.markdown("#### 📉 Analisis Tren Kesalahan per Periode")
            
            df_tren = ambil_rekap_tren()
            if not df_tren.empty:
                df_tren['Tanggal'] = df_tren['periode']
                
                col_kiri, col_kanan = st.columns([1, 2])
                with col_kiri:
                    daftar_ssr = ["SEMUA"] + sorted(df_tren['nama_ssr'].dropna().unique().tolist())
                    pilihan_ssr = st.selectbox("Pilih Lembaga SSR:", daftar_ssr, key="select_ssr_tren")
                    
                if pilihan_ssr == "SEMUA":
                    df_pivot = df_tren.groupby('Tanggal')['jumlah_kesalahan'].sum().reset_index()
                    df_pivot = df_pivot.set_index('Tanggal')
                    st.markdown(f"<p>📈 Tren total kesalahan <b>seluruh SSR</b>:</p>", unsafe_allow_html=True)
                else:
                    df_filtered = df_tren[df_tren['nama_ssr'] == pilihan_ssr]
                    df_pivot = df_filtered.pivot_table(index='Tanggal', columns='indikator_kesalahan', values='jumlah_kesalahan', aggfunc='sum', fill_value=0)
                    st.markdown(f"<p>📈 Tren kesalahan untuk: <strong>{pilihan_ssr}</strong></p>", unsafe_allow_html=True)
                    
                if not df_pivot.empty:
                    st.area_chart(df_pivot)
                else:
                    st.info("Data belum tersedia untuk filter ini.")
            else:
                st.info("Belum ada data rekap tren di tabel rekap_tren_bulanan.")
        
        # Menutup Glass Card HTML Container dari Main Layout (Pastikan ada elemen pembukanya di atas)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


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
