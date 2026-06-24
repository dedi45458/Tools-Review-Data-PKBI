import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from sqlalchemy import create_engine
import datetime as dt

# ==============================================================================
# KATEGORI 1: KONEKSI UTAMA & INFRASTRUKTUR DB
# ==============================================================================

def dapatkan_koneksi_neon():
    """Membuka koneksi aman ke Neon Postgres menggunakan connection pooling."""
    try:
        conn_str = st.secrets["neon_db"]["connection_string"]
        conn = psycopg2.connect(conn_str)
        return conn
    except Exception as e:
        st.error(f"Gagal menyambungkan ke Neon Postgres: {e}")
        return None

def ambil_status_storage_neon():
    """Mengambil ukuran database aktif saat ini di Neon dan menghitung sisa storage."""
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database();")
            db_name = cur.fetchone()[0]
            
            cur.execute("SELECT pg_database_size(%s);", (db_name,))
            size_bytes = cur.fetchone()[0]
            
            size_mb = size_bytes / (1024 * 1024)
            kuota_maksimal_mb = 500.0
            sisa_mb = max(0.0, kuota_maksimal_mb - size_mb)
            persen_terpakai = min(100.0, (size_mb / kuota_maksimal_mb) * 100)
            
            return {
                "terpakai_mb": round(size_mb, 2),
                "sisa_mb": round(sisa_mb, 2),
                "total_mb": kuota_maksimal_mb,
                "persen_terpakai": round(persen_terpakai, 1)
            }
    except Exception as e:
        print("Error saat mengambil ukuran storage:", e)
        return None
    finally:
        conn.close()

# ==============================================================================
# KATEGORI 2: MANAJEMEN KEYWORD MEDIA SOSIAL
# ==============================================================================

def ambil_keyword_medsos_db():
    """Mengambil seluruh daftar keyword medsos dari Neon DB"""
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nama_medsos FROM keyword_medsos")
                rows = cur.fetchall()
                return [row[0].lower() for row in rows]
        except Exception as e:
            print("Error ambil medsos:", e)
        finally:
            conn.close()
    return []

def tambah_keyword_medsos_db(keyword):
    """Menyimpan keyword medsos baru ke Neon DB"""
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO keyword_medsos (nama_medsos) VALUES (%s) ON CONFLICT (nama_medsos) DO NOTHING",
                    (keyword.lower().strip(),)
                )
                conn.commit()
                return cur.rowcount > 0 
        except Exception as e:
            print("Error tambah medsos:", e)
        finally:
            conn.close()
    return False

# ==============================================================================
# KATEGORI 3: LOG VALIDASI & AGREGASI BULANAN (FITUR TREN)
# ==============================================================================

def simpan_log_ke_neon(list_data_log):
    """Menyimpan data hasil review secara batch ke tabel log_hasil_review_data."""
    if not list_data_log:
        return False
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            # 🔥 PERBAIKAN: Menambahkan Kategori_Data ke dalam query INSERT
            query = """
                INSERT INTO public.log_hasil_review_data 
                (Kategori_Data, Lembaga_SSR, Tanggal, ID_Klien, Indikator_Kesalahan_Data, is_revisi, Justifikasi)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """
            cur.executemany(query, list_data_log)
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menyimpan log ke database: {e}")
        return False
    finally:
        conn.close()

def hitung_dan_ambil_log_db():
    """Mengambil riwayat log validasi untuk mengecek status revisi dan justifikasi."""
    dict_revisi, dict_justifikasi = {}, {}
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT Kategori_Data, Lembaga_SSR, Tanggal, ID_Klien, Indikator_Kesalahan_Data, is_revisi, Justifikasi FROM log_hasil_review_data")
                rows = cur.fetchall()
                for r in rows:
                    kat, ssr, tgl, id_klien, ind, is_rev, just = r
                    
                    # Format Key menggunakan 5 Parameter Kapital
                    key = f"{str(kat).strip().upper()}_{str(ssr).strip().upper()}_{str(tgl).split(' ')[0].strip()}_{str(id_klien).strip().upper()}_{str(ind).strip().upper()}"
                    
                    # Pastikan konversi ke boolean Python murni
                    is_rev_bool = True if (is_rev is True or str(is_rev).strip().lower() == 'true') else False
                    dict_revisi[key] = is_rev_bool
                    
                    if just and str(just).strip() not in ['', 'nan', 'None']: 
                        dict_justifikasi[key] = str(just).strip()
        except Exception as e:
            if 'st' in globals():
                st.error(f"Gagal mengambil riwayat Log Review: {e}")
        finally:
            conn.close()
    return dict_revisi, dict_justifikasi

