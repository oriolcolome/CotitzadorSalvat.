import streamlit as st
import pandas as pd
import os

# --- CONFIGURACIÓ ---
st.set_page_config(page_title="Cotitzador Logística", page_icon="🚛", layout="wide")

# --- ESTILS CSS (Per fer-ho bonic) ---
st.markdown("""
    <style>
    .big-font { font-size:36px !important; font-weight: bold; color: #166534; }
    .header-style { font-size:20px; font-weight: bold; color: #1e40af; border-bottom: 2px solid #1e40af; padding-bottom: 5px; margin-bottom: 20px; }
    .success-card { background-color: #dcfce7; padding: 20px; border-radius: 10px; border: 2px solid #16a34a; text-align: center; }
    .info-box { background-color: #eff6ff; padding: 15px; border-radius: 8px; border: 1px solid #bfdbfe; font-size: 14px;}
    </style>
""", unsafe_allow_html=True)

# --- BARRA LATERAL (INSTRUCCIONS) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/759/759238.png", width=50) # Icona decorativa
    st.header("📖 Guia d'Ús")
    
    st.markdown("""
    ### 1️⃣ Destinació
    * Selecciona el **País** de la llista.
    * Introdueix només els **2 primers dígits** del Codi Postal.
    * *Exemple: Per a 08001, escriu 08.*

    ### 2️⃣ Serveis Extres
    Marca les caselles si l'enviament ho requereix:
    * **ADR:** Mercaderia perillosa.
    * **Entrega:** Si el client no té moll i necessita porta elevadora o entrega a domicili.
    * **Cita Prèvia:** Si cal concertar hora exacta.

    ### 3️⃣ La Càrrega
    Defineix els palets:
    * Pots triar **EUR** (1.2x0.8), **Americà** (1.2x1.0) o posar mides lliures.
    * Indica l'**alçada**, el **pes per palet** i la **quantitat**.
    
    ---
    ℹ️ *Els suplements (MAUT, Gasoil, Taxes) es calculen automàticament segons la zona.*
    """)
    st.caption("v10.0 - Edició Completa")

st.title("🚛 Calculadora d'Enviaments")

# --- CÀRREGA INTEL·LIGENT (NO TOCAR) ---
@st.cache_data(ttl=3600)
def carregar_dades_smart():
    # 1. Busquem l'Excel automàticament
    arxius = os.listdir('.')
    fitxer = next((f for f in arxius if f.endswith('.xlsx')), None)
    
    if not fitxer: return None, None, None, "No trobo cap fitxer .xlsx al servidor."

    try:
        # LLEGIR DADES GENERALS
        df_temp = pd.read_excel(fitxer, sheet_name="DATOS", header=None, nrows=20, engine='openpyxl')
        fila_pais = -1
        for i, row in df_temp.iterrows():
            if row.astype(str).str.contains('PAISES', case=False).any():
                fila_pais = i
                break
        
        if fila_pais == -1: return None, None, None, "No trobo la columna 'PAISES' a la pestanya DATOS."
        
        df_datos = pd.read_excel(fitxer, sheet_name="DATOS", header=fila_pais, engine='openpyxl')
        df_datos.columns = df_datos.columns.str.strip().str.upper()

        # LLEGIR TARIFES
        df_temp2 = pd.read_excel(fitxer, sheet_name="SALIDAS EXPORT", header=None, nrows=20, engine='openpyxl')
        fila_tarifes = -1
        for i, row in df_temp2.iterrows():
            if row.astype(str).str.contains('ZIP CODE|AUXILIAR', regex=True, case=False).any():
                fila_tarifes = i
                break
                
        if fila_tarifes == -1: return None, None, None, "No trobo 'ZIP CODE' a SALIDAS EXPORT."

        df_tarifas = pd.read_excel(fitxer, sheet_name="SALIDAS EXPORT", header=fila_tarifes, engine='openpyxl')
        df_tarifas.columns = df_tarifas.columns.str.strip().str.upper()

        # NETEJA
        mapa = df_tarifas.copy()
        renames = {}
        for col in mapa.columns:
            if 'CITA' in col: renames[col] = 'T.CITA'
            elif 'TASA' in col: renames[col] = 'TASA'
            elif 'ENTREGA' in col: renames[col] = 'ENTREGA'
        if renames: mapa = mapa.rename(columns=renames)
        
        cols_existents = [c for c in ['PAIS', 'ZIP CODE', 'AUXILIAR'] if c in mapa.columns]
        mapa = mapa.dropna(subset=cols_existents)
        mapa['ZIP CODE'] = mapa['ZIP CODE'].astype(str).str.replace(".0", "", regex=False).str.zfill(2)
        mapa['PAIS'] = mapa['PAIS'].str.strip().str.upper()
        
        if 'KILOS' in df_tarifas.columns:
            preus = df_tarifas.dropna(subset=['KILOS']).copy()
            preus['KILOS'] = pd.to_numeric(preus['KILOS'], errors='coerce')
            preus = preus.set_index('KILOS').sort_index()
        else:
            preus = None

        return df_datos, mapa, preus, "OK"

    except Exception as e:
        return None, None, None, str(e)

