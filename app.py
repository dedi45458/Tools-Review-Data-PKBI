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
    simpan_agregasi_ke_neon,
    ambil_agregasi_terakhir_dari_neon,
    simpan_detil_review_ke_neon,      
    ambil_detil_terakhir_dari_neon,      
    ambil_status_storage_neon,
    ambil_data_rujukan_hiv_positif,  # 🔥 DITAMBAHKAN UNTUK REFERENSI RUJUKAN
    ambil_database_layanan           # 🔥 DITAMBAHKAN UNTUK REFERENSI LAYANAN
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

    div[data-testid="stPlotlyChart"] .hoverlayer path {
        fill: #1e293b !important;
        stroke: #38bdf8 !important;
        fill-opacity: 0.95 !important;
    }
    div[data-testid="stPlotlyChart"] .hoverlayer text { fill: #f8fafc !important; }
    div[data-testid="stPlotlyChart"] .hoverlayer text tspan { fill: #f8fafc !important; }
    </style>
    """, unsafe_allow_html=True)

set_modern_theme()

# ==========================================================
# 0. MANAGEMENT DEFAULT STATE & INIT DATA
# ==========================================================
if 'total_entri' not in st.session_state: st.session_state['total_entri'] = 0
if 'proses_selesai' not in st.session_state: st.session_state['proses_selesai'] = False
if 'df_tabel_bawah' not in st.session_state: st.session_state['df_tabel_bawah'] = None
if 'aturan_kustom' not in st.session_state: st.session_state['aturan_kustom'] = []

if 'df_tabel_atas' not in st.session_state or st.session_state['df_tabel_atas'] is None:
    try:
        df_dari_db, max_date = ambil_agregasi_terakhir_dari_neon()
        if df_dari_db is not None and not df_dari_db.empty:
            st.session_state['df_tabel_atas'] = df_dari_db
            st.session_state['tanggal_terakhir_review'] = max_date
        else:
            st.session_state['df_tabel_atas'] = pd.DataFrame()
            st.session_state['tanggal_terakhir_review'] = datetime.now()
    except Exception as e:
        st.session_state['df_tabel_atas'] = pd.DataFrame()
        st.session_state['tanggal_terakhir_review'] = datetime.now()
        
if 'df_tabel_bawah' not in st.session_state or st.session_state['df_tabel_bawah'] is None:
    try:
        df_detil_db, max_ts_bawah = ambil_detil_terakhir_dari_neon()
        if df_detil_db is not None and not df_detil_db.empty:
            st.session_state['df_tabel_bawah'] = df_detil_db
            st.session_state['tanggal_terakhir_bawah'] = max_ts_bawah
        else:
            st.session_state['df_tabel_bawah'] = pd.DataFrame()
            st.session_state['tanggal_terakhir_bawah'] = datetime.now()
    except Exception as e:
        st.session_state['df_tabel_bawah'] = pd.DataFrame()
        st.session_state['tanggal_terakhir_bawah'] = datetime.now()

if 'medsoc_keywords' not in st.session_state:
    st.session_state['medsoc_keywords'] = ambil_keyword_medsos_db()

st.markdown('<div class="main-title">📊 Tools Review Data PKBI Jawa Barat</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem Validasi Kualitas Data Penjangkauan & Rujukan</div>', unsafe_allow_html=True)

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
    {"nama": "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)", "periksa": lambda c: c['is_file_rujukan'] and c['df_ref'] is not None and c['v_ssr'] and f"{c['v_ssr']}_{c['id_clean']}" in c['ref_ssr_id_to_nik'] and c['ref_ssr_id_to_nik'][f"{c['v_ssr']}_{c['id_clean']}"] != c['nik_clean']},
    {"nama": "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)", "periksa": lambda c: c['is_file_rujukan'] and c['df_ref'] is not None and c['v_ssr'] and c['nik_clean'] != '' and f"{c['nik_clean']}_{c['v_ssr']}" in c['ref_nik_ssr_to_id'] and c['ref_nik_ssr_to_id'][f"{c['nik_clean']}_{c['v_ssr']}"] != c['id_clean']},
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
    {"nama": "Lokasi outreach diindikasi kurang spesifik atau kurang detil (konfirmasi)", 
    "periksa": lambda c: (
        str(c.get('lokasi', '')).strip() != '' 
        and str(c.get('lokasi', '')).strip().lower() != 'nan' 
        and not c.get('is_vo', False) 
        and not (str(c.get('jns_kontak', '')).split('.')[0].strip() == '3' and str(c.get('jns_kegiatan', '')).split('.')[0].strip() == '8'
            and any(m in str(c.get('lokasi', '')).upper() for m in ['FB', 'FACEBOOK', 'IG', 'INSTAGRAM', 'WA', 'WHATSAPP', 'TELE', 'TELEGRAM', 'TIKTOK', 'TWITTER', 'X ', 'YOUTUBE', 'YT', 'GRUP', 'GROUP', 'ONLINE', 'MEDSOS', 'SOSMED']))
        and len(str(c.get('lokasi', '')).strip()) < 17 
        and not any(k in str(c.get('lokasi', '')).upper() for k in ['ALUN', 'RSUD', 'RS ', 'PUSKESMAS', 'KLINIK', 'TERMINAL', 'STASIUN', 'TAMAN', 'PASAR', 'MALL', 'KAMPUS', 'UNIV', 'SEKOLAH', 'SMK', 'SMA', 'SMP', 'SD', 'MASJID', 'GEREJA', 'HOTEL', 'PANTI', 'AULA', 'BALAI']) 
        and not (bool(re.search(r'\d', str(c.get('lokasi', '')))) or any(p in str(c.get('lokasi', '')).upper() for p in ['JL', 'JALAN', 'RT', 'RW', 'GANG', 'GG', 'KP', 'KAMPUNG', 'BLOK', 'DESA', 'KEC', 'KAB', 'SAMPING', 'DEPAN', 'DEKAT', 'SEBERANG']))
        )
    },
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
# 2. ATURAN VALIDASI KHUSUS RUJUKAN (BARU)
# ==========================================================
ATURAN_VALIDASI_RUJUKAN = [
    # --- CROSS CHECK DATA PENJANGKAUAN & REFERENSI ---
    {"nama": "ID tidak terdaftar di penjangkauan", "periksa": lambda c: f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}" not in c.get('set_ssr_id_penjangkauan', set())},
    {"nama": "Data rujukan tapi tidak ada NIK (konfirmasi)", "periksa": lambda c: str(c['row'].get('ID Klien', '')).strip() != '' and str(c['row'].get('NIK', '')).replace("'", "").strip() in ['', 'nan', 'none']},
    {"nama": "ID sudah dinyatakan Reaktif di semester / tahun lalu (Konfirmasi)", "periksa": lambda c: c.get('is_reaktif_sebelumnya', False)},
    
    # --- CBS (COMMUNITY BASED SCREENING) ---
    {"nama": "Jenis Layanan tidak sesuai", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() not in ['5', '6']},
    {"nama": "Jenis Layanan dengan Metode CBS tidak sesuai", "periksa": lambda c: str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and str(c['row'].get('Metode CBS', '')).split('.')[0].strip() in ['', '0', '1', 'nan']},
    {"nama": "Bukan CBS tapi jenis layanan 5/6", "periksa": lambda c: 'cbs' not in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6']},
    {"nama": "Layanan CBS ada rujukan IMS", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Jenis Layanan', '')).split('.')[0].strip() in ['5', '6'] and cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Layanan CBS ada rujukan PrEp", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and cek_kode(c['row'].get('Rujukan'), '51')},
    {"nama": "Layanan CBS ada rujukan selain VCT", "periksa": lambda c: 'cbs' in str(c['row'].get('Nama Layanan', '')).lower() and str(c['row'].get('Rujukan', '')).replace("'", "").strip() != '2'},
    
    # --- RUJUKAN UMUM ---
    {"nama": "Tidak ada rujukan satupun/tidak diisi", "periksa": lambda c: str(c['row'].get('Rujukan', '')).replace("'", "").strip() in ['', 'nan', 'None']},
    {"nama": "Bukan penasun rujukan 3,4", "periksa": lambda c: str(c['row'].get('Tipe Klien', '')).split('.')[0].strip() != '1401' and (cek_kode(c['row'].get('Rujukan'), '3') or cek_kode(c['row'].get('Rujukan'), '4'))},
    {"nama": "ID akses ke layanan lebih dari 1x tapi belum tes HIV (Konfirmasi)", "periksa": lambda c: c.get('id_counts', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", 0) > 1 and not c.get('rujukan_vct_per_klien', {}).get(f"{c.get('v_ssr', '')}_{c.get('id_clean', '')}", False)},
    
    # --- HIV (VCT) ---
    {"nama": "Tidak menerima hasil tes HIV", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '2') and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', '2', 'nan']},
    {"nama": "Kolom menerima hasil tes HIV terisi tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi tidak ada rujukan HIV", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '2')},
    {"nama": "Ada hasil tes HIV tapi kolom menerima hasil tidak terisi", "periksa": lambda c: str(c['row'].get('Hasil Tes HIV', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Hasil VCT', '')).split('.')[0].strip() in ['', 'nan']},
    
    # --- IMS ---
    {"nama": "Dirujuk IMS tapi tidak ada hasil IMS", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '1') and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil IMS tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi hasil tes IMS Non Reaktif/ N/A", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['2', '3']},
    {"nama": "Hasil tes IMS reaktif tapi tidak menerima pengobatan IMS (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '2'},
    {"nama": "Kolom menerima pengobatan IMS terisi tapi tidak ada rujukan IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '1')},
    {"nama": "Menerima pengobatan IMS tapi tidak ada hasil tes IMS", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada hasil tes IMS tapi kolom menerima pengobatan IMS tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes IMS', '')).split('.')[0].strip() in ['1', '2', '3'] and str(c['row'].get('Menerima Pengobatan IMS', '')).split('.')[0].strip() in ['', 'nan']},
    
    # --- PrEP ---
    {"nama": "DIrujuk PrEP tapi hasil skrining PrEP tidak diisi", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Layanan PrEp tidak terdaftar, indikasi salah mengisi layanan atau belum update jenis layanan PrEP di SIMS (konfirmasi)", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and not c.get('is_layanan_prep_valid', True)},
    {"nama": "Ada hasil skrining PrEP tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and not cek_kode(c['row'].get('Rujukan'), '5')},
    {"nama": "Ada hasil skrining PrEP tapi kolom menerima obat PrEP tidak disi", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() in ['1', '2'] and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Menerima pengobatan PrEP diisi tapi tidak ada rujukan PrEP", "periksa": lambda c: str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and not cek_kode(c['row'].get('Rujukan'), '5')},
    {"nama": "KD sudah menerima obat PrEP tapi hasil skrining PrEP tidak memenuhi syarat", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '5') and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '2'},
    {"nama": "Hasil Skrining PrEP memenuhi syarat tapi KD tidak menerima obat PrEP (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Screening PrEP', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Obat PrEP', '')).split('.')[0].strip() == '2'},
    
    # --- TB / OAT ---
    {"nama": "Dirujuk TB tapi tidak ada Hasil Tes TB", "periksa": lambda c: cek_kode(c['row'].get('Rujukan'), '8') and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['', 'nan']},
    {"nama": "Ada Hasil TB tapi tidak ada rujukan TB", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['1', '2', '3'] and not cek_kode(c['row'].get('Rujukan'), '8')},
    {"nama": "Menerima pengobatan TB tapi hasil tes TB Non Reaktif/ N/A/ tidak diisi", "periksa": lambda c: str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '1' and str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['2', '3', '', 'nan']},
    {"nama": "Hasil tes TB reaktif tapi tidak menerima pengobatan TB (konfirmasi)", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() == '1' and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() == '2'},
    {"nama": "Ada hasil tes TB tapi kolom pengobatan TB tidak diisi", "periksa": lambda c: str(c['row'].get('Hasil Tes TB', '')).split('.')[0].strip() in ['2', '3'] and str(c['row'].get('Menerima Pengobatan TB/OAT', '')).split('.')[0].strip() in ['', 'nan']},
    
    # --- HEP-C / DAA ---
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
    
    menu_pilihan = st.radio("Navigasi Menu", ["🎯 Dashboard Review Data", "⚙️ Pengaturan Keyword Medsos"], label_visibility="collapsed")
    st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1);'></div>", unsafe_allow_html=True)
    tombol_proses = False
    
    if menu_pilihan == "🎯 Dashboard Review Data":
        with st.container():
            st.markdown("<b style='color: #38bdf8; font-size: 0.95rem;'>📁 MANAJEMEN BERKAS</b>", unsafe_allow_html=True)
            st.markdown("<small style='color: #888;'>Unggah berkas master atau raw data.</small>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- 1. UPLOADER PINTAR ---
            file_master = st.file_uploader(
                "Upload Berkas Database Master (.xlsx)", 
                type=["xlsx"], 
                help="Sistem akan otomatis mendeteksi apakah ini Data HIV+ atau Database Layanan.",
                key="uploader_master_tunggal"
            )
            
            if file_master is not None:
                try:
                    df_check = pd.read_excel(file_master)
                    kolom_terdeteksi = [str(c).strip().lower() for c in df_check.columns]
                    is_data_layanan = any("lembaga" in c or "ssr" in c for c in kolom_terdeteksi) and any("layanan" in c for c in kolom_terdeteksi)
                    
                    if is_data_layanan:
                        st.info("🏥 **Terdeteksi:** Berkas Master Layanan Fasyankes / SSR")
                        if st.button("🔄 Update Database Referensi Layanan", use_container_width=False, key="btn_exec_layanan"):
                            with st.spinner("Sedang memproses database master layanan..."):
                                from database import import_database_layanan
                                sukses, pesan = import_database_layanan(df_check)
                                if sukses: st.success(f"✅ {pesan}")
                                else: st.error(f"❌ Gagal: {pesan}")
                    else:
                        st.info("📋 **Terdeteksi:** Berkas Data Referensi HIV+ Semester Lalu")
                        if st.button("🔄 Update Database Referensi HIV", use_container_width=False, key="btn_exec_hiv"):
                            with st.spinner("Sedang memproses data rujukan HIV..."):
                                from database import import_data_HIV
                                if import_data_HIV(df_check): st.success("✅ Database referensi HIV diperbarui!")
                                else: st.error("❌ Gagal mengupdate database.")
                except Exception as e:
                    st.error(f"⚠️ Gagal membaca struktur berkas Excel: {e}")
            
            st.markdown("<div style='margin-top: 15px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 15px;'></div>", unsafe_allow_html=True)
            
            # --- 2. UPLOADER RAW DATA PENJANGKAUAN BERKALA ---
            st.markdown("<span style='font-weight: 500; font-size: 0.9rem;'>📂 Upload RD Penjangkauan & Rujukan</span>", unsafe_allow_html=True)
            files_review = st.file_uploader(
                "Raw Data Penjangkauan/Rujukan (Multi-File)", 
                type=["xlsx", "csv"], 
                accept_multiple_files=True, 
                help="Wajib: Anda bisa memilih lebih dari satu file operasional sekaligus untuk di-review",
                key="uploader_raw_penjangkauan"
            )
            
            if files_review:
                st.info(f"📁 {len(files_review)} file siap diproses.")
    
        st.markdown("<div style='margin: 25px 0;'></div>", unsafe_allow_html=True)
        
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
        # INDIKATOR STORAGE NEON DB
        # ==========================================================
        storage_info = ambil_status_storage_neon()
        if storage_info:
            if storage_info['persen_terpakai'] > 85: kondisi_warna = "#ff4b4b" 
            elif storage_info['persen_terpakai'] > 60: kondisi_warna = "#ffa500"
            else: kondisi_warna = "#38bdf8"
                
            html_storage = f"""
            <div style="background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 12px 14px; margin-bottom: 10px; font-size: 0.82rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
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
            st.markdown("<div style='color: #94a3b8; font-size: 0.8rem; margin-bottom: 15px;'>⚠️ Gagal memuat status storage.</div>", unsafe_allow_html=True)
            
        st.markdown("<div style='margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-top: 15px;'></div>", unsafe_allow_html=True)

# ==========================================================
# 3. ENGINE VALIDASI UTAMA (VERSI SEMPURNA & DINAMIS + INTEGRASI RUJUKAN)
# ==========================================================
def jalankan_review_data(df_asli, df_ref_db=None, df_layanan_db=None, global_ssr_id_penj=set(), nama_file=""):
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    
    # Perbaikan header (Merge Cells)
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
            if main_headers[i] and 'UNNAMED' not in main_headers[i].upper(): current_main = main_headers[i]
            sub = sub_headers[i] if (sub_headers[i] and str(sub_headers[i]).lower() != 'nan') else ""
            
            if current_main and sub and 'UNNAMED' not in sub.upper(): columns_fixed.append(f"{current_main} - {sub}")
            elif sub and 'UNNAMED' not in sub.upper(): columns_fixed.append(sub)
            else: columns_fixed.append(main_headers[i])
                
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
    is_file_rujukan = any('HASIL TES HIV' in c or 'RUJUKAN' in c or 'METODE CBS' in c for c in col_upper_all)
    
    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())

    keywords_aktif = st.session_state.get('medsoc_keywords', [])
    if keywords_aktif: pattern_medsos_dinamis = r'\b(' + '|'.join([re.escape(k) for k in keywords_aktif]) + r')\b'
    else: pattern_medsos_dinamis = r'\b(TIDAK_ADA_MEDSOS_TERDAFTAR_DI_SISTEM)\b'

    try: dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()
    except Exception: dict_revisi, dict_justifikasi = {}, {}

    ref_ssr_id_to_nik, ref_nik_ssr_to_id = {}, {}
    dict_pernah_cbs, dict_pernah_prep_rujukan = {}, {}
    
    # PENYUSUNAN DICTIONARY REFERENSI HISTORIS (Jika File yang diupload adalah Penjangkauan)
    if is_file_rujukan and df_ref_db is not None and not df_ref_db.empty:
        for _, r in df_ref_db.iterrows():
            ssr_r = str(r.get('lembaga_ssr', '')).strip().upper()
            id_r = str(r.get('id_klien', '')).replace("'", "").strip()
            nik_r = str(r.get('nik', '')).replace("'", "").replace('.0', '').strip()
            key_klien = f"{ssr_r}_{id_r}"

            if id_r and id_r != 'nan' and ssr_r and ssr_r != 'nan': ref_ssr_id_to_nik[key_klien] = nik_r
            if nik_r and nik_r != 'nan' and nik_r != '' and ssr_r and ssr_r != 'nan': ref_nik_ssr_to_id[f"{nik_r}_{ssr_r}"] = id_r
            
            layanans = str(r.get('jenis_layanan_detil', '')).replace("'", "").replace(" ", "").split(',')
            if '5' in layanans or '6' in layanans: dict_pernah_cbs[key_klien] = True
            
            rujukans = str(r.get('rujukan', '')).replace("'", "").replace(" ", "").split(',')
            if '5' in rujukans: dict_pernah_prep_rujukan[key_klien] = True

    # 1. PERSIAPAN DB LAYANAN (Untuk Rule: Layanan PrEp tidak terdaftar)
    set_layanan_prep = set()
    if df_layanan_db is not None and not df_layanan_db.empty:
        for _, r in df_layanan_db.iterrows():
            ssr = str(r.get('lembaga_ssr_iu', '')).strip().upper()
            layanan = str(r.get('nama_layanan', '')).strip().upper()
            jenis = str(r.get('jenis', '')).strip().lower()
            if 'prep' in jenis: set_layanan_prep.add(f"{ssr}_{layanan}")

    # 2. PERSIAPAN DB REAKTIF (Untuk Rule: ID sudah dinyatakan Reaktif di semester lalu)
    dict_reaktif_nik = {}
    dict_reaktif_id = {}
    if df_ref_db is not None and not df_ref_db.empty:
        for _, r in df_ref_db.iterrows():
            hasil = str(r.get('hasil_tes_hiv', '')).split('.')[0].strip()
            if hasil == '1': # Reaktif
                nik_r = str(r.get('nik', '')).replace("'", "").replace(".0", "").strip()
                ssr_r = str(r.get('lembaga_ssr', '')).strip().upper()
                id_r = str(r.get('id_klien', '')).replace("'", "").strip()
                kota_r = str(r.get('nama_kota', '')).strip()
                petugas_r = str(r.get('kode_petugas', '')).strip()
                tgl_r = str(r.get('tanggal', '')).strip()
                layanan_r = str(r.get('nama_layanan', '')).strip()

                info_tambahan = f"({ssr_r} - {petugas_r} - {kota_r} - {tgl_r} - {layanan_r})"
                if nik_r and len(nik_r) > 5: dict_reaktif_nik[nik_r] = info_tambahan
                if ssr_r and id_r: dict_reaktif_id[f"{ssr_r}_{id_r}"] = info_tambahan

    # 3. PERSIAPAN JUMLAH & GROUPING INTERNAL
    df['id_mapped'] = df.get('ID Klien', pd.Series(dtype=str)).astype(str).str.replace("'", "").str.strip()
    df['ssr_id_key'] = df.get('Lembaga SSR', pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + df['id_mapped']
    dict_ssr_id_counts = df.iloc[start_row_idx:]['ssr_id_key'].value_counts().to_dict()
    
    def periksa_hiv(x): return '1' in str(x).replace("'", "").replace(" ", "").split(',')
    def periksa_rujukan(x): 
        s = str(x).replace("'", "").replace(" ", "").replace(".0", "")
        if '.' in s and ',' not in s: s = s.replace('.', ',')
        return '2' in s.split(',')

    col_info = next((c for c in df.columns if "INFORMASI" in str(c).upper() and "DIBERIKAN" in str(c).upper()), None)
    col_kegiatan = next((c for c in df.columns if "JENIS KEGIATAN" in str(c).upper()), None)
    col_kontak = next((c for c in df.columns if "JENIS KONTAK" in str(c).upper() or "JNS KONTAK" in str(c).upper()), None)
    col_lokasi = next((c for c in df.columns if "LOKASI" in str(c).upper()), None)
    col_ruj = next((c for c in df.columns if "RUJUKAN" in str(c).upper()), None)
    col_tanggal = next((c for c in df.columns if "TANGGAL" in str(c).upper()), "Tanggal")
    col_tipe_sasaran = next((c for c in df.columns if "TIPE SASARAN" in str(c).upper() or "TIPE KLIEN" in str(c).upper()), "Tipe Sasaran")
    col_vc1 = next((c for c in df.columns if "VIRTUAL" in str(c).upper() or "VC1" in str(c).upper() or "TATAP MUKA" in str(c).upper()), None)
    
    df['is_info_hiv'] = df[col_info].apply(periksa_hiv) | df[col_kegiatan].apply(periksa_hiv) if col_info and col_kegiatan else False
    df['is_rujuk_tes'] = df[col_ruj].apply(periksa_rujukan) if col_ruj else False

    dict_pernah_hiv = df.groupby('ssr_id_key')['is_info_hiv'].any().to_dict()
    dict_pernah_rujuk = df.groupby('ssr_id_key')['is_rujuk_tes'].any().to_dict()
    
    # Khusus untuk Rujukan: Cek ID akses layanan > 1x tapi belum tes HIV
    dict_rujukan_vct = {}
    if is_file_rujukan and col_ruj:
        df['is_rujuk_vct'] = df[col_ruj].apply(lambda x: '2' in str(x).replace("'", "").replace(" ", "").replace(".0", "").split(','))
        dict_rujukan_vct = df.groupby('ssr_id_key')['is_rujuk_vct'].any().to_dict()

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
    df['kunci_klien_ref_log'] = df.get('Lembaga SSR', pd.Series(dtype=str)).astype(str).str.strip().str.upper() + "_" + df['id_mapped']
    dict_total_log_per_klien = df.groupby('kunci_klien_ref_log')['tmp_log'].sum().to_dict()

    aturan_kustom = st.session_state.get('aturan_kustom', [])
    
    # 🔥 PISAHKAN ATURAN YANG DIEKSEKUSI BERDASARKAN JENIS FILE
    if is_file_rujukan: SEMUA_ATURAN_AKTIF = ATURAN_VALIDASI_RUJUKAN + aturan_kustom
    else: SEMUA_ATURAN_AKTIF = ATURAN_VALIDASI_BAWAAN + aturan_kustom

    # LOOP BARIS DATA
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
        local_id_counts = {id_clean: dict_ssr_id_counts.get(kunci_klien_ref, 0)} 

        # Variabel Dinamis Rujukan
        info_reaktif_tambahan = dict_reaktif_nik.get(nik_clean, dict_reaktif_id.get(kunci_klien_ref, ""))
        is_reaktif_sebelumnya = bool(info_reaktif_tambahan)
        
        is_layanan_prep_valid = True
        if cek_kode(rujukan, '5'):
            nama_layanan_val = str(row.get('Nama Layanan', '')).strip().upper()
            if f"{v_ssr}_{nama_layanan_val}" not in set_layanan_prep:
                is_layanan_prep_valid = False

        context_data = {
            'row': row, 'id_clean': id_clean, 'nik_clean': nik_clean, 'v_ssr': v_ssr, 'v_tanggal': v_tanggal,
            'v_petugas': v_petugas, 'v_kota': v_kota, 'v_tipe_sasaran': v_tipe_sasaran, 'umur': umur, 'jk': jk,
            'jns_kontak': jns_kontak, 'jns_kegiatan': jns_kegiatan, 'lokasi': lokasi, 'info_diberikan': info_diberikan,
            'rujukan': rujukan, 'no_hp': no_hp, 'vc1': vc1, 'log_kie': log_kie, 'log_kon': log_kon, 'log_pel': log_pel,
            'log_jar': log_jar, 'log_swab': log_swab, 'jarum_kembali': jarum_kembali, 'tgl_p': tgl_p, 'hari_ini': hari_ini,
            'tahun_sekarang': tahun_sekarang, 'is_vo': (jns_kontak == '3'), 'is_pwid': (v_tipe_sasaran in ['1401', '1403']),
            'id_counts': local_id_counts, 
            'pernah_dapat_info_hiv': dict_pernah_hiv.get(kunci_klien_ref, False) if id_clean else False, 
            'pernah_dapat_rujuk_tes': dict_pernah_rujuk.get(kunci_klien_ref, False) if id_clean else False,
            'is_file_rujukan': is_file_rujukan, 'df_ref': df_ref_db, 
            'ref_ssr_id_to_nik': ref_ssr_id_to_nik, 'ref_nik_ssr_to_id': ref_nik_ssr_to_id,
            'pernah_cbs_di_rujukan': dict_pernah_cbs.get(kunci_klien_ref, False),
            'pernah_prep_di_rujukan': dict_pernah_prep_rujukan.get(kunci_klien_ref, False),
            'total_log_keseluruhan_klien': dict_total_log_per_klien.get(kunci_klien_ref, 0.0),
            'pattern_medsos': pattern_medsos_dinamis,
            
            # Context tambahan Rujukan
            'set_ssr_id_penjangkauan': global_ssr_id_penj,
            'is_reaktif_sebelumnya': is_reaktif_sebelumnya,
            'info_reaktif_tambahan': info_reaktif_tambahan,
            'is_layanan_prep_valid': is_layanan_prep_valid,
            'rujukan_vct_per_klien': dict_rujukan_vct
        }

        # LOOP ATURAN VALIDASI
        for rule in SEMUA_ATURAN_AKTIF:
            nama_ind = rule["nama"]
            try:
                if rule["periksa"](context_data):
                    key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{nama_ind}"
                    status_validasi = "-"
                    
                    # 💡 Menyematkan tambahan informasi untuk rule konfirmasi data Reaktif Semester Lalu
                    if "ID sudah dinyatakan Reaktif di semester" in nama_ind and context_data.get('info_reaktif_tambahan'):
                        status_validasi = f"⚠️ Info Historis: {context_data['info_reaktif_tambahan']}"
                        
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
                        "Validasi Hasil Review": status_validasi, 
                        "Justifikasi": justif_val
                    })
            except Exception as e: 
                pass

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. LOGIKA TOMBOL EKSEKUSI (DENGAN PENYARINGAN GLOBAL)
# ==========================================================
if tombol_proses:
    if not files_review:
        st.error("⚠️ Silakan unggah berkas Raw Data terlebih dahulu di sidebar!")
    else:
        with st.spinner("Sedang memproses validasi data & sinkronisasi database..."):
            
            # 1. Panggil dan persiapkan Data Referensi dari DB
            df_ref_db = ambil_data_rujukan_hiv_positif()
            df_layanan_db = ambil_database_layanan()
            
            # 2. Tahap Pra-Pemrosesan (Kumpulkan semua ID Penjangkauan yang ada)
            global_ssr_id_penj = set()
            df_list_for_review = []
            
            for f in files_review:
                df_target = pd.read_csv(f, low_memory=False) if f.name.endswith('.csv') else pd.read_excel(f)
                df_list_for_review.append((f.name, df_target))
                
                # Cek jika ini bukan file Rujukan, extract semua ID nya sebagai database pembanding
                col_upper = [str(c).upper() for c in df_target.columns]
                is_ruj_file = any('HASIL TES HIV' in c or 'RUJUKAN' in c or 'METODE CBS' in c for c in col_upper)
                
                if not is_ruj_file:
                    col_ssr = next((c for c in df_target.columns if 'SSR' in str(c).upper() or 'LEMBAGA' in str(c).upper()), None)
                    col_id = next((c for c in df_target.columns if 'ID' in str(c).upper() or 'KLIEN' in str(c).upper()), None)
                    if col_ssr and col_id:
                        for _, r in df_target.iterrows():
                            ssr = str(r[col_ssr]).strip().upper()
                            idk = str(r[col_id]).replace("'", "").strip()
                            if ssr and idk:
                                global_ssr_id_penj.add(f"{ssr}_{idk}")
                                
            # 3. Proses Validasi Berjalan
            all_errs, total_records = [], 0
            detected_ssrs = set()

            for fname, df_target in df_list_for_review:
                try:
                    total_records += len(df_target)
                    df_res = jalankan_review_data(
                        df_target, 
                        df_ref_db=df_ref_db, 
                        df_layanan_db=df_layanan_db, 
                        global_ssr_id_penj=global_ssr_id_penj,
                        nama_file=fname
                    )
                    if not df_res.empty:
                        all_errs.append(df_res)
                        detected_ssrs.update(df_res['Lembaga SSR'].unique())
                except Exception as e: 
                    st.error(f"Error memproses {fname}: {e}")

            st.session_state['total_entri'] = total_records

            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                
                # --- SINKRONISASI LOG & AGREGASI NEON ---
                existing_logs = set()         
                existing_details = set()      
                existing_aggregations = set() 
                hari_ini_str = datetime.now().date().isoformat()
                
                try:
                    conn = dapatkan_koneksi_neon()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT LOWER(Lembaga_SSR), LOWER(Tanggal), LOWER(ID_Klien), LOWER(Indikator_Kesalahan_Data) FROM log_validasi_review;")
                            for r in cur.fetchall(): existing_logs.add((str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip()))
                            
                            cur.execute('SELECT LOWER("Lembaga SSR"), LOWER("Tanggal"), LOWER("ID Klien"), LOWER("Indikator Kesalahan Data") FROM hasil_review_penjangkauan_detil_per_baris;')
                            for r in cur.fetchall(): existing_details.add((str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip(), str(r[3]).strip()))
                            
                            cur.execute('SELECT tanggal_dibuat, LOWER(nama_ssr), LOWER(indikator_kesalahan), jumlah_kesalahan FROM agregasi_hasil_review_penjangkauan;')
                            for r in cur.fetchall():
                                tgl_dibuat_str = r[0].date().isoformat() if hasattr(r[0], 'date') else str(r[0]).split()[0]
                                existing_aggregations.add((tgl_dibuat_str.strip(), str(r[1]).strip(), str(r[2]).strip(), int(r[3])))
                        conn.close()
                except Exception as e:
                    st.warning(f"⚠️ Gagal memuat indeks pembanding: {e}")

                if 'Validasi Hasil Review' not in df_bawah.columns: df_bawah['Validasi Hasil Review'] = ""
                
                indices_to_drop = []
                for idx, row in df_bawah.iterrows():
                    ssr = str(row.get('Lembaga SSR', '')).strip().lower()
                    tgl = str(row.get('Tanggal', '')).strip().lower() 
                    id_klien = str(row.get('ID Klien', '')).strip().lower()
                    ind = str(row.get('INDIKATOR KESALAHAN DATA', '')).strip().lower()
                    key = (ssr, tgl, id_klien, ind)
                    
                    if key in existing_details:
                        indices_to_drop.append(idx)
                        continue
                    
                    if key in existing_logs:
                        if "konfirmasi" in ind: indices_to_drop.append(idx)
                        else: df_bawah.at[idx, 'Validasi Hasil Review'] = "kesalahan pada ID yang sama (belum direvisi)"
                
                if indices_to_drop:
                    df_bawah = df_bawah.drop(index=indices_to_drop).reset_index(drop=True)
                
                detected_ssrs = set(df_bawah['Lembaga SSR'].unique()) if not df_bawah.empty else set()
                active_ssrs = sorted(list(detected_ssrs))
                total_seluruh_kesalahan = len(df_bawah)
                
                # Filter agar perhitungan persen agregasi proporsional dengan indikator yang relevan
                DAFTAR_INDIKATOR_AKTIF = [r["nama"] for r in (ATURAN_VALIDASI_BAWAAN + ATURAN_VALIDASI_RUJUKAN + st.session_state['aturan_kustom'])]
                
                matrix_rows = []
                for ind in DAFTAR_INDIKATOR_AKTIF:
                    r_dict = {"INDIKATOR KESALAHAN DATA": ind}
                    total_ind_err = 0
                    for ssr in active_ssrs:
                        c = len(df_bawah[(df_bawah['INDIKATOR KESALAHAN DATA'] == ind) & (df_bawah['Lembaga SSR'] == ssr)])
                        r_dict[ssr] = c
                        total_ind_err += c
                    
                    if total_ind_err > 0: # Hanya proses indikator yang memiliki temuan
                        r_dict["Jumlah per indikator"] = total_ind_err
                        r_dict["%"] = (total_ind_err / total_seluruh_kesalahan * 100) if total_seluruh_kesalahan > 0 else 0.0
                        matrix_rows.append(r_dict)
                
                df_atas = pd.DataFrame(matrix_rows)
                
                if not df_atas.empty:
                    for idx, row in df_atas.iterrows():
                        ind_name = str(row.get('INDIKATOR KESALAHAN DATA', '')).strip().lower()
                        for ssr in active_ssrs:
                            ssr_name = str(ssr).strip().lower()
                            jumlah_hitung_baru = int(row.get(ssr, 0))
                            if jumlah_hitung_baru == 0: continue
                            
                            agg_key = (hari_ini_str, ssr_name, ind_name, jumlah_hitung_baru)
                            if agg_key in existing_aggregations:
                                df_atas.at[idx, ssr] = 0
                    
                    df_atas['Jumlah per indikator'] = [sum(row[ssr] for ssr in active_ssrs) for idx, row in df_atas.iterrows()]
                    df_atas = df_atas[df_atas['Jumlah per indikator'] > 0] 
                    
                    total_sisa_agregat = df_atas['Jumlah per indikator'].sum()
                    if total_sisa_agregat > 0: df_atas['%'] = (df_atas['Jumlah per indikator'] / total_sisa_agregat * 100)
                    else: df_atas['%'] = 0.0

                if not df_atas.empty: df_atas.set_index("INDIKATOR KESALAHAN DATA", inplace=True)
                else: df_atas = pd.DataFrame(columns=["Jumlah per indikator", "%"])
                
                if "INDIKATOR KESALAHAN DATA" in df_bawah.columns:
                    df_bawah = df_bawah.rename(columns={"INDIKATOR KESALAHAN DATA": "Indikator Kesalahan Data"})
                
                try:
                    if df_bawah.empty:
                        st.info("ℹ️ Seluruh data yang diupload sudah ada dan tersimpan di database Neon (Tidak ada data baru yang dimasukkan).", icon="ℹ️")
                        df_atas_db, ts_atas_db = ambil_agregasi_terakhir_dari_neon()
                        df_bawah_db, ts_bawah_db = ambil_detil_terakhir_dari_neon()
                        
                        if not df_atas_db.empty:
                            st.session_state['df_tabel_atas'] = df_atas_db
                            st.session_state['tanggal_terakhir_review'] = ts_atas_db
                        if not df_bawah_db.empty:
                            st.session_state['df_tabel_bawah'] = df_bawah_db
                            st.session_state['tanggal_terakhir_bawah'] = ts_bawah_db
                    else:
                        df_to_db_atas = df_atas.copy().reset_index()
                        sukses_simpan_atas = simpan_agregasi_ke_neon(df_to_db_atas)
                        sukses_simpan_bawah = simpan_detil_review_ke_neon(df_bawah)
                        
                        if sukses_simpan_atas and sukses_simpan_bawah:
                            st.toast("💾 Data baru berhasil disinkronisasi dengan aturan kombinasi baru!", icon="✅")
                            df_atas_db, ts_atas_db = ambil_agregasi_terakhir_dari_neon()
                            df_bawah_db, ts_bawah_db = ambil_detil_terakhir_dari_neon()
                            
                            if not df_atas_db.empty:
                                st.session_state['df_tabel_atas'] = df_atas_db
                                st.session_state['tanggal_terakhir_review'] = ts_atas_db
                            if not df_bawah_db.empty:
                                st.session_state['df_tabel_bawah'] = df_bawah_db
                                st.session_state['tanggal_terakhir_bawah'] = ts_bawah_db
                        else:
                            st.session_state['df_tabel_atas'] = df_atas
                            st.session_state['df_tabel_bawah'] = df_bawah
                            st.session_state['tanggal_terakhir_review'] = datetime.now()
                            st.session_state['tanggal_terakhir_bawah'] = datetime.now()
                            st.error("❌ Gagal Sinkronisasi: Terjadi gangguan koneksi ke DB Neon. Data disimpan sementara di session lokal.")
                            
                except Exception as e:
                    st.error(f"⚠️ Gagal mengeksekusi sinkronisasi database: {str(e)}")
                    st.session_state['df_tabel_atas'] = df_atas
                    st.session_state['df_tabel_bawah'] = df_bawah
                    st.session_state['tanggal_terakhir_review'] = datetime.now()
                    st.session_state['tanggal_terakhir_bawah'] = datetime.now()
                    
            else:
                st.session_state['df_tabel_atas'] = pd.DataFrame()
                st.session_state['df_tabel_bawah'] = pd.DataFrame()

            st.session_state['proses_selesai'] = True
            
            import time
            time.sleep(1.5) 
            st.rerun()

