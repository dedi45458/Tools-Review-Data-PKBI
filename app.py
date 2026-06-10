import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from supabase import create_client, Client

# ==========================================================
# 0. KONFIGURASI SUPABASE (Sesuaikan dengan Akun Anda)
# ==========================================================
# Ganti dengan URL dan Anon Key Supabase Anda sendiri
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
    "Tahun dalam tanggal penjangkauan lebih besar/kecil dari tahun sekarang",
    "Kode Petugas Kosong", "Tanggal lebih besar dari tanggal hari ini",
    "IDKD kurang/lebih dari 10 digit karakter", "Digit nama kurang/lebih dari 4 digit karakter",
    "Digit tanggal lahir lebih/kurang dari 6 digit angka", "Ada tanda titik (.) pada penulisan IDKD",
    "Ada spasi pada penulisan IDKD", "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)",
    "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)", "Tahun Lahir KD terlalu muda (2014 -sekarang)",
    "Usia KD dibawah 16 tahun (konfirmasi)", "Usia KD diatas 70 tahun (konfirmasi)",
    "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)", "NIK kurang/lebih dari 16 digit (konfirmasi)",
    "Kesalahan dalam penulisan NIK (00) (konfirmasi)", "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)",
    "LSL/Waria tapi jenis kelamin perempuan", "Jenis kontak dengan Jenis Kegiatan tidak sesuai",
    "Jenis kontak Individual/kelompok tapi kolom Virtual dan Tatap Muka (VC1) tidak diisi",
    "Penjangkauan tatap muka tapi lokasi outreach diindikasi ada nama medsos", "Lokasi outreach diisi IDKD",
    "Lokasi outreach diindikasi kurang spesifik atau kurang detil (digit huruf <17 digit) (konfirmasi)",
    "Lokasi outreach indikasi diisi nomer HP", "Bukan PWID mendapatkan info 8 atau 9 (LASS, PTRM)",
    "LSL/TG/PWID menerima informasi PMTC (konfirmasi)", "Konfirmasi jumlah KIE yang diberikan adalah wajar",
    "Konfirmasi jumlah kondom yang diberikan adalah wajar", "Konfirmasi jumlah pelicin yang diberikan adalah wajar",
    "Konfirmasi jumlah jarum yang diberikan adalah wajar", "Konfirmasi jumlah alkohol SWAB yang diberikan adalah wajar",
    "VO tapi kolom Virtual dan Tatap Muka (VC1) diisi angka 1", "VO tapi lokasi outreach bukan nama medsos/kurang tepat mencatat nama aplikasi medsos",
    "VO tapi menyerahkan jarum", "VO menerima logistik selain KIE", "VO tapi nama akun /No. Hp tidak diisi",
    "Tidak ada informasi satupun yang diberikan / tidak diisi", "KD dikontak lebih dari 1x tapi tidak mendapat informasi HIV",
    "KD telah menerima layanan CBS tapi tidak ada informasi CBS", "KD ada rujukan PrEp di penjangkauan tapi tidak ada informasi PrEp",
    "KD telah menerima layanan PrEp tapi tidak ada rujukan PrEp di penjangkauan", "Logistik kosong (Konfirmasi)",
    "Tipe klien PWID tapi tidak menerima jarum (konfirmasi)", "Tipe klien PWID tapi tidak menerima alkohol SWAB (konfirmasi)",
    "Popkun selain PWID menerima jarum suntik", "Popkun selain PWID menerima alkohol swab",
    "Popkun selain PWID menyerahkan jarum", "Tidak ada rujukan yang diberikan satupun / tidak diisi",
    "KD dikontak lebih dari 1x tetapi tidak ada Rujukan Tes HIV", "Bukan penasun rujukan 3,4"
]

# ==========================================================
# 2. SIDEBAR INPUT
# ==========================================================
with st.sidebar:
    st.markdown("### 📁 Menu Unggah Berkas")
    file_referensi = st.file_uploader("1️⃣ Data HIV+ Semester / Tahun Lalu (.xlsx)", type=["xlsx"])
    st.markdown("---")
    files_review = st.file_uploader("2️⃣ Raw Data Penjangkauan / Rujukan (.xlsx)", type=["xlsx"], accept_multiple_files=True)

