import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

def dapatkan_koneksi_neon():
    """Membuka koneksi aman ke Neon Postgres menggunakan connection pooling."""
    try:
        conn_str = st.secrets["neon_db"]["connection_string"]
        conn = psycopg2.connect(conn_str)
        return conn
    except Exception as e:
        st.error(f"Gagal menyambungkan ke Neon Postgres: {e}")
        return None

def simpan_log_ke_neon(list_data_log):
    """
    Menyimpan data hasil review secara batch ke tabel log_validasi_review.
    Tanpa klausa ON CONFLICT untuk menghindari error jika constraint unik belum dibuat.
    """
    if not list_data_log:
        return False
        
    conn = dapatkan_koneksi_neon()
    if conn is None:
        return False
        
    try:
        with conn.cursor() as cur:
            # Menggunakan INSERT standar tanpa pengecekan konflik
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

from sqlalchemy import create_engine

def import_data_rujukan(df_rujukan):
    # Bersihkan spasi gaib di awal/akhir nama kolom Excel jika ada
    df_rujukan.columns = df_rujukan.columns.str.strip()

    # Mapping: Nama di Excel (kiri) -> Nama di Database (Ubah ke HURUF KECIL semua)
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

    # 1. Rename kolom di dataframe agar cocok dengan database (versi lowercase)
    df_rujukan.rename(columns=pemetaan, inplace=True)
    
    # 2. Antisipasi: Jika ada kolom rujukan yang absen di Excel, isi otomatis dengan Kosong/None
    kolom_db = list(pemetaan.values())
    for col in kolom_db:
        if col not in df_rujukan.columns:
            df_rujukan[col] = None 
            
    # Saring dataframe hanya berisi kolom yang terdaftar di DB
    df_rujukan = df_rujukan[kolom_db]

    # 3. Proses pengosongan tabel lama & upload ulang
    conn = dapatkan_koneksi_neon()
    if conn is None: 
        return False
    
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE public.data_rujukan_hiv_positif;")
            conn.commit()
        
        # Buka engine SQLAlchemy untuk upload data secara massal
        engine = create_engine(st.secrets["neon_db"]["connection_string"])
        
        # Kirim data ke database
        df_rujukan.to_sql(
            'data_rujukan_hiv_positif', 
            engine, 
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