def jalankan_agregasi_tren():
    """Memanggil fungsi PL/pgSQL untuk memindahkan log harian ke rekap tren bulanan."""
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT proses_sari_data_bulanan();")
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menjalankan agregasi data: {e}")
        return False
    finally:
        conn.close()

def ambil_rekap_tren():
    """Mengambil data tren bulanan untuk ditampilkan dalam grafik/tabel di Streamlit."""
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return pd.DataFrame()
    try:
        query = "SELECT periode, nama_ssr, indikator_kesalahan, jumlah_kesalahan FROM rekap_tren_bulanan ORDER BY periode DESC;"
        return pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Gagal mengambil data rekap tren: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# ==============================================================================
# KATEGORI 4: IMPORT DATA REFERENSI MASTER (EXCEL DATA TO DB)
# ==============================================================================

def import_data_HIV(df_HIV):
    """Mengosongkan tabel rujukan lama dan mengupload ulang data dari Excel secara massal."""
    df_HIV.columns = df_HIV.columns.str.strip()
    pemetaan = {
        "Lembaga SR": "lembaga_sr", "Lembaga SSR": "lembaga_ssr", "Kode Petugas": "kode_petugas",
        "Nama Kota": "nama_kota", "Nama Layanan": "nama_layanan", "Tanggal": "tanggal",
        "ID Klien": "id_klien", "NIK": "nik", "Tipe Klien": "tipe_klien", "Umur": "umur",
        "Jenis Kelamin": "jenis_kelamin", "Kontak Awal": "kontak_awal", "Jenis Layanan": "jenis_layanan_detil", 
        "Rujukan": "rujukan", "Hasil Tes IMS": "hasil_tes_ims", "Menerima Pengobatan IMS": "menerima_pengobatan_ims",
        "Menerima Hasil VCT": "menerima_hasil_vct", "Hasil Tes HIV": "hasil_tes_hiv"
    }
    df_HIV.rename(columns=pemetaan, inplace=True)
    kolom_db = list(pemetaan.values())
    for col in kolom_db:
        if col not in df_HIV.columns:
            df_HIV[col] = None 
    df_HIV = df_HIV[kolom_db]

    conn = dapatkan_koneksi_neon()
    if conn is None: return False
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE public.data_rujukan_hiv_positif;")
            conn.commit()
        engine = create_engine(st.secrets["neon_db"]["connection_string"])
        with engine.connect() as sql_conn:
            df_HIV.to_sql('data_rujukan_hiv_positif', sql_conn, if_exists='append', index=False, method='multi', chunksize=500)
        return True
    except Exception as e:
        st.error(f"Gagal melakukan sinkronisasi ke database Neon: {e}")
        return False
    finally:
        conn.close()