# ==========================================================
# 3. ENGINE PENGAMBILAN LOG MEMORI DATABASE (SUPABASE)
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
# 4. ENGINE VALIDASI UTAMA
# ==========================================================
def jalankan_review_data(df_asli, df_ref=None):
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    is_file_rujukan = any('RUJUKAN' in str(c).upper() for c in df.columns) or any('FASYANKES' in str(c).upper() for c in df.columns)
    
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    hari_ini = pd.Timestamp(datetime.now().date())
    dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()

    # Logika Pencocokan HIV+ (Hanya untuk File Rujukan)
    ref_ssr_id_to_nik = {}
    if is_file_rujukan and df_ref is not None and not df_ref.empty:
        df_ref_cp = df_ref.copy()
        df_ref_cp.columns = [str(c).strip() for c in df_ref_cp.columns]
        col_id_ref = [c for c in df_ref_cp.columns if 'ID' in c or 'Klien' in c]
        col_nik_ref = [c for c in df_ref_cp.columns if 'NIK' in c]
        col_ssr_ref = [c for c in df_ref_cp.columns if 'SSR' in c or 'Lembaga' in c]
        if col_id_ref and col_nik_ref and col_ssr_ref:
            for _, r in df_ref_cp.iterrows():
                ref_ssr_id_to_nik[f"{str(r[col_ssr_ref[0]]).strip().upper()}_{str(r[col_id_ref[0]]).strip()}"] = str(r[col_nik_ref[0]]).strip()

    for idx in range(start_row_idx, len(df)):
        row = df.iloc[idx]
        no_excel_row = idx + 2
        
        v_ssr = str(row.get('Lembaga SSR', '')).strip().upper() if pd.notna(row.get('Lembaga SSR')) else ''
        v_tanggal = str(row.get('Tanggal', '')).split(' ')[0] if pd.notna(row.get('Tanggal')) else ''
        id_clean = str(row.get('ID Klien', '')).replace("'", "").strip()
        nik_clean = str(row.get('NIK', '')).replace("'", "").replace('.0', '').strip()
        v_petugas = str(row.get('Kode Petugas', '')).replace("'", "").strip()
        v_kota = str(row.get('Nama Kota', '')).strip()
        v_tipe = str(row.get('Tipe Sasaran', row.get('Tipe Klien', ''))).strip()

        def tambah_log(ind_text):
            key_db = f"{v_ssr}_{v_tanggal}_{id_clean}_{ind_text}"
            is_butuh_konfirmasi = "konfirmasi" in ind_text.lower()
            
            # JIKA DATA KONFIRMASI SUDAH ADA JUSTIFIKASI DI DATABASE, JANGAN TAMPILKAN SEBAGAI ERROR
            if is_butuh_konfirmasi and key_db in dict_justifikasi and not dict_revisi.get(key_db, False):
                return
                
            status_validasi = "-"
            checked_state = False
            
            # Kolom Justifikasi dikunci string kosong jika indikator bukan tipe konfirmasi
            justif_val = dict_justifikasi.get(key_db, "") if is_butuh_konfirmasi else ""
            
            # CEK APAKAH ERROR INI BERULANG
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
                "Tipe Sasaran": v_tipe
            })

        # --- Contoh Trigger Pengecekan Indikator ---
        if not v_petugas or v_petugas == 'nan': tambah_log(DAFTAR_INDIKATOR[1])
        if len(id_clean) != 10: tambah_log(DAFTAR_INDIKATOR[3])
        if len(nik_clean) != 16 and nik_clean != 'nan' and nik_clean != '': tambah_log(DAFTAR_INDIKATOR[14])
        
        # Validasi silang khusus rujukan
        if is_file_rujukan and df_ref is not None:
            key_match = f"{v_ssr}_{id_clean}"
            if key_match in ref_ssr_id_to_nik and ref_ssr_id_to_nik[key_match] != nik_clean:
                tambah_log(DAFTAR_INDIKATOR[8])

    return pd.DataFrame(list_kesalahan)

# ==========================================================
# 5. EKSEKUSI REVIEW LAKUKAN ANALISIS
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
                
                # MEMBUAT TABEL ATAS SECARA DINAMIS (Hanya SSR yang memiliki temuan)
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
# 6. TAMPILAN INTERFACE & INTERAKSI DATA
# ==========================================================
if st.session_state['proses_selesai']:
    
    # --- METRICS ---
    m1, m2 = st.columns([1, 1])
    m1.metric("Total Entri Diperiksa", f"{st.session_state['total_entri']} Baris")
    tot_err = len(st.session_state['df_tabel_bawah']) if st.session_state['df_tabel_bawah'] is not None else 0
    m2.metric("Total Temuan Kesalahan", f"{tot_err} Kasus")

    st.markdown("---")
    
    # ------------------------------------------------------
    # TABEL ATAS: REKAP HASIL REVIEW DATA PER SSR
    # ------------------------------------------------------
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

    # ------------------------------------------------------
    # TABEL BAWAH: HASIL REVIEW PENJANGKAUAN
    # ------------------------------------------------------
    st.markdown("#### Hasil Review Penjangkauan")
    
    if st.session_state['df_tabel_bawah'] is not None and not st.session_state['df_tabel_bawah'].empty:
        kolom_susunan = [
            "Pilih", "Lembaga SSR", "Tanggal", "ID Klien", 
            "INDIKATOR KESALAHAN DATA", "validasi hasil review", "Justifikasi",
            "Baris Excel", "Kode Petugas", "Nama Kota", "NIK"
        ]
        
        df_bawah_view = st.session_state['df_tabel_bawah'][kolom_susunan].copy()
        
        # Render editor tabel
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
                        
                        # VALIDASI ATURAN: Jika user mengisi justifikasi pada baris MUTLAK (bukan konfirmasi)
                        if not is_butuh_konfirmasi and text_justifikasi != "":
                            peringatan_justifikasi = True
                            text_justifikasi = "" # Paksa kosongkan sebelum dikirim ke database
                        
                        # Kirim ke DB jika dicentang ATAU diisi justifikasi (khusus tipe konfirmasi)
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
