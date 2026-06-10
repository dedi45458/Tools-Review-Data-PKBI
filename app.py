import streamlit as st
import pandas as pd
import io

# ==========================================================
# 1. KONFIGURASI HALAMAN & TAMPILAN UTAMA
# ==========================================================
st.set_page_config(page_title="Tools Review PKBI Jabar", layout="wide")

st.title("📊 Tools Review Data Masal (Online)")
st.write("Sistem otomatisasi pemeriksaan kualitas data Penjangkauan dan Rujukan PKBI Jawa Barat.")
st.divider()

# Inisialisasi Session State agar data hasil eksekusi tidak hilang saat interaksi UI
if 'file_proses_selesai' not in st.session_state:
    st.session_state['file_proses_selesai'] = False
if 'output_excel_data' not in st.session_state:
    st.session_state['output_excel_data'] = None

# ==========================================================
# 2. MENU UNGGAH FILE (LAYOUT 2 KOLOM)
# ==========================================================
st.subheader("📁 Menu Unggah File")

kolom_kiri, kolom_kanan = st.columns(2)

with kolom_kiri:
    st.markdown("### 1️⃣ Database Referensi")
    st.caption("Unggah data master / acuan (misal: Database HIV+, Validasi NIK, dll)")
    file_referensi = st.file_uploader(
        "Pilih file database referensi", 
        type=["xlsx"], 
        key="upload_referensi"
    )

with kolom_kanan:
    st.markdown("### 2️⃣ Data yang Direview")
    st.caption("Unggah data lapangan bulanan (File Penjangkauan & Rujukan sekaligus)")
    files_review = st.file_uploader(
        "Pilih file penjangkauan & rujukan", 
        type=["xlsx", "xlsb"], 
        accept_multiple_files=True, 
        key="upload_review"
    )

st.divider()

# ==========================================================
# 3. FUNGSI LOGIKA VALIDASI (KONVERSI FORMULA EXCEL)
# ==========================================================
def jalankan_validasi_logika(df, df_ref=None):
    """
    Fungsi ini merepresentasikan sheet 'rekap kesalahan' dan 'blueprint formula'.
    Setiap indikator kesalahan dikonversi dari formula Excel ke Pandas Python.
    """
    list_kesalahan = []
    
    # Pastikan nama kolom disesuaikan dengan header file asli Anda
    # Contoh Indikator 1: Validasi Format NIK (Harus 16 Digit) -> Padanan Excel: =IF(LEN(A2)<>16; "Salah"; "Benar")
    if 'NIK' in df.columns:
        invalid_nik = df[df['NIK'].astype(str).str.strip().str.len() != 16]
        for idx, row in invalid_nik.iterrows():
            list_kesalahan.append({
                "Baris/Row": idx + 2, # +2 karena index pandas mulai dari 0 dan baris 1 adalah header Excel
                "Kolom Target": "NIK",
                "Indikator Review": "Format NIK Tidak Valid",
                "Deskripsi Kesalahan": f"Panjang NIK adalah {len(str(row['NIK']))} digit (Harus 16 digit)",
                "Nilai Eksisting": row['NIK']
            })

    # Contoh Indikator 2: Keselarasan Tanggal -> Padanan Excel: =IF(Tgl_Rujukan < Tgl_Penjangkauan; "Eror"; "OK")
    if 'Tanggal Penjangkauan' in df.columns and 'Tanggal Rujukan' in df.columns:
        df['Tanggal Penjangkauan'] = pd.to_datetime(df['Tanggal Penjangkauan'], errors='coerce')
        df['Tanggal Rujukan'] = pd.to_datetime(df['Tanggal Rujukan'], errors='coerce')
        
        invalid_date = df[df['Tanggal Rujukan'] < df['Tanggal Penjangkauan']]
        for idx, row in invalid_date.iterrows():
            list_kesalahan.append({
                "Baris/Row": idx + 2,
                "Kolom Target": "Tanggal Rujukan",
                "Indikator Review": "Tanggal Rujukan Tidak Logis",
                "Deskripsi Kesalahan": "Tanggal rujukan mendahului tanggal penjangkauan",
                "Nilai Eksisting": f"Jangkau: {row['Tanggal Penjangkauan'].strftime('%Y-%m-%d')}, Rujuk: {row['Tanggal Rujukan'].strftime('%Y-%m-%d')}"
            })

    # Contoh Indikator 3: Integrasi VLOOKUP dengan Database Referensi
    # Excel: =VLOOKUP(B2; 'Database Referensi'!A:B; 2; FALSE) -> Jika #N/A berarti data rujukan tidak ada di master
    if df_ref is not None and 'ID Pasien' in df.columns and 'ID Pasien' in df_ref.columns:
        # Cari ID Pasien di df yang tidak ada di df_ref
        id_missing = df[~df['ID Pasien'].isin(df_ref['ID Pasien'])]
        for idx, row in id_missing.iterrows():
            list_kesalahan.append({
                "Baris/Row": idx + 2,
                "Kolom Target": "ID Pasien",
                "Indikator Review": "ID Tidak Terdaftar di Database Referensi",
                "Deskripsi Kesalahan": "ID Pasien tidak ditemukan pada data master referensi (Gagal VLOOKUP)",
                "Nilai Eksisting": row['ID Pasien']
            })
            
    # 💡 SILAKAN TAMBAHKAN INDIKATOR LAIN SESUAI BLUEPRINT ANDA DI SINI 💡
    # Gunakan pola penkondisian df[kondisi_salah] lalu loop ke list_kesalahan
    
    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 4. TOMBOL EKSEKUSI UTAMA
