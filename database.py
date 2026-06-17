import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from sqlalchemy import create_engine
import datetime as dt

def dapatkan_koneksi_neon():
    """Membuka koneksi aman ke Neon Postgres menggunakan connection pooling."""
    try:
        conn_str = st.secrets["neon_db"]["connection_string"]
        conn = psycopg2.connect(conn_str)
        return conn
    except Exception as e:
        st.error(f"Gagal menyambungkan ke Neon Postgres: {e}")
        return None

# ==========================================================
# FITUR TAMBAHAN: MANAJEMEN KEYWORD MEDIA SOSIAL
# ==========================================================

# Tambahkan ini di dalam file database.py

def ambil_keyword_medsos_db():
    """Mengambil seluruh daftar keyword medsos dari Neon DB"""
    conn = dapatkan_koneksi_neon()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nama_medsos FROM keyword_medsos")
                rows = cur.fetchall()
                # Kembalikan sebagai list of string
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
                # Jika rowcount > 0, berarti berhasil ditambah (bukan duplikat)
                return cur.rowcount > 0 
        except Exception as e:
            print("Error tambah medsos:", e)
        finally:
            conn.close()
    return False

# ==========================================================
# FITUR LOG & VALIDASI REVIEW
# ==========================================================

def simpan_log_ke_neon(list_data_log):
    """
    Menyimpan data hasil review secara batch ke tabel log_validasi_review.
    """
    if not list_data_log:
        return False
        
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
        
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO public.log_validasi_review 
                (Lembaga_SSR, Tanggal, ID_Klien, Indikator_Kesalahan_Data, is_revisi, Justifikasi)
                VALUES (%s, %s, %s, %s, %s, %s);
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
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"Gagal mengambil data rekap tren: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def import_data_rujukan(df_rujukan):
    """Mengosongkan tabel rujukan lama dan mengupload ulang data dari Excel secara massal."""
    df_rujukan.columns = df_rujukan.columns.str.strip()

    pemetaan = {
        "Lembaga SR": "lembaga_sr",
        "Lembaga SSR": "lembaga_ssr",
        "Kode Petugas": "kode_petugas",
        "Nama Kota": "nama_kota",
        "Nama Layanan": "nama_layanan",
        "Tanggal": "tanggal",
        "ID Klien": "id_klien",
        "NIK": "nik",
        "Tipe Klien": "tipe_klien",
        "Umur": "umur",
        "Jenis Kelamin": "jenis_kelamin",
        "Kontak Awal": "kontak_awal",
        "Jenis Layanan": "jenis_layanan_detil", 
        "Rujukan": "rujukan",
        "Hasil Tes IMS": "hasil_tes_ims",
        "Menerima Pengobatan IMS": "menerima_pengobatan_ims",
        "Menerima Hasil VCT": "menerima_hasil_vct",
        "Hasil Tes HIV": "hasil_tes_hiv"
    }

    df_rujukan.rename(columns=pemetaan, inplace=True)
    
    kolom_db = list(pemetaan.values())
    for col in kolom_db:
        if col not in df_rujukan.columns:
            df_rujukan[col] = None 
            
    df_rujukan = df_rujukan[kolom_db]

    conn = dapatkan_koneksi_neon()
    if conn is None: 
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE public.data_rujukan_hiv_positif;")
            conn.commit()
        
        # Peningkatan: Membuka engine dengan context manager agar otomatis tertutup setelah selesai
        engine = create_engine(st.secrets["neon_db"]["connection_string"])
        with engine.connect() as sql_conn:
            df_rujukan.to_sql(
                'data_rujukan_hiv_positif', 
                sql_conn, 
                if_exists='append', 
                index=False, 
                method='multi', 
                chunksize=500
            )
        return True
    except Exception as e:
        st.error(f"Gagal melakukan sinkronisasi ke database Neon: {e}")
        return False
    finally:
        conn.close()

def hitung_dan_ambil_log_db():
    """Mengambil riwayat log validasi untuk mengecek status revisi dan justifikasi."""
    conn = dapatkan_koneksi_neon()
    dict_revisi = {}
    dict_justifikasi = {}
    
    if conn is None:
        return dict_revisi, dict_justifikasi
        
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT lembaga_ssr, tanggal, id_klien, indikator_kesalahan_data, is_revisi, justifikasi 
                FROM public.log_validasi_review;
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            for row in rows:
                key_db = f"{row['lembaga_ssr']}_{row['tanggal']}_{row['id_klien']}_{row['indikator_kesalahan_data']}"
                dict_revisi[key_db] = row['is_revisi']
                dict_justifikasi[key_db] = row['justifikasi'] if row['justifikasi'] else ""
                
    except Exception as e:
        # 🚨 PERBAIKAN 4: Ganti `pass` dengan pemberitahuan
        st.error(f"Gagal mengambil riwayat Log Review. Apakah tabel 'log_validasi_review' terhapus? : {e}")
    finally:
        conn.close()
        
    return dict_revisi, dict_justifikasi

