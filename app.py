import streamlit as st
import pandas as pd
import os
import gc # Garbage Collector (per netejar memòria)

# --- CONFIGURACIÓ ---
st.set_page_config(page_title="Cotitzador Logística", page_icon="🚛", layout="wide")

# --- ESTILS ---
st.markdown("""
    <style>
    .big-font { font-size:36px !important; font-weight: bold; color: #166534; }
    .header-style { font-size:20px; font-weight: bold; color: #1e40af; border-bottom: 2px solid #1e40af; padding-bottom: 5px; margin-bottom: 20px; }
    .success-card { background-color: #dcfce7; padding: 20px; border-radius: 10px; border: 2px solid #16a34a; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# --- CAPÇALERA AMB CONTROL D'ERRORS IMATGE ---
col_logo, col_titol = st.columns([1, 4])
with col_logo:
    # Sistema anti-error de logo
    arxius = os.listdir('.')
    logo_file = next((f for f in arxius if f.lower().startswith('logo') and f.endswith(('.png', '.jpg', '.jpeg'))), None)
    if logo_file: st.image(logo_file, width=120)
    else: st.write("🚛")

with col_titol:
    st.title("Calculadora d'Enviaments")

with st.sidebar:
    st.header("📖 Guia Ràpida")
    st.info("1. Selecciona País i CP.\n2. Marca els extres.\n3. Posa mides i pes.")
    st.caption("v12.0 - Memòria Optimitzada")

# --- CÀRREGA OPTIMITZADA (NO SOBRECARREGA LA RAM) ---
@st.cache_data(ttl="2h", show_spinner="Carregant tarifes...")
def carregar_dades_light():
    # Netejem memòria abans de començar
    gc.collect()
    
    arxius = os.listdir('.')
    fitxer = next((f for f in arxius if f.endswith('.xlsx') and not f.startswith('~$')), None)
    
    if not fitxer: return None, None, None, "MISSING_EXCEL"

    try:
        # LLEGIR NOMÉS EL NECESSARI (Engine openpyxl és obligatori)
        xls = pd.ExcelFile(fitxer, engine='openpyxl')
        
        # 1. DADES GENERALS
        df_datos = pd.read_excel(xls, "DATOS", header=None, nrows=25)
        fila_pais = df_datos[df_datos.apply(lambda x: x.astype(str).str.contains('PAISES', case=False)).any(axis=1)].index[0]
        df_datos = pd.read_excel(xls, "DATOS", header=fila_pais)
        df_datos.columns = df_datos.columns.str.strip().str.upper()
        # Netejem columnes buides per estalviar espai
        df_datos = df_datos.dropna(how='all', axis=1)

        # 2. TARIFES
        df_tarifas = pd.read_excel(xls, "SALIDAS EXPORT", header=None, nrows=25)
        fila_tarifes = df_tarifas[df_tarifas.apply(lambda x: x.astype(str).str.contains('ZIP CODE|AUXILIAR', regex=True, case=False)).any(axis=1)].index[0]
        df_tarifas = pd.read_excel(xls, "SALIDAS EXPORT", header=fila_tarifes)
        df_tarifas.columns = df_tarifas.columns.str.strip().str.upper()

        # NETEJA I MAPA
        renames = {}
        for col in df_tarifas.columns:
            if 'CITA' in col: renames[col] = 'T.CITA'
            elif 'TASA' in col: renames[col] = 'TASA'
            elif 'ENTREGA' in col: renames[col] = 'ENTREGA'
        if renames: df_tarifas = df_tarifas.rename(columns=renames)
        
        cols_clau = ['PAIS', 'ZIP CODE', 'AUXILIAR']
        cols_existents = [c for c in cols_clau if c in df_tarifas.columns]
        
        # Guardem només les columnes necessàries al mapa (Estalvi RAM)
        cols_extra = [c for c in ['SALIDAS', 'TRANSIT TIME', 'LLEGADA', 'ADR', 'ENTREGA', 'T.CITA', 'TASA'] if c in df_tarifas.columns]
        mapa = df_tarifas[cols_existents + cols_extra].dropna(subset=cols_existents).copy()
        
        mapa['ZIP CODE'] = mapa['ZIP CODE'].astype(str).str.replace(".0", "", regex=False).str.zfill(2)
        mapa['PAIS'] = mapa['PAIS'].str.strip().str.upper()
        
        # PREUS (Només carreguem KILOS i columnes de zones)
        if 'KILOS' in df_tarifas.columns:
            # Detectem quines columnes són zones (comencen per lletra o tenen numeros)
            # Simplificació: Agafem tot i netegem files sense kilos
            preus = df_tarifas.dropna(subset=['KILOS']).copy()
            preus['KILOS'] = pd.to_numeric(preus['KILOS'], errors='coerce')
            preus = preus.set_index('KILOS').sort_index()
        else:
            preus = None

        return df_datos, mapa, preus, "OK"

    except Exception as e:
        return None, None, None, str(e)

# Execució
df_datos, mapa_zones, df_preus, error = carregar_dades_light()

if error != "OK":
    st.error(f"⚠️ Error carregant: {error}")
    if error == "MISSING_EXCEL": st.info("No trobo el fitxer .xlsx a GitHub.")
    st.stop()

# --- INTERFÍCIE ---
c_left, c_right = st.columns([1, 1.5])

with c_left:
    st.markdown('<div class="header-style">1. Servei</div>', unsafe_allow_html=True)
    llista_paises = sorted(df_datos['PAISES'].dropna().unique().tolist())
    pais = st.selectbox("País", llista_paises)
    cp = st.text_input("Codi Postal (2 dígits)", max_chars=2)
    
    with st.expander("⚙️ Serveis Addicionals", expanded=True):
        col_x1, col_x2, col_x3 = st.columns(3)
        es_adr = col_x1.checkbox("ADR", help="Mercaderia Perillosa")
        vol_entrega = col_x2.checkbox("Entrega", help="Plataforma/Domicili")
        vol_cita = col_x3.checkbox("Cita", help="Concertar hora")
    
    st.markdown('<div class="header-style">2. Càrrega</div>', unsafe_allow_html=True)
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
            st.error("⚠️ Falta el Codi Postal")
        else:
            pes_total = pes_unitari * quantitat
            volum_total = llarg * ample * alt * quantitat
            pes_tasable = max(pes_total, volum_total * 333)

            cp_norm = str(cp).zfill(2)
            rutes = mapa_zones[(mapa_zones['PAIS'] == pais.upper()) & (mapa_zones['ZIP CODE'] == cp_norm)].copy()

            if rutes.empty:
                st.warning(f"❌ No hi ha tarifa per a {pais} CP {cp_norm}")
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
                        st.markdown("**📋 Info**")
                        st.write(f"Zona: {zona}")
                        st.write(f"Sortides: {dies}")
                        st.write(f"Trànsit: {transit}")
                    with c2:
                        st.markdown("**💰 Detall**")
                        st.write(f"Base: {preu_base:.2f}€")
                        for d in detalls: st.write(f"+ {d}")
                else:
                    st.error("Pes fora de rang.")