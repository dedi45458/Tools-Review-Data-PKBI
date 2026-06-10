import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Penanganan pencegahan hard-crash jika modul supabase belum terinstal di environment
try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ModuleNotFoundError:
    HAS_SUPABASE = False

# ==========================================================
# 0. KONFIGURASI UTAMA & INISIALISASI SESSION STATE
# ==========================================================
st.set_page_config(page_title="Data Quality Review - PKBI Jabar", page_icon="📊", layout="wide")

if 'total_entri' not in st.session_state:
    st.session_state['total_entri'] = 0
if 'proses_selesai' not in st.session_state:
    st.session_state['proses_selesai'] = False
if 'data_unduhan' not in st.session_state:
    st.session_state['data_unduhan'] = None
if 'df_tabel_bawah' not in st.session_state:
    st.session_state['df_tabel_bawah'] = None
if 'df_tabel_atas' not in st.session_state:
    st.session_state['df_tabel_atas'] = None

# Konfigurasi Supabase
SUPABASE_URL = "https://fughiktqrtrtxrwoerud.supabase.co" 
SUPABASE_KEY = "sb_publishable_0RXs2YvzFtj2b8K2zeCFvQ_XAMQW1aM"

@st.cache_resource
def init_supabase():
    if not HAS_SUPABASE:
        st.error("⚠️ Library 'supabase' belum terinstal. Tambahkan 'supabase' ke file requirements.txt.")
        return None
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        return None

supabase = init_supabase()