def simpan_agregasi_ke_neon(df_tabel_atas, tanggal_review=None):
    """Menyimpan otomatis hasil rekap data per SSR ke database Neon dengan sistem pengaman."""
    if df_tabel_atas is None or df_tabel_atas.empty:
        return False

    df_lokal = df_tabel_atas.copy()
    
    # 🛠️ PERBAIKAN 1: Deteksi nama kolom secara dinamis (anti typo / case-insensitive)
    kolom_indikator_ada = [c for c in df_lokal.columns if 'INDIKATOR' in str(c).upper()]
    
    if kolom_indikator_ada:
        # Jika kolom ditemukan, seragamkan namanya
        df_lokal.rename(columns={kolom_indikator_ada[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
    else:
        # Jika benar-benar tidak ada di kolom, reset index secara aman
        df_lokal = df_lokal.reset_index()
        df_lokal.rename(columns={df_lokal.columns[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
        
    if tanggal_review is None:
        tanggal_review = dt.datetime.now().date()
        
    conn = dapatkan_koneksi_neon()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM agregasi_hasil_review_penjangkauan WHERE tanggal_review = %s", 
                (tanggal_review,)
            )
            
            kolom_indikator = 'INDIKATOR KESALAHAN DATA'
            kolom_ssr = [c for c in df_lokal.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%']]
            
            for _, row in df_lokal.iterrows():
                indikator = str(row[kolom_indikator]).strip()
                for ssr in kolom_ssr:
                    try:
                        jumlah = int(float(row[ssr]))
                    except:
                        jumlah = 0
                    
                    if jumlah > 0:
                        cur.execute("""
                            INSERT INTO agregasi_hasil_review_penjangkauan 
                            (tanggal_review, nama_ssr, indikator_kesalahan, jumlah_kesalahan)
                            VALUES (%s, %s, %s, %s)
                        """, (tanggal_review, str(ssr).strip(), indikator, jumlah))
                        
            conn.commit()
            return True
    except Exception as e:
        # 🚨 PERBAIKAN 2: Tampilkan error ke layar agar kita tahu jika tabel hilang!
        st.error(f"Gagal simpan agregasi ke Neon (Apakah tabel ikut terhapus?): {e}")
        return False
    finally:
        conn.close()

def ambil_agregasi_terakhir_dari_neon():
    """
    Mengambil data review terakhir dari Neon DB dan merekonstruksinya 
    kembali menjadi format DataFrame wide yang siap dibaca oleh UI Streamlit.
    """
    conn = dapatkan_koneksi_neon()
    if not conn:
        return pd.DataFrame(), None
        
    try:
        with conn.cursor() as cur:
            # 1. Cari tanggal review paling terakhir/terbaru
            cur.execute("SELECT MAX(tanggal_review) FROM agregasi_hasil_review_penjangkauan")
            max_date = cur.fetchone()[0]
            if not max_date:
                return pd.DataFrame(), None
                
            # 2. Ambil semua data kesalahan pada tanggal tersebut
            cur.execute("""
                SELECT nama_ssr, indikator_kesalahan, jumlah_kesalahan 
                FROM agregasi_hasil_review_penjangkauan 
                WHERE tanggal_review = %s
            """, (max_date,))
            rows = cur.fetchall()
            
            if not rows:
                return pd.DataFrame(), max_date
                
            # 3. Transformasi kembali dari format baris (long) ke format tabel lebar (wide)
            df_long = pd.DataFrame(rows, columns=['nama_ssr', 'indikator_kesalahan', 'jumlah_kesalahan'])
            
            # 🔥 GANTI pivot() MENJADI pivot_table() DAN TAMBAHKAN aggfunc='sum'
            df_wide = df_long.pivot_table(
                index='indikator_kesalahan', 
                columns='nama_ssr', 
                values='jumlah_kesalahan',
                aggfunc='sum'
            ).fillna(0).astype(int)
            
            # Kembalikan kolom indeks menjadi kolom biasa untuk kebutuhan manipulasi data
            df_wide = df_wide.reset_index()
            df_wide.rename(columns={'indikator_kesalahan': 'INDIKATOR KESALAHAN DATA'}, inplace=True)
            
            # Hitung ulang kolom 'Jumlah per indikator' secara dinamis
            kolom_ssr = [c for c in df_wide.columns if c != 'INDIKATOR KESALAHAN DATA']
            df_wide['Jumlah per indikator'] = df_wide[kolom_ssr].sum(axis=1)
            
            # Hitung ulang kolom presentase (%)
            total_semua = df_wide['Jumlah per indikator'].sum()
            if total_semua > 0:
                df_wide['%'] = ((df_wide['Jumlah per indikator'] / total_semua) * 100).round(1)
            else:
                df_wide['%'] = 0.0
                
            # Kembalikan ke format UI aslinya (Indikator Kesalahan diatur sebagai Indeks kembali)
            df_wide.set_index('INDIKATOR KESALAHAN DATA', inplace=True)
                
            return df_wide, max_date
    except Exception as e:
        # 🚨 PERBAIKAN 3: Jangan disembunyikan pakai print, tampilkan di UI Streamlit
        st.error(f"Gagal memuat agregasi terakhir dari Neon DB: {e}")
        return pd.DataFrame(), None
    finally:
        conn.close()