# ==========================================================
# 5. RENDER LAYOUT UTAMA
# ==========================================================
if menu_pilihan == "🎯 Dashboard Review Data":
    df_historis = st.session_state.get('df_tabel_atas', pd.DataFrame())
    
    if st.session_state.get('proses_selesai', False) or (df_historis is not None and not df_historis.empty):
        tot_data = st.session_state.get('total_entri', 0)
       
        if st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
            df_baris_unik = st.session_state['df_tabel_bawah'].drop_duplicates(subset=["Lembaga SSR", "Tanggal", "ID Klien"])
            tot_err = len(df_baris_unik)
        elif df_historis is not None and not df_historis.empty:
            tot_err = int(df_historis['Jumlah per indikator'].sum()) if 'Jumlah per indikator' in df_historis.columns else 0
        else: tot_err = 0
            
        akurasi = 100.0 if tot_data == 0 else max(0, 100 - (tot_err / tot_data * 100))
        akurasi_teks = f"{akurasi:.1f}%" if tot_data > 0 else "Data Historis DB"
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        tanggal_hari_ini = datetime.now().strftime('%d %B %Y')
        st.markdown(f"<p style='color: #94a3b8; font-size: 0.9rem; margin-bottom: 15px;'>📅 <b>Executive Review</b> | Tanggal: {tanggal_hari_ini}</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1: st.metric(label="Total Data Diproses", value=f"{tot_data:,}")
        with col2: st.metric(label="Total Baris Temuan", value=f"{tot_err:,}", delta="Data Perlu Perhatian", delta_color="inverse")
        with col3: st.metric(label="Tingkat Akurasi", value=akurasi_teks, delta="Berdasarkan Validasi")

        st.markdown("""
            <style>
            .stTabs [data-baseweb="tab"] p { font-size: 1.2rem !important; font-weight: 600 !important; color: #ffffff !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 8px; margin-bottom: 10px; }
            </style>
        """, unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["📋 Hasil Review Data SR", "📈 Analisis Tren Temuan"])

        with tab1:
            st.markdown("#### 📋 Rekap Hasil Review Data Penjangkauan SSR")
            df_atas_view = st.session_state.get('df_tabel_atas', pd.DataFrame())
            tanggal_terakhir = st.session_state.get('tanggal_terakhir_review', None)
                    
            if tanggal_terakhir:
                if hasattr(tanggal_terakhir, 'strftime'): tgl_format = tanggal_terakhir.strftime("%d-%m-%Y pukul %H:%M WIB")
                else: tgl_format = str(tanggal_terakhir)
                    
                badge_html = f"""
                <div style="display: inline-flex; align-items: center; gap: 6px; background-color: rgba(28, 131, 225, 0.12); color: #1c83e1; padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(28, 131, 225, 0.25); font-size: 0.88rem; font-weight: 500; margin-bottom: 18px;">
                    ℹ️ Review Data Penjangkauan SR terakhir tanggal : <span style="font-weight: 700;">{tgl_format}</span>
                </div>
                """
                st.markdown(badge_html, unsafe_allow_html=True)
                
            if df_atas_view is not None and not df_atas_view.empty:
                df_render = df_atas_view.copy()
                if df_render.index.name == 'INDIKATOR KESALAHAN DATA' or 'INDIKATOR KESALAHAN DATA' not in df_render.columns:
                    df_render = df_render.reset_index()
                    
                kolom_indikator = 'INDIKATOR KESALAHAN DATA'
                kolom_ssr = [c for c in df_render.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
                for col in kolom_ssr: df_render[col] = pd.to_numeric(df_render[col], errors='coerce').fillna(0).astype(int)
                
                ssr_aktif = [col for col in kolom_ssr if df_render[col].sum() > 0]
                kolom_final = [kolom_indikator] + ssr_aktif + ['Jumlah per indikator', '%']
                df_final = df_render[[c for c in kolom_final if c in df_render.columns]].copy()
                
                df_display = df_final.copy()
                for col in ssr_aktif:
                    if col in df_display.columns:
                        df_display[col] = df_display[col].astype(str).replace({'0': '-', '0.0': '-'})
                
                column_config = {
                    kolom_indikator: st.column_config.TextColumn("Indikator Kesalahan", width=340),
                    "Jumlah per indikator": st.column_config.NumberColumn("Total", width="small", format="%d"),
                    "%": st.column_config.ProgressColumn("%", format="%.1f%%", min_value=0, max_value=100, width="small")
                }
                for col in ssr_aktif: column_config[col] = st.column_config.TextColumn(col, width="small")
            
                st.dataframe(df_display, use_container_width=True, column_config=column_config, hide_index=True)
            else:
                st.info("✨ Belum ada data review dalam database Neon.")

            # =========================================================================
            # TABEL HASIL REVIEW PENJANGKAUAN DETIL PER BARIS
            # =========================================================================
            st.markdown("### 🔍 Hasil Review Penjangkauan")
            st.markdown("<small style='color: #888;'>💡 Kolom Justifikasi hanya dapat diisi jika indikator kesalahan mengandung kata 'konfirmasi'. Kolom lain dikunci.</small>", unsafe_allow_html=True)
                        
            tanggal_terakhir_bawah = st.session_state.get('tanggal_terakhir_bawah', None)
            if tanggal_terakhir_bawah and st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
                if hasattr(tanggal_terakhir_bawah, 'strftime'): tgl_format_bawah = tanggal_terakhir_bawah.strftime("%d-%m-%Y pukul %H:%M WIB")
                else: tgl_format_bawah = str(tanggal_terakhir_bawah)
                                
                badge_bawah_html = f"""
                <div style="display: inline-flex; align-items: center; gap: 6px; background-color: rgba(28, 131, 225, 0.12); color: #1c83e1; padding: 6px 14px; border-radius: 20px; border: 1px solid rgba(28, 131, 225, 0.25); font-size: 0.88rem; font-weight: 500; margin-bottom: 12px;">
                    ℹ️ Hasil Review Data Penjangkauan SR terakhir tanggal : <span style="font-weight: 700;">{tgl_format_bawah}</span>
                </div>
                """
                st.markdown(badge_bawah_html, unsafe_allow_html=True)
            
            pilihan_ssr = "Semua"
            if st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
                df_sumber = st.session_state['df_tabel_bawah']
                kolom_ssr_asli = next((c for c in df_sumber.columns if "lembaga" in str(c).lower() or "ssr" in str(c).lower()), None)
                
                if kolom_ssr_asli:
                    list_ssr_unik = sorted(df_sumber[kolom_ssr_asli].dropna().unique().tolist())
                    col_filter, _ = st.columns([1, 2])
                    with col_filter:
                        pilihan_ssr = st.selectbox("🎯 Pilih Lembaga SSR:", options=["Semua"] + list_ssr_unik, index=0)
                        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)
            
            if st.session_state.get('df_tabel_bawah') is not None and not st.session_state['df_tabel_bawah'].empty:
                kolom_susunan = [
                    "Pilih", "Lembaga SSR", "Tanggal", "ID Klien", "Kode Petugas", "Nama Kota", 
                    "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", "Validasi Hasil Review", "Justifikasi"
                ]
                
                df_bawah_raw = st.session_state['df_tabel_bawah'].copy()
                rename_dict = {}
                for col in df_bawah_raw.columns:
                    c_clean = str(col).strip().lower()
                    if "indikator" in c_clean or "kesalahan" in c_clean or "error" in c_clean: rename_dict[col] = "Indikator Kesalahan Data"
                    elif "validasi" in c_clean or "review" in c_clean: rename_dict[col] = "Validasi Hasil Review"
                    elif "justifikasi" in c_clean: rename_dict[col] = "Justifikasi"
                    elif "lembaga" in c_clean or "ssr" in c_clean: rename_dict[col] = "Lembaga SSR" 
                        
                if rename_dict: df_bawah_raw = df_bawah_raw.rename(columns=rename_dict)
                for col in kolom_susunan:
                    if col not in df_bawah_raw.columns:
                        if col == "Pilih": df_bawah_raw["Pilih"] = False
                        else: df_bawah_raw[col] = "-"
                
                if pilihan_ssr != "Semua": df_bawah_raw = df_bawah_raw[df_bawah_raw["Lembaga SSR"] == pilihan_ssr]
                            
                df_bawah_view = df_bawah_raw[kolom_susunan].copy()
                        
                for idx, row in df_bawah_view.iterrows():
                    ind_text = str(row['Indikator Kesalahan Data']).lower()
                    if "konfirmasi" not in ind_text: df_bawah_view.at[idx, 'Justifikasi'] = ""  
                
                if df_bawah_view.empty:
                    st.info(f"✨ Tidak ada data kesalahan yang perlu divalidasi untuk Lembaga SSR: **{pilihan_ssr}**")
                else:
                    df_hasil_edit = st.data_editor(
                        df_bawah_view,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang jika telah direvisi", default=False),
                            "Lembaga SSR": st.column_config.TextColumn("Lembaga SSR", width=120),
                            "Tanggal": st.column_config.TextColumn("Tanggal", width=110),
                            "ID Klien": st.column_config.TextColumn("ID Klien", width=110),
                            "Kode Petugas": st.column_config.TextColumn("Kode Petugas", width=110),
                            "Nama Kota": st.column_config.TextColumn("Nama Kota", width=120),
                            "NIK": st.column_config.TextColumn("NIK", width=140),
                            "Tipe Sasaran": st.column_config.TextColumn("Tipe Sasaran", width=120),
                            "Indikator Kesalahan Data": st.column_config.TextColumn("Indikator Kesalahan Data", width=320),
                            "Validasi Hasil Review": st.column_config.TextColumn("Validasi Hasil Review", width=220),
                            "Justifikasi": st.column_config.TextColumn("Justifikasi", help="Hanya untuk baris berunsur 'konfirmasi'", width=280),
                        },
                        disabled=[c for c in kolom_susunan if c not in ["Pilih", "Justifikasi"]]
                    )
                         
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_save, _ = st.columns([1, 2])
                    with col_save:
                        if st.button("💾 Simpan Progres Validasi", type="secondary", use_container_width=False):
                            with st.spinner("Menyimpan progres validasi..."):
                                list_log_db = []
                                indeks_baris_terpilih = []
                                peringatan_justifikasi = False
                            
                                for idx, row_edit in df_hasil_edit.iterrows():
                                    ind_text = str(row_edit['Indikator Kesalahan Data'])
                                    text_justifikasi = str(row_edit['Justifikasi']).strip()
                                    is_konfirmasi = "konfirmasi" in ind_text.lower()
                                            
                                    if not is_konfirmasi:
                                        if text_justifikasi not in ["", "None", "-", "nan"]: peringatan_justifikasi = True
                                        text_justifikasi = ""  
                                    else:
                                        if text_justifikasi in ["None", "-", "nan"]: text_justifikasi = ""
                            
                                    if bool(row_edit['Pilih']) or (is_konfirmasi and text_justifikasi != ""):
                                        status_revisi = bool(row_edit['Pilih'])
                                        list_log_db.append((
                                            str(row_edit.get('Lembaga SSR', '-')), str(row_edit.get('Tanggal', '-')),
                                            str(row_edit.get('ID Klien', '-')), ind_text,
                                            status_revisi, text_justifikasi
                                        ))
                                        indeks_baris_terpilih.append(idx)
                                            
                                if len(list_log_db) > 0:
                                    if simpan_log_ke_neon(list_log_db):
                                        df_sekarang = st.session_state['df_tabel_bawah']
                                        df_sisa = df_sekarang.drop(indeks_baris_terpilih).reset_index(drop=True)
                                        st.session_state['df_tabel_bawah'] = df_sisa
                                        
                                        st.success(f"🎉 Berhasil memindahkan {len(list_log_db)} baris ke tabel log_validasi_review!")
                                        if peringatan_justifikasi:
                                            st.warning("⚠️ Catatan: Input Justifikasi pada baris non-konfirmasi otomatis diabaikan oleh sistem.")
                                                    
                                        import time
                                        time.sleep(1.5)
                                        st.rerun()
                                    else:
                                        st.error("❌ Gagal menyimpan log ke Neon Database. Periksa kembali koneksi Anda.")
                                else:
                                    st.info("ℹ️ Tidak ada data yang diproses. Silakan centang 'Pilih' atau isi 'Justifikasi' sebelum menyimpan.")

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
            # 1. VISUALISASI CLEVELAND DOT PLOT
            # =========================================================================
            if st.session_state.get('proses_selesai', False) and st.session_state.get('df_tabel_bawah') is not None:
                df_bawah = st.session_state['df_tabel_bawah'].copy()
                
                if not df_bawah.empty:
                    st.markdown("#### 📊 Sebaran Titik Kesalahan Berdasarkan Kelompok Sasaran")
                    df_bawah['Tipe Sasaran'] = df_bawah['Tipe Sasaran'].astype(str).str.replace('.0', '', regex=False).str.strip()
                    map_sasaran = {'1304': '1304 (MSM)', '1301': '1301 (TG)', '1401': '1401 (PWID)'}
                    df_bawah['Kelompok Sasaran'] = df_bawah['Tipe Sasaran'].map(map_sasaran).fillna(df_bawah['Tipe Sasaran'])
                    df_bawah = df_bawah.drop_duplicates(subset=["Lembaga SSR", "Tanggal", "ID Klien", "INDIKATOR KESALAHAN DATA"])
                    
                    is_konfirmasi = df_bawah['INDIKATOR KESALAHAN DATA'].str.contains(r'\(konfirmasi\)', case=False, na=False)
                    df_mutlak_all = df_bawah[~is_konfirmasi]
                    df_konf_all = df_bawah[is_konfirmasi]
                    
                    st.markdown("##### 🟥 A. Top 5 Temuan Mutlak (Perlu Koreksi / Non-Konfirmasi)")
                    if not df_mutlak_all.empty:
                        top_5_mutlak_idx = df_mutlak_all['INDIKATOR KESALAHAN DATA'].value_counts().head(5).index
                        df_top_5_mutlak = df_mutlak_all[df_mutlak_all['INDIKATOR KESALAHAN DATA'].isin(top_5_mutlak_idx)]
                        df_dot_mutlak = df_top_5_mutlak.groupby(['INDIKATOR KESALAHAN DATA', 'Kelompok Sasaran']).size().reset_index(name='Jumlah Kasus')
                        
                        fig_mutlak = px.scatter(
                            df_dot_mutlak, x='Jumlah Kasus', y='INDIKATOR KESALAHAN DATA', color='Kelompok Sasaran',
                            template="plotly_dark", color_discrete_map={'1304 (MSM)': '#EF4444', '1301 (TG)': '#3B82F6', '1401 (PWID)': '#10B981'}
                        )
                        fig_mutlak.update_traces(
                            marker=dict(size=14, opacity=0.85, line=dict(width=1, color='#FFFFFF')),
                            hovertemplate="<b>%{hovertext}</b><br>Jumlah: %{x} Kasus<extra></extra>", hovertext=df_dot_mutlak['Kelompok Sasaran']
                        )
                        fig_mutlak.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font_color='#E0E0E0', xaxis_title="Jumlah Kasus Kesalahan", yaxis_title="", legend_title_text="Sasaran", 
                            height=280, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            yaxis={'categoryorder':'total ascending'}, hoverlabel=dict(bgcolor="#0f172a", font_size=12, font_color="#f8fafc") 
                        )
                        fig_mutlak.update_xaxes(showgrid=True, gridcolor='#333333')
                        fig_mutlak.update_yaxes(showgrid=True, gridcolor='#222222')
                        st.plotly_chart(fig_mutlak, use_container_width=True, theme=None)
                    else: st.info("✨ Bersih! Tidak ada temuan mutlak terdeteksi.")
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                
                    st.markdown("##### 🟨 B. Top 5 Temuan Butuh Klarifikasi (Ada Unsur Justifikasi / Konfirmasi)")
                    if not df_konf_all.empty:
                        top_5_konf_idx = df_konf_all['INDIKATOR KESALAHAN DATA'].value_counts().head(5).index
                        df_top_5_konf = df_konf_all[df_konf_all['INDIKATOR KESALAHAN DATA'].isin(top_5_konf_idx)]
                        df_dot_konf = df_top_5_konf.groupby(['INDIKATOR KESALAHAN DATA', 'Kelompok Sasaran']).size().reset_index(name='Jumlah Kasus')
                        
                        fig_konf = px.scatter(
                            df_dot_konf, x='Jumlah Kasus', y='INDIKATOR KESALAHAN DATA', color='Kelompok Sasaran',
                            template="plotly_dark", color_discrete_map={'1304 (MSM)': '#EF4444', '1301 (TG)': '#3B82F6', '1401 (PWID)': '#10B981'}
                        )
                        fig_konf.update_traces(
                            marker=dict(size=14, opacity=0.85, line=dict(width=1, color='#FFFFFF')),
                            hovertemplate="<b>%{hovertext}</b><br>Jumlah: %{x} Kasus<extra></extra>", hovertext=df_dot_konf['Kelompok Sasaran']
                        )
                        fig_konf.update_layout(
                            margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            font_color='#E0E0E0', xaxis_title="Jumlah Kasus Kesalahan", yaxis_title="", legend_title_text="Sasaran", 
                            height=280, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            yaxis={'categoryorder':'total ascending'}, hoverlabel=dict(bgcolor="#0f172a", font_size=12, font_color="#f8fafc")
                        )
                        fig_konf.update_xaxes(showgrid=True, gridcolor='#333333')
                        fig_konf.update_yaxes(showgrid=True, gridcolor='#222222')
                        st.plotly_chart(fig_konf, use_container_width=True, theme=None)
                    else: st.info("✨ Aman! Tidak ada data yang membutuhkan konfirmasi tambahan.")
                else: st.info("✨ Tidak ada rincian data kesalahan untuk dianalisa berdasarkan target.")
                    
            st.markdown("---")
            st.markdown("<br>", unsafe_allow_html=True)
            
            # =========================================================================
            # 2. ANALISIS TREN SEMESTER (AREA CHART)
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
                    
                if not df_pivot.empty: st.area_chart(df_pivot)
                else: st.info("Data belum tersedia untuk filter ini.")
            else: st.info("Belum ada data rekap tren di tabel rekap_tren_bulanan.")
        
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
                    sukses = tambah_keyword_medsos_db(keyword_clean)
                    if sukses:
                        st.session_state['medsoc_keywords'].append(keyword_clean)
                        st.session_state['medsoc_keywords'].sort()
                        st.success(f"Berhasil menambahkan '{keyword_clean}' ke database!")
                        import time
                        time.sleep(1)
                        st.rerun()
                    else: st.warning(f"Keyword '{keyword_clean}' sudah ada di dalam database.")
                else: st.warning("Kolom tidak boleh kosong!")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_kanan:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        list_medsos = st.session_state.get('medsoc_keywords', [])
        st.subheader(f"📋 Daftar Keyword Aktif ({len(list_medsos)})")
        
        if list_medsos:
            html_badges = ""
            for m in list_medsos:
                html_badges += f"""
                <span style="background-color: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 6px 12px; border-radius: 20px; font-family: inherit; font-size: 0.85rem; font-weight: 500; white-space: nowrap; display: flex; align-items: center; gap: 5px;">
                    🔹 {m}
                </span>
                """
            st.markdown(f"""
                <div style="display: flex; flex-wrap: wrap; gap: 10px; padding: 15px; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; background-color: rgba(0,0,0,0.2);">
                    {html_badges}
                </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Belum ada data medsos di database.")
            
        st.markdown('</div>', unsafe_allow_html=True)