# Modern 2026 Custom UI CSS & Mobile Responsiveness
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stSidebarNav"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-title { 
        font-size: 2.4rem; 
        font-weight: 800; 
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.3rem; 
    }
    .sub-title { 
        font-size: 1.1rem; 
        color: #6B7280; 
        margin-bottom: 2rem; 
        font-weight: 400;
    }
    h4 { 
        font-weight: 700; 
        color: #111827; 
        margin-top: 1.8rem;
        font-size: 1.3rem;
    }
    .stButton>button { 
        border-radius: 10px; 
        font-weight: 600; 
        padding: 0.6rem 1.5rem;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
    }
    
    /* Mobile Responsive Adjustments */
    @media (max-width: 768px) {
        .main-title { font-size: 1.7rem !important; }
        .sub-title { font-size: 0.95rem !important; }
        .stMetric { padding: 0.5rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 Tools Review Data Massal</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem otomatisasi penelaahan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat berbasis matriks validasi terbaru.</div>', unsafe_allow_html=True)

# Helper function global
def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom): return False
    clean_str = str(teks_kolom).replace("'", "").replace(" ", "")
    list_kode = clean_str.split(",")
    return str(kode_target) in list_kode

# ==========================================================
# 1. REGISTRI INDIKATOR & LOGIKA VALIDASI DINAAMIS (FLEKSIBEL)
# ==========================================================
# Cukup tambahkan item baru ke list ini jika di kemudian hari ada indikator baru.
# Parameter 'c' adalah dictionary context yang berisi semua variabel baris data yang sedang aktif.
ATURAN_VALIDASI = [
    {
        "nama": "Tahun dalam tanggal penjangkauan lebih besar/kecil dari tahun sekarang",
        "periksa": lambda c: pd.notna(c['tgl_p']) and c['tgl_p'].year != c['tahun_sekarang']
    },
    {
        "nama": "Kode Petugas Kosong",
        "periksa": lambda c: pd.isna(c['row'].get('Kode Petugas')) or str(c['row'].get('Kode Petugas')).strip() == ''
    },
    {
        "nama": "Tanggal lebih besar dari tanggal hari ini",
        "periksa": lambda c: pd.notna(c['tgl_p']) and c['tgl_p'] > c['hari_ini']
    },
    {
        "nama": "IDKD kurang/lebih dari 10 digit karakter",
        "periksa": lambda c: c['id_clean'] != '' and (len(c['id_clean']) != 10 or not c['id_clean'].isalnum())
    },
    {
        "nama": "Digit nama kurang/lebih dari 4 digit karakter",
        "periksa": lambda c: c['id_clean'] != '' and len(c['id_clean']) >= 4 and not c['id_clean'][:4].isalpha()
    },
    {
        "nama": "Digit tanggal lahir lebih/kurang dari 6 digit angka",
        "periksa": lambda c: c['id_clean'] != '' and len(c['id_clean']) == 10 and not c['id_clean'][4:].isdigit()
    },
    {
        "nama": "Ada tanda titik (.) pada penulisan IDKD",
        "periksa": lambda c: '.' in str(c['row'].get('ID Klien', ''))
    },
    {
        "nama": "Ada spasi pada penulisan IDKD",
        "periksa": lambda c: ' ' in str(c['row'].get('ID Klien', ''))
    },
    {
        "nama": "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)",
        "periksa": lambda c: c['is_file_rujukan'] and c['df_ref'] is not None and c['v_ssr'] and f"{c['v_ssr']}_{c['id_clean']}" in c['ref_ssr_id_to_nik'] and c['ref_ssr_id_to_nik'][f"{c['v_ssr']}_{c['id_clean']}"] != c['nik_clean']
    },
    {
        "nama": "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)",
        "periksa": lambda c: c['is_file_rujukan'] and c['df_ref'] is not None and c['v_ssr'] and c['nik_clean'] != '' and f"{c['nik_clean']}_{c['v_ssr']}" in c['ref_nik_ssr_to_id'] and c['ref_nik_ssr_to_id'][f"{c['nik_clean']}_{c['v_ssr']}"] != c['id_clean']
    },
    {
        "nama": "Tahun Lahir KD terlalu muda (2014 -sekarang)",
        "periksa": lambda c: pd.notna(c['umur']) and str(c['umur']).strip() != '' and 2014 <= (c['tahun_sekarang'] - float(c['umur'])) <= c['tahun_sekarang'] if False else False  # diproteksi try-except di engine
    },
    {
        "nama": "Usia KD dibawah 16 tahun (konfirmasi)",
        "periksa": lambda c: pd.notna(c['umur']) and str(c['umur']).strip() != '' and float(c['umur']) < 17
    },
    {
        "nama": "Usia KD diatas 70 tahun (konfirmasi)",
        "periksa": lambda c: pd.notna(c['umur']) and str(c['umur']).strip() != '' and float(c['umur']) > 70
    },
    {
        "nama": "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)",
        "periksa": lambda c: c['id_clean'] != '' and len(c['id_clean']) == 10 and c['nik_clean'] != '' and len(c['nik_clean']) == 16 and c['id_clean'][4:6] != (str(c['row'].get('NIK', '')) if str(c['row'].get('NIK', '')).startswith("'") else "'" + c['nik_clean'])[11:13]
    },
    {
        "nama": "NIK kurang/lebih dari 16 digit (konfirmasi)",
        "periksa": lambda c: c['nik_clean'] != '' and len(c['nik_clean']) != 16
    },
    {
        "nama": "Kesalahan dalam penulisan NIK (00) (konfirmasi)",
        "periksa": lambda c: c['nik_clean'] != '' and c['nik_clean'].endswith('00')
    },
    {
        "nama": "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)",
        "periksa": lambda c: len(c['nik_clean']) == 16 and c['jk'] == '1' and int(c['nik_clean'][6:8]) > 31 if c['nik_clean'].isdigit() and len(c['nik_clean'])>=8 else False
    },
    {
        "nama": "LSL/Waria tapi jenis kelamin perempuan",
        "periksa": lambda c: c['v_tipe_sasaran'] in ['1304', '1301'] and c['jk'] == '2'
    },
    {
        "nama": "Jenis kontak dengan Jenis Kegiatan tidak sesuai",
        "periksa": lambda c: (c['jns_kontak'] == '1' and c['jns_kegiatan'] not in ['1', '5']) or (c['jns_kontak'] == '2' and c['jns_kegiatan'] not in ['2', '3', '4', '6', '7']) or (c['jns_kontak'] == '3' and c['jns_kegiatan'] != '8')
    },
    {
        "nama": "Jenis kontak Individual/kelompok tapi kolom Virtual dan Tatap Muka (VC1) tidak diisi",
        "periksa": lambda c: c['jns_kontak'] in ['1', '2'] and (c['vc1'] == '' or c['vc1'] == 'nan')
    },
    {
        "nama": "Penjangkauan tatap muka tapi lokasi outreach diindikasi ada nama medsos",
        "periksa": lambda c: c['jns_kontak'] in ['1', '2'] and c['any_medsoc_in_lokasi']
    },
    {
        "nama": "Lokasi outreach diisi IDKD",
        "periksa": lambda c: c['lokasi'] != '' and c['lokasi'] != 'nan' and len(c['lokasi']) == 10 and c['lokasi'][:4].isalpha() and c['lokasi'][4:].isdigit()
    },
    {
        "nama": "Lokasi outreach diindikasi kurang spesifik atau kurang detil (digit huruf <17 digit) (konfirmasi)",
        "periksa": lambda c: c['lokasi'] != '' and c['lokasi'] != 'nan' and len(c['lokasi']) < 17 and not c['is_vo']
    },
    {
        "nama": "Lokasi outreach indikasi diisi nomer HP",
        "periksa": lambda c: c['lokasi'] != '' and c['lokasi'] != 'nan' and re.search(r'(08\d{8,11})|(\+62\d{8,11})', c['lokasi'].replace('-', '').replace(' ', ''))
    },
    {
        "nama": "Bukan PWID mendapatkan info 8 atau 9 (LASS, PTRM)",
        "periksa": lambda c: not c['is_pwid'] and (cek_kode(c['info_diberikan'], '8') or cek_kode(c['info_diberikan'], '9') or cek_kode(c['jns_kegiatan'], '8') or cek_kode(c['jns_kegiatan'], '9'))
    },
    {
        "nama": "LSL/TG/PWID menerima informasi PMTC (konfirmasi)",
        "periksa": lambda c: c['v_tipe_sasaran'] in ['1304', '1301', '1401'] and (cek_kode(c['info_diberikan'], '6') or cek_kode(c['jns_kegiatan'], '6'))
    },
    {
        "nama": "Konfirmasi jumlah KIE yang diberikan adalah wajar",
        "periksa": lambda c: c['log_kie'] > 10
    },
    {
        "nama": "Konfirmasi jumlah kondom yang diberikan adalah wajar",
        "periksa": lambda c: c['log_kon'] > 144
    },
    {
        "nama": "Konfirmasi jumlah pelicin yang diberikan adalah wajar",
        "periksa": lambda c: c['log_pel'] > 50
    },
    {
        "nama": "Konfirmasi jumlah jarum yang diberikan adalah wajar",
        "periksa": lambda c: c['log_jar'] > 100
    },
    {
        "nama": "Konfirmasi jumlah alkohol SWAB yang diberikan adalah wajar",
        "periksa": lambda c: c['log_swab'] > 100
    },
    {
        "nama": "VO tapi kolom Virtual dan Tatap Muka (VC1) diisi angka 1",
        "periksa": lambda c: c['is_vo'] and c['vc1'] == '1'
    },
    {
        "nama": "VO tapi lokasi outreach bukan nama medsos/kurang tepat mencatat nama aplikasi medsos",
        "periksa": lambda c: c['is_vo'] and c['lokasi'] != '' and not c['any_medsoc_in_lokasi']
    },
    {
        "nama": "VO tapi menyerahkan jarum",
        "periksa": lambda c: c['is_vo'] and c['log_jar'] > 0
    },
    {
        "nama": "VO menerima logistik selain KIE",
        "periksa": lambda c: c['is_vo'] and (c['log_kon'] > 0 or c['log_pel'] > 0 or c['log_swab'] > 0)
    },
    {
        "nama": "VO tapi nama akun /No. Hp tidak diisi",
        "periksa": lambda c: c['is_vo'] and (c['no_hp'] == '' or c['no_hp'] == 'nan')
    },
    {
        "nama": "Tidak ada informasi satupun yang diberikan / tidak diisi",
        "periksa": lambda c: c['info_diberikan'] == '' or c['info_diberikan'] == 'nan'
    },
    {
        "nama": "KD dikontak lebih dari 1x tapi tidak mendapat informasi HIV",
        "periksa": lambda c: c['id_clean'] != '' and c['id_counts'].get(c['id_clean'], 0) > 1 and not c['pernah_dapat_info_hiv']
    },
    {
        "nama": "KD telah menerima layanan CBS tapi tidak ada informasi CBS",
        "periksa": lambda c: cek_kode(c['jns_kegiatan'], '13') and not cek_kode(c['info_diberikan'], '13')
    },
    {
        "nama": "KD ada rujukan PrEp di penjangkauan tapi tidak ada informasi PrEp",
        "periksa": lambda c: (cek_kode(c['rujukan'], '5') or cek_kode(c['jns_kegiatan'], '10')) and not (cek_kode(c['info_diberikan'], '10') or cek_kode(c['jns_kegiatan'], '10'))
    },
    {
        "nama": "KD telah menerima layanan PrEp tapi tidak ada rujukan PrEp di penjangkauan",
        "periksa": lambda c: cek_kode(c['jns_kegiatan'], '10') and not cek_kode(c['rujukan'], '5')
    },
    {
        "nama": "Logistik kosong (Konfirmasi)",
        "periksa": lambda c: c['log_kie'] == 0 and c['log_kon'] == 0 and c['log_pel'] == 0 and c['log_jar'] == 0 and c['log_swab'] == 0
    },
    {
        "nama": "Tipe klien PWID tapi tidak menerima jarum (konfirmasi)",
        "periksa": lambda c: c['is_pwid'] and c['log_jar'] == 0 and not c['is_vo']
    },
    {
        "nama": "Tipe klien PWID tapi tidak menerima alkohol SWAB (konfirmasi)",
        "periksa": lambda c: c['is_pwid'] and c['log_swab'] == 0 and not c['is_vo']
    },
    {
        "nama": "Popkun selain PWID menerima jarum suntik",
        "periksa": lambda c: not c['is_pwid'] and c['log_jar'] > 0
    },
    {
        "nama": "Popkun selain PWID menerima alkohol swab",
        "periksa": lambda c: not c['is_pwid'] and c['log_swab'] > 0
    },
    {
        "nama": "Popkun selain PWID menyerahkan jarum",
        "periksa": lambda c: not c['is_pwid'] and c['jarum_kembali'] > 0
    },
    {
        "nama": "Tidak ada rujukan yang diberikan satupun / tidak diisi",
        "periksa": lambda c: c['rujukan'] == '' or c['rujukan'] == 'nan'
    },
    {
        "nama": "KD dikontak lebih dari 1x tetapi tidak ada Rujukan Tes HIV",
        "periksa": lambda c: c['id_clean'] != '' and c['id_counts'].get(c['id_clean'], 0) > 1 and not c['pernah_dapat_rujuk_tes']
    },
    {
        "nama": "Bukan penasun rujukan 3,4",
        "periksa": lambda c: not c['is_pwid'] and (cek_kode(c['rujukan'], '3') or cek_kode(c['rujukan'], '4'))
    }
]

# Mendapatkan daftar nama unik untuk generator matriks tabel atas
DAFTAR_INDIKATOR = [item["nama"] for item in ATURAN_VALIDASI]

def hitung_dan_ambil_log_db():
    dict_revisi = {}
    dict_justifikasi = {}
    if supabase:
        try:
            res = supabase.table("log_validasi_review").select("ssr, tanggal, id_klien, indikator_kesalahan, is_revisi, justifikasi").execute()
            for r in res.data:
                key = f"{str(r['ssr']).upper()}_{str(r['tanggal'])}_{str(r['id_klien'])}_{str(r['indikator_kesalahan'])}"
                dict_revisi[key] = r['is_revisi']
                if r['justifikasi']:
                    dict_justifikasi[key] = r['justifikasi']
        except Exception:
            pass
    return dict_revisi, dict_justifikasi

# ==========================================================
# 2. PANEL SIDEBAR UNTUK UNGGAH BERKAS
# ==========================================================
with st.sidebar:
    st.markdown("### 📁 Menu Unggah Berkas")
    file_referensi = st.file_uploader("1️⃣ Data HIV+ Semester / Tahun Lalu (.xlsx)", type=["xlsx"])
    st.markdown("---")
    files_review = st.file_uploader("2️⃣ Raw Data Penjangkauan / Rujukan (.xlsx)", type=["xlsx"], accept_multiple_files=True)

# ==========================================================
# 3. ENGINE VALIDASI UTAMA
# ==========================================================
def jalankan_review_data(df_asli, df_ref=None, nama_file=""):
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    is_file_rujukan = any('RUJUKAN' in str(c).upper() for c in df.columns) or any('FASYANKES' in str(c).upper() for c in df.columns)
    
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())
    medsoc_keywords = ['whatsapp', 'wa', 'badoo', 'hornet', 'michat', 'blued', 'bumble', 'walla', 'sms', 'grindr', 'growlr', 'instagram', 'ig', 'tantan', 'telegram', 'telepon', 'tinder', 'twitter', 'line', 'facebook', 'fb', 'messenger', 'romeo', 'tiktok', 'tagged', 'litmatch', 'scruff', 'wechat', 'threads']

    dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()

    ref_ssr_id_to_nik = {}
    ref_nik_ssr_to_id = {}
    if is_file_rujukan and df_ref is not None and not df_ref.empty:
        df_ref_cp = df_ref.copy()
        df_ref_cp.columns = [str(c).strip() for c in df_ref_cp.columns]
        col_id_ref = [c for c in df_ref_cp.columns if 'ID' in c or 'Klien' in c]
        col_nik_ref = [c for c in df_ref_cp.columns if 'NIK' in c]
        col_ssr_ref = [c for c in df_ref_cp.columns if 'SSR' in c or 'Lembaga' in c]
        
        if col_id_ref and col_nik_ref and col_ssr_ref:
            for _, r in df_ref_cp.iterrows():
                ssr_r = str(r[col_ssr_ref[0]]).strip().upper()
                id_r = str(r[col_id_ref[0]]).replace("'", "").strip()
                nik_r = str(r[col_nik_ref[0]]).replace("'", "").replace('.0', '').strip()
                if id_r and id_r != 'nan' and ssr_r and ssr_r != 'nan':
                    ref_ssr_id_to_nik[f"{ssr_r}_{id_r}"] = nik_r
                if nik_r and nik_r != 'nan' and nik_r != '' and ssr_r and ssr_r != 'nan':
                    ref_nik_ssr_to_id[f"{nik_r}_{ssr_r}"] = id_r

    id_counts = df.iloc[start_row_idx:]['ID Klien'].astype(str).str.strip().value_counts().to_dict()

    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        no_excel_row = idx + 2
        
        v_ssr = str(row.get('Lembaga SSR', '')).strip().upper() if pd.notna(row.get('Lembaga SSR')) else ''
        v_petugas = str(row.get('Kode Petugas', '')).replace("'", "").strip() if pd.notna(row.get('Kode Petugas')) else ''
        v_kota = str(row.get('Nama Kota', '')).strip() if pd.notna(row.get('Nama Kota')) else ''
        v_tanggal = str(row.get('Tanggal', '')).split(' ')[0] if pd.notna(row.get('Tanggal')) else ''
        
        id_raw = str(row.get('ID Klien', '')).strip()
        id_clean = id_raw.replace("'", "").strip()
        nik_raw = str(row.get('NIK', '')).strip()
        nik_clean = nik_raw.replace("'", "").replace('.0', '').strip()

        v_tipe_sasaran = str(row.get('Tipe Sasaran', row.get('Tipe Klien', ''))).replace('.0', '').strip()
        umur = row.get('Umur', None)
        jk = str(row.get('Jenis Kelamin', '')).replace('.0', '').strip()
        jns_kontak = str(row.get('Jenis Kontak', '')).replace('.0', '').strip()
        jns_kegiatan = str(row.get('Jenis Kegiatan', '')).strip()
        lokasi = str(row.get('Lokasi Outreach / Jenis Sosial Media', '')).strip()
        info_diberikan = str(row.get('Informasi Yang diberikan', '')).strip()
        rujukan = str(row.get('Rujukan', '')).strip()
        no_hp = str(row.get('No. HP / Nama Akun', '')).strip()
        vc1 = str(row.get('Virtual & Tatap Muka', '')).replace('.0', '').strip()

        try:
            log_kie = float(row.iloc[17]) if pd.notna(row.iloc[17]) and str(row.iloc[17]).strip() not in ['', 'NaN'] else 0
            log_kon = float(row.iloc[18]) if pd.notna(row.iloc[18]) and str(row.iloc[18]).strip() not in ['', 'NaN'] else 0
            log_pel = float(row.iloc[19]) if pd.notna(row.iloc[19]) and str(row.iloc[19]).strip() not in ['', 'NaN'] else 0
            log_jar = float(row.iloc[20]) if pd.notna(row.iloc[20]) and str(row.iloc[20]).strip() not in ['', 'NaN'] else 0
            log_swab = float(row.iloc[21]) if pd.notna(row.iloc[21]) and str(row.iloc[21]).strip() not in ['', 'NaN'] else 0
            jarum_kembali = float(row.get('Jumlah Jarum Suntik Kembali', 0)) if pd.notna(row.get('Jumlah Jarum Suntik Kembali', 0)) else 0
        except:
            log_kie = log_kon = log_pel = log_jar = log_swab = jarum_kembali = 0

        tgl_raw = row.get('Tanggal', None)
        tgl_p = pd.to_datetime(tgl_raw, errors='coerce') if pd.notna(tgl_raw) else None

        pernah_dapat_info_hiv = False
        pernah_dapat_rujuk_tes = False
        if id_clean and id_counts.get(id_clean, 0) > 1:
            df_klien_ini = df[df['ID Klien'].astype(str).str.replace("'", "").str.strip() == id_clean]
            pernah_dapat_info_hiv = any(cek_kode(inf, '1') for inf in df_klien_ini['Informasi Yang diberikan'].values) or any(cek_kode(keg, '1') for keg in df_klien_ini['Jenis Kegiatan'].values)
            pernah_dapat_rujuk_tes = any(cek_kode(ruj, '2') for ruj in df_klien_ini['Rujukan'].values)

        any_medsoc_in_lokasi = any(kw in lokasi.lower() for kw in medsoc_keywords)
        is_vo = (jns_kontak == '3')
        is_pwid = (v_tipe_sasaran == '1401')

        # Membangun Paket Context Data untuk dikirim ke Engine Validasi Dinamis
        context_data = {
            'row': row, 'id_clean': id_clean, 'nik_clean': nik_clean, 'v_ssr': v_ssr, 'v_tanggal': v_tanggal,
            'v_petugas': v_petugas, 'v_kota': v_kota, 'v_tipe_sasaran': v_tipe_sasaran, 'umur': umur, 'jk': jk,
            'jns_kontak': jns_kontak, 'jns_kegiatan': jns_kegiatan, 'lokasi': lokasi, 'info_diberikan': info_diberikan,
            'rujukan': rujukan, 'no_hp': no_hp, 'vc1': vc1, 'log_kie': log_kie, 'log_kon': log_kon, 'log_pel': log_pel,
            'log_jar': log_jar, 'log_swab': log_swab, 'jarum_kembali': jarum_kembali, 'tgl_p': tgl_p, 'hari_ini': hari_ini,
            'tahun_sekarang': tahun_sekarang, 'any_medsoc_in_lokasi': any_medsoc_in_lokasi, 'is_vo': is_vo, 'is_pwid': is_pwid,
            'id_counts': id_counts, 'pernah_dapat_info_hiv': pernah_dapat_info_hiv, 'pernah_dapat_rujuk_tes': pernah_dapat_rujuk_tes,
            'is_file_rujukan': is_file_rujukan, 'df_ref': df_ref, 'ref_ssr_id_to_nik': ref_ssr_id_to_nik, 'ref_nik_ssr_to_id': ref_nik_ssr_to_id
        }

        # Perulangan Otomatis mengecek seluruh rule di list ATURAN_VALIDASI
        for rule in ATURAN_VALIDASI:
            nama_ind = rule["nama"]
            
            # Proteksi khusus perhitungan umur bertipe teks/kosong agar tidak crash
            if "terlalu muda" in nama_ind.lower() and pd.notna(umur) and str(umur).strip() != '':
                try:
                    tahun_lahir = tahun_sekarang - float(umur)
                    if not (2014 <= tahun_lahir <= tahun_sekarang): continue
                except: continue
            
            try:
                if rule["periksa"](context_data):
                    key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{nama_ind}"
                    is_butuh_konfirmasi = "konfirmasi" in nama_ind.lower()
                    
                    if is_butuh_konfirmasi and key_db in dict_justifikasi and not dict_revisi.get(key_db, False):
                        continue
                        
                    status_validasi = "-"
                    checked_state = False
                    justif_val = dict_justifikasi.get(key_db, "") if is_butuh_konfirmasi else ""
                    
                    if key_db in dict_revisi:
                        status_validasi = "kesalahan pada ID yang berulang (belum dilakukan revisi)"
                        checked_state = True

                    list_kesalahan.append({
                        "Pilih": checked_state,
                        "Lembaga SSR": v_ssr,
                        "Tanggal": v_tanggal, 
                        "ID Klien": id_clean, 
                        "INDIKATOR KESALAHAN DATA": nama_ind,
                        "validasi hasil review": status_validasi,
                        "Justifikasi": justif_val,
                        "Kode Petugas": v_petugas, 
                        "Nama Kota": v_kota, 
                        "NIK": nik_clean, 
                        "Tipe Sasaran": v_tipe_sasaran
                    })
            except:
                pass

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. TOMBOL EKSEKUSI UTAMA
# ==========================================================
col_btn, _ = st.columns([1, 2])
with col_btn:
    tombol_proses = st.button("🚀 Jalankan Penelaahan Laporan", type="primary", use_container_width=True)

