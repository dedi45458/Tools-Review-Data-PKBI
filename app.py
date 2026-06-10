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
SUPABASE_KEY = "sb_publishable_0RXs2YvzFtj2b8K2zeCFvQ_XAMQW1aM"

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

# ==========================================================
# REVISI: 15 INDIKATOR KESALAHAN DATA SESUAI ATURAN BARU
# ==========================================================
DAFTAR_INDIKATOR = [
    "Placeholder Indeks 0",                                                     # 0
    "Kode Petugas Kosong",                                                      # 1
    "Tanggal lebih besar dari tanggal hari ini",                                # 2
    "IDKD kurang/lebih dari 10 digit karakter",                                 # 3
    "Digit nama kurang/lebih dari 4 digit karakter",                            # 4
    "Digit tanggal lahir lebih/kurang dari 6 digit angka",                      # 5
    "ID sama tapi NIK berbeda dengan data Semester/Tahun lalu (Konfirmasi)",    # 6
    "NIK sama tapi ID berbeda dengan data Semester/Tahun lalu (Konfirmasi)",    # 7
    "Usia KD dibawah 16 tahun (konfirmasi)",                                    # 8
    "Usia KD diatas 70 tahun (konfirmasi)",                                     # 9
    "Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (konfirmasi)",   # 10
    "NIK kurang/lebih dari 16 digit (konfirmasi)",                              # 11
    "Kesalahan dalam penulisan NIK (00) (konfirmasi)",                          # 12
    "Secara NIK harusnya perempuan bukan laki-laki (konfirmasi)",               # 13
    "LSL/Waria tapi jenis kelamin perempuan",                                   # 14
    "Jenis kontak dengan Jenis Kegiatan tidak sesuai"                           # 15
]

