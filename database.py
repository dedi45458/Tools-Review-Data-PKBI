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

# ==========================================================
# FITUR LOG & VALIDASI REVIEW
# ==========================================================

def simpan_log_ke_neon(list_data_log):
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
    df_rujukan.columns = df_rujukan.columns.str.strip()

    pemetaan = {
        "Lembaga SR": "lembaga_sr", "Lembaga SSR": "lembaga_ssr", "Kode Petugas": "kode_petugas",
        "Nama Kota": "nama_kota", "Nama Layanan": "nama_layanan", "Tanggal": "tanggal",
        "ID Klien": "id_klien", "NIK": "nik", "Tipe Klien": "tipe_klien", "Umur": "umur",
        "Jenis Kelamin": "jenis_kelamin", "Kontak Awal": "kontak_awal", 
        "Jenis Layanan": "jenis_layanan_detil", "Rujukan": "rujukan", 
        "Hasil Tes IMS": "hasil_tes_ims", "Menerima Pengobatan IMS": "menerima_pengobatan_ims",
        "Menerima Hasil VCT": "menerima_hasil_vct", "Hasil Tes HIV": "hasil_tes_hiv"
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
        st.error(f"Gagal mengambil riwayat Log Review. Apakah tabel 'log_validasi_review' terhapus? : {e}")
    finally:
        conn.close()
        
    return dict_revisi, dict_justifikasi

def simpan_agregasi_ke_neon(df_tabel_atas, tanggal_review=None):
    if df_tabel_atas is None or df_tabel_atas.empty:
        return False

    df_lokal = df_tabel_atas.copy()
    
    kolom_indikator_ada = [c for c in df_lokal.columns if 'INDIKATOR' in str(c).upper()]
    
    if kolom_indikator_ada:
        df_lokal.rename(columns={kolom_indikator_ada[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
    else:
        df_lokal = df_lokal.reset_index()
        df_lokal.rename(columns={df_lokal.columns[0]: 'INDIKATOR KESALAHAN DATA'}, inplace=True)
        
    if tanggal_review is None:
        # 🔥 PERBAIKAN 1: Menggunakan datetime langsung (bukan dt.datetime)
        tanggal_review = datetime.now().date()
        
    conn = dapatkan_koneksi_neon()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM agregasi_hasil_review WHERE tanggal_review = %s", (tanggal_review,))
            
            kolom_indikator = 'INDIKATOR KESALAHAN DATA'
            kolom_ssr = [c for c in df_lokal.columns if c not in [kolom_indikator, 'Jumlah per indikator', '%'] and 'indikator' not in str(c).lower()]
            
            for _, row in df_lokal.iterrows():
                indikator = str(row[kolom_indikator]).strip()
                for ssr in kolom_ssr:
                    try:
                        jumlah = int(float(row[ssr]))
                    except:
                        jumlah = 0
                    
                    if jumlah > 0:
                        cur.execute("""
                            INSERT INTO agregasi_hasil_review 
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

def ambil_agregasi_terakhir_dari_neon():
    conn = dapatkan_koneksi_neon()
    if not conn:
        return pd.DataFrame(), None
        
    try:
        with conn.cursor() as cur:
            # 🔥 PERBAIKAN 2: Ubah dari tanggal_dibuat menjadi tanggal_review yang memang ada di tabel
            cur.execute("SELECT MAX(tanggal_review) FROM agregasi_hasil_review")
            target_date = cur.fetchone()[0]
            
            if not target_date:
                return pd.DataFrame(), None
                
            cur.execute("""
                SELECT nama_ssr, indikator_kesalahan, jumlah_kesalahan 
                FROM agregasi_hasil_review 
                WHERE tanggal_review = %s
            """, (target_date,))
            rows = cur.fetchall()
            
            if not rows:
                return pd.DataFrame(), target_date
                
            df_long = pd.DataFrame(rows, columns=['nama_ssr', 'indikator_kesalahan', 'jumlah_kesalahan'])
            df_wide = df_long.pivot_table(
                index='indikator_kesalahan', 
                columns='nama_ssr', 
                values='jumlah_kesalahan',
                aggfunc='sum'
            ).fillna(0).astype(int)
            
            df_wide = df_wide.reset_index()
            df_wide.rename(columns={'indikator_kesalahan': 'INDIKATOR KESALAHAN DATA'}, inplace=True)
            
            kolom_ssr = [c for c in df_wide.columns if c != 'INDIKATOR KESALAHAN DATA']
            df_wide['Jumlah per indikator'] = df_wide[kolom_ssr].sum(axis=1)
            
            total_semua = df_wide['Jumlah per indikator'].sum()
            if total_semua > 0:
                df_wide['%'] = ((df_wide['Jumlah per indikator'] / total_semua) * 100).round(1)
            else:
                df_wide['%'] = 0.0
                
            df_wide.set_index('INDIKATOR KESALAHAN DATA', inplace=True)
            return df_wide, target_date
            
    except Exception as e:
        st.error(f"Gagal memuat agregasi terakhir dari Neon DB: {e}")
        return pd.DataFrame(), None
    finally:
        conn.close()

def simpan_detil_review_ke_neon(df_detil):
    if df_detil is None or df_detil.empty:
        return False
        
    conn = dapatkan_koneksi_neon()
    if not conn:
        return False
        
    try:
        with conn.cursor() as cur:
            query = """
                INSERT INTO hasil_review_penjangkauan 
                ("Lembaga SSR", "Tanggal", "ID Klien", "Kode Petugas", 
                 "Nama Kota", "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", 
                 "Validasi Hasil Review", "Justifikasi")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            
            list_data = []
            for _, row in df_detil.iterrows():
                list_data.append((
                    str(row.get('Lembaga SSR', '')),
                    str(row.get('Tanggal', '')),
                    str(row.get('ID Klien', '')),
                    str(row.get('Kode Petugas', '')),
                    str(row.get('Nama Kota', '')),
                    str(row.get('NIK', '')),
                    str(row.get('Tipe Sasaran', '')),
                    str(row.get('Indikator Kesalahan Data', row.get('INDIKATOR KESALAHAN DATA', ''))),
                    str(row.get('Validasi Hasil Review', '')),
                    str(row.get('Justifikasi', ''))
                ))
                
            cur.executemany(query, list_data)
            conn.commit()
            return True
    except Exception as e:
        conn.rollback()
        st.error(f"Gagal menyimpan ke DB: {e}") 
        return False
    finally:
        conn.close()

def ambil_detil_terakhir_dari_neon():
    conn = dapatkan_koneksi_neon()
    if not conn:
        return pd.DataFrame(), None
        
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT "Lembaga SSR", "Tanggal", "ID Klien", "Kode Petugas", 
                       "Nama Kota", "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", 
                       "Validasi Hasil Review", "Justifikasi"
                FROM hasil_review_penjangkauan
                ORDER BY "Tanggal" DESC
                LIMIT 500
            """)
            
            rows = cur.fetchall()
            
            if not rows:
                # 🔥 PERBAIKAN 3: Menggunakan datetime langsung (bukan dt.datetime)
                return pd.DataFrame(), datetime.now()
                
            df = pd.DataFrame(rows, columns=[
                "Lembaga SSR", "Tanggal", "ID Klien", "Kode Petugas", 
                "Nama Kota", "NIK", "Tipe Sasaran", "Indikator Kesalahan Data", 
                "Validasi Hasil Review", "Justifikasi"
            ])
            
            # 🔥 PERBAIKAN 4: Menggunakan datetime langsung (bukan dt.datetime)
            return df, datetime.now()
    except Exception as e:
        st.error(f"Gagal memuat histori detil review dari Neon: {e}")
        return pd.DataFrame(), None
    finally:
        conn.close()

def ambil_status_storage_neon():
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
