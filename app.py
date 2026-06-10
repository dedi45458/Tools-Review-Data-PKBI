import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

# ==========================================================
# 1. KONFIGURASI UTAMA STREAMLIT ONLINE
# ==========================================================
st.set_page_config(page_title="Tools Review PKBI Jabar - Format Tabel Baru", layout="wide")

st.title("📊 Tools Review Data Masal (Online) - PKBI Jabar")
st.markdown("""
Sistem otomatisasi penelaahan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat.
**Format Tabel Output: Disesuaikan dengan Kebutuhan Pengguna**
""")
st.divider()

if 'proses_selesai' not in st.session_state:
    st.session_state['proses_selesai'] = False
if 'data_unduhan' not in st.session_state:
    st.session_state['data_unduhan'] = None
if 'rekap_tampilan' not in st.session_state:
    st.session_state['rekap_tampilan'] = None

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

# ==========================================================
# 3. HELPER FUNCTION UNTUK STRIP & CEK KODE MULTI-VALUE
# ==========================================================
def cek_kode(teks_kolom, kode_target):
    if pd.isna(teks_kolom):
        return False
    clean_str = str(teks_kolom).replace("'", "").replace(" ", "")
    list_kode = clean_str.split(",")
    return str(kode_target) in list_kode

# ==========================================================
# 4. ENGINE VALIDASI UTAMA DENGAN FORMAT KOLOM REKAP BARU
# ==========================================================
def jalankan_review_penjangkauan(df_asli, df_ref=None, nama_file=""):
    list_kesalahan = []
    if df_asli.empty:
        return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    # Deteksi baris petunjuk pengisian (Bypass baris indeks 0 jika template)
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    tahun_sekarang = datetime.now().year
    hari_ini = pd.Timestamp(datetime.now().date())
    medsoc_keywords = ['whatsapp', 'wa', 'facebook', 'fb', 'instagram', 'ig', 'michat', 'blued', 'tinder', 'hornet', 'telegram', 'tantan', 'grindr', 'twitter']

    # Pre-load database pembanding tahun lalu
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

    # Hitung frekuensi kontak klien
    id_counts = df.iloc[start_row_idx:]['ID Klien'].astype(str).str.strip().value_counts().to_dict()

    # LOOPING PEMERIKSAAN PER BARIS DATA EXCEL
    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        no_excel_row = idx + 2  # Nomor baris fisik Excel
        
        # Ekstraksi Data Identitas Utama untuk Kebutuhan Tabel Anda
        v_ssr = str(row.get('Lembaga SSR', '')).strip() if pd.notna(row.get('Lembaga SSR')) else ''
        v_petugas = str(row.get('Kode Petugas', '')).replace("'", "").strip() if pd.notna(row.get('Kode Petugas')) else ''
        v_kota = str(row.get('Nama Kota', '')).strip() if pd.notna(row.get('Nama Kota')) else ''
        v_layanan = str(row.get('Nama Layanan', '')).strip() if pd.notna(row.get('Nama Layanan')) else '-' # Jika kolom kosong diisi tanda strip
        v_tanggal = str(row.get('Tanggal', '')).split(' ')[0] if pd.notna(row.get('Tanggal')) else ''
        id_klien = str(row.get('ID Klien', '')).replace("'", "").strip() if pd.notna(row.get('ID Klien')) else ''
        nik = str(row.get('NIK', '')).replace('.0', '').replace("'", "").strip() if pd.notna(row.get('NIK')) else ''
        
        # Penanganan Nama Kolom Tipe Sasaran / Tipe Klien
        v_tipe_sasaran = str(row.get('Tipe Sasaran', row.get('Tipe Klien', ''))).replace('.0', '').strip()

        # Variabel Logika Internal Pengecekan
        umur = row.get('Umur', None)
        jk = str(row.get('Jenis Kelamin', '')).replace('.0', '').strip()
        jns_kontak = str(row.get('Jenis Kontak', '')).replace('.0', '').strip()
        jns_kegiatan = str(row.get('Jenis Kegiatan', '')).strip()
        lokasi = str(row.get('Lokasi Outreach / Jenis Sosial Media', '')).strip()
        info_diberikan = str(row.get('Informasi Yang diberikan', '')).strip()
        rujukan = str(row.get('Rujukan', '')).strip()
        no_hp = str(row.get('No. HP / Nama Akun', '')).strip()
        vc1 = str(row.get('Virtual & Tatap Muka', '')).replace('.0', '').strip()

        # Parsing Logistik
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

        # Fungsi Pengumpul Log - DISESUAIKAN DENGAN STRUKTUR BARU ANDA
        def tambah_log(nama_indikator, deskripsi_detail):
            list_kesalahan.append({
                "Nama File": nama_file,
                "Baris Excel": no_excel_row,
                "Lembaga SSR": v_ssr,
                "Kode Petugas": v_petugas,
                "Nama Kota": v_kota,
                "Nama Layanan": v_layanan,
                "Tanggal": v_tanggal,
                "ID Klien": id_klien,
                "NIK": nik,
                "Tipe Sasaran": v_tipe_sasaran,
                "Keterangan review": f"[{nama_indikator}] {deskripsi_detail}"
            })

        # ==========================================================
        # JALUR LOGIKA VALIDASI (50 INDIKATOR)
        # ==========================================================
        
        if pd.notna(tgl_p):
            if tgl_p.year != tahun_sekarang:
                tambah_log("Tahun Tanggal Salah", f"Tahun pelaksanaan ({tgl_p.year}) tidak sesuai tahun berjalan ({tahun_sekarang})")
            if tgl_p > hari_ini:
                tambah_log("Tanggal Melebihi Hari Ini", "Tanggal penjangkauan berada di masa depan")

        if pd.isna(row.get('Kode Petugas')) or str(row.get('Kode Petugas')).strip() == '':
            tambah_log("Kode Petugas Kosong", "Kolom kode petugas tidak terisi")

        if id_klien and id_klien != 'nan':
            if len(id_klien) != 10:
                tambah_log("IDKD Bukan 10 Digit", f"Panjang IDKD {len(id_klien)} karakter (Harus tepat 10 digit)")
            if '.' in id_klien:
                tambah_log("IDKD Mengandung Titik", "Ditemukan tanda baca titik (.) pada IDKD")
            if ' ' in id_klien:
                tambah_log("IDKD Mengandung Spasi", "Ditemukan spasi kosong di dalam kode IDKD")
            
            if len(id_klien) == 10:
                nama_part = id_klien[:4]
                tgl_part = id_klien[4:]
                if not nama_part.isalpha():
                    tambah_log("Digit Nama IDKD Salah", "4 Karakter awal IDKD harus berupa huruf alfabet")
                if not tgl_part.isdigit():
                    tambah_log("Digit Tgl Lahir IDKD Salah", "6 Karakter akhir IDKD harus berupa angka (DDMMYY)")

        if df_ref is not None:
            if id_klien in ref_id_to_nik and ref_id_to_nik[id_klien] != nik:
                tambah_log("ID Sama NIK Berbeda (Konfirmasi)", f"ID terikat dengan NIK {ref_id_to_nik[id_klien]} di data semester lalu")
            if nik in ref_nik_to_id and ref_nik_to_id[nik] != id_klien:
                tambah_log("NIK Sama ID Berbeda (Konfirmasi)", f"NIK terikat dengan ID {ref_nik_to_id[nik]} di data semester lalu")

        if pd.notna(umur) and str(umur).strip() != '':
            try:
                val_umur = float(umur)
                if val_umur < 16: tambah_log("Usia di Bawah 16 Tahun (Konfirmasi)", "Usia klien terlalu muda (< 16 tahun)")
                if val_umur > 70: tambah_log("Usia di Atas 70 Tahun (Konfirmasi)", "Usia klien tergolong lansia (> 70 tahun)")
            except: pass

        if id_klien and len(id_klien) == 10 and len(nik) == 16:
            if id_klien[8:10] != nik[10:12]:
                tambah_log("Tahun Lahir IDKD vs NIK Berbeda", "Tahun lahir di IDKD tidak sinkron dengan NIK")

        if nik and nik != 'nan':
            if len(nik) != 16:
                tambah_log("NIK Bukan 16 Digit (Konfirmasi)", f"Panjang NIK terdeteksi {len(nik)} digit")
            if nik.startswith('00') or '000000' in nik:
                tambah_log("Kesalahan Penulisan NIK (00)", "Format nomor NIK terindikasi dummy/salah catat")

        if len(nik) == 16 and jk in ['1', '2']:
            try:
                dd_nik = int(nik[6:8])
                if jk == '2' and dd_nik <= 40: tambah_log("NIK Harusnya Perempuan", "Klien Perempuan (2) tapi digit NIK menunjukkan Laki-laki")
                elif jk == '1' and dd_nik > 40: tambah_log("NIK Harusnya Laki-laki", "Klien Laki-laki (1) tapi digit NIK menunjukkan Perempuan")
            except: pass

        if (v_tipe_sasaran in ['1304', '1301']) and jk == '2':
            tambah_log("LSL/Waria Tapi Perempuan", f"Tipe Sasaran ({v_tipe_sasaran}) bertentangan dengan Jenis Kelamin Perempuan")

        is_vo = (jns_kontak == '3')
        any_medsoc_in_lokasi = any(kw in lokasi.lower() for kw in medsos_keywords)

        if jns_kontak in ['1', '2']:
            if vc1 == '' or vc1 == 'nan':
                tambah_log("VC1 Tidak Diisi", "Kontak lapangan wajib mengisi instrumen kolom Virtual & Tatap Muka")
            if any_medsoc_in_lokasi:
                tambah_log("Tatap Muka Tapi Lokasi Medsos", "Kontak lapangan dilaporkan namun lokasi outreach diisi nama aplikasi medsos")

        if is_vo:
            if vc1 == '1': tambah_log("VO Tapi VC1 Diisi Angka 1", "Kontak bertipe VO tidak boleh mengisi VC1 dengan angka 1 (Ya)")
            if lokasi and not any_medsoc_in_lokasi: tambah_log("Lokasi VO Bukan Medsos", "Kontak VO namun kolom lokasi tidak mencantumkan nama platform medsos")
            if log_jar > 0: tambah_log("VO Tapi Menyerahkan Jarum", "Kontak VO (Virtual) tidak logis menyerahkan Jarum Suntik fisik")
            if log_kon > 0 or log_pel > 0 or log_swab > 0: tambah_log("VO Menerima Logistik Selain KIE", "Kontak VO hanya diperbolehkan menyalurkan KIE digital")
            if no_hp == '' or no_hp == 'nan' or no_hp == "'": tambah_log("Akun / No HP VO Kosong", "Kontak VO wajib mengisi identitas akun media sosial")

        if lokasi and lokasi != 'nan':
            if len(lokasi) == 10 and lokasi[:4].isalpha() and lokasi[4:].isdigit():
                tambah_log("Lokasi Outreach Diisi IDKD", "Kolom lokasi tertukar diisi kode IDKD klien")
            if len(lokasi) < 17 and not is_vo:
                tambah_log("Lokasi Kurang Spesifik (Konfirmasi)", "Deskripsi nama jalan/lokasi terlalu pendek (< 17 huruf)")
            if re.search(r'(08\d{8,11})|(\+62\d{8,11})', lokasi.replace('-', '').replace(' ', '')):
                tambah_log("Lokasi Diisi Nomor HP", "Kolom lokasi outreach terindikasi diisi nomor seluler")

        is_pwid = (v_tipe_sasaran == '1401')
        
        if not is_pwid:
            if cek_kode(info_diberikan, '8') or cek_kode(info_diberikan, '9') or cek_kode(jns_kegiatan, '8') or cek_kode(jns_kegiatan, '9'):
                tambah_log("Bukan PWID Dapat Info LASS/PTRM", "Klien non-penasun terdata mendapatkan materi edukasi jarum/metadon (8/9)")
            if log_jar > 0: tambah_log("Non-PWID Menerima Jarum Suntik", "Distribusi jarum suntik steril bocor ke kelompok non-penasun")
            if log_swab > 0: tambah_log("Non-PWID Menerima Alkohol Swab", "Distribusi alkohol swab bocor ke kelompok non-penasun")
            if jarum_kembali > 0: tambah_log("Non-PWID Menyerahkan Jarum Kembali", "Tercatat angka pengembalian jarum suntik untuk non-penasun")
            if cek_kode(rujukan, '3') or cek_kode(rujukan, '4'): tambah_log("Bukan Penasun Rujukan 3/4", "Klien non-penasun diberi kertas rujukan layanan LASS/PTRM")
        else:
            if log_jar == 0 and not is_vo: tambah_log("PWID Lapangan Tidak Menerima Jarum", "Klien Penasun tidak dibekali pasokan alat suntik steril")
            if log_swab == 0 and not is_vo: tambah_log("PWID Lapangan Tidak Menerima Swab", "Klien Penasun tidak dibekali alkohol swab")

        if (v_tipe_sasaran in ['1304', '1301', '1401']) and (cek_kode(info_diberikan, '6') or cek_kode(jns_kegiatan, '6')):
            tambah_log("Popkun Utama Menerima Info PMTCT", "Kelompok populasi kunci LSL/TG/PWID terdata menerima informasi PMTCT (6)")

        if log_kie > 10: tambah_log("Jumlah KIE Tidak Wajar", "Input angka penyerahan KIE sangat ekstrem")
        if log_kon > 144: tambah_log("Jumlah Kondom Tidak Wajar", "Input pembagian kondom melebihi batas gross (>144)")
        if log_pel > 50: tambah_log("Jumlah Pelicin Tidak Wajar", "Input pembagian cairan pelicin terlalu tinggi")
        if log_jar > 100: tambah_log("Jumlah Jarum Tidak Wajar", "Input pembagian jarum steril lapangan sangat masif")
        if log_swab > 100: tambah_log("Jumlah Swab Tidak Wajar", "Input pembagian alkohol swab lapangan sangat masif")

        if info_diberikan == '' or info_diberikan == 'nan' or info_diberikan == "'":
            tambah_log("Tidak Ada Informasi Diberikan", "Klien terdata tanpa rekam jejak edukasi/informasi materi")
        if log_kie == 0 and log_kon == 0 and log_pel == 0 and log_jar == 0 and log_swab == 0:
            tambah_log("Logistik Kosong (Konfirmasi)", "Penjangkauan terekam tanpa adanya penyerahan materi/logistik fisik")
        if rujukan == '' or rujukan == 'nan' or rujukan == "'":
            tambah_log("Tidak Ada Rujukan Diberikan", "Kolom rujukan kosong / tidak ada faskes dirujuk")

        if id_klien and id_counts.get(id_klien, 0) > 1:
            df_klien_ini = df[df['ID Klien'].astype(str).str.replace("'", "").str.strip() == id_klien]
            pernah_dapat_info_hiv = any(cek_kode(inf, '1') for inf in df_klien_ini['Informasi Yang diberikan'].values) or any(cek_kode(keg, '1') for keg in df_klien_ini['Jenis Kegiatan'].values)
            pernah_dapat_rujuk_tes = any(cek_kode(ruj, '2') for ruj in df_klien_ini['Rujukan'].values)
            if not pernah_dapat_info_hiv:
                tambah_log("Kontak >1x Tanpa Info HIV", f"Klien dikontak sebanyak {id_counts[id_klien]}x, tapi tidak pernah diberikan edukasi HIV (1)")
            if not pernah_dapat_rujuk_tes:
                tambah_log("Kontak >1x Tanpa Rujukan Tes HIV", f"Klien dikontak sebanyak {id_counts[id_klien]}x, tapi tidak pernah dirujuk VCT (2)")

        if cek_kode(jns_kegiatan, '13') and not cek_kode(info_diberikan, '13'):
            tambah_log("Layanan CBS Tanpa Info CBS", "Jenis kegiatan bermodus CBS (13), namun info materi CBS tidak terinput")
        if (cek_kode(rujukan, '5') or cek_kode(jns_kegiatan, '10')) and not (cek_kode(info_diberikan, '10') or cek_kode(jns_kegiatan, '10')):
            tambah_log("Ada Rujukan/Kegiatan PrEP Tanpa Info PrEP", "Ada intervensi/rujukan PrEP, namun tidak dibarengi edukasi materi PrEP (10)")
        if cek_kode(jns_kegiatan, '10') and not cek_kode(rujukan, '5'):
            tambah_log("Menerima Layanan PrEP Tanpa Rujukan PrEP", "Status jenis kegiatan adalah PrEP (10), namun kolom Rujukan PrEP (5) kosong")

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 5. PANEL KONTROL EKSEKUSI DATA STREAMLIT
# ==========================================================
if files_review:
    st.success(f"📂 Berhasil mendeteksi {len(files_review)} berkas penjangkauan.")
    if file_referensi:
        st.info("💡 Berkas riwayat tahun lalu aktif. Sistem siap mengaudit sinkronisasi kebenaran ID vs NIK secara historis.")
    else:
        st.warning("⚠️ Berkas pembanding semester lalu kosong. Deteksi indikator nomor 9 & 10 otomatis dilewati.")

    tombol_eksekusi = st.button("🚀 Jalankan Sistem Validasi Data Masal", type="primary")
    
    if tombol_eksekusi:
        with st.spinner("Sedang mengevaluasi ratusan ribu data berdasarkan format tabel baru..."):
            df_ref = None
            if file_referensi:
                try: df_ref = pd.read_excel(file_referensi)
                except Exception as e: st.error(f"Gagal membaca berkas pembanding historis: {e}")
            
            semua_rekap_kesalahan = []
            output_stream = io.BytesIO()
            
            with pd.ExcelWriter(output_stream, engine='openpyxl') as writer:
                for file in files_review:
                    try:
                        df_target = pd.read_excel(file)
                        df_rekap_file = jalankan_review_penjangkauan(df_target, df_ref, nama_file=file.name)
                        
                        if not df_rekap_file.empty:
                            semua_rekap_kesalahan.append(df_rekap_file)
                        
                        clean_sheet_name = file.name[:25].replace(".xlsx", "")
                        df_target.to_excel(writer, sheet_name=clean_sheet_name, index=False)
                    except Exception as e:
                        st.error(f"Gagal mengevaluasi berkas {file.name}. Pesan Eror: {str(e)}")
                
                if semua_rekap_kesalahan:
                    df_final_rekap = pd.concat(semua_rekap_kesalahan, ignore_index=True)
                else:
                    # Buat dataframe kosong dengan susunan kolom persis permintaan Anda
                    df_final_rekap = pd.DataFrame(columns=[
                        'Nama File', 'Baris Excel', 'Lembaga SSR', 'Kode Petugas', 
                        'Nama Kota', 'Nama Layanan', 'Tanggal', 'ID Klien', 'NIK', 'Tipe Sasaran', 'Keterangan review'
                    ])
                    df_final_rekap.loc[0] = ['Semua Berkas', '-', '-', '-', '-', '-', '-', '-', '-', '-', 'CLEAN! Tidak ditemukan anomali.']
                
                # Susun ulang urutan kolom untuk memastikan kecocokan mutlak
                kolom_order = [
                    'Nama File', 'Baris Excel', 'Lembaga SSR', 'Kode Petugas', 
                    'Nama Kota', 'Nama Layanan', 'Tanggal', 'ID Klien', 'NIK', 'Tipe Sasaran', 'Keterangan review'
                ]
                df_final_rekap = df_final_rekap[kolom_order]
                df_final_rekap.to_excel(writer, sheet_name="REKAP KESALAHAN", index=False)
            
            st.session_state['data_unduhan'] = output_stream.getvalue()
            st.session_state['rekap_tampilan'] = df_final_rekap
            st.session_state['proses_selesai'] = True

    if st.session_state['proses_selesai']:
        st.success("🎉 Analisis selesai! Pratinjau daftar kesalahan data ditemukan dengan format kolom baru:")
        st.dataframe(st.session_state['rekap_tampilan'], use_container_width=True)
        st.divider()
        st.subheader("📥 Unduh Laporan Audit Kualitas Data")
        st.download_button(
            label="🟢 Download Excel Rekap Kesalahan (.xlsx)",
            data=st.session_state['data_unduhan'],
            file_name="LAPORAN_REKAP_KESALAHAN_PKBI.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("👋 Panel siap. Silakan unggah berkas data lapangan pada menu sidebar di sebelah kiri untuk memulai audit otomatis.")
