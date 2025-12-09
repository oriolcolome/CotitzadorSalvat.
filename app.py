import streamlit as st
import pandas as pd
import os
import time

# --- CONFIGURACIÓ ---
st.set_page_config(page_title="Cotitzador Logística", page_icon="🚛", layout="wide")

# --- ESTILS ---
st.markdown("""
    <style>
    .big-font { font-size:36px !important; font-weight: bold; color: #166534; }
    .header-style { font-size:20px; font-weight: bold; color: #1e40af; border-bottom: 2px solid #1e40af; padding-bottom: 5px; margin-bottom: 20px; }
    .success-card { background-color: #dcfce7; padding: 20px; border-radius: 10px; border: 2px solid #16a34a; text-align: center; }
    .error-card { background-color: #fee2e2; padding: 20px; border-radius: 10px; border: 2px solid #ef4444; color: #991b1b; }
    </style>
""", unsafe_allow_html=True)

st.title("🚛 Calculadora d'Enviaments")

# --- SISTEMA DE REANIMACIÓ ---
# Això evita que l'app es pengi si l'excel triga a carregar
@st.cache_data(ttl=3600) # Manté les dades 1 hora en memòria
def carregar_dades_segures():
    fitxer = "dades.xlsx"
    
    # 1. Comprovem si el fitxer existeix
    if not os.path.exists(fitxer):
        return None, None, None, "MISSING_FILE"
    
    try:
        # 2. Intentem llegir-lo amb motor específic
        df_datos = pd.read_excel(fitxer, sheet_name="DATOS", engine="openpyxl")
        
        # Truc: Busquem la fila de títols dinàmicament
        fila_pais = -1
        for i, row in df_datos.head(20).iterrows():
            if row.astype(str).str.contains('PAISES', case=False).any():
                fila_pais = i
                break
        
        if fila_pais == -1: return None, None, None, "FORMAT_ERROR_DATOS"
        
        # Recarreguem net
        df_datos = pd.read_excel(fitxer, sheet_name="DATOS", header=fila_pais, engine="openpyxl")
        df_datos.columns = df_datos.columns.str.strip().str.upper()

        # Llegim Tarifes
        df_tarifas = pd.read_excel(fitxer, sheet_name="SALIDAS EXPORT", engine="openpyxl")
        fila_tarifes = -1
        for i, row in df_tarifas.head(20).iterrows():
            if row.astype(str).str.contains('ZIP CODE|AUXILIAR', regex=True).any():
                fila_tarifes = i
                break
                
        if fila_tarifes == -1: return None, None, None, "FORMAT_ERROR_TARIFAS"

        df_tarifas = pd.read_excel(fitxer, sheet_name="SALIDAS EXPORT", header=fila_tarifes, engine="openpyxl")
        df_tarifas.columns = df_tarifas.columns.str.strip().str.upper()

        # Neteja
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

# --- EXECUCIÓ AMB CONTROL D'ERRORS ---
df_datos, mapa_zones, df_preus, estat = carregar_dades_segures()

# SI HI HA ERROR, MOSTREM BOTÓ DE REPARAR
if estat != "OK":
    st.error("⚠️ S'ha perdut la connexió amb les dades.")
    
    if estat == "MISSING_FILE":
        st.info("El servidor no troba 'dades.xlsx'.")
    else:
        st.write(f"Detall de l'error: {estat}")
        
    if st.button("🔄 RECARREGAR SISTEMA (Clic aquí)", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.stop()

# --- INTERFÍCIE NORMAL ---
c_left, c_right = st.columns([1, 1.5])

with c_left:
    st.markdown('<div class="header-style">1. Serveis i Destí</div>', unsafe_allow_html=True)
    llista_paises = sorted(df_datos['PAISES'].dropna().unique().tolist())
    pais = st.selectbox("País", llista_paises)
    cp = st.text_input("Codi Postal (2 xifres)", max_chars=2)
    
    col_x1, col_x2, col_x3 = st.columns(3)
    es_adr = col_x1.checkbox("ADR")
    vol_entrega = col_x2.checkbox("Entrega")
    vol_cita = col_x3.checkbox("Cita Prèvia")
    
    st.markdown('<div class="header-style">2. Mercaderia</div>', unsafe_allow_html=True)
    tipus_palet = st.radio("Tipus:", ["EUR (1.2x0.8)", "Americà (1.2x1.0)", "Lliure"], horizontal=True)
    
    if "EUR" in tipus_palet: llarg, ample = 1.20, 0.80
    elif "Americà" in tipus_palet: llarg, ample = 1.20, 1.00
    else:
        c_l, c_a = st.columns(2)
        llarg = c_l.number_input("Llarg", 0.0, 13.6, 1.2)
        ample = c_a.number_input("Ample", 0.0, 3.0, 0.8)
        
    c_h, c_q = st.columns(2)
    alt = c_h.number_input("Alt", 0.0, 3.0, 1.0)
    quantitat = c_q.number_input("Nº Palets", 1, 50, 1)
    pes_unitari = st.number_input("Pes per Palet (kg)", 0, 2000, 200)

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
                        if val_cita > 0: detalls.append(f"Cita Prèvia: {val_cita:.2f}€")

                    val_tasa = float(ruta_final.get('TASA', 0)) if str(ruta_final.get('TASA', 0)).replace('.','').isdigit() else 0
                    total_extres += val_tasa
                    if val_tasa > 0: detalls.append(f"Taxes: {val_tasa:.2f}€")

                    total_final = preu_base + total_extres

                    st.markdown(f"""
                    <div class="success-card">
                        <div style="font-size:14px; color:#15803d">TOTAL ESTIMAT</div>
                        <div class="big-font">{total_final:.2f} €</div>
                        <div style="font-size:12px">Pes Tasable: {pes_tasable:.2f}kg</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.write("")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**📋 Info Servei**")
                        st.write(f"- Zona: {zona}")
                        st.write(f"- Sortides: {dies}")
                        st.write(f"- Trànsit: {transit}")
                    with c2:
                        if detalls:
                            st.markdown("**💰 Extres**")
                            for d in detalls: st.write(f"- {d}")
                else:
                    st.error("Pes fora de rang.")