if tombol_proses:
    if not files_review:
        st.error("⚠️ Silakan unggah berkas Raw Data terlebih dahulu di sidebar!")
    else:
        with st.spinner("Sedang memproses validasi data, mohon tunggu..."):
            df_ref = None
            if file_referensi:
                try: df_ref = pd.read_excel(file_referensi)
                except Exception: pass
            
            all_errs = []
            total_records = 0
            detected_ssrs = set()

            for f in files_review:
                try:
                    df_target = pd.read_excel(f)
                    total_records += len(df_target)
                    df_res = jalankan_review_data(df_target, df_ref, nama_file=f.name)
                    if not df_res.empty:
                        all_errs.append(df_res)
                        detected_ssrs.update(df_res['Lembaga SSR'].unique())
                except Exception:
                    pass

            st.session_state['total_entri'] = total_records

            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                active_ssrs = sorted(list(detected_ssrs))
                
                # Menghitung Total Global Kesalahan untuk penyebut persentase (%)
                total_seluruh_kesalahan = len(df_bawah)
                
                matrix_rows = []
                for ind in DAFTAR_INDIKATOR:
                    r_dict = {"INDIKATOR KESALAHAN DATA": ind}
                    total_ind_err = 0
                    for ssr in active_ssrs:
                        c = len(df_bawah[(df_bawah['INDIKATOR KESALAHAN DATA'] == ind) & (df_bawah['Lembaga SSR'] == ssr)])
                        r_dict[ssr] = c
                        total_ind_err += c
                    
                    r_dict["Jumlah per indikator"] = total_ind_err
                    
                    # Logika Tambahan Perhitungan Persentase (%)
                    if total_seluruh_kesalahan > 0:
                        r_dict["%"] = (total_ind_err / total_seluruh_kesalahan) * 100
                    else:
                        r_dict["%"] = 0.0
                        
                    matrix_rows.append(r_dict)
                
                df_atas = pd.DataFrame(matrix_rows)
                df_atas = df_atas[df_atas['Jumlah per indikator'] > 0]
                df_atas.set_index("INDIKATOR KESALAHAN DATA", inplace=True)
                
                st.session_state['df_tabel_atas'] = df_atas
                st.session_state['df_tabel_bawah'] = df_bawah
            else:
                st.session_state['df_tabel_atas'] = pd.DataFrame()
                st.session_state['df_tabel_bawah'] = pd.DataFrame()

            st.session_state['proses_selesai'] = True