# ==========================================================
if files_review:
    st.success(f"✅ Berhasil memuat {len(files_review)} file untuk direview.")
    
    if file_referensi:
        st.info("💡 Sistem mendeteksi Database Referensi aktif. Rumus berbasis VLOOKUP siap dijalankan.")
    else:
        st.warning("⚠️ Perhatian: Anda belum mengunggah Database Referensi. Indikator review yang membutuhkan data pembanding akan dilewati otomatis.")
    
    # TOMBOL EKSEKUSI VALIDASI
    tombol_eksekusi = st.button("🚀 Jalankan Validasi & Review Data", type="primary")
    
    if tombol_eksekusi:
        with st.spinner("Sedang mengeksekusi logika rumus dan menyusun rekap kesalahan..."):
            
            # Membaca database referensi jika diunggah
            df_ref = None
            if file_referensi:
                try:
                    df_ref = pd.read_excel(file_referensi)
                except Exception as e:
                    st.error(f"Gagal membaca data referensi: {e}")
            
            # Memory stream untuk menampung output excel baru
            output_stream = io.BytesIO()
            
            # List untuk menampung semua dataframe rekap kesalahan dari seluruh file
            semua_rekap_kesalahan = []
            
            # Gunakan ExcelWriter untuk membuat file Excel multi-sheet
            with pd.ExcelWriter(output_stream, engine='openpyxl') as writer:
                
                for file in files_review:
                    try:
                        # Baca sheet utama dari file yang direview
                        df_target = pd.read_excel(file)
                        
                        # Jalankan fungsi validasi indikator
                        df_hasil_rekap = jalankan_validasi_logika(df_target, df_ref)
                        
                        if not df_hasil_rekap.empty:
                            df_hasil_rekap['Nama File'] = file.name
                            semua_rekap_kesalahan.append(df_hasil_rekap)
                        
                        # Beri tanda status validasi sederhana di dalam sheet data asli
                        df_target['STATUS_REVIEW'] = "Selesai Diperiksa"
                        
                        # Simpan data asli ke dalam sheet tersendiri (nama sheet dipotong agar aman maks 31 karakter)
                        sheet_name = file.name[:25].replace(".xlsx", "").replace(".xls", "")
                        df_target.to_excel(writer, sheet_name=sheet_name, index=False)
                        
                        st.write(f"🔹 File **{file.name}** selesai diproses.")
                    except Exception as e:
                        st.error(f"❌ Gagal memproses file {file.name}. Error: {str(e)}")
                
                # Menggabungkan rekap kesalahan dari semua file ke sheet tersendiri
                if semua_rekap_kesalahan:
                    df_rekap_total = pd.concat(semua_rekap_kesalahan, ignore_index=True)
                    # Mengatur urutan kolom agar rapi
                    kolom_order = ['Nama File', 'Baris/Row', 'Kolom Target', 'Indikator Review', 'Deskripsi Kesalahan', 'Nilai Eksisting']
                    df_rekap_total = df_rekap_total[kolom_order]
                else:
                    # Jika tidak ada kesalahan sama sekali
                    df_rekap_total = pd.DataFrame(columns=['Nama File', 'Status', 'Catatan'])
                    df_rekap_total.loc[0] = ['Semua File', 'Bersih', 'Tidak ditemukan kesalahan data berdasarkan indikator aktif.']
                
                # Simpan sheet Rekap Kesalahan di urutan paling depan/awal file excel
                df_rekap_total.to_excel(writer, sheet_name="REKAP KESALAHAN", index=False)
            
            # Simpan hasil akhir ke session state
            st.session_state['output_excel_data'] = output_stream.getvalue()
            st.session_state['file_proses_selesai'] = True
            
            st.success("🎉 Proses Eksekusi Selesai! Pratinjau Lembar Rekap Kesalahan ada di bawah ini:")
            st.dataframe(df_rekap_total, use_container_width=True)

# ==========================================================
# 5. MENU UNDUH HASIL REVIEW
# ==========================================================
if st.session_state['file_proses_selesai']:
    st.divider()
    st.subheader("📥 Unduh Hasil Review")
    st.write("Silakan unduh dokumen Excel yang telah berisi sheet **'REKAP KESALAHAN'** di bagian paling awal.")
    
    st.download_button(
        label="🟢 Download Excel Hasil Review (.xlsx)",
        data=st.session_state['output_excel_data'],
        file_name="REKAP_HASIL_REVIEW_PKBI_JABAR.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    if not files_review:
        st.info("👋 Selamat datang! Silakan unggah berkas data pada menu di atas untuk memulai analisis.")
