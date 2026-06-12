# --- TAMBAHKAN DI BAWAH FILE database.py ---
from sqlalchemy import create_engine

def import_data_rujukan(df_rujukan):
    """
    Mengimpor data Excel rujukan ke dalam tabel data_rujukan_hiv_positif.
    Data lama akan dihapus (TRUNCATE) agar database selalu berisi data terbaru.
    """
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
    
    try:
        # 1. Bersihkan tabel lama
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE public.data_rujukan_hiv_positif;")
            conn.commit()
        
        # 2. Persiapkan koneksi SQLAlchemy untuk insert massal yang cepat
        conn_str = st.secrets["neon_db"]["connection_string"]
        engine = create_engine(conn_str)
        
        # 3. Masukkan data dari DataFrame
        # Pastikan nama kolom di DataFrame sudah sesuai dengan nama kolom di tabel SQL
        df_rujukan.to_sql(
            'data_rujukan_hiv_positif', 
            engine, 
            if_exists='append', 
            index=False,
            method='multi', # Mengoptimalkan kecepatan insert
            chunksize=1000
        )
        return True
        
    except Exception as e:
        st.error(f"Gagal mengimpor data rujukan ke database: {e}")
        return False
    finally:
        conn.close()

def cek_nik_di_rujukan(nik_target):
    """
    Mengecek apakah NIK sudah terdaftar di database referensi HIV Positif.
    Berguna untuk validasi data rujukan.
    """
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
        
    try:
        with conn.cursor() as cur:
            # Menggunakan parameterized query untuk keamanan
            cur.execute("SELECT 1 FROM public.data_rujukan_hiv_positif WHERE NIK = %s LIMIT 1;", (str(nik_target),))
            hasil = cur.fetchone()
            return hasil is not None
    except Exception as e:
        return False
    finally:
        conn.close()