def ambil_data_rujukan_hiv_positif():
    """Mengambil seluruh data referensi HIV Positif dari database."""
    conn = dapatkan_koneksi_neon()
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT lembaga_ssr, id_klien, nik, hasil_tes_hiv, nama_kota, kode_petugas, tanggal, nama_layanan FROM data_rujukan_hiv_positif"
        return pd.read_sql(query, conn)
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def ambil_set_reaktif_sebelumnya():
    """
    Mengambil data riwayat HIV positif dan mengubahnya menjadi dua Set:
    1. Set NIK
    2. Set Kunci SSR_ID
    """
    # 1. Panggil fungsi yang baru saja Anda buat
    df_riwayat = ambil_data_rujukan_hiv_positif()
    
    set_nik = set()
    set_ssr_id = set()
    
    if df_riwayat.empty:
        return set_nik, set_ssr_id
        
    for _, row in df_riwayat.iterrows():
        # --- Ekstraksi dan Pembersihan NIK ---
        nik_raw = str(row.get('nik', '')).strip()
        # Bersihkan NIK dari tanda petik, spasi, dan akhiran float (.0)
        nik_clean = nik_raw.replace("'", "").replace('.0', '').strip()
        
        if nik_clean and nik_clean.lower() not in ['nan', 'none', '']:
            set_nik.add(nik_clean)
            
        # --- Ekstraksi dan Pembersihan Lembaga SSR + ID Klien ---
        ssr = str(row.get('lembaga_ssr', '')).strip().upper()
        idk_raw = str(row.get('id_klien', '')).strip()
        idk_clean = idk_raw.replace("'", "").strip()
        
        if ssr and idk_clean:
            kunci = f"{ssr}_{idk_clean}"
            set_ssr_id.add(kunci)
            
    return set_nik, set_ssr_id