# Executem càrrega
df_datos, mapa_zones, df_preus, error = carregar_dades_smart()

if error != "OK":
    st.error(f"⚠️ Error de sistema: {error}")
    st.info("Revisa el fitxer requirements.txt a GitHub.")
    st.stop()

# --- INTERFÍCIE PRINCIPAL ---
c_left, c_right = st.columns([1, 1.5])

with c_left:
    st.markdown('<div class="header-style">1. Dades del Servei</div>', unsafe_allow_html=True)
    
    # Destí
    llista_paises = sorted(df_datos['PAISES'].dropna().unique().tolist())
    pais = st.selectbox("País de Destí", llista_paises)
    cp = st.text_input("Codi Postal (2 primers dígits)", max_chars=2, help="Ex: 08001 -> 08")
    
    st.write("")
    st.markdown("**Serveis Addicionals:**")
    
    # AQUI ESTAN ELS TOOLTIPS (?) QUE DEMANAVES
    col_x1, col_x2, col_x3 = st.columns(3)
    es_adr = col_x1.checkbox("ADR", help="Mercaderia Perillosa. Requereix vehicles especials i conductors certificats.")
    vol_entrega = col_x2.checkbox("Entrega", help="Marca aquesta opció si el destí és un domicili particular o no té moll de descàrrega (necessita plataforma).")
    vol_cita = col_x3.checkbox("Cita Prèvia", help="Servei per concertar dia i hora específica d'entrega. Sol tenir un cost extra.")
    
    st.markdown('<div class="header-style">2. Dades de la Càrrega</div>', unsafe_allow_html=True)
    tipus_palet = st.radio("Tipus de Palet:", ["EUR (1.2x0.8)", "Americà (1.2x1.0)", "Lliure"], horizontal=True)
    
    if "EUR" in tipus_palet: llarg, ample = 1.20, 0.80
    elif "Americà" in tipus_palet: llarg, ample = 1.20, 1.00
    else:
        c_l, c_a = st.columns(2)
        llarg = c_l.number_input("Llarg (m)", 0.0, 13.6, 1.2)
        ample = c_a.number_input("Ample (m)", 0.0, 3.0, 0.8)
        
    c_h, c_q = st.columns(2)
    alt = c_h.number_input("Alçada (m)", 0.0, 3.0, 1.0)
    quantitat = c_q.number_input("Quantitat de Palets", 1, 50, 1)
    
    pes_unitari = st.number_input("Pes per Palet (kg)", 0, 2000, 200, help="El pes real de cada palet individual.")

    st.write("")
    calcular = st.button("CALCULAR COTITZACIÓ", type="primary", use_container_width=True)

