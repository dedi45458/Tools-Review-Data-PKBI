import streamlit as st
import pandas as pd
import io
import datetime

# ==========================================================
# 1. KONFIGURASI HALAMAN UTAMA STREAMLIT
# ==========================================================
st.set_page_config(
    page_title="Tools Review PKBI Jabar", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

st.title("📊 Tools Review Data Masal (Online) - PKBI Jabar")
st.markdown("""
Sistem otomatisasi pemeriksaan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat. 
Script ini mengonversi aturan *blueprint* formula Excel menjadi mesin validasi berbasis Python.
""")
st.divider()

# Inisialisasi Session State agar hasil eksekusi persisten
if 'proses_selesai' not in st.session_state:
    st.session_state['proses_selesai'] = False
if 'data_unduhan' not in st.session_state:
    st.session_state['data_unduhan'] = None
if 'rekap_tampilan' not in st.session_state:
    st.session_state['rekap_tampilan'] = None

# ==========================================================
# 2. INTERFACE UNGGAH FILE
# ==========================================================
st.sidebar.header("📁 Menu Unggah Berkas")
file_referensi = st.sidebar.file_uploader(
    "1️⃣ Database Referensi (.xlsx)", 
    type=["xlsx"], 
    help="Unggah database master (Data HIV+, Validasi NIK, dll) untuk keperluan VLOOKUP silang."
)

files_review = st.sidebar.file_uploader(
    "2️⃣ Data Lapangan (.xlsx, .xlsb)", 
    type=["xlsx", "xlsb"], 
    accept_multiple_files=True,
    help="Unggah satu atau banyak file bulanan Penjangkauan/Rujukan yang ingin diperiksa."
)

# ==========================================================
# 3. ENGINE VALIDASI: KONVERSI FORMULA EXCEL KE PYTHON
# ==========================================================
def jalankan_validasi_logika(df, df_ref=None, nama_file=""):
    """
    Fungsi inti yang menerjemahkan aturan logis dari Excel blueprint 
    ke dalam manipulasi matriks data menggunakan Pandas.
    """
    list_kesalahan = []
    
    # Standarisasi nama kolom agar tidak sensitif spasi/huruf besar-kecil
    df.columns = [str(c).strip() for c in df.columns]
    if df_ref is not None:
        df_ref.columns = [str(c).strip() for c in df_ref.columns]

    # Looping mendeteksi kesalahan per baris data
    for idx, row in df.iterrows():
        no_baris = idx + 2 # Konversi indeks Python (0) ke nomor baris Excel (2)
        
        # ------------------------------------------------------------------
        # INDIKATOR 1: Kolom Wajib Tidak Boleh Kosong (ISBLANK / COUNTA)
        # ------------------------------------------------------------------
        kolom_wajib = ['Nama', 'Tanggal Penjangkauan', 'Status', 'Kab/Kota']
        for kol in kolom_wajib:
            if kol in df.columns:
                nilai = str(row[kol]).strip()
                if nilai == "" or nilai == "nan" or pd.isna(row[kol]):
                    list_kesalahan.append({
                        "Nama File": nama_file, "Baris": no_baris, "Kolom Target": kol,
                        "Indikator Review": "Kolom Wajib Kosong",
                        "Deskripsi Kesalahan": f"Kolom {kol} tidak boleh kosong.",
                        "Nilai Eksisting": "-"
                    })

        # ------------------------------------------------------------------
        # INDIKATOR 2: Validasi Format & Panjang NIK (LEN <> 16)
        # Excel: =IF(LEN(TRIM(NIK))<>16; "Salah"; "Benar")
        # ------------------------------------------------------------------
        if 'NIK' in df.columns and not pd.isna(row['NIK']):
            nik_str = str(row['NIK']).replace(".0", "").strip() # bersihkan format float jika ada
            if nik_str != "" and nik_str != "nan" and len(nik_str) != 16:
                list_kesalahan.append({
                    "Nama File": nama_file, "Baris": no_baris, "Kolom Target": "NIK",
                    "Indikator Review": "Format NIK Tidak Valid",
                    "Deskripsi Kesalahan": f"Panjang NIK terdeteksi {len(nik_str)} digit. Harus tepat 16 digit.",
                    "Nilai Eksisting": nik_str
                })

        # ------------------------------------------------------------------
        # INDIKATOR 3: Logika Urutan Tanggal (Tanggal Rujukan < Tanggal Jangkau)
        # Excel: =IF(Tgl_Rujuk < Tgl_Jangkau; "Tanggal Terbalik"; "OK")
        # ------------------------------------------------------------------
        if 'Tanggal Penjangkauan' in df.columns and 'Tanggal Rujukan' in df.columns:
            tgl_jangkau = pd.to_datetime(row['Tanggal Penjangkauan'], errors='coerce')
            tgl_rujuk = pd.to_datetime(row['Tanggal Rujukan'], errors='coerce')
            
            if pd.notna(tgl_jangkau) and pd.notna(tgl_rujuk):
                if tgl_rujuk < tgl_jangkau:
                    list_kesalahan.append({
                        "Nama File": nama_file, "Baris": no_baris, "Kolom Target": "Tanggal Rujukan",
                        "Indikator Review": "Kronologi Tanggal Terbalik",
                        "Deskripsi Kesalahan": "Tanggal rujukan terjadi sebelum tanggal penjangkauan dilakukan.",
                        "Nilai Eksisting": f"Jangkau: {tgl_jangkau.strftime('%Y-%m-%d')} | Rujuk: {tgl_rujuk.strftime('%Y-%m-%d')}"
                    })

        # ------------------------------------------------------------------
        # INDIKATOR 4: Validasi Silang / VLOOKUP dengan Database Referensi
        # Excel: =IF(ISNA(VLOOKUP(ID_Pasien; Referensi!A:B; 1; FALSE)); "Tidak Valid"; "Valid")
        # ------------------------------------------------------------------
        if df_ref is not None and 'ID Pasien' in df.columns and 'ID Pasien' in df_ref.columns:
            id_target = str(row['ID Pasien']).strip()
            if id_target != "" and id_target != "nan":
                # Lakukan pengecekan apakah ID ada di kolom ID Pasien data referensi
                if id_target not in df_ref['ID Pasien'].astype(str).str.strip().values:
                    list_kesalahan.append({
                        "Nama File": nama_file, "Baris": no_baris, "Kolom Target": "ID Pasien",
                        "Indikator Review": "Data Tidak Terdaftar (Gagal VLOOKUP)",
                        "Deskripsi Kesalahan": "ID Pasien ini tidak ditemukan pada database referensi pusat.",
                        "Nilai Eksisting": id_target
                    })

        # 💡 SUNTIKAN FORMULA BARU: Tambahkan logika if-statement tambahan di sini 
        # sesuai baris indikator baru pada lembar kerja Excel Anda.

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. KONTROL ALUR EKSEKUSI DATA
# ==========================================================
if files_review:
    st.info(f"📊 **{len(files_review)} file** siap diproses sistem. Klik tombol di bawah untuk memulai pencocokan.")
    
    # Tombol Eksekusi Validasi Utama
    if st.button("🚀 Mulai Review & Terapkan Formula", type="primary"):
        with st.spinner("Sedang menerapkan formula kompilasi data..."):
            
            # Memuat lembar database referensi jika diunggah user
            df_ref = None
            if file_referensi:
                try:
                    df_ref = pd.read_excel(file_referensi)
                except Exception as e:
                    st.error(f"Gagal memuat database referensi: {e}")
            
            # Wadah penampung
            gabungan_rekap_kesalahan = []
            output_stream = io.BytesIO()
            
            with pd.ExcelWriter(output_stream, engine='openpyxl') as writer:
                for file in files_review:
                    try:
                        # Baca sheet aktif dari file instansi lapangan
                        df_target = pd.read_excel(file)
                        
                        # Jalankan mesin interpretasi logika
                        df_hasil = jalankan_validasi_logika(df_target, df_ref, nama_file=file.name)
                        
                        if not df_hasil.empty:
                            gabungan_rekap_kesalahan.append(df_hasil)
                        
                        # Simpan salinan sheet asli ke dalam output file baru
                        clean_sheet_name = file.name[:25].replace(".xlsx", "").replace(".xls", "")
                        df_target.to_excel(writer, sheet_name=clean_sheet_name, index=False)
                        
                    except Exception as e:
                        st.sidebar.error(f"Eror pada berkas {file.name}: {e}")
                
                # Konsolidasi seluruh temuan eror ke satu sheet utama
                if gabungan_rekap_kesalahan:
                    df_final_rekap = pd.concat(gabungan_rekap_kesalahan, ignore_index=True)
                else:
                    df_final_rekap = pd.DataFrame(columns=['Nama File', 'Status', 'Catatan'])
                    df_final_rekap.loc[0] = ['Semua Berkas', 'CLEAN', 'Tidak ditemukan anomali / kesalahan input data.']
                
                # Tulis lembar REKAP KESALAHAN di posisi lembar paling awal
                df_final_rekap.to_excel(writer, sheet_name="REKAP KESALAHAN", index=False)
            
            # Simpan status ke dalam session state agar tidak hilang saat diunduh
            st.session_state['data_unduhan'] = output_stream.getvalue()
            st.session_state['rekap_tampilan'] = df_final_rekap
            st.session_state['proses_selesai'] = True

    # Menampilkan tabel rekap kesalahan jika proses berhasil dilakukan
    if st.session_state['proses_selesai']:
        st.success("🎉 Analisis selesai! Lembar kendali kesalahan berhasil dibentuk.")
        
        # Tampilkan visualisasi tabel langsung pada browser streamlit
        st.subheader("📋 Ringkasan Indikator Kesalahan Terdeteksi")
        st.dataframe(st.session_state['rekap_tampilan'], use_container_width=True)
        
        # Penyediaan tombol download hasil kompilasi
        st.divider()
        st.subheader("📥 Unduh File Laporan")
        st.download_button(
            label="🟢 Download Dokumen Hasil Review (.xlsx)",
            data=st.session_state['data_unduhan'],
            file_name="REKAP_HASIL_REVIEW_PKBI_JABAR.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    # Komponen visual edukasi awal jika aplikasi kosong data
    st.info("👋 Selamat datang! Silakan unggah file database referensi dan data bulanan pada panel menu sebelah kiri untuk memulai pemeriksaan otomatis.")
