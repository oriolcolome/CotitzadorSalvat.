import streamlit as st
import pandas as pd
import os
import gc

# --- CONFIGURACIÓ ---
st.set_page_config(page_title="Cotitzador Logística", page_icon="🚛", layout="wide")

# --- ESTILS (CSS) PER CENTRAR I MAQUILLAR ---
st.markdown("""
    <style>
    /* Estils generals */
    .big-font { font-size:36px !important; font-weight: bold; color: #166534; }
    .success-card { background-color: #dcfce7; padding: 20px; border-radius: 10px; border: 2px solid #16a34a; text-align: center; }
    
    /* CAPÇALERA PERSONALITZADA (LOGO + TÍTOL JUNTS) */
    .header-container {
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: center;
        padding: 20px;
        background-color: white;
        border-radius: 10px;
        margin-bottom: 30px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .logo-img {
        width: 80px;
        height: auto;
        margin-right: 20px;
    }
    
    .title-text {
        font-family: 'Helvetica Neue', sans-serif;
        color: #0f172a;
        margin: 0;
        font-size: 40px;
        font-weight: 700;
    }
    
    /* Subtítols de secció */
    .section-header {
        color: #1e40af;
        font-size: 20px;
        font-weight: bold;
        border-bottom: 2px solid #1e40af;
        padding-bottom: 5px;
        margin-top: 10px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CAPÇALERA AMB HTML (PERQUÈ QUEDI CENTRAT PERFECTE) ---
# Intentem trobar el logo local, si no, posem una url d'un camió
arxius = os.listdir('.')
logo_local = next((f for f in arxius if f.lower().startswith('logo') and f.endswith(('.png', '.jpg', '.jpeg'))), None)

if logo_local:
    # Si tens el fitxer 'logo.png', el farem servir (cal llegir-lo en binari, però per simplificar usem st.image standard ocult i HTML per estructura)
    # Truc visual: Usem columnes natives però ajustades per centrar
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.image(logo_local, width=150)
        st.markdown("<h1 style='text-align: center;'>Calculadora d'Enviaments</h1>", unsafe_allow_html=True)
else:
    # Si no tens logo, usem aquest disseny HTML que queda perfecte
    st.markdown("""
    <div class="header-container">
        <img src="https://cdn-icons-png.flaticon.com/512/6213/6213387.png" class="logo-img">
        <h1 class="title-text">Calculadora d'Enviaments</h1>
    </div>
    """, unsafe_allow_html=True)


# --- BARRA LATERAL (INSTRUCCIONS DETALLADES) ---
with st.sidebar:
    st.header("📖 Guia d'Ús")
    
    st.markdown("""
    ### 1️⃣ Destinació
    * Selecciona el **País** al desplegable.
    * Escriu els **2 primers dígits** del Codi Postal.
    * *Ex: Per a 08001, posa 08.*

    ### 2️⃣ Serveis Extres
    Marca les caselles si cal:
    * **ADR:** Per a mercaderies perilloses.
    * **Entrega:** Si és domicili particular o cal plataforma.
    * **Cita Prèvia:** Si cal concertar hora.

    ### 3️⃣ La Càrrega
    * Tria si és **Pallet Europeu**, **Americà** o mida lliure.
    * Indica **pes per palet** i **quantitat**.
    
    ---
    ℹ️ *Nota: Els suplements (MAUT, Gasoil...) es calculen automàticament.*
    """)
    st.caption("v13.0 - Disseny Centrat")

# --- CÀRREGA OPTIMITZADA ---
@st.cache_data(ttl="2h", show_spinner="Carregant tarifes...")
def carregar_dades_light():
    gc.collect()
    arxius = os.listdir('.')
    fitxer = next((f for f in arxius if f.endswith('.xlsx') and not f.startswith('~$')), None)
    
    if not fitxer: return None, None, None, "MISSING_EXCEL"

    try:
        xls = pd.ExcelFile(fitxer, engine='openpyxl')
        
        # DADES
        df_datos = pd.read_excel(xls, "DATOS", header=None, nrows=25)
        fila_pais = df_datos[df_datos.apply(lambda x: x.astype(str).str.contains('PAISES', case=False)).any(axis=1)].index[0]
        df_datos = pd.read_excel(xls, "DATOS", header=fila_pais)
        df_datos.columns = df_datos.columns.str.strip().str.upper()
        df_datos = df_datos.dropna(how='all', axis=1)

        # TARIFES
        df_tarifas = pd.read_excel(xls, "SALIDAS EXPORT", header=None, nrows=25)
        fila_tarifes = df_tarifas[df_tarifas.apply(lambda x: x.astype(str).str.contains('ZIP CODE|AUXILIAR', regex=True, case=False)).any(axis=1)].index[0]
        df_tarifas = pd.read_excel(xls, "SALIDAS EXPORT", header=fila_tarifes)
        df_tarifas.columns = df_tarifas.columns.str.strip().str.upper()

        renames = {}
        for col in df_tarifas.columns:
            if 'CITA' in col: renames[col] = 'T.CITA'
            elif 'TASA' in col: renames[col] = 'TASA'
            elif 'ENTREGA' in col: renames[col] = 'ENTREGA'
        if renames: df_tarifas = df_tarifas.rename(columns=renames)
        
        cols_clau = ['PAIS', 'ZIP CODE', 'AUXILIAR']
        cols_existents = [c for c in cols_clau if c in df_tarifas.columns]
        
        cols_extra = [c for c in ['SALIDAS', 'TRANSIT TIME', 'LLEGADA', 'ADR', 'ENTREGA', 'T.CITA', 'TASA'] if c in df_tarifas.columns]
        mapa = df_tarifas[cols_existents + cols_extra].dropna(subset=cols_existents).copy()
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

df_datos, mapa_zones, df_preus, error = carregar_dades_light()

if error != "OK":
    st.error(f"⚠️ Error: {error}")
    st.stop()

# --- INTERFÍCIE ---
c_left, c_right = st.columns([1, 1.5])

with c_left:
    st.markdown('<div class="section-header">1. Dades del Servei</div>', unsafe_allow_html=True)
    llista_paises = sorted(df_datos['PAISES'].dropna().unique().tolist())
    pais = st.selectbox("País de Destí", llista_paises)
    cp = st.text_input("Codi Postal (2 dígits)", max_chars=2, help="Ex: 08")
    
    with st.expander("⚙️ Serveis Addicionals (Opcional)", expanded=True):
        col_x1, col_x2, col_x3 = st.columns(3)
        es_adr = col_x1.checkbox("ADR", help="Mercaderia Perillosa")
        vol_entrega = col_x2.checkbox("Entrega", help="Plataforma/Domicili")
        vol_cita = col_x3.checkbox("Cita", help="Concertar hora")
    
    st.markdown('<div class="section-header">2. La Càrrega</div>', unsafe_allow_html=True)
    tipus_palet = st.radio("Tipus:", ["EUR (1.2x0.8)", "Americà (1.2x1.0)", "Lliure"], horizontal=True)
    
    if "EUR" in tipus_palet: llarg, ample = 1.20, 0.80
    elif "Americà" in tipus_palet: llarg, ample = 1.20, 1.00
    else:
        c_l, c_a = st.columns(2)
        llarg = c_l.number_input("Llarg", 0.0, 13.6, 1.2)
        ample = c_a.number_input("Ample", 0.0, 3.0, 0.8)
        
    c_h, c_q = st.columns(2)
    alt = c_h.number_input("Alt", 0.0, 3.0, 1.0)
    quantitat = c_q.number_input("Unitats", 1, 50, 1)
    pes_unitari = st.number_input("Pes/Unitat (kg)", 0, 2000, 200)

    st.write("")
    calcular = st.button("CALCULAR COTITZACIÓ", type="primary", use_container_width=True)

with c_right:
    if calcular:
        if not cp:
            st.error("⚠️ Posa el Codi Postal")
        else:
            pes_total = pes_unitari * quantitat
            volum_total = llarg * ample * alt * quantitat
            pes_tasable = max(pes_total, volum_total * 333)

            cp_norm = str(cp).zfill(2)
            rutes = mapa_zones[(mapa_zones['PAIS'] == pais.upper()) & (mapa_zones['ZIP CODE'] == cp_norm)].copy()

            if rutes.empty:
                st.warning(f"❌ No s'ha trobat tarifa per a {pais} CP {cp_norm}")
            else:
                ruta_final = rutes.iloc[0]
                if es_adr and 'ADR' in rutes.columns:
                    match = rutes[rutes['ADR'] == "SI"]
                    if not match.empty: ruta_final = match.iloc[0]
                if vol_entrega and 'ENTREGA' in rutes.columns:
                    match = rutes[rutes['ENTREGA'] == "SI"]
                    if not match.empty: ruta_final = match.iloc[0]

                zona = ruta_final['AUXILIAR']
                dies = ruta_final.get('SALIDAS', '-')
                transit = ruta_final.get('TRANSIT TIME', ruta_final.get('LLEGADA', '-'))

                pesos = df_preus.index.tolist()
                pes_tarifa = next((p for p in pesos if p >= pes_tasable), None)
                
                if pes_tarifa and zona in df_preus.columns:
                    preu_base = df_preus.loc[pes_tarifa, zona]
                    total_extres = 0
                    detalls = []
                    
                    info_pais = df_datos[df_datos['PAISES'] == pais].iloc[0]
                    if str(info_pais.get('MAUT', '')).upper() == 'SI':
                        pct = info_pais.get('MAUD %', 0)
                        if pct > 1: pct /= 100
                        val_maut = preu_base * pct
                        total_extres += val_maut
                        detalls.append(f"MAUT ({pct*100:.1f}%): {val_maut:.2f}€")

                    if vol_cita:
                        val_cita = float(ruta_final.get('T.CITA', 0)) if str(ruta_final.get('T.CITA', 0)).replace('.','').isdigit() else 0
                        total_extres += val_cita
                        detalls.append(f"Cita: {val_cita:.2f}€")

                    val_tasa = float(ruta_final.get('TASA', 0)) if str(ruta_final.get('TASA', 0)).replace('.','').isdigit() else 0
                    total_extres += val_tasa
                    if val_tasa > 0: detalls.append(f"Taxes: {val_tasa:.2f}€")

                    total_final = preu_base + total_extres

                    st.markdown(f"""
                    <div class="success-card">
                        <div style="font-size:16px; color:#15803d; margin-bottom:5px;">PREU TOTAL ESTIMAT</div>
                        <div class="big-font">{total_final:.2f} €</div>
                        <div style="font-size:12px; color:#15803d;">Pes Tasable: {pes_tasable:.2f} kg</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.write("")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📋 Info Operativa**")
                        st.write(f"Zona: {zona}")
                        st.write(f"Sortides: {dies}")
                        st.write(f"Trànsit: {transit}")
                    with c2:
                        st.markdown("**💰 Desglossament**")
                        st.write(f"Base: {preu_base:.2f}€")
                        for d in detalls: st.write(f"+ {d}")
                else:
                    st.error("Pes fora de rang.")