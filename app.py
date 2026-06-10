import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# ==========================================================
# 1. KONFIGURASI UTAMA STREAMLIT ONLINE
# ==========================================================
st.set_page_config(page_title="Tools Review PKBI Jabar - Dashboard Matrik SSR", layout="wide")

st.title("📊 Tools Review Data Masal (Online) - PKBI Jabar")
st.markdown("""
Sistem otomatisasi penelaahan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat.
**Fitur Baru: Dashboard Rekap per Lembaga SSR sesuai format gambar.**
""")
st.divider()

if 'proses_selesai' not in st.session_state:
    st.session_state['proses_selesai'] = False
if 'data_unduhan' not in st.session_state:
    st.session_state['data_unduhan'] = None
if 'rekap_tampilan' not in st.session_state:
    st.session_state['rekap_tampilan'] = None
if 'dashboard_tampilan' not in st.session_state:
    st.session_state['dashboard_tampilan'] = None

# MASTER LIST 50 INDIKATOR KESALAHAN (URUTAN SESUAI TEMPLATE)
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

# ==========================================================
# 2. PANEL SIDEBAR UNTUK UNGGAH BERKAS
# ==========================================================
st.sidebar.header("📁 Menu Unggah Berkas")
file_referensi = st.sidebar.file_uploader(
    "1️⃣ Data Semester / Tahun Lalu (.xlsx)", 
    type=["xlsx"], 
    help="Digunakan untuk validasi silang (ID vs NIK) data historis."
)

files_review = st.sidebar.file_uploader(
    "2️⃣ Raw Data Penjangkauan (.xlsx)", 
    type=["xlsx"], 
    accept_multiple_files=True,
    help="Unggah satu atau banyak berkas lapangan bulanan yang ingin diperiksa."
)

def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom):
        return False
    clean_str = str(teks_kolom).replace("'", "").replace(" ", "")
    list_kode = clean_str.split(",")
    return str(kode_target) in list_kode

