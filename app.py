import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from supabase import create_client, Client

# ==========================================================
# 0. KONFIGURASI SUPABASE
# ==========================================================
SUPABASE_URL = "https://fughiktqrtrtxrwoerud.supabase.co" 
SUPABASE_KEY = "MASUKKAN_ANON_KEY_SUPABASE_ANDA_DI_SINI"

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Gagal koneksi ke Supabase: {e}")
        return None

supabase = init_supabase()

# ==========================================================
# 1. INISIALISASI SESSION STATE
# ==========================================================
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

# Config Halaman
st.set_page_config(page_title="Data Quality Review - PKBI Jabar", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem; }
    h4 { font-weight: 600; color: #1F2937; margin-top: 1.5rem; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 Tools Review Data Massal — PKBI Jabar</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem otomatisasi penelaahan kualitas data berbasis matriks validasi terintegrasi Database.</div>', unsafe_allow_html=True)

# 50 Indikator Kesalahan Data
DAFTAR_INDIKATOR = [
    "Tahun dalam tanggal penjangkauan lebih besar/kecil dari tahun sekarang", # 0
    "Kode Petugas Kosong", # 1
    "Tanggal lebih besar dari tanggal hari ini", # 2
    "IDKD kurang/lebih dari 10 digit karakter", # 3
    "Digit nama kurang/lebih dari 4 digit karakter", # 4
    "Digit tanggal lahir lebih/kurang dari 6 digit angka", # 5
    "Ada tanda titik (.) pada penulisan IDKD", # 6
    "Ada spasi pada penulisan IDKD", # 7
    "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)", # 8
    "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)", # 9
    "Tahun Lahir KD terlalu muda (2014 -sekarang)", # 10
    "Usia KD dibawah 16 tahun (konfirmasi)", # 11
    "Usia KD diatas 70 tahun (konfirmasi)", # 12
    "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)", # 13
    "NIK kurang/lebih dari 16 digit (konfirmasi)", # 14
    "Kesalahan dalam penulisan NIK (00) (konfirmasi)", # 15
    "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)", # 16
    "LSL/Waria tapi jenis kelamin perempuan", # 17
    "Jenis kontak dengan Jenis Kegiatan tidak sesuai", # 18
    "Jenis kontak Individual/kelompok tapi kolom Virtual dan Tatap Muka (VC1) tidak diisi", # 19
    "Penjangkauan tatap muka tapi lokasi outreach diindikasi ada nama medsos", # 20
    "Lokasi outreach diisi IDKD", # 21
    "Lokasi outreach diindikasi kurang spesifik atau kurang detil (digit huruf <17 digit) (konfirmasi)", # 22
    "Lokasi outreach indikasi diisi nomer HP", # 23
    "Bukan PWID mendapatkan info 8 atau 9 (LASS, PTRM)", # 24
    "LSL/TG/PWID menerima informasi PMTC (konfirmasi)", # 25
    "Konfirmasi jumlah KIE yang diberikan adalah wajar", # 26
    "Konfirmasi jumlah kondom yang diberikan adalah wajar", # 27
    "Konfirmasi jumlah pelicin yang diberikan adalah wajar", # 28
    "Konfirmasi jumlah jarum yang diberikan adalah wajar", # 29
    "Konfirmasi jumlah alkohol SWAB yang diberikan adalah wajar", # 30
    "VO tapi kolom Virtual dan Tatap Muka (VC1) diisi angka 1", # 31
    "VO tapi lokasi outreach bukan nama medsos/kurang tepat mencatat nama aplikasi medsos", # 32
    "VO tapi menyerahkan jarum", # 33
    "VO menerima logistik selain KIE", # 34
    "VO tapi nama akun /No. Hp tidak diisi", # 35
    "Tidak ada informasi satupun yang diberikan / tidak diisi", # 36
    "KD dikontak lebih dari 1x tapi tidak mendapat informasi HIV", # 37
    "KD telah menerima layanan CBS tapi tidak ada informasi CBS", # 38
    "KD ada rujukan PrEp di penjangkauan tapi tidak ada informasi PrEp", # 39
    "KD telah menerima layanan PrEp tapi tidak ada rujukan PrEp di penjangkauan", # 40
    "Logistik kosong (Konfirmasi)", # 41
    "Tipe klien PWID tapi tidak menerima jarum (konfirmasi)", # 42
    "Tipe klien PWID tapi tidak menerima alkohol SWAB (konfirmasi)", # 43
    "Popkun selain PWID menerima jarum suntik", # 44
    "Popkun selain PWID menerima alkohol swab", # 45
    "Popkun selain PWID menyerahkan jarum", # 46
    "Tidak ada rujukan yang diberikan satupun / tidak diisi", # 47
    "KD dikontak lebih dari 1x tetapi tidak ada Rujukan Tes HIV", # 48
    "Bukan penasun rujukan 3,4" # 49
]

# Helper cek kode multi-nilai dalam satu sel (misal info diberikan: '1,2,5')
def cek_kode(text_sel, kode_cari):
    if pd.isna(text_sel) or str(text_sel).strip() == '':
        return False
    parts = [p.strip() for p in re.split(r'[.,;\s]+', str(text_sel))]
    return str(kode_cari).strip() in parts

# Helper standardisasi tanggal untuk database Supabase
def standarisasi_tanggal(val_tanggal):
    if pd.isna(val_tanggal) or str(val_tanggal).strip() == '' or str(val_tanggal).lower() == 'nan':
        return '2026-01-01'
    try:
        if isinstance(val_tanggal, datetime) or hasattr(val_tanggal, 'strftime'):
            return val_tanggal.strftime('%Y-%m-%d')
        t_str = str(val_tanggal).split(' ')[0].strip()
        if '/' in t_str:
            parts = t_str.split('/')
            if len(parts) == 3 and len(parts[0]) <= 2:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        elif '-' in t_str:
            parts = t_str.split('-')
            if len(parts) == 3 and len(parts[0]) <= 2:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        return t_str
    except:
        return '2026-01-01'

# ==========================================================
# 2. ENGINE PENGAMBILAN LOG MEMORI DATABASE (SUPABASE)
# ==========================================================
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
        except Exception as e:
            pass
    return dict_revisi, dict_justifikasi

# ==========================================================
# 3. ENGINE VALIDASI UTAMA GABUNGAN (SMART & ADVANCED)
# ==========================================================
def jalankan_review_data(df_asli, df_ref=None):
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    # ------------------------------------------------------
    # SMART MAPPING: Menyelaraskan variasi penulisan kolom Excel
    # ------------------------------------------------------
    mapping_kolom = {}
    for c in df.columns:
        c_upper = c.upper().replace("_", " ").replace(".", "")
        if "SSR" in c_upper or "LEMBAGA" in c_upper: mapping_kolom['Lembaga SSR'] = c
        elif "PETUGAS" in c_upper or "KODE PO" in c_upper or "KODE STAFF" in c_upper: mapping_kolom['Kode Petugas'] = c
        elif "TANGGAL" in c_upper or "TGL" in c_upper: mapping_kolom['Tanggal'] = c
        elif "ID KLIEN" in c_upper or "IDKD" in c_upper or "ID KREASI" in c_upper: mapping_kolom['ID Klien'] = c
        elif "NIK" in c_upper or "NO KTP" in c_upper: mapping_kolom['NIK'] = c
        elif "KOTA" in c_upper or "KABUPATEN" in c_upper: mapping_kolom['Nama Kota'] = c
        elif "TIPE SASARAN" in c_upper or "TIPE KLIEN" in c_upper or "POPKUN" in c_upper: mapping_kolom['Tipe Sasaran'] = c
        elif "UMUR" in c_upper or "USIA" in c_upper: mapping_kolom['Umur'] = c
        elif "KELAMIN" in c_upper or "JK" in c_upper: mapping_kolom['Jenis Kelamin'] = c
        elif "KONTAK" in c_upper: mapping_kolom['Jenis Kontak'] = c
        elif "KEGIATAN" in c_upper: mapping_kolom['Jenis Kegiatan'] = c
        elif "LOKASI" in c_upper or "MEDSOS" in c_upper: mapping_kolom['Lokasi Outreach'] = c
        elif "INFORMASI" in c_upper or "INFO" in c_upper: mapping_kolom['Informasi Yang diberikan'] = c
        elif "RUJUKAN" in c_upper: mapping_kolom['Rujukan'] = c
        elif "HP" in c_upper or "AKUN" in c_upper: mapping_kolom['No. HP'] = c
        elif "VC1" in c_upper or "VIRTUAL" in c_upper: mapping_kolom['VC1'] = c

    # Deteksi Jenis File
    is_file_rujukan = any('RUJUKAN' in str(c).upper() for c in df.columns) or any('FASYANKES' in str(c).upper() for c in df.columns)
    
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())
    
    medsoc_keywords = [
        'whatsapp', 'wa', 'badoo', 'hornet', 'michat', 'blued', 'bumble', 
        'walla', 'sms', 'grindr', 'growlr', 'instagram', 'ig', 'tantan', 
        'telegram', 'telepon', 'tinder', 'twitter', 'line', 'facebook', 'fb', 
        'messenger', 'romeo', 'tiktok', 'tagged', 'litmatch', 'scruff', 
        'wechat', 'threads'
    ]

    df_clean = df.iloc[start_row_idx:].copy()
    dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()

    # Pre-calculate count untuk aturan dinamis (kontak > 1x) berbasis penyesuaian kolom ID Klien
    kolom_id_real = mapping_kolom.get('ID Klien', 'ID Klien')
    id_counts = {}
    if kolom_id_real in df_clean.columns:
        id_counts = df_clean[kolom_id_real].astype(str).str.replace("'", "").str.strip().value_counts().to_dict()

    # Mapping Data Referensi HIV+
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
                if id_r and id_r != 'nan' and ssr_r != 'nan':
                    ref_ssr_id_to_nik[f"{ssr_r}_{id_r}"] = nik_r
                if nik_r and nik_r != 'nan' and nik_r != '' and ssr_r != 'nan':
                    ref_nik_ssr_to_id[f"{nik_r}_{ssr_r}"] = id_r

    # Iterasi Data Laporan
    for idx, row in df_clean.iterrows():
        no_excel_row = idx + 2
        
        # Penarikan nilai dinamis via Smart Mapping Helper
        def dapatkan_val(nama_sistem, default=''):
            k_asli = mapping_kolom.get(nama_sistem)
            if k_asli and k_asli in row:
                val = row[k_asli]
                if isinstance(val, pd.Series):
                    val = val.iloc[0] if not val.empty else default
                return val
            return default

        v_ssr = str(dapatkan_val('Lembaga SSR')).strip().upper() if dapatkan_val('Lembaga SSR') != '' else 'PKBI JABAR'
        v_tanggal_raw = dapatkan_val('Tanggal')
        v_tanggal = standarisasi_tanggal(v_tanggal_raw)
        
        id_raw = str(dapatkan_val('ID Klien')).strip()
        id_clean = id_raw.replace("'", "").strip() if id_raw != 'nan' else ''
        
        nik_raw = str(dapatkan_val('NIK')).strip()
        nik_clean = nik_raw.replace("'", "").replace('.0', '').strip() if nik_raw != 'nan' else ''
        
        v_petugas = str(dapatkan_val('Kode Petugas')).replace("'", "").strip() if dapatkan_val('Kode Petugas') != 'nan' else ''
        v_kota = str(dapatkan_val('Nama Kota')).strip()
        v_tipe_sasaran = str(dapatkan_val('Tipe Sasaran')).replace('.0', '').strip()
        umur = dapatkan_val('Umur', None)
        jk = str(dapatkan_val('Jenis Kelamin', '')).replace('.0', '').strip()
        jns_kontak = str(dapatkan_val('Jenis Kontak', '')).replace('.0', '').strip()
        jns_kegiatan = str(dapatkan_val('Jenis Kegiatan', '')).strip()
        lokasi = str(dapatkan_val('Lokasi Outreach', '')).strip()
        info_diberikan = str(dapatkan_val('Informasi Yang diberikan', '')).strip()
        rujukan = str(dapatkan_val('Rujukan', '')).strip()
        no_hp = str(dapatkan_val('No. HP', '')).strip()
        vc1 = str(dapatkan_val('VC1', '')).replace('.0', '').strip()

        # Parsing Aman Nilai Logistik Indeks Posisi Kolom Arus Lama
        try:
            log_kie = float(row.iloc[17]) if pd.notna(row.iloc[17]) and str(row.iloc[17]).strip() not in ['', 'NaN'] else 0
            log_kon = float(row.iloc[18]) if pd.notna(row.iloc[18]) and str(row.iloc[18]).strip() not in ['', 'NaN'] else 0
            log_pel = float(row.iloc[19]) if pd.notna(row.iloc[19]) and str(row.iloc[19]).strip() not in ['', 'NaN'] else 0
            log_jar = float(row.iloc[20]) if pd.notna(row.iloc[20]) and str(row.iloc[20]).strip() not in ['', 'NaN'] else 0
            log_swab = float(row.iloc[21]) if pd.notna(row.iloc[21]) and str(row.iloc[21]).strip() not in ['', 'NaN'] else 0
            jarum_kembali = float(row.get('Jumlah Jarum Suntik Kembali', 0)) if pd.notna(row.get('Jumlah Jarum Suntik Kembali', 0)) else 0
        except:
            log_kie = log_kon = log_pel = log_jar = log_swab = jarum_kembali = 0

        tgl_p = pd.to_datetime(v_tanggal_raw, errors='coerce') if pd.notna(v_tanggal_raw) else None

        # Penengah Log Validasi & Sinkronisasi Database Supabase
        def tambah_log(ind_text):
            key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{ind_text}"
            is_butuh_konfirmasi = "konfirmasi" in ind_text.lower()
            
            if is_butuh_konfirmasi and key_db in dict_justifikasi and not dict_revisi.get(key_db, False):
                return
                
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
                "INDIKATOR KESALAHAN DATA": ind_text,
                "validasi hasil review": status_validasi,
                "Justifikasi": justif_val,
                "Baris Excel": no_excel_row,
                "Kode Petugas": v_petugas,
                "Nama Kota": v_kota,
                "NIK": nik_clean,
                "Tipe Sasaran": v_tipe_sasaran
            })

        # ==========================================================
        # 📌 BLOK EKSEKUSI JALUR VALIDASI UTAMA (LOGIKA LENGKAP ANDA)
        # ==========================================================
        if not v_petugas or v_petugas == '': 
            tambah_log(DAFTAR_INDIKATOR[1])

        if pd.notna(tgl_p) and tgl_p > hari_ini:
            tambah_log(DAFTAR_INDIKATOR[2])

        if id_clean and id_clean != '':
            if len(id_clean) != 10 or not id_clean.isalnum():
                tambah_log(DAFTAR_INDIKATOR[3])
            if len(id_clean) >= 4 and not id_clean[:4].isalpha():
                tambah_log(DAFTAR_INDIKATOR[4])
            if len(id_clean) == 10 and not id_clean[4:].isdigit():
                tambah_log(DAFTAR_INDIKATOR[5])
            
            if is_file_rujukan and df_ref is not None and v_ssr:
                key_ssr_id = f"{v_ssr}_{id_clean}"
                if key_ssr_id in ref_ssr_id_to_nik and ref_ssr_id_to_nik[key_ssr_id] != nik_clean:
                    tambah_log(DAFTAR_INDIKATOR[8])

        if is_file_rujukan and df_ref is not None and v_ssr and nik_clean:
            key_nik_ssr = f"{nik_clean}_{v_ssr}"
            if key_nik_ssr in ref_nik_ssr_to_id and ref_nik_ssr_to_id[key_nik_ssr] != id_clean:
                tambah_log(DAFTAR_INDIKATOR[9])

        if pd.notna(umur) and str(umur).strip() != '':
            try:
                val_umur = float(umur)
                if val_umur < 16: tambah_log(DAFTAR_INDIKATOR[11])
                if val_umur > 70: tambah_log(DAFTAR_INDIKATOR[12])
                
                tahun_lahir = tahun_sekarang - val_umur
                if 2014 <= tahun_lahir <= tahun_sekarang: 
                    tambah_log(DAFTAR_INDIKATOR[10])
            except: pass

        if id_clean and len(id_clean) == 10 and nik_clean and len(nik_clean) == 16:
            thn_id = id_clean[4:6]
            nik_with_quote = nik_raw if nik_raw.startswith("'") else "'" + nik_clean
            if len(nik_with_quote) >= 13:
                thn_nik = nik_with_quote[11:13]
                if thn_id != thn_nik:
                    tambah_log(DAFTAR_INDIKATOR[13])

        if nik_clean and nik_clean != '':
            if len(nik_clean) != 16:
                tambah_log(DAFTAR_INDIKATOR[14])
            if nik_clean.endswith('00'):
                tambah_log(DAFTAR_INDIKATOR[15])

        if len(nik_clean) == 16 and jk == '1':
            try:
                dd_nik = int(nik_clean[6:8])
                if dd_nik > 31: tambah_log(DAFTAR_INDIKATOR[16])
            except: pass

        if (v_tipe_sasaran in ['1304', '1301']) and jk == '2': 
            tambah_log(DAFTAR_INDIKATOR[17])

        if jns_kontak == '1' and jns_kegiatan not in ['1', '5']:
            tambah_log(DAFTAR_INDIKATOR[18])
        elif jns_kontak == '2' and jns_kegiatan not in ['2', '3', '4', '6', '7']:
            tambah_log(DAFTAR_INDIKATOR[18])
        elif jns_kontak == '3' and jns_kegiatan != '8':
            tambah_log(DAFTAR_INDIKATOR[18])

        if '.' in id_raw: tambah_log(DAFTAR_INDIKATOR[6])
        if ' ' in id_raw: tambah_log(DAFTAR_INDIKATOR[7])

        is_vo = (jns_kontak == '3')
        any_medsoc_in_lokasi = any(kw in lokasi.lower() for kw in medsoc_keywords)

        if jns_kontak in ['1', '2']:
            if vc1 == '' or vc1 == 'nan': tambah_log(DAFTAR_INDIKATOR[19])
            if any_medsoc_in_lokasi: tambah_log(DAFTAR_INDIKATOR[20])

        if is_vo:
            if vc1 == '1': tambah_log(DAFTAR_INDIKATOR[31])
            if lokasi and not any_medsoc_in_lokasi: tambah_log(DAFTAR_INDIKATOR[32])
            if log_jar > 0: tambah_log(DAFTAR_INDIKATOR[33])
            if log_kon > 0 or log_pel > 0 or log_swab > 0: tambah_log(DAFTAR_INDIKATOR[34])
            if no_hp == '' or no_hp == 'nan': tambah_log(DAFTAR_INDIKATOR[35])

        if lokasi and lokasi != 'nan':
            if len(lokasi) == 10 and lokasi[:4].isalpha() and lokasi[4:].isdigit(): tambah_log(DAFTAR_INDIKATOR[21])
            if len(lokasi) < 17 and not is_vo: tambah_log(DAFTAR_INDIKATOR[22])
            if re.search(r'(08\d{8,11})|(\+62\d{8,11})', lokasi.replace('-', '').replace(' ', '')): tambah_log(DAFTAR_INDIKATOR[23])

        is_pwid = (v_tipe_sasaran == '1401')
        if not is_pwid:
            if cek_kode(info_diberikan, '8') or cek_kode(info_diberikan, '9') or cek_kode(jns_kegiatan, '8') or cek_kode(jns_kegiatan, '9'):
                tambah_log(DAFTAR_INDIKATOR[24])
            if log_jar > 0: tambah_log(DAFTAR_INDIKATOR[44])
            if log_swab > 0: tambah_log(DAFTAR_INDIKATOR[45])
            if jarum_kembali > 0: tambah_log(DAFTAR_INDIKATOR[46])
            if cek_kode(rujukan, '3') or cek_kode(rujukan, '4'): tambah_log(DAFTAR_INDIKATOR[49])
        else:
            if log_jar == 0 and not is_vo: tambah_log(DAFTAR_INDIKATOR[42])
            if log_swab == 0 and not is_vo: tambah_log(DAFTAR_INDIKATOR[43])

        if (v_tipe_sasaran in ['1304', '1301', '1401']) and (cek_kode(info_diberikan, '6') or cek_kode(jns_kegiatan, '6')):
            tambah_log(DAFTAR_INDIKATOR[25])

        if log_kie > 10: tambah_log(DAFTAR_INDIKATOR[26])
        if log_kon > 144: tambah_log(DAFTAR_INDIKATOR[27])
        if log_pel > 50: tambah_log(DAFTAR_INDIKATOR[28])
        if log_jar > 100: tambah_log(DAFTAR_INDIKATOR[29])
        if log_swab > 100: tambah_log(DAFTAR_INDIKATOR[30])

        if info_diberikan == '' or info_diberikan == 'nan': tambah_log(DAFTAR_INDIKATOR[36])
        if log_kie == 0 and log_kon == 0 and log_pel == 0 and log_jar == 0 and log_swab == 0: tambah_log(DAFTAR_INDIKATOR[41])
        if rujukan == '' or rujukan == 'nan': tambah_log(DAFTAR_INDIKATOR[47])

        if id_clean and id_counts.get(id_clean, 0) > 1:
            # Seleksi subset baris yang memuat ID yang sama secara dinamis
            df_klien_ini = df_clean[df_clean[kolom_id_real].astype(str).str.replace("'", "").str.strip() == id_clean]
            pernah_dapat_info_hiv = any(cek_kode(inf, '1') for inf in df_klien_ini[mapping_kolom.get('Informasi Yang diberikan', 'Informasi Yang diberikan')].values) or any(cek_kode(keg, '1') for keg in df_klien_ini[mapping_kolom.get('Jenis Kegiatan', 'Jenis Kegiatan')].values)
            pernah_dapat_rujuk_tes = any(cek_kode(ruj, '2') for ruj in df_klien_ini[mapping_kolom.get('Rujukan', 'Rujukan')].values)
            
            if not pernah_dapat_info_hiv: tambah_log(DAFTAR_INDIKATOR[37])
            if not pernah_dapat_rujuk_tes: tambah_log(DAFTAR_INDIKATOR[48])

        if cek_kode(jns_kegiatan, '13') and not cek_kode(info_diberikan, '13'): tambah_log(DAFTAR_INDIKATOR[38])
        if (cek_kode(rujukan, '5') or cek_kode(jns_kegiatan, '10')) and not (cek_kode(info_diberikan, '10') or cek_kode(jns_kegiatan, '10')):
            tambah_log(DAFTAR_INDIKATOR[39])
        if cek_kode(jns_kegiatan, '10') and not cek_kode(rujukan, '5'): tambah_log(DAFTAR_INDIKATOR[40])

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. EKSEKUSI REVIEW LAKUKAN ANALISIS
# ==========================================================
if st.button("🚀 Jalankan Penelaahan Laporan", type="primary"):
    if not files_review:
        st.sidebar.error("⚠️ Unggah berkas Raw Data terlebih dahulu!")
    else:
        with st.spinner("Menganalisis data laporan..."):
            df_ref = pd.read_excel(file_referensi) if file_referensi else None
            
            all_errs = []
            total_records = 0
            all_detected_ssrs = set()

            for f in files_review:
                df_target = pd.read_excel(f)
                total_records += len(df_target)
                df_res = jalankan_review_data(df_target, df_ref)
                if not df_res.empty:
                    all_errs.append(df_res)
                    all_detected_ssrs.update(df_res['Lembaga SSR'].unique())

            st.session_state['total_entri'] = total_records

            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                
                active_ssrs = sorted(list(all_detected_ssrs))
                matrix_rows = []
                for idx, ind in enumerate(DAFTAR_INDIKATOR, 1):
                    r_dict = {"INDIKATOR KESALAHAN DATA": ind}
                    total_ind_err = 0
                    for ssr in active_ssrs:
                        c = len(df_bawah[(df_bawah['INDIKATOR KESALAHAN DATA'] == ind) & (df_bawah['Lembaga SSR'] == ssr)])
                        r_dict[ssr] = c
                        total_ind_err += c
                    
                    r_dict["Jumlah"] = total_ind_err
                    matrix_rows.append(r_dict)
                
                df_atas = pd.DataFrame(matrix_rows)
                df_atas = df_atas[df_atas['Jumlah'] > 0]
                
                st.session_state['df_tabel_atas'] = df_atas
                st.session_state['df_tabel_bawah'] = df_bawah
            else:
                st.session_state['df_tabel_atas'] = pd.DataFrame(columns=["INDIKATOR KESALAHAN DATA", "Jumlah"])
                st.session_state['df_tabel_bawah'] = pd.DataFrame()

            st.session_state['proses_selesai'] = True