with c_right:
    if calcular:
        if not cp:
            st.error("⚠️ Si us plau, introdueix el Codi Postal.")
        else:
            # CÀLCULS
            pes_total = pes_unitari * quantitat
            volum_total = llarg * ample * alt * quantitat
            pes_tasable = max(pes_total, volum_total * 333)

            cp_norm = str(cp).zfill(2)
            rutes = mapa_zones[(mapa_zones['PAIS'] == pais.upper()) & (mapa_zones['ZIP CODE'] == cp_norm)].copy()

            if rutes.empty:
                st.warning(f"❌ No s'ha trobat tarifa per a {pais} amb CP {cp_norm}")
            else:
                # SELECCIÓ DE RUTA
                ruta_final = rutes.iloc[0]
                
                # Busquem si hi ha línia específica per ADR o Entrega
                if es_adr and 'ADR' in rutes.columns:
                    match = rutes[rutes['ADR'] == "SI"]
                    if not match.empty: ruta_final = match.iloc[0]
                
                if vol_entrega and 'ENTREGA' in rutes.columns:
                    match = rutes[rutes['ENTREGA'] == "SI"]
                    if not match.empty: ruta_final = match.iloc[0]

                zona = ruta_final['AUXILIAR']
                dies = ruta_final.get('SALIDAS', '-')
                transit = ruta_final.get('TRANSIT TIME', ruta_final.get('LLEGADA', '-'))

                # BUSCAR PREU
                pesos = df_preus.index.tolist()
                pes_tarifa = next((p for p in pesos if p >= pes_tasable), None)
                
                if pes_tarifa and zona in df_preus.columns:
                    preu_base = df_preus.loc[pes_tarifa, zona]
                    total_extres = 0
                    detalls = []
                    
                    # CÀLCUL EXTRES
                    info_pais = df_datos[df_datos['PAISES'] == pais].iloc[0]
                    
                    # MAUT
                    if str(info_pais.get('MAUT', '')).upper() == 'SI':
                        pct = info_pais.get('MAUD %', 0)
                        if pct > 1: pct /= 100
                        val_maut = preu_base * pct
                        total_extres += val_maut
                        detalls.append(f"Suplement MAUT ({pct*100:.1f}%): {val_maut:.2f}€")

                    # CITA
                    if vol_cita:
                        val_cita = float(ruta_final.get('T.CITA', 0)) if str(ruta_final.get('T.CITA', 0)).replace('.','').isdigit() else 0
                        total_extres += val_cita
                        if val_cita > 0: detalls.append(f"Cita Prèvia: {val_cita:.2f}€")
                        else: detalls.append("⚠️ Cita demanada (sense cost definit a tarifa)")

                    # TASA
                    val_tasa = float(ruta_final.get('TASA', 0)) if str(ruta_final.get('TASA', 0)).replace('.','').isdigit() else 0
                    total_extres += val_tasa
                    if val_tasa > 0: detalls.append(f"Taxes Gestió: {val_tasa:.2f}€")

                    total_final = preu_base + total_extres

                    # VISUALITZACIÓ RESULTATS
                    st.markdown(f"""
                    <div class="success-card">
                        <div style="font-size:16px; color:#15803d; margin-bottom: 5px;">PREU TOTAL ESTIMAT</div>
                        <div class="big-font">{total_final:.2f} €</div>
                        <div style="font-size:12px; color:#15803d;">Pes Tasable: {pes_tasable:.2f} kg (Rang {pes_tarifa}kg)</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.write("")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📋 Informació Operativa**")
                        st.markdown(f"""
                        * **Zona:** `{zona}`
                        * **Dies Sortida:** `{dies}`
                        * **Trànsit:** `{transit}`
                        """)
                    
                    with c2:
                        st.markdown("**💰 Desglossament**")
                        st.write(f"* Tarifa Base: {preu_base:.2f}€")
                        for d in detalls:
                            st.write(f"* {d}")

                else:
                    st.error(f"Pes fora de rang. Màxim admès per zona {zona}: {max(pesos)}kg")