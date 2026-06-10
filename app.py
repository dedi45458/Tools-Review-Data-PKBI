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

# Custom CSS
st.markdown("""
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.1rem; color: #4B5563; margin-bottom: 1.5rem; }
    h4 { font-weight: 600; color: #1F2937; margin-top: 1.5rem; }
    .stButton>button { border-radius: 8px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 Tools Review Data Massal — PKBI Jabar</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sistem otomatisasi penelaahan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat berbasis matriks validasi terbaru.</div>', unsafe_allow_html=True)

# ==========================================================
# 1. DAFTAR INDIKATOR & FUNGSI HELPER
# ==========================================================
DAFTAR_INDIKATOR = [
    "Tahun dalam tanggal penjangkauan lebih besar/kecil dari tahun sekarang",
    "Kode Petugas Kosong",
    "Tanggal lebih besar dari tanggal hari ini",
    "IDKD kurang/lebih dari 10 digit karakter",
    "Digit nama kurang/lebih dari 4 digit karakter",
    "Digit tanggal lahir lebih/kurang dari 6 digit angka",
    "Ada tanda titik (.) pada penulisan IDKD",
    "Ada spasi pada penulisan IDKD",
    "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)",
    "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)",
    "Tahun Lahir KD terlalu muda (2014 -sekarang)",
    "Usia KD dibawah 16 tahun (konfirmasi)",
    "Usia KD diatas 70 tahun (konfirmasi)",
    "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)",
    "NIK kurang/lebih dari 16 digit (konfirmasi)",
    "Kesalahan dalam penulisan NIK (00) (konfirmasi)",
    "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)",
    "LSL/Waria tapi jenis kelamin perempuan",
    "Jenis kontak dengan Jenis Kegiatan tidak sesuai",
    "Jenis kontak Individual/kelompok tapi kolom Virtual dan Tatap Muka (VC1) tidak diisi",
    "Penjangkauan tatap muka tapi lokasi outreach diindikasi ada nama medsos",
    "Lokasi outreach diisi IDKD",
    "Lokasi outreach diindikasi kurang spesifik atau kurang detil (digit huruf <17 digit) (konfirmasi)",
    "Lokasi outreach indikasi diisi nomer HP",
    "Bukan PWID mendapatkan info 8 atau 9 (LASS, PTRM)",
    "LSL/TG/PWID menerima informasi PMTC (konfirmasi)",
    "Konfirmasi jumlah KIE yang diberikan adalah wajar",
    "Konfirmasi jumlah kondom yang diberikan adalah wajar",
    "Konfirmasi jumlah pelicin yang diberikan adalah wajar",
    "Konfirmasi jumlah jarum yang diberikan adalah wajar",
    "Konfirmasi jumlah alkohol SWAB yang diberikan adalah wajar",
    "VO tapi kolom Virtual dan Tatap Muka (VC1) diisi angka 1",
    "VO tapi lokasi outreach bukan nama medsos/kurang tepat mencatat nama aplikasi medsos",
    "VO tapi menyerahkan jarum",
    "VO menerima logistik selain KIE",
    "VO tapi nama akun /No. Hp tidak diisi",
    "Tidak ada informasi satupun yang diberikan / tidak diisi",
    "KD dikontak lebih dari 1x tapi tidak mendapat informasi HIV",
    "KD telah menerima layanan CBS tapi tidak ada informasi CBS",
    "KD ada rujukan PrEp di penjangkauan tapi tidak ada informasi PrEp",
    "KD telah menerima layanan PrEp tapi tidak ada rujukan PrEp di penjangkauan",
    "Logistik kosong (Konfirmasi)",
    "Tipe klien PWID tapi tidak menerima jarum (konfirmasi)",
    "Tipe klien PWID tapi tidak menerima alkohol SWAB (konfirmasi)",
    "Popkun selain PWID menerima jarum suntik",
    "Popkun selain PWID menerima alkohol swab",
    "Popkun selain PWID menyerahkan jarum",
    "Tidak ada rujukan yang diberikan satupun / tidak diisi",
    "KD dikontak lebih dari 1x tetapi tidak ada Rujukan Tes HIV",
    "Bukan penasun rujukan 3,4"
]

def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom): return False
    clean_str = str(teks_kolom).replace("'", "").replace(" ", "")
    list_kode = clean_str.split(",")
    return str(kode_target) in list_kode

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

        def tambah_log(nama_indikator):
            key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{nama_indikator}"
            is_butuh_konfirmasi = "konfirmasi" in nama_indikator.lower()
            
            # Jika sudah dijustifikasi sebelumnya, sembunyikan dari daftar error
            if is_butuh_konfirmasi and key_db in dict_justifikasi and not dict_revisi.get(key_db, False):
                return
                
            status_validasi = "-"
            checked_state = False
            justif_val = dict_justifikasi.get(key_db, "") if is_butuh_konfirmasi else ""
            
            # Flag data yang diulang tanpa revisi
            if key_db in dict_revisi:
                status_validasi = "kesalahan pada ID yang berulang (belum dilakukan revisi)"
                checked_state = True

            list_kesalahan.append({
                "Pilih": checked_state,
                "Baris Excel": no_excel_row, 
                "Lembaga SSR": v_ssr,
                "Tanggal": v_tanggal, 
                "ID Klien": id_clean, 
                "INDIKATOR KESALAHAN DATA": nama_indikator,
                "validasi hasil review": status_validasi,
                "Justifikasi": justif_val,
                "Kode Petugas": v_petugas, 
                "Nama Kota": v_kota, 
                "NIK": nik_clean, 
                "Tipe Sasaran": v_tipe_sasaran
            })

        # --- LOGIKA VALIDASI UTAMA MENGGUNAKAN INDEKS ---
        if pd.isna(row.get('Kode Petugas')) or str(row.get('Kode Petugas')).strip() == '': tambah_log(DAFTAR_INDIKATOR[1])
        if pd.notna(tgl_p) and tgl_p > hari_ini: tambah_log(DAFTAR_INDIKATOR[2])

        if id_clean and id_clean != 'nan' and id_clean != '':
            if len(id_clean) != 10 or not id_clean.isalnum(): tambah_log(DAFTAR_INDIKATOR[3])
            if len(id_clean) >= 4 and not id_clean[:4].isalpha(): tambah_log(DAFTAR_INDIKATOR[4])
            if len(id_clean) == 10 and not id_clean[4:].isdigit(): tambah_log(DAFTAR_INDIKATOR[5])
            
            if is_file_rujukan and df_ref is not None and v_ssr:
                key_ssr_id = f"{v_ssr}_{id_clean}"
                if key_ssr_id in ref_ssr_id_to_nik and ref_ssr_id_to_nik[key_ssr_id] != nik_clean:
                    tambah_log(DAFTAR_INDIKATOR[8])

        if is_file_rujukan and df_ref is not None and v_ssr and nik_clean and nik_clean != 'nan' and nik_clean != '':
            key_nik_ssr = f"{nik_clean}_{v_ssr}"
            if key_nik_ssr in ref_nik_ssr_to_id and ref_nik_ssr_to_id[key_nik_ssr] != id_clean: tambah_log(DAFTAR_INDIKATOR[9])

        if pd.notna(umur) and str(umur).strip() != '':
            try:
                val_umur = float(umur)
                if val_umur < 17: tambah_log(DAFTAR_INDIKATOR[11])
                if val_umur > 70: tambah_log(DAFTAR_INDIKATOR[12])
            except: pass

        if id_clean and len(id_clean) == 10 and nik_clean and len(nik_clean) == 16:
            thn_id = id_clean[4:6]
            nik_with_quote = nik_raw if nik_raw.startswith("'") else "'" + nik_clean
            if len(nik_with_quote) >= 13:
                thn_nik = nik_with_quote[11:13]
                if thn_id != thn_nik: tambah_log(DAFTAR_INDIKATOR[13])

        if nik_clean and nik_clean != 'nan' and nik_clean != '':
            if len(nik_clean) != 16: tambah_log(DAFTAR_INDIKATOR[14])
            if nik_clean.endswith('00'): tambah_log(DAFTAR_INDIKATOR[15])

        if len(nik_clean) == 16 and jk == '1':
            try:
                dd_nik = int(nik_clean[6:8])
                if dd_nik > 31: tambah_log(DAFTAR_INDIKATOR[16])
            except: pass

        if (v_tipe_sasaran in ['1304', '1301']) and jk == '2': tambah_log(DAFTAR_INDIKATOR[17])

        if jns_kontak == '1' and jns_kegiatan not in ['1', '5']: tambah_log(DAFTAR_INDIKATOR[18])
        elif jns_kontak == '2' and jns_kegiatan not in ['2', '3', '4', '6', '7']: tambah_log(DAFTAR_INDIKATOR[18])
        elif jns_kontak == '3' and jns_kegiatan != '8': tambah_log(DAFTAR_INDIKATOR[18])

        if '.' in id_raw: tambah_log(DAFTAR_INDIKATOR[6])
        if ' ' in id_raw: tambah_log(DAFTAR_INDIKATOR[7])
        
        if pd.notna(umur) and str(umur).strip() != '':
            try:
                val_umur = float(umur)
                tahun_lahir = tahun_sekarang - val_umur
                if 2014 <= tahun_lahir <= tahun_sekarang: tambah_log(DAFTAR_INDIKATOR[10])
            except: pass

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
            df_klien_ini = df[df['ID Klien'].astype(str).str.replace("'", "").str.strip() == id_clean]
            pernah_dapat_info_hiv = any(cek_kode(inf, '1') for inf in df_klien_ini['Informasi Yang diberikan'].values) or any(cek_kode(keg, '1') for keg in df_klien_ini['Jenis Kegiatan'].values)
            pernah_dapat_rujuk_tes = any(cek_kode(ruj, '2') for ruj in df_klien_ini['Rujukan'].values)
            if not pernah_dapat_info_hiv: tambah_log(DAFTAR_INDIKATOR[37])
            if not pernah_dapat_rujuk_tes: tambah_log(DAFTAR_INDIKATOR[48])

        if cek_kode(jns_kegiatan, '13') and not cek_kode(info_diberikan, '13'): tambah_log(DAFTAR_INDIKATOR[38])
        if (cek_kode(rujukan, '5') or cek_kode(jns_kegiatan, '10')) and not (cek_kode(info_diberikan, '10') or cek_kode(jns_kegiatan, '10')):
            tambah_log(DAFTAR_INDIKATOR[39])
        if cek_kode(jns_kegiatan, '10') and not cek_kode(rujukan, '5'): tambah_log(DAFTAR_INDIKATOR[40])

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
                        # Kumpulkan SSR Dinamis yang hanya ada temuannya
                        detected_ssrs.update(df_res['Lembaga SSR'].unique())
                except Exception:
                    pass

            st.session_state['total_entri'] = total_records

            if all_errs:
                df_bawah = pd.concat(all_errs, ignore_index=True)
                active_ssrs = sorted(list(detected_ssrs))
                
                # Membangun Matriks Dinamis (Tabel Atas)
                matrix_rows = []
                for ind in DAFTAR_INDIKATOR:
                    r_dict = {"INDIKATOR KESALAHAN DATA": ind}
                    total_ind_err = 0
                    for ssr in active_ssrs:
                        c = len(df_bawah[(df_bawah['INDIKATOR KESALAHAN DATA'] == ind) & (df_bawah['Lembaga SSR'] == ssr)])
                        r_dict[ssr] = c
                        total_ind_err += c
                    
                    r_dict["Jumlah per indikator"] = total_ind_err
                    matrix_rows.append(r_dict)
                
                df_atas = pd.DataFrame(matrix_rows)
                # Filter out rows with 0 total errors for a cleaner matrix
                df_atas = df_atas[df_atas['Jumlah per indikator'] > 0]
                
                # Trik Membekukan Kolom (Freeze Pane): Jadikan indikator sebagai index tabel
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
    
    m1, m2 = st.columns([1, 1])
    m1.metric("Total Entri Data Diperiksa", f"{st.session_state['total_entri']} Baris")
    tot_err = len(st.session_state['df_tabel_bawah']) if st.session_state['df_tabel_bawah'] is not None else 0
    m2.metric("Total Temuan Log Kesalahan", f"{tot_err} Kasus")

    st.markdown("---")
    
    # ------------------------------------------------------
    # TABEL ATAS: REKAP HASIL REVIEW DATA PER SSR
    # ------------------------------------------------------
    st.markdown("#### Rekap Hasil Review Data per SSR")
    df_atas_view = st.session_state['df_tabel_atas'].copy() if st.session_state['df_tabel_atas'] is not None else pd.DataFrame()
    
    if not df_atas_view.empty:
        # Styling Pandas: Ubah angka 0 menjadi "-" dan buat teks center
        styled_atas = df_atas_view.style.format(
            lambda x: "-" if x == 0 else f"{x}"
        ).set_properties(**{'text-align': 'center'})
        
        # Konfigurasi agar kolom width nya terbagi merata
        st.dataframe(
            styled_atas,
            use_container_width=True,
            column_config={
                col: st.column_config.NumberColumn(col, width="medium") for col in df_atas_view.columns
            }
        )
    else:
        st.info("✨ Tidak ada rekapan karena file data bersih dari kesalahan.")

    st.markdown("---")

    # ------------------------------------------------------
    # TABEL BAWAH: HASIL REVIEW PENJANGKAUAN
    # ------------------------------------------------------
    st.markdown("#### Hasil Review Penjangkauan")
    
    if st.session_state['df_tabel_bawah'] is not None and not st.session_state['df_tabel_bawah'].empty:
        kolom_susunan = [
            "Pilih", "Baris Excel", "Lembaga SSR", "Tanggal", "ID Klien", 
            "INDIKATOR KESALAHAN DATA", "validasi hasil review", "Justifikasi",
            "Kode Petugas", "Nama Kota", "NIK", "Tipe Sasaran"
        ]
        
        df_bawah_view = st.session_state['df_tabel_bawah'][kolom_susunan].copy()
        
        # Data Editor untuk ceklis dan input teks
        df_hasil_edit = st.data_editor(
            df_bawah_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Pilih": st.column_config.CheckboxColumn("Pilih", help="Centang jika telah direvisi", default=False),
                "Baris Excel": st.column_config.NumberColumn("Baris Excel", width=100),
                "Justifikasi": st.column_config.TextColumn("Justifikasi (Khusus Baris Konfirmasi)", width=280),
                "INDIKATOR KESALAHAN DATA": st.column_config.TextColumn("INDIKATOR KESALAHAN DATA", width=350),
                "validasi hasil review": st.column_config.TextColumn("Validasi Hasil Review", width=250)
            },
            disabled=[c for c in kolom_susunan if c not in ["Pilih", "Justifikasi"]]
        )
        
        # --- TOMBOL SIMPAN DATABASE ---
        if st.button("💾 Simpan Progres Validasi & Justifikasi Ke Database", type="secondary"):
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
