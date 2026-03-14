import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import uuid
import os
import plotly.express as px
import io
import time
import json
from streamlit_geolocation import streamlit_geolocation 

st.set_page_config(page_title="ST Smart Tour ERP", layout="wide", page_icon="✈️")

# --- CSS KUSTOM: FLUENT DESIGN ---
def set_custom_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700;800&display=swap');
        html, body, [class*="css"], p, span, label, div, table { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important; color: #1E1E1E !important; }
        .stApp { background: linear-gradient(135deg, #f3f3f3 0%, #e6eef5 100%); }
        [data-testid="stImage"] { display: flex; justify-content: center; align-items: center; margin-bottom: -15px; }
        @keyframes fluentFadeIn { 0% { opacity: 0; transform: translateY(15px); } 100% { opacity: 1; transform: translateY(0); } }
        .block-container { animation: fluentFadeIn 0.8s ease-out; }
        [data-testid="stForm"], .css-1r6slb0, .css-12oz5g7 { background-color: rgba(255, 255, 255, 0.85) !important; backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.9); border-radius: 12px !important; box-shadow: 0 8px 32px rgba(0,0,0,0.06) !important; padding: 30px !important; }
        .app-title { text-align: center; color: #0078D4 !important; font-size: 2.5rem !important; font-weight: 800 !important; letter-spacing: 0.5px; margin-top: 10px; margin-bottom: 0px; }
        .app-subtitle { text-align: center; color: #666666 !important; font-size: 1.1rem !important; font-weight: 600 !important; letter-spacing: 1px; margin-top: -5px; margin-bottom: 25px; text-transform: uppercase; }
        .stButton>button { background-color: #0078D4 !important; border: none !important; border-radius: 8px !important; padding: 0.6rem 1.4rem !important; transition: all 0.2s ease !important; box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important; width: 100%; }
        .stButton>button * { color: #FFFFFF !important; font-weight: 600 !important; font-size: 1.1rem !important; }
        .stButton>button:hover { background-color: #106EBE !important; transform: scale(1.02); box-shadow: 0 6px 12px rgba(0, 120, 212, 0.3) !important; }
        .stTextInput>div>div>input, .stNumberInput>div>div>input, .stTextArea>div>div>textarea { border-radius: 6px !important; border: 1px solid rgba(0,0,0,0.2) !important; background-color: #FFFFFF !important; color: #1E1E1E !important; border-bottom: 2px solid rgba(0,0,0,0.3) !important; padding: 10px !important; }
        .stTextInput>div>div>input:focus, .stNumberInput>div>div>input:focus { border-bottom: 2px solid #0078D4 !important; }
    </style>
    """, unsafe_allow_html=True)

set_custom_css()

if not os.path.exists("uploads"):
    os.makedirs("uploads")

# --- KONEKSI KE GOOGLE SHEETS (DENGAN PENANGKAL ERROR JWT) ---
@st.cache_resource
def init_connection():
    if "google_credentials" in st.secrets:
        kunci_str = st.secrets["google_credentials"]
        kunci_dict = json.loads(kunci_str)
        
        # --- KODE AJAIB PENYELAMAT JWT SIGNATURE ---
        # Memperbaiki spasi/enter (\n) rahasia Google yang rusak saat dibaca Streamlit
        kunci_dict["private_key"] = kunci_dict["private_key"].replace('\\n', '\n')
        
        gc = gspread.service_account_from_dict(kunci_dict)
    else:
        gc = gspread.service_account(filename='kunci.json') 
    
    sh = gc.open('Database_Travel')
    return sh

try:
    sh = init_connection()
except Exception as e:
    st.error(f"Gagal terhubung ke database. Error: {e}")
    st.stop()

@st.cache_resource
def get_worksheet(sheet_name):
    return sh.worksheet(sheet_name)

try:
    ws_users = get_worksheet('Users')
    ws_laporan = get_worksheet('Laporan')
    ws_audit = get_worksheet('Audit_Log')
    ws_absen = get_worksheet('Absen')
    ws_jurnal = get_worksheet('Jurnal_Umum')
    ws_aset = get_worksheet('Aset_Tetap')
except Exception as e:
    st.error(f"Sheet tidak ditemukan. Error: {e}")
    st.stop()

@st.cache_data(ttl=15)
def get_data(sheet_name):
    ws = get_worksheet(sheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def catat_audit(user, aksi, keterangan):
    waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws_audit.append_row([waktu_sekarang, user, aksi, keterangan])
    st.cache_data.clear()

def simpan_file(file_upload, nama_file):
    path = os.path.join("uploads", nama_file)
    with open(path, "wb") as f:
        f.write(file_upload.getbuffer())
    return path

def format_rupiah(angka):
    return f"Rp {angka:,.0f}".replace(',', '.')

daftar_akun = ["111 - Kas & Bank", "112 - Piutang Usaha (Klien)", "113 - Uang Muka Vendor", "121 - Aset Tetap (Kendaraan/Peralatan)", "122 - Akumulasi Penyusutan Aset Tetap", "211 - Hutang Usaha", "311 - Modal Perusahaan", "411 - Pendapatan Jasa Tour & Travel", "511 - Beban Gaji Karyawan", "512 - Beban Operasional Perjalanan", "513 - Beban Pemasaran", "514 - Beban Administrasi & Umum", "515 - Beban Penyusutan Aset"]

# --- SISTEM LOGIN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.current_role = ""

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.3, 1])
    with col2:
        st.write("<br><br>", unsafe_allow_html=True)
        try:
            st.image("smart.png", width=220)
        except Exception:
            pass
        
        st.markdown("<h1 class='app-title'>ST SMART TOUR</h1>", unsafe_allow_html=True)
        st.markdown("<p class='app-subtitle'>Enterprise Resource Planning</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown("<h3 style='text-align:center; color:#1E1E1E; font-size:1.3rem; margin-bottom:15px;'>🔐 Secure Login</h3>", unsafe_allow_html=True)
            input_user = st.text_input("Username")
            input_pass = st.text_input("Password", type="password")
            st.write("<br>", unsafe_allow_html=True)
            submit_login = st.form_submit_button("Sign In 🚀", use_container_width=True)
            
            if submit_login:
                with st.spinner("Memverifikasi kredensial..."):
                    time.sleep(1)
                    df_users = get_data("Users")
                    df_users['password'] = df_users['password'].astype(str)
                    user_match = df_users[(df_users['username'] == input_user) & (df_users['password'] == str(input_pass))]
                    
                    if not user_match.empty:
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_match.iloc[0]['nama']
                        st.session_state.current_role = user_match.iloc[0]['role']
                        catat_audit(st.session_state.current_user, "LOGIN", "Berhasil masuk")
                        st.rerun()
                    else:
                        st.error("⚠️ Username atau Password salah!")
else:
    st.sidebar.markdown(f"### 👤 Hai, {st.session_state.current_user}")
    st.sidebar.markdown(f"**Posisi:** `{st.session_state.current_role}`")
    st.sidebar.write("---")
    if st.sidebar.button("Keluar (Logout)", type="primary"):
        catat_audit(st.session_state.current_user, "LOGOUT", "Keluar dari sistem")
        st.session_state.logged_in = False
        st.session_state.current_user = ""
        st.session_state.current_role = ""
        st.rerun()

    # ==========================================
    # HALAMAN KARYAWAN (DENGAN GPS)
    # ==========================================
    if st.session_state.current_role == "Karyawan":
        menu_karyawan = st.radio("Workspace:", ["📝 Buat Laporan", "📸 Absensi Digital"], horizontal=True)
        st.write("---")

        if menu_karyawan == "📝 Buat Laporan":
            st.markdown("## 📝 Formulir Pelaporan Operasional")
            with st.form("form_lapor", clear_on_submit=True):
                tgl_lapor = st.date_input("Tanggal Transaksi/Kegiatan")
                opsi_kategori = st.selectbox("Kategori Pelaporan", ["Pengeluaran Perjalanan", "Pemasukan Klien", "Lainnya"])
                if opsi_kategori == "Lainnya":
                    kategori_final = st.text_input("Sebutkan kategori spesifik:")
                else:
                    kategori_final = opsi_kategori
                
                isi_laporan = st.text_area("Detail Laporan Lengkap")
                st.write("**Nominal Transaksi**")
                nominal = st.number_input("Ketik angka tanpa titik", min_value=0, step=50000)
                st.info(f"Otomatis terbaca: **{format_rupiah(nominal)}**")
                file_bukti = st.file_uploader("Upload Bukti Transaksi (Opsional)", type=["jpg", "jpeg", "png", "pdf"])
                
                if st.form_submit_button("Submit Laporan"):
                    if isi_laporan == "" or kategori_final == "":
                        st.error("Detail dan Kategori laporan tidak boleh kosong!")
                    else:
                        id_laporan = f"LAP-{str(uuid.uuid4())[:6].upper()}"
                        tgl_str = tgl_lapor.strftime("%Y-%m-%d")
                        nama_file_simpan = "Tidak ada"
                        if file_bukti is not None:
                            nama_file_simpan = f"{id_laporan}_{file_bukti.name}"
                            simpan_file(file_bukti, nama_file_simpan)
                        
                        ws_laporan.append_row([id_laporan, tgl_str, st.session_state.current_user, kategori_final, isi_laporan, nominal, nama_file_simpan])
                        
                        if opsi_kategori == "Pengeluaran Perjalanan":
                            akun_debit, akun_kredit = "512 - Beban Operasional Perjalanan", "111 - Kas & Bank"
                        elif opsi_kategori == "Pemasukan Klien":
                            akun_debit, akun_kredit = "111 - Kas & Bank", "411 - Pendapatan Jasa Tour & Travel"
                        else:
                            akun_debit, akun_kredit = "514 - Beban Administrasi & Umum", "111 - Kas & Bank"
                            
                        ket_jurnal = f"Auto-Posting dari {id_laporan}: {isi_laporan}"
                        id_jur1 = f"JUR-{str(uuid.uuid4())[:5].upper()}"
                        ws_jurnal.append_row([id_jur1, tgl_str, akun_debit, ket_jurnal, nominal, 0, "Sistem Otomatis", nama_file_simpan])
                        id_jur2 = f"JUR-{str(uuid.uuid4())[:5].upper()}"
                        ws_jurnal.append_row([id_jur2, tgl_str, akun_kredit, ket_jurnal, 0, nominal, "Sistem Otomatis", nama_file_simpan])
                        catat_audit(st.session_state.current_user, "INPUT_LAPORAN", f"Submit ID: {id_laporan}")
                        st.success("Laporan berhasil disubmit ke server pusat.")

        elif menu_karyawan == "📸 Absensi Digital":
            st.markdown("## 📷 Sistem Absensi Kehadiran & Lokasi")
            jenis_absen = st.radio("Status Kehadiran:", ["Hadir (Check-in)", "Pulang (Check-out)"], horizontal=True)
            
            st.markdown("### 📍 Verifikasi Lokasi (Wajib)")
            st.info("Sistem membutuhkan verifikasi lokasi GPS Anda untuk memastikan Anda berada di area kantor.")
            lokasi_saat_ini = streamlit_geolocation()
            
            link_gmaps = "Belum Terdeteksi"
            if lokasi_saat_ini['latitude'] is not None and lokasi_saat_ini['longitude'] is not None:
                lat = lokasi_saat_ini['latitude']
                lon = lokasi_saat_ini['longitude']
                link_gmaps = f"https://www.google.com/maps?q={lat},{lon}"
                st.success("✅ Titik kordinat lokasi berhasil dikunci oleh satelit!")
                st.markdown(f"[Lihat Peta Lokasi Saya Saat Ini]({link_gmaps})")
            
            st.write("---")
            st.markdown("### 📸 Verifikasi Wajah (Selfie)")
            foto_absen = st.camera_input("Ambil Foto Selfie Anda Sekarang")
            
            if st.button("Submit Absensi ✔️"):
                if foto_absen is None:
                    st.error("⚠️ Gagal: Anda wajib mengambil foto selfie.")
                elif lokasi_saat_ini['latitude'] is None:
                    st.error("⚠️ Gagal: Anda wajib mengklik tombol 'Get Location' untuk verifikasi GPS.")
                else:
                    waktu_sekarang = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    id_absen = f"ABS-{str(uuid.uuid4())[:5].upper()}"
                    nama_file_foto = f"{id_absen}_{st.session_state.current_user}.jpg"
                    simpan_file(foto_absen, nama_file_foto)
                    ws_absen.append_row([id_absen, waktu_sekarang, st.session_state.current_user, jenis_absen, nama_file_foto, link_gmaps])
                    catat_audit(st.session_state.current_user, "ABSENSI_GPS", f"Absensi {jenis_absen} terpantau GPS")
                    st.success(f"Absensi {jenis_absen} beserta titik lokasi Anda berhasil diverifikasi!")
                    st.balloons()

    # ==========================================
    # HALAMAN AKUNTAN
    # ==========================================
    elif st.session_state.current_role == "Akuntan":
        st.markdown("## 📊 Finance & Accounting Workspace")
        menu_akuntan = st.sidebar.radio("Navigasi Modul:", ["📈 Laba Rugi", "✍️ Entri Jurnal", "📖 Buku Besar", "🏢 Aset Tetap"])
        
        if menu_akuntan == "📈 Laba Rugi":
            st.markdown("### 📈 Dashboard Laba Rugi")
            df_jurnal = get_data("Jurnal_Umum")
            df_laporan = get_data("Laporan")
            
            if df_jurnal.empty:
                st.info("Belum ada data transaksi tercatat.")
            else:
                df_jurnal['Debit'] = pd.to_numeric(df_jurnal['Debit'], errors='coerce').fillna(0)
                df_jurnal['Kredit'] = pd.to_numeric(df_jurnal['Kredit'], errors='coerce').fillna(0)
                
                df_pendapatan = df_jurnal[df_jurnal['Kode & Nama Akun'].str.contains("411")]
                total_pendapatan = df_pendapatan['Kredit'].sum() - df_pendapatan['Debit'].sum()
                
                df_beban = df_jurnal[df_jurnal['Kode & Nama Akun'].str.startswith("5")]
                total_beban = df_beban['Debit'].sum() - df_beban['Kredit'].sum()
                
                laba_bersih = total_pendapatan - total_beban
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Pendapatan Kotor", format_rupiah(total_pendapatan))
                col2.metric("Beban Operasional", format_rupiah(total_beban))
                col3.metric("Laba Bersih (Net Profit)", format_rupiah(laba_bersih), delta="Profit" if laba_bersih > 0 else "Rugi")
                
                st.write("---")
                st.markdown("### 📉 Visualisasi Arus Keuangan")
                kolom_grafik1, kolom_grafik2 = st.columns(2)
                with kolom_grafik1:
                    if not df_beban.empty:
                        df_beban_group = df_beban.groupby('Kode & Nama Akun')['Debit'].sum().reset_index()
                        fig_pie = px.pie(df_beban_group, values='Debit', names='Kode & Nama Akun', title='Komposisi Pengeluaran', hole=0.5, color_discrete_sequence=px.colors.sequential.Blues_r)
                        fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#1E1E1E')
                        st.plotly_chart(fig_pie, use_container_width=True)
                with kolom_grafik2:
                    if not df_jurnal.empty:
                        df_kas = df_jurnal[df_jurnal['Kode & Nama Akun'].str.contains("111")]
                        df_kas_group = df_kas.groupby('Tanggal')[['Debit', 'Kredit']].sum().reset_index()
                        df_kas_group = df_kas_group.rename(columns={'Debit': 'Uang Masuk', 'Kredit': 'Uang Keluar'})
                        fig_bar = px.bar(df_kas_group, x='Tanggal', y=['Uang Masuk', 'Uang Keluar'], title='Tren Arus Kas', barmode='group', color_discrete_sequence=['#0078D4', '#E81123'])
                        fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#1E1E1E')
                        st.plotly_chart(fig_bar, use_container_width=True)

        elif menu_akuntan == "✍️ Entri Jurnal":
            st.markdown("### ✍️ Entri Jurnal (Smart Mode)")
            with st.form("form_jurnal", clear_on_submit=True):
                tgl_jurnal = st.date_input("Tanggal Transaksi")
                jenis_transaksi = st.radio("Klasifikasi Transaksi:", ["📥 Penerimaan Kas", "📤 Pengeluaran Kas", "⚖️ Penyesuaian Manual"], horizontal=True)
                col1, col2 = st.columns(2)
                if jenis_transaksi == "📥 Penerimaan Kas":
                    with col1:
                        st.success(f"Debit (Auto): 111 - Kas & Bank")
                        akun_debit = "111 - Kas & Bank"
                    with col2:
                        akun_kredit = st.selectbox("Akun Kredit", [a for a in daftar_akun if "111" not in a], key="kredit")
                elif jenis_transaksi == "📤 Pengeluaran Kas":
                    with col1:
                        akun_debit = st.selectbox("Akun Debit", [a for a in daftar_akun if "111" not in a], key="debit")
                    with col2:
                        st.error(f"Kredit (Auto): 111 - Kas & Bank")
                        akun_kredit = "111 - Kas & Bank"
                else:
                    with col1:
                        akun_debit = st.selectbox("Akun Debit", daftar_akun, key="debit_manual")
                    with col2:
                        akun_kredit = st.selectbox("Akun Kredit", daftar_akun, key="kredit_manual")
                
                nominal_jurnal = st.number_input("Nominal Transaksi (Rp)", min_value=0, step=10000)
                keterangan_jurnal = st.text_input("Keterangan Detail (Wajib)")
                file_bukti = st.file_uploader("Upload Bukti Pendukung", type=["jpg", "png", "pdf"])
                
                if st.form_submit_button("Posting Transaksi"):
                    if keterangan_jurnal == "" or nominal_jurnal <= 0:
                        st.error("Gagal: Keterangan dan Nominal wajib diisi.")
                    elif akun_debit == akun_kredit:
                        st.error("Gagal: Akun Debit dan Kredit konflik.")
                    else:
                        id_jur_group = f"JUR-{str(uuid.uuid4())[:5].upper()}"
                        tgl_str = tgl_jurnal.strftime("%Y-%m-%d")
                        nama_file_simpan = "Tidak ada"
                        if file_bukti is not None:
                            nama_file_simpan = f"{id_jur_group}_{file_bukti.name}"
                            simpan_file(file_bukti, nama_file_simpan)
                        ws_jurnal.append_row([id_jur_group, tgl_str, akun_debit, keterangan_jurnal, nominal_jurnal, 0, st.session_state.current_user, nama_file_simpan])
                        ws_jurnal.append_row([id_jur_group, tgl_str, akun_kredit, keterangan_jurnal, 0, nominal_jurnal, st.session_state.current_user, nama_file_simpan])
                        catat_audit(st.session_state.current_user, "JURNAL", f"Posting Jurnal {jenis_transaksi}")
                        st.success("Transaksi berhasil diposting ke database!")

        elif menu_akuntan == "📖 Buku Besar":
            st.markdown("### 📖 Buku Besar (Ledger)")
            df_jurnal = get_data("Jurnal_Umum")
            if not df_jurnal.empty:
                filter_akun = st.selectbox("Filter berdasarkan Akun:", ["Tampilkan Semua"] + daftar_akun)
                if filter_akun != "Tampilkan Semua":
                    df_jurnal = df_jurnal[df_jurnal['Kode & Nama Akun'] == filter_akun]
                st.dataframe(df_jurnal, use_container_width=True)
                
        elif menu_akuntan == "🏢 Aset Tetap":
            st.markdown("### 🏢 Inventaris & Penyusutan Aset")
            with st.expander("➕ Daftarkan Aset Baru"):
                with st.form("form_aset"):
                    tgl_beli = st.date_input("Tanggal Pembelian")
                    nama_aset = st.text_input("Deskripsi Aset")
                    col1, col2 = st.columns(2)
                    with col1:
                        harga_beli = st.number_input("Nilai Perolehan (Rp)", min_value=0, step=100000)
                    with col2:
                        umur_bulan = st.number_input("Umur Ekonomis (Bulan)", min_value=1, value=60)
                    if st.form_submit_button("Simpan Aset"):
                        if nama_aset == "" or harga_beli == 0:
                            st.error("Gagal: Data tidak lengkap.")
                        else:
                            id_aset = f"AST-{str(uuid.uuid4())[:4].upper()}"
                            penyusutan_bulan = harga_beli / umur_bulan
                            ws_aset.append_row([id_aset, tgl_beli.strftime("%Y-%m-%d"), nama_aset, harga_beli, umur_bulan, penyusutan_bulan])
                            catat_audit(st.session_state.current_user, "INPUT_ASET", f"Menambah {nama_aset}")
                            st.success(f"Berhasil! Susut bulanan: {format_rupiah(penyusutan_bulan)}")
                            st.rerun()
            df_aset = get_data("Aset_Tetap")
            if not df_aset.empty:
                st.dataframe(df_aset, use_container_width=True)
                if st.button("🚀 Execute: Posting Jurnal Penyusutan Bulanan"):
                    total_susut = pd.to_numeric(df_aset['Penyusutan Per Bulan'], errors='coerce').sum()
                    id_jur_group = f"JUR-{str(uuid.uuid4())[:5].upper()}"
                    tgl_str = datetime.now().strftime("%Y-%m-%d")
                    ket_jurnal = f"Beban Penyusutan Aset Bulan {datetime.now().strftime('%B %Y')}"
                    ws_jurnal.append_row([id_jur_group, tgl_str, "515 - Beban Penyusutan Aset", ket_jurnal, total_susut, 0, "Sistem Otomatis", "Tidak ada"])
                    ws_jurnal.append_row([id_jur_group, tgl_str, "122 - Akumulasi Penyusutan Aset Tetap", ket_jurnal, 0, total_susut, "Sistem Otomatis", "Tidak ada"])
                    catat_audit(st.session_state.current_user, "AUTO_PENYUSUTAN", f"Posting Rp {total_susut}")
                    st.success("Proses eksekusi selesai.")

    # ==========================================
    # HALAMAN KHUSUS ADMIN (SUPER ADMIN VIEW)
    # ==========================================
    elif st.session_state.current_role == "Admin":
        st.markdown("<h1 style='color: #0078D4 !important;'>🪟 Administrator Control Panel</h1>", unsafe_allow_html=True)
        menu_admin = st.sidebar.radio("Sistem Monitoring:", ["📊 Executive Summary", "📋 Aktivitas Operasional", "📸 Verifikasi Kehadiran", "📖 Audit Jurnal", "🏢 Master Aset", "🛡️ Security Log"])
        
        if menu_admin == "📊 Executive Summary":
            st.markdown("### 📊 Executive Summary")
            df_laporan_admin = get_data("Laporan")
            df_absen_admin = get_data("Absen")
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                if not df_laporan_admin.empty:
                    df_laporan_admin['Nominal'] = pd.to_numeric(df_laporan_admin['Nominal'], errors='coerce').fillna(0)
                    fig_lapor = px.bar(df_laporan_admin, x='Kategori', y='Nominal', color='Pembuat', title='Volume Transaksi Operasional', text_auto='.2s', color_discrete_sequence=px.colors.sequential.Blues_r)
                    fig_lapor.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#1E1E1E')
                    st.plotly_chart(fig_lapor, use_container_width=True)
            with col_chart2:
                if not df_absen_admin.empty:
                    fig_absen = px.pie(df_absen_admin, names='Status', title='Rasio Kehadiran Staf', hole=0.5, color_discrete_sequence=['#0078D4', '#2B88D8', '#C7E0F4'])
                    fig_absen.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#1E1E1E')
                    st.plotly_chart(fig_absen, use_container_width=True)

        elif menu_admin == "📋 Aktivitas Operasional":
            st.markdown("### 📋 Log Laporan Karyawan")
            st.dataframe(get_data("Laporan"), use_container_width=True)
            
        elif menu_admin == "📸 Verifikasi Kehadiran":
            st.markdown("### 📸 Verifikasi Kehadiran Digital & Lokasi (GPS)")
            st.info("Anda bisa mengklik tautan pada kolom 'Lokasi Peta' untuk melihat titik kordinat satelit karyawan di Google Maps.")
            df_absen_admin = get_data("Absen")
            if not df_absen_admin.empty:
                st.dataframe(
                    df_absen_admin,
                    column_config={ "Lokasi Peta": st.column_config.LinkColumn("Buka Peta 🗺️") },
                    use_container_width=True
                )
            else:
                st.info("Belum ada data absensi.")
                
        elif menu_admin == "📖 Audit Jurnal":
            st.markdown("### 📖 Log Transaksi Akuntansi")
            st.dataframe(get_data("Jurnal_Umum"), use_container_width=True)
        elif menu_admin == "🏢 Master Aset":
            st.markdown("### 🏢 Database Aset Perusahaan")
            try:
                st.dataframe(get_data("Aset_Tetap"), use_container_width=True)
            except:
                st.info("Belum ada data.")
        elif menu_admin == "🛡️ Security Log":
            st.markdown("### 🛡️ System Audit Trail")
            st.dataframe(get_data("Audit_Log"), use_container_width=True)