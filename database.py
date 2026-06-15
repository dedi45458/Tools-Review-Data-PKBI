import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from sqlalchemy import create_engine

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

def ambil_keyword_medsos():
    """
    Mengambil daftar keyword media sosial dari database Neon 
    untuk digunakan sebagai penyaring data di app.py.
    """
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return []
        
    try:
        with conn.cursor() as cur:
            # Mengambil keyword dan mengurutkannya secara alfabetis (A-Z)
            cur.execute("SELECT keyword FROM public.keyword_medsos ORDER BY keyword ASC;")
            rows = cur.fetchall()
            # Mengubah hasil query [( 'grindr',), ('michat',)] menjadi list standar ['grindr', 'michat']
            return [row[0] for row in rows]
    except Exception as e:
        # Jika tabel belum dibuat di awal, kembalikan list kosong agar aplikasi tidak crash
        return []
    finally:
        conn.close()

def simpan_keyword_medsos(keyword):
    """
    Menyimpan keyword media sosial baru yang diinput user ke database.
    Menggunakan klausa 'ON CONFLICT' agar jika kata tersebut sudah ada, tidak memicu error duplikat.
    """
    if not keyword or keyword.strip() == "":
        st.warning("Keyword tidak boleh kosong!")
        return False
        
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
        
    try:
        with conn.cursor() as cur:
            # Mengubah input menjadi huruf kecil semua dan menghapus spasi gaib
            keyword_bersih = keyword.strip().lower()
            
            query = """
                INSERT INTO public.keyword_medsos (keyword) 
                VALUES (%s) 
                ON CONFLICT (keyword) DO NOTHING;
            """
            cur.execute(query, (keyword_bersih,))
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menyimpan keyword medsos ke database: {e}")
        return False
    finally:
        conn.close()

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
        pass
    finally:
        conn.close()
        
    return dict_revisi, dict_justifikasi
