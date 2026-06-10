import streamlit as st
import pandas as pd
import datetime as dt

# --- BAGIAN 1: MESIN VALIDASI (Logika Blueprint Anda) ---
def jalankan_validasi(df_pj):
    # Logika untuk Penjangkauan (sesuai indikator Anda)
    tahun_sekarang = dt.datetime.now().year
    
    # Validasi 1: Tahun Tanggal PJ
    df_pj['Tanggal_PJ'] = pd.to_datetime(df_pj['Tanggal_PJ'], errors='coerce')
    df_pj['ERR_Tahun'] = df_pj['Tanggal_PJ'].dt.year.apply(lambda x: "Error: Bukan Tahun Ini" if x != tahun_sekarang else "Valid")
    
    # Validasi 2: Kode Petugas Kosong
    df_pj['ERR_Petugas'] = df_pj['Kode_Petugas'].isna().apply(lambda x: "Error: Kosong" if x else "Valid")
    
    # Validasi 3: IDKD 10 Digit
    df_pj['ERR_IDKD'] = df_pj['IDKD'].astype(str).apply(lambda x: "Error: Harus 10 Digit" if len(x) != 10 else "Valid")
    
    return df_pj

# --- BAGIAN 2: TAMPILAN DASHBOARD ---
st.set_page_config(page_title="Tools Review PKBI", layout="wide")
st.title("📊 Mesin Review Otomatis PKBI Jabar")

col1, col2 = st.columns(2)
with col1:
    file_ref = st.file_uploader("1. Database Referensi", type=["xlsx"])
with col2:
    files_review = st.file_uploader("2. Data Penjangkauan", type=["xlsx"], accept_multiple_files=True)

# --- BAGIAN 3: EKSEKUSI & DOWNLOAD ---
if files_review:
    for file in files_review:
        df = pd.read_excel(file)
        
        # Panggil Mesin Validasi
        df_hasil = jalankan_validasi(df)
        
        st.write(f"### Hasil Review: {file.name}")
        st.dataframe(df_hasil)
        
        # Tombol Download
        hasil_csv = df_hasil.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"Download Hasil {file.name}",
            data=hasil_csv,
            file_name=f"REVIEW_{file.name}.csv"
        )