# Helper cek kode multi-nilai dalam satu sel (misal kegiatan: '2,3')
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
# 3. ENGINE VALIDASI UTAMA GABUNGAN (15 ATURAN BARU)
# ==========================================================
def jalankan_review_data(df_asli, df_ref=None):
    list_kesalahan = []
    if df_asli.empty: return pd.DataFrame(list_kesalahan)
    
    df = df_asli.copy()
    df.columns = [str(c).strip() for c in df.columns]
    
    # ------------------------------------------------------
    # SMART MAPPING: Keselarasan kolom otomatis
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

    # Penentuan baris awal data real
    start_row_idx = 0
    if len(df) > 0 and ('dd/mm/yyyy' in str(df.iloc[0].values) or 'Laki-laki' in str(df.iloc[0].values)):
        start_row_idx = 1

    hari_ini = pd.Timestamp(datetime.now().date())
    df_clean = df.iloc[start_row_idx:].copy()
    dict_revisi, dict_justifikasi = hitung_dan_ambil_log_db()

    # Mapping Data Referensi Penjangkauan Sebelumnya (HIV+ / Semester Lalu)
    ref_ssr_id_to_nik = {}
    ref_nik_ssr_to_id = {}
    if df_ref is not None and not df_ref.empty:
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

    # Iterasi Data Laporan Real
    for idx, row in df_clean.iterrows():
        no_excel_row = idx + 2
        
        def dapatkan_val(nama_sistem, default=''):
            k_asli = mapping_kolom.get(nama_sistem)
            if k_asli and k_asli in row:
                val = row[k_asli]
                return val.iloc[0] if isinstance(val, pd.Series) else val
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

        tgl_p = pd.to_datetime(v_tanggal_raw, errors='coerce') if pd.notna(v_tanggal_raw) else None

        # Penengah Sinkronisasi Log
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
        # 📌 BLOK EKSEKUSI JALUR VALIDASI (15 LOGIKA ATURAN PRESISI)
        # ==========================================================
        
        # 1. Kode Petugas Kosong
        if not v_petugas or v_petugas == '' or v_petugas.lower() == 'nan': 
            tambah_log(DAFTAR_INDIKATOR[1])

        # 2. Tanggal lebih besar dari tanggal hari ini
        if pd.notna(tgl_p) and tgl_p > hari_ini:
            tambah_log(DAFTAR_INDIKATOR[2])

        # Aturan Khusus IDKD
        if id_clean and id_clean != '':
            # 3. IDKD kurang/lebih dari 10 digit karakter & kombinasi huruf-angka saja
            if len(id_clean) != 10 or not id_clean.isalnum():
                tambah_log(DAFTAR_INDIKATOR[3])
            
            # Ekstraksi komponen ID jika panjangnya tepat 10 digit untuk hindari salah indeks
            if len(id_clean) == 10:
                komponen_nama = id_clean[:4]
                komponen_tgl = id_clean[4:]
                
                # 4. Digit nama kurang/lebih dari 4 digit karakter (wajib huruf)
                if not komponen_nama.isalpha():
                    tambah_log(DAFTAR_INDIKATOR[4])
                
                # 5. Digit tanggal lahir lebih/kurang dari 6 digit angka
                if not komponen_tgl.isdigit():
                    tambah_log(DAFTAR_INDIKATOR[5])

            # 6. ID sama tapi NIK berbeda dengan data lama (Konfirmasi)
            if df_ref is not None and v_ssr:
                key_ssr_id = f"{v_ssr}_{id_clean}"
                if key_ssr_id in ref_ssr_id_to_nik and ref_ssr_id_to_nik[key_ssr_id] != nik_clean:
                    tambah_log(DAFTAR_INDIKATOR[6])

        # 7. NIK sama tapi ID berbeda dengan data lama (Konfirmasi)
        if df_ref is not None and v_ssr and nik_clean and nik_clean != 'nan' and nik_clean != '':
            key_nik_ssr = f"{nik_clean}_{v_ssr}"
            if key_nik_ssr in ref_nik_ssr_to_id and ref_nik_ssr_to_id[key_nik_ssr] != id_clean:
                tambah_log(DAFTAR_INDIKATOR[7])

        # Validasi Umur
        if pd.notna(umur) and str(umur).strip() != '' and str(umur).lower() != 'nan':
            try:
                val_umur = float(umur)
                # 8. Usia KD dibawah 16 tahun (aturan tertulis: dibawah 17 tahun)
                if val_umur < 17: 
                    tambah_log(DAFTAR_INDIKATOR[8])
                # 9. Usia KD diatas 70 tahun (>70 tahun)
                if val_umur > 70: 
                    tambah_log(DAFTAR_INDIKATOR[9])
            except: pass

        # 10. Tahun lahir pada IDKD berbeda dengan Tahun lahir pada NIK (Konfirmasi)
        if id_clean and len(id_clean) == 10 and nik_clean and len(nik_clean) == 16:
            thn_id = id_clean[4:6]  # Digit ke 5 dan 6 pada ID Klien
            nik_for_idx = nik_raw if nik_raw.startswith("'") else "'" + nik_clean
            if len(nik_for_idx) >= 14:
                thn_nik = nik_for_idx[11:13] # Digit ke 12 dan 13 dengan asumsi tanda petik (') dihitung
                if thn_id != thn_nik:
                    tambah_log(DAFTAR_INDIKATOR[10])

        # Validasi NIK Teknis
        if nik_clean and nik_clean != '' and nik_clean != 'nan':
            # 11. NIK kurang/lebih dari 16 digit (tanpa petik)
            if len(nik_clean) != 16:
                tambah_log(DAFTAR_INDIKATOR[11])
            
            # 12. Kesalahan dalam penulisan NIK (akhir digit adalah 00)
            if nik_clean.endswith('00'):
                tambah_log(DAFTAR_INDIKATOR[12])

            # 13. Secara NIK harusnya perempuan bukan laki-laki (Laki-laki = 1, tapi tanggal lahir di NIK > 31)
            if len(nik_clean) == 16 and jk == '1':
                nik_for_jk = nik_raw if nik_raw.startswith("'") else "'" + nik_clean
                if len(nik_for_jk) >= 10:
                    try:
                        dd_nik = int(nik_for_jk[13:15]) # Digit 14 dan 15 jika tanda petik dihitung
                        if dd_nik > 31: 
                            tambah_log(DAFTAR_INDIKATOR[13])
                    except: pass

        # 14. LSL/Waria tapi jenis kelamin perempuan
        if (v_tipe_sasaran in ['1304', '1301']) and jk == '2': 
            tambah_log(DAFTAR_INDIKATOR[14])

        # 15. Jenis kontak dengan Jenis Kegiatan tidak sesuai
        if jns_kontak == '1': # Individual
            if not (cek_kode(jns_kegiatan, '1') or cek_kode(jns_kegiatan, '5')):
                tambah_log(DAFTAR_INDIKATOR[15])
        elif jns_kontak == '2': # Kelompok
            if not (cek_kode(jns_kegiatan, '2') or cek_kode(jns_kegiatan, '3') or cek_kode(jns_kegiatan, '4') or cek_kode(jns_kegiatan, '6') or cek_kode(jns_kegiatan, '7')):
                tambah_log(DAFTAR_INDIKATOR[15])
        elif jns_kontak == '3': # Virtual / VO
            if not cek_kode(jns_kegiatan, '8'):
                tambah_log(DAFTAR_INDIKATOR[15])

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