def buat_tabel_dan_index_layanan():
    """Membuat tabel database_layanan sekaligus index kombinasi di Neon PostgreSQL."""
    query_tabel = """
    CREATE TABLE IF NOT EXISTS database_layanan (
        no SERIAL PRIMARY KEY, lembaga_ssr_iu VARCHAR(150), nama_layanan VARCHAR(255),
        jenis VARCHAR(100), kab_kota VARCHAR(100), kode_siha VARCHAR(50)
    );
    """
    query_index = "CREATE INDEX IF NOT EXISTS idx_layanan_ssr_nama ON database_layanan (lembaga_ssr_iu, nama_layanan);"
    conn = None
    cursor = None
    try:
        conn = dapatkan_koneksi_neon() 
        cursor = conn.cursor()
        cursor.execute(query_tabel)
        cursor.execute(query_index)
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def import_database_layanan(df):
    """Memasukkan/memperbarui data dari Excel ke tabel database_layanan di Neon."""
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_ssr = next((c for c in df.columns if "lembaga" in c or "ssr" in c), None)
    col_layanan = next((c for c in df.columns if "nama" in c and "layanan" in c), None)
    col_jenis = next((c for c in df.columns if "jenis" in c), None)
    col_kabkota = next((c for c in df.columns if "kab" in c or "kota" in c), None)
    col_siha = next((c for c in df.columns if "siha" in c), None)
    
    if not col_ssr or not col_layanan:
        return False, "Kolom 'Lembaga SSR/IU' atau 'Nama Layanan' tidak ditemukan."
    
    conn = None
    cursor = None
    baris_terinsert = 0
    try:
        conn = dapatkan_koneksi_neon()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE database_layanan RESTART IDENTITY;")
        
        for _, row in df.iterrows():
            val_ssr = str(row[col_ssr]).strip() if pd.notna(row[col_ssr]) else None
            val_layanan = str(row[col_layanan]).strip() if pd.notna(row[col_layanan]) else None
            val_jenis = str(row[col_jenis]).strip() if pd.notna(row[col_jenis]) else '-'
            val_kabkota = str(row[col_kabkota]).strip() if pd.notna(row[col_kabkota]) else '-'
            val_siha = str(row[col_siha]).strip() if pd.notna(row[col_siha]) else '-'
            
            if not val_ssr or not val_layanan: continue
                
            query_insert = """
            INSERT INTO database_layanan (lembaga_ssr_iu, nama_layanan, jenis, kab_kota, kode_siha)
            VALUES (%s, %s, %s, %s, %s);
            """
            cursor.execute(query_insert, (val_ssr, val_layanan, val_jenis, val_kabkota, val_siha))
            baris_terinsert += 1
            
        conn.commit()
        return True, f"Referensi layanan diperbarui! {baris_terinsert} baris diintegrasikan."
    except Exception as e:
        if conn: conn.rollback()
        return False, f"Gagal insert ke database: {str(e)}"
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def ambil_database_layanan():
    """Mengambil seluruh data referensi Layanan Fasyankes dari database."""
    conn = dapatkan_koneksi_neon()
    if not conn: return pd.DataFrame()
    try:
        query = "SELECT lembaga_ssr_iu, nama_layanan, jenis FROM database_layanan"
        return pd.read_sql(query, conn)
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def ambil_set_layanan_prep_valid():
    """
    Mengambil daftar kombinasi Lembaga SSR dan Nama Layanan PrEP yang valid
    dari database_layanan, kemudian mengembalikannya dalam bentuk set of tuples
    dengan format lowercase untuk validasi lintas file rujukan.
    """
    set_prep_valid = set()
    conn = dapatkan_koneksi_neon()
    
    if conn is None:
        return set_prep_valid
        
    try:
        with conn.cursor() as cur:
            # Query mengambil data dari tabel database_layanan yang sudah Anda miliki
            # Menggunakan LOWER() untuk standarisasi data text ke huruf kecil
            query = """
                SELECT LOWER(lembaga_ssr_iu), LOWER(nama_layanan) 
                FROM database_layanan 
                WHERE jenis IS NOT NULL;
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            for row in rows:
                ssr_val = str(row[0]).strip() if row[0] else None
                layanan_val = str(row[1]).strip() if row[1] else None
                
                # Memastikan data tidak kosong atau string representasi nan sebelum dimasukkan ke set
                if ssr_val and layanan_val and ssr_val != 'nan' and layanan_val != 'nan':
                    set_prep_valid.add((ssr_val, layanan_val))
                    
    except Exception as e:
        print(f"Error saat mengekstrak set layanan PrEP valid: {e}")
    finally:
        conn.close()
        
    return set_prep_valid

# ==============================================================================
# KATEGORI 5: OPERASI PROSES REVIEW DATA VALIDASI (3 TABEL UTAMA)
# ==============================================================================

# --- Bagian A: Tabel 1 (agregasi_hasil_review_penjangkauan) ---

def simpan_agregasi_ke_neon(df_tabel_atas, tanggal_review=None):
    """Menyimpan otomatis hasil rekap data per SSR ke database Neon."""
    if df_tabel_atas is None or df_tabel_atas.empty: return False
    df_lokal = df_tabel_atas.copy()
    kolom_indikator_ada = [c for c in df_lokal.columns if 'INDIKATOR' in str(c).upper()]
    if kolom_indikator_ada:
        df_lokal.rename(columns={kolom_indikator_ada[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
    else:
        df_lokal = df_lokal.reset_index()
        df_lokal.rename(columns={df_lokal.columns[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
        
    if tanggal_review is None: tanggal_review = dt.datetime.now().date()
    conn = dapatkan_koneksi_neon()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agregasi_hasil_review_penjangkauan WHERE tanggal_review = %s", (tanggal_review,))
            kolom_indikator = 'INDIKATOR KESALAHAN DATA'
            kolom_ssr = [c for c in df_lokal.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
            for _, row in df_lokal.iterrows():
                indikator = str(row[kolom_indikator]).strip()
                for ssr in kolom_ssr:
                    try: jumlah = int(float(row[ssr]))
                    except: jumlah = 0
                    if jumlah > 0:
                        cur.execute("""
                            INSERT INTO agregasi_hasil_review_penjangkauan 
                            (tanggal_review, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                            VALUES (%s, %s, %s, %s)
                        """, (tanggal_review, str(ssr).strip(), indikator, jumlah))
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Gagal simpan agregasi ke Neon: {e}")
        return False
    finally:
        conn.close()

def ambil_agregasi_penjangkauan_terakhir():
    """Mengambil data review penjangkauan terakhir berdasarkan MAX(tanggal_dibuat) ke format wide UI."""
    conn = dapatkan_koneksi_neon()
    if not conn: return pd.DataFrame(), None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(tanggal_dibuat) FROM agregasi_hasil_review_penjangkauan")
            max_timestamp = cur.fetchone()[0]
            if not max_timestamp: return pd.DataFrame(), None
            
            cur.execute("SELECT tanggal_review FROM agregasi_hasil_review_penjangkauan WHERE tanggal_dibuat = %s LIMIT 1", (max_timestamp,))
            target_date = cur.fetchone()[0]
            
            cur.execute("""
                SELECT nama_ssr, indikator_kesalahan, jumlah_kesalahan 
                FROM agregasi_hasil_review_penjangkauan WHERE tanggal_review = %s
            """, (target_date,))
            rows = cur.fetchall()
            if not rows: return pd.DataFrame(), max_timestamp
            
            df_long = pd.DataFrame(rows, columns=['nama_ssr', 'indikator_kesalahan', 'jumlah_kesalahan'])
            df_wide = df_long.pivot_table(index='indikator_kesalahan', columns='nama_ssr', values='jumlah_kesalahan', aggfunc='sum').fillna(0).astype(int)
            df_wide = df_wide.reset_index()
            df_wide.rename(columns={'indikator_kesalahan': 'INDIKATOR KESALAHAN DATA'}, inplace=True)
            
            kolom_ssr = [c for c in df_wide.columns if c != 'INDIKATOR KESALAHAN DATA']
            df_wide['Jumlah per indikator'] = df_wide[kolom_ssr].sum(axis=1)
            total_semua = df_wide['Jumlah per indikator'].sum()
            df_wide['%'] = ((df_wide['Jumlah per indikator'] / total_semua) * 100).round(1) if total_semua > 0 else 0.0
            
            df_wide.set_index('INDIKATOR KESALAHAN DATA', inplace=True)
            return df_wide, max_timestamp
    except Exception as e:
        st.error(f"Gagal memuat agregasi penjangkauan terakhir dari DB: {e}")
        return pd.DataFrame(), None
    finally:
        conn.close()


# --- Bagian B: Tabel 2 (agregasi_hasil_review_rujukan) ---

def simpan_agregasi_rujukan_db(data_input):
    """Menyimpan data agregasi hasil review rujukan ke database (Mendukung DataFrame/List)"""
    if data_input is None: return False
    
    # Konversi DataFrame ke List of Tuples dan tangani nilai kosong (NaN -> None)
    if isinstance(data_input, pd.DataFrame):
        if data_input.empty: return False
        df_bersih = data_input.astype(object).where(pd.notnull(data_input), None)
        list_data = [tuple(x) for x in df_bersih.to_numpy()]
    else:
        if not data_input: return False
        list_data = data_input

    conn = dapatkan_koneksi_neon()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # 🔥 SINKRONISASI: Kolom disesuaikan dengan struktur tabel asli database
            query = """
                INSERT INTO agregasi_hasil_review_rujukan 
                (tanggal_review, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                VALUES (%s, %s, %s, %s);
            """
            cur.executemany(query, list_data)
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menyimpan ke tabel agregasi rujukan: {e}")
        return False
    finally:
        if conn: conn.close()

def ambil_agregasi_rujukan_terakhir():
    """🔥 SINKRON: Mengambil seluruh baris data rujukan dari batch agregasi terakhir 
    menggunakan buffer interval 5 detik berdasarkan kolom tanggal_dibuat."""
    conn = dapatkan_koneksi_neon()
    if not conn: return pd.DataFrame(), None
    try:
        # 🔥 SINKRONISASI: Nama kolom SELECT diubah ke versi baru & pencarian menggunakan tanggal_dibuat
        query = """
            SELECT 
                nama_ssr AS "LEMBAGA SSR", 
                tanggal_review AS "TANGGAL REVIEW", 
                indikator_kesalahan AS "INDIKATOR KESALAHAN DATA", 
                jumlah_kesalahan AS "JUMLAH KESALAHAN",
                tanggal_dibuat
            FROM agregasi_hasil_review_rujukan
            WHERE tanggal_dibuat >= (SELECT MAX(tanggal_dibuat) FROM agregasi_hasil_review_rujukan) - INTERVAL '5 second'
        """
        df = pd.read_sql(query, conn)
        
        # Mengambil nilai timestamp asli untuk informasi di UI tanggal badge terakhir
        max_timestamp = None
        if not df.empty:
            max_timestamp = df['tanggal_dibuat'].max()
            # Drop kolom tanggal_dibuat agar tidak mengotori render visual tabel di Streamlit
            df = df.drop(columns=['tanggal_dibuat'])
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(tanggal_dibuat) FROM agregasi_hasil_review_rujukan")
                res = cur.fetchone()
                if res: max_timestamp = res[0]
            
        return df, max_timestamp
    except Exception as e:
        st.error(f"Gagal memuat rekap rujukan terakhir: {e}")
        return pd.DataFrame(), None
    finally:
        if conn: conn.close()


# --- Bagian C: Tabel 3 (hasil_review_data) ---

def simpan_hasil_review_utama_db(data_input):
    """Menyimpan data mandiri khusus untuk tabel utama gabungan UI (Mendukung DataFrame/List)"""
    if data_input is None: return False
    
    # Konversi DataFrame ke List of Tuples dan tangani nilai kosong (NaN -> None)
    if isinstance(data_input, pd.DataFrame):
        if data_input.empty: return False
        df_bersih = data_input.astype(object).where(pd.notnull(data_input), None)
        list_data = [tuple(x) for x in df_bersih.to_numpy()]
    else:
        if not data_input: return False
        list_data = data_input

    conn = dapatkan_koneksi_neon()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO hasil_review_data 
                (kategori_data, lembaga_ssr, kode_petugas, nama_kota, nama_layanan, tanggal, id_klien, nik, tipe_sasaran, indikator_kesalahan, validasi_hasil_review, justifikasi)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            cur.executemany(query, list_data)
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menyimpan ke tabel hasil review data: {e}")
        return False
    finally:
        if conn: conn.close()

def ambil_hasil_review_utama_terakhir():
    """🔥 SINKRON: Mengambil detail data review gabungan utama dari batch terakhir."""
    conn = dapatkan_koneksi_neon()
    if not conn: return pd.DataFrame(), None
    try:
        # 🛡️ PERBAIKAN: Alias kolom diubah menjadi Title Case agar cocok dengan Script UI
        query = """
            SELECT 
                kategori_data AS "Kategori Data", 
                lembaga_ssr AS "Lembaga SSR", 
                kode_petugas AS "Kode Petugas", 
                nama_kota AS "Nama Kota", 
                nama_layanan AS "Nama Layanan", 
                tanggal AS "Tanggal", 
                id_klien AS "ID Klien", 
                nik AS "NIK", 
                tipe_sasaran AS "Tipe Sasaran", 
                indikator_kesalahan AS "Indikator Kesalahan Data", 
                validasi_hasil_review AS "Validasi Hasil Review", 
                justifikasi AS "Justifikasi"
            FROM hasil_review_data
            WHERE created_at >= (SELECT MAX(created_at) FROM hasil_review_data) - INTERVAL '5 second'
        """
        df = pd.read_sql(query, conn)
        
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(created_at) FROM hasil_review_data")
            max_timestamp = cur.fetchone()[0]
            
        return df, max_timestamp
    except Exception as e:
        st.error(f"Gagal memuat hasil review utama gabungan terakhir: {e}")
        return pd.DataFrame(), None
    finally:
        conn.close()

def simpan_metrik_akurasi_db(kategori, total_proses, total_temuan, akurasi):
    """Menyimpan log metrik akurasi saat validasi berjalan menggunakan skema UPSERT."""
    conn = dapatkan_koneksi_neon()
    if not conn: 
        return False
    try:
        with conn.cursor() as cur:
            # 1. Pastikan tabel dibuat dengan constraint UNIQUE pada kolom 'kategori'
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrik_akurasi (
                    id SERIAL PRIMARY KEY,
                    kategori VARCHAR(50) UNIQUE, 
                    total_proses INT, 
                    total_temuan INT, 
                    akurasi FLOAT, 
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 2. Gunakan ON CONFLICT untuk memperbarui data jika kategori sudah ada (UPSERT)
            query_upsert = """
                INSERT INTO metrik_akurasi (kategori, total_proses, total_temuan, akurasi, created_at) 
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (kategori) 
                DO UPDATE SET 
                    total_proses = EXCLUDED.total_proses,
                    total_temuan = EXCLUDED.total_temuan,
                    akurasi = EXCLUDED.akurasi,
                    created_at = CURRENT_TIMESTAMP;
            """
            
            # Pastikan parameter kategori dipaksa menjadi lowercase agar konsisten saat dibaca di UI
            cur.execute(query_upsert, (kategori.lower().strip(), total_proses, total_temuan, akurasi))
            
        conn.commit()
        return True
    except Exception as e:
        if conn: 
            conn.rollback()
        # Anda bisa mencetak print(f"Error DB: {e}") di sini untuk mempermudah debugging jika diperlukan
        return False
    finally:
        if conn: 
            conn.close()


def ambil_metrik_akurasi_terakhir():
    """Mengambil persentase akurasi terakhir untuk ditampilkan di UI Kartu Skor."""
    conn = dapatkan_koneksi_neon()
    metrik_default = {'akurasi_penjangkauan': 100.0, 'akurasi_rujukan': 100.0}
    ts_metrik = dt.datetime.now()
    
    if not conn: return metrik_default, ts_metrik
    try:
        with conn.cursor() as cur:
            # Cek apakah tabel ada
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'metrik_akurasi');")
            tabel_ada = cur.fetchone()[0]
            
            if tabel_ada:
                cur.execute("SELECT MAX(created_at) FROM metrik_akurasi")
                max_ts = cur.fetchone()[0]
                if max_ts:
                    ts_metrik = max_ts
                    cur.execute("SELECT kategori, akurasi FROM metrik_akurasi WHERE created_at = %s", (max_ts,))
                    for row in cur.fetchall():
                        kat = str(row[0]).lower()
                        if 'penjangkauan' in kat: metrik_default['akurasi_penjangkauan'] = float(row[1])
                        if 'rujukan' in kat: metrik_default['akurasi_rujukan'] = float(row[1])
    except Exception:
        pass # Jika eror, biarkan mengembalikan nilai 100.0 (Aman)
    finally:
        conn.close()
        
    return metrik_default, ts_metrik

# ==============================================================================
# KATEGORI 6: FUNGSI SINKRONISASI 3 TABEL & METRIK AKURASI BARU
# ==============================================================================

def simpan_paket_validasi_ke_tiga_tabel(list_tabel_1, list_tabel_2, list_tabel_3):
    """Menyimpan data hasil review ke 3 tabel secara bersamaan (Database Transaction)."""
    conn = dapatkan_koneksi_neon()
    if not conn: return False
    
    try:
        with conn.cursor() as cur:
            tanggal_hari_ini = dt.datetime.now().date()

            # -----------------------------------------------------------------
            # 1. TABEL PENJANGKAUAN (Agregasi - 4 Kolom)
            # -----------------------------------------------------------------
            if list_tabel_1:
                list_1_lengkap = [(tanggal_hari_ini, row[0], row[1], row[2]) for row in list_tabel_1]
                cur.executemany("""
                    INSERT INTO agregasi_hasil_review_penjangkauan (tanggal_review, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                    VALUES (%s, %s, %s, %s);
                """, list_1_lengkap)

            # -----------------------------------------------------------------
            # 2. 🔥 TABEL RUJUKAN (Agregasi - Sudah Diubah ke 4 Kolom Sesuai DDL Baru)
            # -----------------------------------------------------------------
            if list_tabel_2:
                # Karena dari tombol proses UI kita sudah mengirimkan tuple lengkap (4 kolom):
                # (tanggal_skr, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                cur.executemany("""
                    INSERT INTO agregasi_hasil_review_rujukan (tanggal_review, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                    VALUES (%s, %s, %s, %s);
                """, list_tabel_2)

            # -----------------------------------------------------------------
            # 3. 🔥 TABEL UTAMA (MASTER DATA DETIL KLIEN - 12 Kolom)
            # -----------------------------------------------------------------
            if list_tabel_3:
                # Memperbaiki nama kolom master agar merekam data baris mentah (bukan agregasi)
                cur.executemany("""
                    INSERT INTO hasil_review_data
                    (kategori_data, lembaga_ssr, kode_petugas, nama_kota, nama_layanan, tanggal, id_klien, nik, tipe_sasaran, indikator_kesalahan, validasi_hasil_review, justifikasi)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, list_tabel_3)

        # Jika semua berhasil tanpa error, simpan ke database secara permanen
        conn.commit()
        return True

    except Exception as e:
        # Jika ada SATU saja yang gagal, batalkan semua (rollback) agar data tidak berantakan
        if conn: conn.rollback()
        import streamlit as st
        st.error(f"Gagal transaksi multi-tabel: {e}")
        return False
    finally:
        if conn: conn.close()


def simpan_metrik_akurasi_db(kategori, total_proses, total_temuan, akurasi):
    """Menyimpan atau memperbarui metrik ke Neon secara otomatis (UPSERT)."""
    conn = dapatkan_koneksi_neon()
    if not conn: 
        return False
    try:
        with conn.cursor() as cur:
            # Menggunakan ON CONFLICT UPDATE untuk memperbarui data jika metrik sama persis
            cur.execute("""
                INSERT INTO akurasi_review_data (
                    kategori, 
                    total_data_diproses, 
                    total_baris_temuan, 
                    tingkat_akurasi
                ) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT ON CONSTRAINT unique_kategori_metrik 
                DO UPDATE SET 
                    tingkat_akurasi = EXCLUDED.tingkat_akurasi,
                    created_at = CURRENT_TIMESTAMP;
            """, (kategori, total_proses, total_temuan, akurasi))
            
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def ambil_metrik_akurasi_terakhir():
    """Mengambil data metrik terakhir untuk UI Kartu Skor dari Neon."""
    conn = dapatkan_koneksi_neon()
    # Nilai default jika tabel kosong atau database putus
    metrik_default = {
        'akurasi_penjangkauan': 100.0, 'temuan_penjangkauan': 0, 'total_pjj': 0,
        'akurasi_rujukan': 100.0, 'temuan_rujukan': 0, 'total_rjk': 0
    }
    ts_metrik = dt.datetime.now()
    
    if not conn: 
        return metrik_default, ts_metrik
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'akurasi_review_data');")
            if cur.fetchone()[0]:
                # Mengambil kolom yang ada secara eksplisit
                cur.execute("""
                    SELECT kategori, total_data_diproses, total_baris_temuan, tingkat_akurasi, created_at 
                    FROM akurasi_review_data 
                    ORDER BY created_at DESC 
                    LIMIT 2
                """)
                rows = cur.fetchall()
                if rows:
                    ts_metrik = rows[0][4]  # Indeks ke-4 adalah created_at
                    for row in rows:
                        kat = str(row[0]).lower()
                        if 'penjangkauan' in kat:
                            metrik_default['total_pjj'] = int(row[1])
                            metrik_default['temuan_penjangkauan'] = int(row[2])
                            metrik_default['akurasi_penjangkauan'] = float(row[3])
                        elif 'rujukan' in kat:
                            metrik_default['total_rjk'] = int(row[1])
                            metrik_default['temuan_rujukan'] = int(row[2])
                            metrik_default['akurasi_rujukan'] = float(row[3])
    except Exception:
        pass
    finally:
        conn.close()
        
    return metrik_default, ts_metrik

def ambil_set_error_belum_direvisi():
    """
    Mengambil SELURUH riwayat log kesalahan (baik yang True maupun False)
    untuk kebutuhan deteksi kepatuhan revisi (Fraud Detection) di UI.
    """
    conn = dapatkan_koneksi_neon()
    if not conn:
        return pd.DataFrame()
        
    try:
        # 🔥 PERBAIKAN: Hapus WHERE is_revisi = FALSE agar semua data log (termasuk yang 'true') ditarik.
        query = """
            SELECT 
                kategori_data AS "KATEGORI DATA", 
                lembaga_ssr AS "LEMBAGA SSR", 
                tanggal AS "TANGGAL", 
                id_klien AS "ID KLIEN", 
                indikator_kesalahan_data AS "INDIKATOR KESALAHAN DATA", 
                is_revisi, 
                justifikasi AS "JUSTIFIKASI"
            FROM public.log_hasil_review_data;
        """
        df_historis = pd.read_sql(query, conn)
        return df_historis
        
    except Exception as e:
        print(f"Error saat mengambil log error historis: {e}")
        return pd.DataFrame()
    finally:
        conn.close()