# ==========================================================
# 5. BLOCK OUTPUT INTERFACE UTAMA STREAMLIT
# ==========================================================
if st.session_state['proses_selesai']:
    st.markdown("### 📊 Dashboard Hasil Review Analisis")
    
    # Grid Informasi Atas Modern Card style
    with st.container(border=True):
        m1, m2 = st.columns([1, 1])
        m1.metric("Total Entri Data Diperiksa", f"{st.session_state['total_entri']} Baris")
        tot_err = len(st.session_state['df_tabel_bawah']) if st.session_state['df_tabel_bawah'] is not None else 0
        m2.metric("Total Temuan Log Kesalahan", f"{tot_err} Kasus")

    # ------------------------------------------------------
    # TABEL ATAS: REKAP HASIL REVIEW DATA PER SSR
    # ------------------------------------------------------
    st.markdown("#### Rekap Hasil Review Data per SSR")
    df_atas_view = st.session_state['df_tabel_atas'].copy() if st.session_state['df_tabel_atas'] is not None else pd.DataFrame()
    
    if not df_atas_view.empty:
        # Formatter Pandas Styler dinamis untuk memformat kolom persentase & angka nol menjadi strip
        format_rules = {col: (lambda x: "-" if x == 0 else f"{x}") for col in df_atas_view.columns if col != '%'}
        format_rules['%'] = lambda x: f"{x:.1f}%"
        
        styled_atas = df_atas_view.style.format(format_rules).set_properties(**{'text-align': 'center'})
        
        st.dataframe(
            styled_atas,
            use_container_width=True,
            column_config={
                col: st.column_config.NumberColumn(col, width="medium") for col in df_atas_view.columns if col != '%'
            }
        )
    else:
        st.info("✨ Tidak ada rekapan karena file data bersih dari kesalahan.")

    st.markdown("---")

    # ------------------------------------------------------
    # TABEL BAWAH: HASIL REVIEW PENJANGKAUAN (RE-ORDERED & RE-CONFIGURED)
    # ------------------------------------------------------
    st.markdown("#### Hasil Review Penjangkauan")
    
    if st.session_state['df_tabel_bawah'] is not None and not st.session_state['df_tabel_bawah'].empty:
        # 1. Menghilangkan "Baris Excel"
        # 2. Posisi "validasi hasil review" & "Justifikasi" digeser tepat setelah "Tipe Sasaran"
        kolom_susunan = [
            "Pilih", "Lembaga SSR", "Tanggal", "ID Klien", "INDIKATOR KESALAHAN DATA", 
            "Kode Petugas", "Nama Kota", "NIK", "Tipe Sasaran", "validasi hasil review", "Justifikasi"
        ]
        
        df_bawah_view = st.session_state['df_tabel_bawah'][kolom_susunan].copy()
        
        df_hasil_edit = st.data_editor(
            df_bawah_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang jika telah direvisi", default=False),
                "Lembaga SSR": st.column_config.TextColumn("Lembaga SSR", width=120),
                "Tanggal": st.column_config.TextColumn("Tanggal", width=110),
                "ID Klien": st.column_config.TextColumn("ID Klien", width=110),
                "INDIKATOR KESALAHAN DATA": st.column_config.TextColumn("Indikator Kesalahan Data", width=320),
                "Tipe Sasaran": st.column_config.TextColumn("Tipe Sasaran", width=110),
                "validasi hasil review": st.column_config.TextColumn("Validasi Hasil Review", width=220),
                "Justifikasi": st.column_config.TextColumn("Justifikasi (Khusus Baris Konfirmasi)", width=280),
            },
            disabled=[c for c in kolom_susunan if c not in ["Pilih", "Justifikasi"]]
        )
        
        # --- TOMBOL SIMPAN DATABASE ---
        col_save, _ = st.columns([1, 2])
        with col_save:
            tombol_simpan = st.button("💾 Simpan Progres Validasi Ke Database", type="secondary", use_container_width=True)
            
        if tombol_simpan:
            if not supabase:
                st.error("Koneksi database tidak tersedia. Periksa library supabase Anda.")
            else:
                sukses_simpan = 0
                peringatan_justifikasi = False
                
                with st.spinner("Menyimpan data..."):
                    for idx, row_edit in df_hasil_edit.iterrows():
                        ind_text = str(row_edit['INDIKATOR KESALAHAN DATA'])
                        is_butuh_konfirmasi = "konfirmasi" in ind_text.lower()
                        text_justifikasi = str(row_edit['Justifikasi']).strip()
                        
                        if not is_butuh_konfirmasi and text_justifikasi != "":
                            peringatan_justifikasi = True
                            text_justifikasi = "" 
                        
                        if row_edit['Pilih'] or text_justifikasi != "":
                            try:
                                supabase.table("log_validasi_review").upsert({
                                    "ssr": str(row_edit['Lembaga SSR']),
                                    "tanggal": str(row_edit['Tanggal']),
                                    "id_klien": str(row_edit['ID Klien']),
                                    "indikator_kesalahan": ind_text,
                                    "is_revisi": bool(row_edit['Pilih']),
                                    "justifikasi": text_justifikasi
                                }, on_conflict="ssr,tanggal,id_klien,indikator_kesalahan").execute()
                                sukses_simpan += 1
                            except Exception:
                                pass
                        
                    if peringatan_justifikasi:
                        st.warning("⚠️ Beberapa teks Justifikasi otomatis diabaikan karena ditaruh pada indikator mutlak (bukan tipe konfirmasi).")
                    
                    st.success(f"🎉 Sukses memproses {sukses_simpan} baris validasi ke database Supabase!")
                    st.rerun()
    else:
        st.info("✨ Data bersih! Tidak ada kasus validasi pada data ini.")