# ==========================================================
# 5. TAMPILAN INTERFACE & INTERAKSI DATA
# ==========================================================
if st.session_state['proses_selesai']:
    
    m1, m2 = st.columns([1, 1])
    m1.metric("Total Entri Diperiksa", f"{st.session_state['total_entri']} Baris")
    tot_err = len(st.session_state['df_tabel_bawah']) if st.session_state['df_tabel_bawah'] is not None else 0
    m2.metric("Total Temuan Kesalahan", f"{tot_err} Kasus")

    st.markdown("---")
    
    # TABEL ATAS: REKAP MATRIKS DATA PER SSR
    st.markdown("#### Rekap Hasil Review Data per SSR")
    df_atas_view = st.session_state['df_tabel_atas'].copy()
    
    if not df_atas_view.empty:
        styled_atas = df_atas_view.style.format(
            lambda x: "-" if x == 0 else f"{x}",
            subset=[c for c in df_atas_view.columns if c != "INDIKATOR KESALAHAN DATA"]
        ).set_properties(**{'text-align': 'center'}, subset=[c for c in df_atas_view.columns if c != "INDIKATOR KESALAHAN DATA"])
        
        st.dataframe(
            styled_atas,
            use_container_width=True,
            hide_index=True,
            column_config={
                "INDIKATOR KESALAHAN DATA": st.column_config.TextColumn("INDIKATOR KESALAHAN DATA", width=450),
                **{col: st.column_config.NumberColumn(col, width=130) for col in df_atas_view.columns if col != "INDIKATOR KESALAHAN DATA"}
            }
        )
    else:
        st.info("✨ Tidak ditemukan kesalahan data pada berkas.")

    st.markdown("---")

    # TABEL BAWAH: DATA EDITOR DETAIL TEMUAN KASUS
    st.markdown("#### Hasil Review Penjangkauan")
    
    if st.session_state['df_tabel_bawah'] is not None and not st.session_state['df_tabel_bawah'].empty:
        kolom_susunan = [
            "Pilih", "Lembaga SSR", "Tanggal", "ID Klien", 
            "INDIKATOR KESALAHAN DATA", "validasi hasil review", "Justifikasi",
            "Baris Excel", "Kode Petugas", "Nama Kota", "NIK"
        ]
        
        df_bawah_view = st.session_state['df_tabel_bawah'][kolom_susunan].copy()
        
        df_hasil_edit = st.data_editor(
            df_bawah_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang jika baris telah dikonfirmasi/direvisi", default=False),
                "Justifikasi": st.column_config.TextColumn("Justifikasi (Khusus Baris Konfirmasi)", width=280),
                "INDIKATOR KESALAHAN DATA": st.column_config.TextColumn("INDIKATOR KESALAHAN DATA", width=350),
                "validasi hasil review": st.column_config.TextColumn("Validasi Hasil Review", width=250)
            },
            disabled=[c for c in kolom_susunan if c not in ["Pilih", "Justifikasi"]]
        )
        
        # --- TOMBOL SIMPAN DATABASE ---
        if st.button("💾 Simpan Progres Validasi & Justifikasi Ke Database", type="secondary"):
            if not supabase:
                st.error("Koneksi database tidak tersedia.")
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
                            except Exception as ex:
                                pass
                    
                    if peringatan_justifikasi:
                        st.warning("⚠️ Beberapa teks Justifikasi otomatis diabaikan karena ditulis pada baris indikator kesalahan mutlak (Bukan tipe konfirmasi).")
                    
                    st.success(f"🎉 Sukses memproses {sukses_simpan} baris validasi ke database Supabase!")
                    st.rerun()
    else:
        st.info("✨ Data bersih! Tidak ada kasus validasi.")