# ==========================================================
# 3. ENGINE VALIDASI UTAMA PER BARIS
# ==========================================================
def jalankan_review_penjangkauan(df_asli, df_ref=None, nama_file=""):
    list_kesalahan = []
    if df_asli.empty:
        return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())
    medsoc_keywords = ['whatsapp', 'wa', 'facebook', 'fb', 'instagram', 'ig', 'michat', 'blued', 'tinder', 'hornet', 'telegram', 'tantan', 'grindr', 'twitter']

    ref_id_to_nik = {}
    ref_nik_to_id = {}
    if df_ref is not None:
        df_ref.columns = [str(c).strip() for c in df_ref.columns]
        col_id_ref = [c for c in df_ref.columns if 'ID' in c or 'Klien' in c]
        col_nik_ref = [c for c in df_ref.columns if 'NIK' in c]
        if col_id_ref and col_nik_ref:
            for _, r in df_ref.iterrows():
                id_r = str(r[col_id_ref[0]]).strip()
                nik_r = str(r[col_nik_ref[0]]).replace('.0', '').strip()
                if id_r and id_r != 'nan': ref_id_to_nik[id_r] = nik_r
                if nik_r and nik_r != 'nan': ref_nik_to_id[nik_r] = id_r

    id_counts = df.iloc[start_row_idx:]['ID Klien'].astype(str).str.strip().value_counts().to_dict()

    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        no_excel_row = idx + 2
        
        v_ssr = str(row.get('Lembaga SSR', '')).strip() if pd.notna(row.get('Lembaga SSR')) else ''
        v_petugas = str(row.get('Kode Petugas', '')).replace("'", "").strip() if pd.notna(row.get('Kode Petugas')) else ''
        v_kota = str(row.get('Nama Kota', '')).strip() if pd.notna(row.get('Nama Kota')) else ''
        v_layanan = str(row.get('Nama Layanan', '')).strip() if pd.notna(row.get('Nama Layanan')) else '-'
        v_tanggal = str(row.get('Tanggal', '')).split(' ')[0] if pd.notna(row.get('Tanggal')) else ''
        id_klien = str(row.get('ID Klien', '')).replace("'", "").strip() if pd.notna(row.get('ID Klien')) else ''
        nik = str(row.get('NIK', '')).replace('.0', '').replace("'", "").strip() if pd.notna(row.get('NIK')) else ''
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

        def tambah_log(nama_indikator, deskripsi_detail):
            list_kesalahan.append({
                "Nama File": nama_file, "Baris Excel": no_excel_row, "Lembaga SSR": v_ssr,
                "Kode Petugas": v_petugas, "Nama Kota": v_kota, "Nama Layanan": v_layanan,
                "Tanggal": v_tanggal, "ID Klien": id_klien, "NIK": nik, "Tipe Sasaran": v_tipe_sasaran,
                "Nama Indikator Murni": nama_indikator,
                "Keterangan review": f"[{nama_indikator}] {deskripsi_detail}"
            })

        # CORE AUDIT ENGINE (50 INDIKATOR)
        if pd.notna(tgl_p):
            if tgl_p.year != tahun_sekarang: tambah_log(DAFTAR_INDIKATOR[0], f"Tahun pelaksanaan ({tgl_p.year}) tidak sesuai tahun berjalan")
            if tgl_p > hari_ini: tambah_log(DAFTAR_INDIKATOR[2], "Tanggal penjangkauan berada di masa depan")

        if pd.isna(row.get('Kode Petugas')) or str(row.get('Kode Petugas')).strip() == '':
            tambah_log(DAFTAR_INDIKATOR[1], "Kolom kode petugas tidak terisi")

        if id_klien and id_klien != 'nan':
            if len(id_klien) != 10: tambah_log(DAFTAR_INDIKATOR[3], f"Panjang IDKD {len(id_klien)} karakter")
            if '.' in id_klien: tambah_log(DAFTAR_INDIKATOR[6], "Ditemukan tanda baca titik (.)")
            if ' ' in id_klien: tambah_log(DAFTAR_INDIKATOR[7], "Ditemukan spasi kosong")
            if len(id_klien) == 10:
                if not id_klien[:4].isalpha(): tambah_log(DAFTAR_INDIKATOR[4], "4 Huruf awal IDKD bukan alfabet")
                if not id_klien[4:].isdigit(): tambah_log(DAFTAR_INDIKATOR[5], "6 Angka akhir IDKD bukan tanggal digital")

        if df_ref is not None:
            if id_klien in ref_id_to_nik and ref_id_to_nik[id_klien] != nik: tambah_log(DAFTAR_INDIKATOR[8], "ID terikat NIK berbeda di semester lalu")
            if nik in ref_nik_to_id and ref_nik_to_id[nik] != id_klien: tambah_log(DAFTAR_INDIKATOR[9], "NIK terikat ID berbeda di semester lalu")

        if pd.notna(umur) and str(umur).strip() != '':
            try:
                val_umur = float(umur)
                if val_umur < 16: tambah_log(DAFTAR_INDIKATOR[11], "Usia terlalu muda")
                if val_umur > 70: tambah_log(DAFTAR_INDIKATOR[12], "Usia tergolong lansia")
                if 2014 <= (tahun_sekarang - val_umur) <= tahun_sekarang: tambah_log(DAFTAR_INDIKATOR[10], "Estimasi tahun lahir terlalu muda")
            except: pass

        if id_klien and len(id_klien) == 10 and len(nik) == 16:
            if id_klien[8:10] != nik[10:12]: tambah_log(DAFTAR_INDIKATOR[13], "Tahun lahir di IDKD tidak sinkron dengan NIK")

        if nik and nik != 'nan':
            if len(nik) != 16: tambah_log(DAFTAR_INDIKATOR[14], f"Panjang NIK {len(nik)} digit")
            if nik.startswith('00') or '000000' in nik: tambah_log(DAFTAR_INDIKATOR[15], "Format nomor NIK terindikasi dummy")

        if len(nik) == 16 and jk in ['1', '2']:
            try:
                dd_nik = int(nik[6:8])
                if jk == '2' and dd_nik <= 40: tambah_log(DAFTAR_INDIKATOR[16], "Klien Perempuan (2) tapi digit NIK menunjukkan Laki-laki")
                elif jk == '1' and dd_nik > 40: tambah_log(DAFTAR_INDIKATOR[16], "Klien Laki-laki (1) tapi digit NIK menunjukkan Perempuan")
            except: pass

        if (v_tipe_sasaran in ['1304', '1301']) and jk == '2': tambah_log(DAFTAR_INDIKATOR[17], "LSL/Waria bertentangan dengan Gender Perempuan")

        is_vo = (jns_kontak == '3')
        any_medsoc_in_lokasi = any(kw in lokasi.lower() for kw in medsos_keywords)

        if is_vo and (cek_kode(jns_kegiatan, '8') or cek_kode(jns_kegiatan, '9')):
            tambah_log(DAFTAR_INDIKATOR[18], "Kontak VO tidak sesuai dengan jenis kegiatan LASS/PTRM")

        if jns_kontak in ['1', '2']:
            if vc1 == '' or vc1 == 'nan': tambah_log(DAFTAR_INDIKATOR[19], "Kontak lapangan wajib mengisi instrumen kolom VC1")
            if any_medsoc_in_lokasi: tambah_log(DAFTAR_INDIKATOR[20], "Kontak lapangan tapi lokasi outreach diisi nama aplikasi medsos")

        if is_vo:
            if vc1 == '1': tambah_log(DAFTAR_INDIKATOR[31], "Kontak bertipe VO tidak boleh mengisi VC1 dengan angka 1")
            if lokasi and not any_medsoc_in_lokasi: tambah_log(DAFTAR_INDIKATOR[32], "Kontak VO namun kolom lokasi tidak mencantumkan nama platform medsos")
            if log_jar > 0: tambah_log(DAFTAR_INDIKATOR[33], "Kontak VO tidak logis menyerahkan Jarum Suntik fisik")
            if log_kon > 0 or log_pel > 0 or log_swab > 0: tambah_log(DAFTAR_INDIKATOR[34], "Kontak VO hanya boleh menyalurkan KIE digital")
            if no_hp == '' or no_hp == 'nan' or no_hp == "'": tambah_log(DAFTAR_INDIKATOR[35], "Kontak VO wajib mengisi identitas akun media sosial")

        if lokasi and lokasi != 'nan':
            if len(lokasi) == 10 and lokasi[:4].isalpha() and lokasi[4:].isdigit(): tambah_log(DAFTAR_INDIKATOR[21], "Kolom lokasi tertukar diisi kode IDKD")
            if len(lokasi) < 17 and not is_vo: tambah_log(DAFTAR_INDIKATOR[22], "Deskripsi nama jalan/lokasi terlalu pendek")
            if re.search(r'(08\d{8,11})|(\+62\d{8,11})', lokasi.replace('-', '').replace(' ', '')): tambah_log(DAFTAR_INDIKATOR[23], "Kolom lokasi outreach diisi nomor seluler")

        is_pwid = (v_tipe_sasaran == '1401')
        if not is_pwid:
            if cek_kode(info_diberikan, '8') or cek_kode(info_diberikan, '9') or cek_kode(jns_kegiatan, '8') or cek_kode(jns_kegiatan, '9'):
                tambah_log(DAFTAR_INDIKATOR[24], "Klien non-penasun terdata mendapatkan materi LASS/PTRM")
            if log_jar > 0: tambah_log(DAFTAR_INDIKATOR[44], "Distribusi jarum steril bocor ke kelompok non-penasun")
            if log_swab > 0: tambah_log(DAFTAR_INDIKATOR[45], "Distribusi alkohol swab bocor ke kelompok non-penasun")
            if jarum_kembali > 0: tambah_log(DAFTAR_INDIKATOR[46], "Tercatat angka pengembalian jarum untuk non-penasun")
            if cek_kode(rujukan, '3') or cek_kode(rujukan, '4'): tambah_log(DAFTAR_INDIKATOR[49], "Klien non-penasun diberi rujukan LASS/PTRM")
        else:
            if log_jar == 0 and not is_vo: tambah_log(DAFTAR_INDIKATOR[42], "Klien Penasun lapangan tidak dibekali pasokan alat suntik steril")
            if log_swab == 0 and not is_vo: tambah_log(DAFTAR_INDIKATOR[43], "Klien Penasun lapangan tidak dibekali alkohol swab")

        if (v_tipe_sasaran in ['1304', '1301', '1401']) and (cek_kode(info_diberikan, '6') or cek_kode(jns_kegiatan, '6')):
            tambah_log(DAFTAR_INDIKATOR[25], "Kelompok populasi kunci LSL/TG/PWID menerima info PMTCT")

        if log_kie > 10: tambah_log(DAFTAR_INDIKATOR[26], "Input penyerahan KIE sangat ekstrem")
        if log_kon > 144: tambah_log(DAFTAR_INDIKATOR[27], "Input pembagian kondom melebihi batas gross (>144)")
        if log_pel > 50: tambah_log(DAFTAR_INDIKATOR[28], "Input pembagian cairan pelicin terlalu tinggi")
        if log_jar > 100: tambah_log(DAFTAR_INDIKATOR[29], "Input pembagian jarum steril lapangan sangat masif")
        if log_swab > 100: tambah_log(DAFTAR_INDIKATOR[30], "Input pembagian alkohol swab lapangan sangat masif")

        if info_diberikan == '' or info_diberikan == 'nan' or info_diberikan == "'": tambah_log(DAFTAR_INDIKATOR[36], "Klien tanpa rekam jejak edukasi/informasi")
        if log_kie == 0 and log_kon == 0 and log_pel == 0 and log_jar == 0 and log_swab == 0: tambah_log(DAFTAR_INDIKATOR[41], "Penjangkauan terekam tanpa penyerahan logistik fisik")
        if rujukan == '' or rujukan == 'nan' or rujukan == "'": tambah_log(DAFTAR_INDIKATOR[47], "Kolom rujukan kosong")

        if id_klien and id_counts.get(id_klien, 0) > 1:
            df_klien_ini = df[df['ID Klien'].astype(str).str.replace("'", "").str.strip() == id_klien]
            pernah_dapat_info_hiv = any(cek_kode(inf, '1') for inf in df_klien_ini['Informasi Yang diberikan'].values) or any(cek_kode(keg, '1') for keg in df_klien_ini['Jenis Kegiatan'].values)
            pernah_dapat_rujuk_tes = any(cek_kode(ruj, '2') for ruj in df_klien_ini['Rujukan'].values)
            if not pernah_dapat_info_hiv: tambah_log(DAFTAR_INDIKATOR[37], "Klien dikontak berulang tanpa edukasi HIV")
            if not pernah_dapat_rujuk_tes: tambah_log(DAFTAR_INDIKATOR[48], "Klien dikontak berulang tanpa rujukan Tes HIV")

        if cek_kode(jns_kegiatan, '13') and not cek_kode(info_diberikan, '13'): tambah_log(DAFTAR_INDIKATOR[38], "Layanan CBS tanpa info CBS")
        if (cek_kode(rujukan, '5') or cek_kode(jns_kegiatan, '10')) and not (cek_kode(info_diberikan, '10') or cek_kode(jns_kegiatan, '10')):
            tambah_log(DAFTAR_INDIKATOR[39], "Ada intervensi/rujukan PrEP tanpa dibarengi edukasi materi PrEP")
        if cek_kode(jns_kegiatan, '10') and not cek_kode(rujukan, '5'): tambah_log(DAFTAR_INDIKATOR[40], "Menerima Layanan PrEP tanpa instrumen Rujukan PrEP")

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. KONTROL UTAMA & GENERATOR EXCEL DASHBOARD
# ==========================================================
if files_review:
    st.success(f"📂 Berhasil mendeteksi {len(files_review)} berkas penjangkauan.")
    
    # Ekstraksi Nama SSR Unik dari Data Lapangan secara Realtime
    unique_ssrs = set()
    total_records_processed = 0
    
    for file in files_review:
        try:
            df_temp = pd.read_excel(file)
            df_temp.columns = [str(c).strip() for c in df_temp.columns]
            if 'Lembaga SSR' in df_temp.columns:
                start_row = 1 if len(df_temp) > 0 and ('dd/mm/yyyy' in str(df_temp.iloc[0].values) or 'Laki-laki' in str(df_temp.iloc[0].values)) else 0
                ssrs_in_file = df_temp.iloc[start_row:]['Lembaga SSR'].dropna().astype(str).str.strip().unique()
                for s in ssrs_in_file:
                    if s and s != 'nan' and s != '':
                        unique_ssrs.add(s)
                total_records_processed += (len(df_temp) - start_row)
        except:
            pass
            
    list_ssr_unik = sorted(list(unique_ssrs))
    if not list_ssr_unik:
        list_ssr_unik = ["BINA MUDA GEMILANG", "YAYASAN SRIKANDI PASUNDAN", "LENSA SUKABUMI"]

    tombol_eksekusi = st.button("🚀 Jalankan Sistem & Buat Rekap Matrik SSR", type="primary")
    
    if tombol_eksekusi:
        with st.spinner("Mengevaluasi data & menyusun Dashboard Rekap sesuai format gambar..."):
            df_ref = None
            if file_referensi:
                try: df_ref = pd.read_excel(file_referensi)
                except: pass
            
            semua_rekap_kesalahan = []
            for file in files_review:
                try:
                    df_target = pd.read_excel(file)
                    df_rekap_file = jalankan_review_penjangkauan(df_target, df_ref, nama_file=file.name)
                    if not df_rekap_file.empty:
                        semua_rekap_kesalahan.append(df_rekap_file)
                except Exception as e:
                    st.error(f"Gagal memproses berkas {file.name}: {e}")
            
            if semua_rekap_kesalahan:
                df_final_rekap = pd.concat(semua_rekap_kesalahan, ignore_index=True)
            else:
                df_final_rekap = pd.DataFrame(columns=['Lembaga SSR', 'Nama Indikator Murni'])
            
            # --- MEMBUAT DATA FRAME MATRIX UNTUK TAMPILAN DASHBOARD DI STREAMLIT ---
            matrix_data = []
            for idx, ind in enumerate(DAFTAR_INDIKATOR, 1):
                row_dict = {"No.": idx, "INDIKATOR KESALAHAN DATA": ind}
                total_row_err = 0
                for ssr in list_ssr_unik:
                    count_err = len(df_final_rekap[(df_final_rekap['Nama Indikator Murni'] == ind) & (df_final_rekap['Lembaga SSR'] == ssr)])
                    row_dict[ssr] = count_err
                    total_row_err += count_err
                
                row_dict["Jumlah per indikator"] = total_row_err
                pct = (total_row_err / total_records_processed * 100) if total_records_processed > 0 else 0
                row_dict["% Kesalahan"] = f"{pct:.2f}%"
                matrix_data.append(row_dict)
                
            df_dashboard_view = pd.DataFrame(matrix_data)
            
            # --- PROSES EKSPOR EXCEL DENGAN OPENPYXL (STYLE SAMA SEPERTI GAMBAR) ---
            output_stream = io.BytesIO()
            wb = openpyxl.Workbook()
            
            # Sheet 1: REKAP KESALAHAN (DASHBOARD)
            ws_dash = wb.active
            ws_dash.title = "Rekap Kesalahan"
            ws_dash.views.sheetView[0].showGridLines = True
            
            # Fonts & Fills (Sesuai image_dffa7d.png)
            font_title = Font(name="Calibri", size=11, bold=True)
            font_header = Font(name="Calibri", size=9, bold=True)
            font_sec = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            font_data = Font(name="Calibri", size=10)
            
            fill_blue_header = PatternFill(start_color="BCD6EE", end_color="BCD6EE", fill_type="solid")
            fill_orange_summary = PatternFill(start_color="F8CBAD", end_color="F8CBAD", fill_type="solid")
            fill_section_bar = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
            
            thin_border = Border(
                left=Side(style='thin', color='BFBFBF'), right=Side(style='thin', color='BFBFBF'),
                top=Side(style='thin', color='BFBFBF'), bottom=Side(style='thin', color='BFBFBF')
            )
            
            # Tulis Susunan Header Dua Tingkat (Row 1 & Row 2)
            ws_dash['A1'] = "No."
            ws_dash['B1'] = "INDIKATOR KESALAHAN DATA"
            ws_dash.merge_cells('A1:A2')
            ws_dash.merge_cells('B1:B2')
            
            start_col_idx = 3
            end_col_idx = start_col_idx + len(list_ssr_unik) - 1
            
            ws_dash.cell(row=1, column=start_col_idx, value="Jml. Kesalahan data")
            if len(list_ssr_unik) > 1:
                ws_dash.merge_cells(start_row=1, start_column=start_col_idx, end_row=1, end_column=end_col_idx)
                
            for i, ssr in enumerate(list_ssr_unik):
                ws_dash.cell(row=2, column=start_col_idx + i, value=ssr)
                
            col_jml = end_col_idx + 1
            col_pct = end_col_idx + 2
            
            ws_dash.cell(row=1, column=col_jml, value="Jumlah per indikator")
            ws_dash.cell(row=1, column=col_pct, value="% Kesalahan")
            ws_dash.merge_cells(start_row=1, start_column=col_jml, end_row=2, end_column=col_jml)
            ws_dash.merge_cells(start_row=1, start_column=col_pct, end_row=2, end_column=col_pct)
            
            # Beri Warna & Center pada Header Row 1 & 2
            for r in [1, 2]:
                for c in range(1, col_pct + 1):
                    cell = ws_dash.cell(row=r, column=c)
                    cell.font = font_header
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    if c in [col_jml, col_pct]:
                        cell.fill = fill_orange_summary
                    else:
                        cell.fill = fill_blue_header
                    cell.border = thin_border

            # Row 3: Judul Seksi "Penjangkauan"
            ws_dash.cell(row=3, column=1, value="Penjangkauan")
            ws_dash.merge_cells(start_row=3, start_column=1, end_row=3, end_column=col_pct)
            ws_dash.cell(row=3, column=1).fill = fill_section_bar
            ws_dash.cell(row=3, column=1).font = font_sec
            ws_dash.cell(row=3, column=1).alignment = Alignment(vertical="center", indent=1)
            ws_dash.row_dimensions[3].height = 24
            
            # Tulis Baris Data 1 s/d 50 (Mulai Row 4)
            for idx, ind in enumerate(DAFTAR_INDIKATOR):
                current_row = 4 + idx
                ws_dash.cell(row=current_row, column=1, value=idx + 1)
                ws_dash.cell(row=current_row, column=2, value=ind)
                
                total_row_err = 0
                for i, ssr in enumerate(list_ssr_unik):
                    count_err = len(df_final_rekap[(df_final_rekap['Nama Indikator Murni'] == ind) & (df_final_rekap['Lembaga SSR'] == ssr)])
                    val_cell = count_err if count_err > 0 else "-"
                    c_cell = ws_dash.cell(row=current_row, column=start_col_idx + i, value=val_cell)
                    c_cell.alignment = Alignment(horizontal="center")
                    total_row_err += count_err
                
                # Kolom Ringkasan Akhir
                j_cell = ws_dash.cell(row=current_row, column=col_jml, value=total_row_err if total_row_err > 0 else "-")
                j_cell.alignment = Alignment(horizontal="center")
                j_cell.fill = fill_orange_summary
                
                pct_val = (total_row_err / total_records_processed) if total_records_processed > 0 else 0
                p_cell = ws_dash.cell(row=current_row, column=col_pct, value=pct_val)
                p_cell.number_format = '0.00%'
                p_cell.alignment = Alignment(horizontal="center")
                p_cell.fill = fill_orange_summary
                
                # Apply Font & Border standard data
                for c in range(1, col_pct + 1):
                    cell = ws_dash.cell(row=current_row, column=c)
                    cell.font = font_data
                    cell.border = thin_border
            
            # Auto-fit lebar kolom
            for col in ws_dash.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = openpyxl.utils.get_column_letter(col[0].column)
                ws_dash.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)
            ws_dash.column_dimensions['B'].width = 65 # Kolom Indikator dibuat lebar
            
            # Sheet 2: LOG DETAIL KESALAHAN (UNTUK FIXING LAPANGAN)
            ws_detail = wb.create_sheet(title="Detail Kesalahan Per Baris")
            if not df_final_rekap.empty:
                # Susun kolom rapi untuk detail log per baris
                kolom_log = ['Nama File', 'Baris Excel', 'Lembaga SSR', 'Kode Petugas', 'Nama Kota', 'Nama Layanan', 'Tanggal', 'ID Klien', 'NIK', 'Tipe Sasaran', 'Keterangan review']
                df_detail_save = df_final_rekap[kolom_log]
                
                # Write to Excel sheet 2
                ws_detail.append(kolom_log)
                for r in df_detail_save.values.tolist():
                    ws_detail.append(r)
            else:
                ws_detail.append(["Status", "Catatan"])
                ws_detail.append(["CLEAN", "Selamat! Tidak ditemukan anomali input berdasarkan 50 indikator aktif."])
            
            wb.save(output_stream)
            
            st.session_state['data_unduhan'] = output_stream.getvalue()
            st.session_state['dashboard_tampilan'] = df_dashboard_view
            st.session_state['proses_selesai'] = True

    if st.session_state['proses_selesai']:
        st.success("🎉 Dashboard Ringkasan Matrik SSR Berhasil Dibuat!")
        
        # Tampilkan Pratinjau Dashboard di Aplikasi Streamlit
        st.subheader("📋 Pratinjau Matrik Lembaga SSR (Sesuai Berkas Lapangan)")
        st.dataframe(st.session_state['dashboard_tampilan'], use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📥 Unduh Berkas Dashboard Hasil Review")
        st.download_button(
            label="🟢 Download Excel Laporan Rekap Matrik SSR (.xlsx)",
            data=st.session_state['data_unduhan'],
            file_name=f"LAPORAN_REKAP_MATRIK_SSR_PKBI_{datetime.now().strftime('%d%m%y')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("👋 Panel siap. Silakan unggah satu atau beberapa file raw data Penjangkauan di sidebar kiri untuk menghasilkan berkas matrik SSR otomatis.")
