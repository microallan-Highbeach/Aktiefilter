import json
import os
import re
import pandas as pd
import pandas_ta as ta
import streamlit as st
import yfinance as yf

# Sidlayout
st.set_page_config(layout="wide")
st.title("Mitt Stora Aktiefilter (Allt-i-Ett Super-Vy)")

# --- FILHANTERING ---
SPARFIL = "min_virtuella_portfolj.json"

def ladda_sparad_data():
    if os.path.exists(SPARFIL):
        try:
            with open(SPARFIL, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("kontanter", 20000.0), data.get("portfolj", [])
        except:
            pass
    return 20000.0, []

def spara_till_disk(kontanter, portfolj):
    data = {"kontanter": kontanter, "portfolj": portfolj}
    try:
        with open(SPARFIL, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except:
        pass

if "kvar_kontanter" not in st.session_state or "portfolj" not in st.session_state:
    sparade_kontanter, sparad_portfolj = ladda_sparad_data()
    st.session_state.kvar_kontanter = sparade_kontanter
    st.session_state.portfolj = sparad_portfolj

large_cap_tickers = [
    "ABB.ST", "ALFA.ST", "ASSA-B.ST", "ATCO-A.ST", "ATCO-B.ST", "AZN.ST",
    "AXFO.ST", "BOL.ST", "CAST.ST", "ELUX-B.ST", "EQT.ST", "ERIC-B.ST",
    "ESSITY-B.ST", "EVO.ST", "GETI-B.ST", "HEXA-B.ST", "HM-B.ST", "HOLM-B.ST",
    "HUSQ-B.ST", "INVE-B.ST", "KINV-B.ST", "LATO-B.ST", "LIFCO-B.ST",
    "NIBE-B.ST", "NDA-SE.ST", "PEAB-B.ST", "SAND.ST", "SCA-B.ST", "SEB-A.ST",
    "SECU-B.ST", "SKA-B.ST", "SKF-B.ST", "SOBI.ST", "SSAB-A.ST", "STE-R.ST",
    "SWED-A.ST", "TEL2-B.ST", "TELIA.ST", "TREL-B.ST", "VOLV-A.ST",
    "VOLV-B.ST", "WIHL.ST"
]

@st.cache_data(ttl=600)
def hamta_borsdata_med_allt(tickers):
    resultat_lista = []
    for ticker in tickers:
        try:
            aktie = yf.Ticker(ticker)
            historik = aktie.history(period="1y")

            if not historik.empty and len(historik) > 200:
                historik.ta.rsi(length=14, append=True)
                historik.ta.sma(length=200, append=True)
                historik.ta.macd(append=True)
                historik.ta.atr(length=14, append=True)
                historik["Vol_SMA20"] = historik["Volume"].rolling(20).mean()

                macd_col = [c for c in historik.columns if c.startswith("MACD_")][0]
                macds_col = [c for c in historik.columns if c.startswith("MACDs_")][0]
                atr_col = [c for c in historik.columns if c.startswith("ATRr_")][0]

                dagens_rsi = historik.iloc[-1]["RSI_14"]
                dagens_kurs = historik.iloc[-1]["Close"]
                dagens_sma200 = historik.iloc[-1]["SMA_200"]
                dagens_macd = historik.iloc[-1][macd_col]
                dagens_macds = historik.iloc[-1][macds_col]
                dagens_atr = historik.iloc[-1][atr_col]
                dagens_vol = historik.iloc[-1]["Volume"]
                dagens_volsma = historik.iloc[-1]["Vol_SMA20"]
                ars_botten = historik["Low"].min()
                
                if pd.isna(ars_botten) or ars_botten == 0:
                    avstand_botten = 0.0
                else:
                    avstand_botten = ((dagens_kurs - ars_botten) / ars_botten) * 100

                rapport = "Okänt"
                try:
                    kalender = aktie.calendar
                    if isinstance(kalender, dict) and "Earnings Date" in kalender:
                        rapport = kalender["Earnings Date"][0].strftime("%Y-%m-%d")
                except:
                    pass

                lang_trend = "🟢 Över" if dagens_kurs > dagens_sma200 else "🔴 Under"
                macd_signal = "🟢 Köp" if dagens_macd > dagens_macds else "🔴 Sälj"
                volym_kraft = "🔥 Hög" if dagens_vol > dagens_volsma else "📉 Låg"
                
                resultat_lista.append({
                    "Aktie": ticker.replace(".ST", ""),
                    "Kurs": round(dagens_kurs, 2),
                    "RSI": round(dagens_rsi, 2),
                    "Från Botten": f"+{round(avstand_botten, 1)}%",
                    "Rapport": rapport,
                    "SMA200": lang_trend,
                    "MACD": macd_signal,
                    "Volym": volym_kraft,
                    "ATR (SEK)": round(dagens_atr, 2),
                    "_raw_atr": dagens_atr,
                    "_ticker": ticker
                })
        except:
            pass
    return resultat_lista

@st.cache_data(ttl=3600)
def snabb_backtest(ticker, test_rsi, test_krav_sma, test_krav_macd):
    try:
        hist = yf.Ticker(ticker).history(period="3y")
        if len(hist) < 200: return "Ingen data", -1.0
        
        hist.ta.rsi(length=14, append=True)
        hist.ta.sma(length=200, append=True)
        hist.ta.macd(append=True)
        hist.ta.atr(length=14, append=True)
        
        macd_col = [c for c in hist.columns if c.startswith("MACD_")][0]
        macds_col = [c for c in hist.columns if c.startswith("MACDs_")][0]
        atr_col = [c for c in hist.columns if c.startswith("ATRr_")][0]

        trades, vinster, forlaster = 0, 0, 0
        i = 200 
        
        while i < len(hist) - 10:
            d_rsi = hist.iloc[i]["RSI_14"]
            d_close = hist.iloc[i]["Close"]
            d_sma = hist.iloc[i]["SMA_200"]
            d_macd = hist.iloc[i][macd_col]
            d_macds = hist.iloc[i][macds_col]
            d_atr = hist.iloc[i][atr_col]
            
            rsi_ok = d_rsi <= test_rsi
            sma_ok = (d_close > d_sma) if test_krav_sma else True
            macd_ok = (d_macd > d_macds) if test_krav_macd else True

            if rsi_ok and sma_ok and macd_ok:
                sl = d_close - (2 * d_atr)
                tp = d_close + (4 * d_atr)
                trades += 1
                
                for j in range(i+1, min(i+40, len(hist))):
                    framtids_pris = hist.iloc[j]["Close"]
                    if framtids_pris >= tp:
                        vinster += 1
                        i = j 
                        break
                    elif framtids_pris <= sl:
                        forlaster += 1
                        i = j
                        break
            i += 1
        
        if trades == 0: return "0 Signaler", -1.0
        win_rate = round((vinster / trades) * 100, 1)
        return f"{win_rate}% (Av {trades} st)", win_rate
    except:
        return "Fel", -1.0

flik1, flik2, flik3 = st.tabs([
    "📊 Den Stora Skannern",
    "💼 Min Portfölj & Auto-Sälj",
    "📖 Strategi"
])

# ==========================================
# FLIK 1: SUPER-FILTRET
# ==========================================
with flik1:
    st.write("Skannar Large Cap, visar historisk träffsäkerhet och låter dig filtrera bort förlorare med ett klick!")
    if st.button("🔄 Uppdatera marknadsdata"):
        st.cache_data.clear()
        st.rerun()

    with st.spinner("Hämtar data för alla Large Cap..."):
        resultat_lista = hamta_borsdata_med_allt(tuple(large_cap_tickers))

    if resultat_lista:
        df_resultat = pd.DataFrame(resultat_lista).sort_values(by="RSI")
        st.divider()

        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            vald_rsi_grans = st.slider("Max RSI:", min_value=20, max_value=80, value=45)
        with col_f2:
            krav_macd = st.checkbox("Kräv positiv MACD (Köp)", value=True)
        with col_f3:
            krav_sma = st.checkbox("Kräv grön trend (SMA200)", value=False)
        with col_f4:
            krav_vinnare = st.checkbox("🏆 Dölj historiska förlorare (Kräv >33% Win Rate)", value=False)

        df_filtrerad = df_resultat[df_resultat["RSI"] <= vald_rsi_grans]
        if krav_macd:
            df_filtrerad = df_filtrerad[df_filtrerad["MACD"] == "🟢 Köp"]
        if krav_sma:
            df_filtrerad = df_filtrerad[df_filtrerad["SMA200"] == "🟢 Över"]

        if not df_filtrerad.empty:
            with st.spinner("Kör backtest på filtrerade aktier..."):
                historik_resultat = []
                win_rates = []
                for _, rad in df_filtrerad.iterrows():
                    hist_str, wr_val = snabb_backtest(rad["_ticker"], vald_rsi_grans, krav_sma, krav_macd)
                    historik_resultat.append(hist_str)
                    win_rates.append(wr_val)
                
                df_filtrerad["Historisk Win Rate (3 år)"] = historik_resultat
                df_filtrerad["_wr_val"] = win_rates

        if krav_vinnare and not df_filtrerad.empty:
            df_filtrerad = df_filtrerad[df_filtrerad["_wr_val"] > 33.3]

        if not df_filtrerad.empty:
            st.dataframe(df_filtrerad.drop(columns=["_raw_atr", "_ticker", "_wr_val"]), hide_index=True, use_container_width=True)
        else:
            st.warning("Inga aktier matchar dina filter (eller så rensades alla bort av vinnar-filtret).")

        st.subheader("🛒 Lägg order")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            valda_aktier = df_filtrerad["Aktie"].tolist() if not df_filtrerad.empty else []
            vald_kop = st.selectbox("Välj aktie:", valda_aktier) if valda_aktier else None
        with col2:
            kop_belopp = st.number_input("Belopp (kr):", min_value=500, max_value=20000, value=4000, step=500)
        with col3:
            st.write("")
            st.write("")
            if vald_kop and st.button("Köp virtuellt"):
                rad = df_filtrerad[df_filtrerad["Aktie"] == vald_kop].iloc[0]
                kop_kurs, atr = rad["Kurs"], rad["_raw_atr"]
                antal_aktier = int(kop_belopp / kop_kurs)

                if antal_aktier < 1:
                    st.error("Beloppet räcker inte till en aktie.")
                else:
                    brutto = antal_aktier * kop_kurs
                    courtage = max(1.0, round(brutto * 0.0025, 2))
                    tot_kostnad = round(brutto + courtage, 2)

                    if tot_kostnad > st.session_state.kvar_kontanter:
                        st.error("För lite kontanter!")
                    else:
                        sl_kurs = round(kop_kurs - (2 * atr), 2)
                        tp_kurs = round(kop_kurs + (4 * atr), 2)
                        sl_proc = round(((kop_kurs - sl_kurs)/kop_kurs)*100, 1)
                        tp_proc = round(((tp_kurs - kop_kurs)/kop_kurs)*100, 1)

                        st.session_state.portfolj.append({
                            "Aktie": vald_kop, "Antal": antal_aktier, "Inköpskurs": kop_kurs,
                            "Investerat (kr)": tot_kostnad,
                            "Stop-Loss": f"-{sl_proc}% ({sl_kurs} kr)",
                            "Målkurs": f"+{tp_proc}% ({tp_kurs} kr)",
                            "SL_pris": sl_kurs, "TP_pris": tp_kurs
                        })
                        st.session_state.kvar_kontanter -= tot_kostnad
                        spara_till_disk(st.session_state.kvar_kontanter, st.session_state.portfolj)
                        st.success(f"Köpt {antal_aktier} st {vald_kop}!")

# ==========================================
# FLIK 2: MIN PORTFÖLJ & MANUELL SÄLJ
# ==========================================
with flik2:
    st.subheader("💼 Dina fiktiva köp & live-resultat")
    st.write(f"Startbudget: **20 000 kr** | Kvar i kontanter: **{round(st.session_state.kvar_kontanter, 2)} kr**")

    if st.session_state.portfolj:
        live_portfolj = []
        uppdaterad_portfolj = []
        notiser = []
        tot_nuv, tot_inv, har_forandring = 0, 0, False

        for post in st.session_state.portfolj:
            ticker = post["Aktie"] + ".ST"
            dagens_pris = post["Inköpskurs"]

            try:
                hist = yf.Ticker(ticker).history(period="1d")
                if not hist.empty:
                    dagens_pris = hist["Close"].iloc[-1]
            except:
                pass

            sl_pris = post.get("SL_pris", 0.0)
            tp_pris = post.get("TP_pris", 999999.0)
            if sl_pris == 0.0:
                sl_match = re.search(r'\(([\d\.]+)\s*kr\)', post["Stop-Loss"])
                if sl_match: sl_pris = float(sl_match.group(1))
                tp_match = re.search(r'\(([\d\.]+)\s*kr\)', post["Målkurs"])
                if tp_match: tp_pris = float(tp_match.group(1))

            # --- AUTO-SÄLJ KONTROLL ---
            if dagens_pris >= tp_pris or dagens_pris <= sl_pris:
                salj_summa = post["Antal"] * dagens_pris
                courtage = max(1.0, round(salj_summa * 0.0025, 2))
                netto = round(salj_summa - courtage, 2)
                st.session_state.kvar_kontanter += netto
                vinst = round(netto - post["Investerat (kr)"], 2)
                har_forandring = True
                ikon = "🎯 MÅLKURS" if dagens_pris >= tp_pris else "🛡️ STOP-LOSS"
                notiser.append(f"{ikon}! Sålde automatiskt {post['Antal']} st {post['Aktie']}. Resultat: {vinst:+} kr.")
            else:
                uppdaterad_portfolj.append(post)
                antal = post["Antal"]
                inkopskurs = post["Inköpskurs"]
                investerat = post["Investerat (kr)"]
                nuv_varde = round(antal * dagens_pris, 2)
                
                forandring_sek = round(nuv_varde - investerat, 2)
                forandring_procent = round(((nuv_varde - investerat) / investerat) * 100, 2)

                tot_nuv += nuv_varde
                tot_inv += investerat

                live_portfolj.append({
                    "Aktie": post["Aktie"],
                    "Antal": antal,
                    "Inköpskurs": inkopskurs,
                    "Nuvarande Kurs": round(dagens_pris, 2),
                    "Nuvarande Värde": nuv_varde,
                    "Resultat": f"{forandring_sek:+} kr ({forandring_procent:+}%)",
                    "Stop-Loss": post["Stop-Loss"],
                    "Målkurs": post["Målkurs"],
                })

        if har_forandring:
            st.session_state.portfolj = uppdaterad_portfolj
            spara_till_disk(st.session_state.kvar_kontanter, st.session_state.portfolj)

        for n in notiser:
            st.success(n) if "🎯" in n else st.warning(n)

        if live_portfolj:
            st.dataframe(pd.DataFrame(live_portfolj), hide_index=True, use_container_width=True)

            tot_vinst = round(tot_nuv - tot_inv, 2)
            st.divider()
            col_A, col_B = st.columns(2)
            with col_A:
                st.metric(label="Totalt aktievärde", value=f"{tot_nuv} kr")
            with col_B:
                st.metric(label="Total orealiserad vinst/förlust", value=f"{tot_vinst} kr", delta=f"{tot_vinst} kr")

            # --- MANUELL SÄLJKONTROLL ---
            st.divider()
            st.subheader("🔴 Sälj innehav manuellt")
            aktier_i_portfolj = [p["Aktie"] for p in st.session_state.portfolj]
            
            col_s1, col_s2 = st.columns([2, 1])
            with col_s1:
                vald_for_salj = st.selectbox("Välj aktie att avyttra:", aktier_i_portfolj) if aktier_i_portfolj else None
            with col_s2:
                st.write("")
                st.write("")
                if vald_for_salj and st.button("Sälj nu"):
                    # Hitta och ta bort posten, lägg till pengar i kassan
                    for idx, p in enumerate(st.session_state.portfolj):
                        if p["Aktie"] == vald_for_salj:
                            # Hämta aktuell kurs för försäljningen
                            pris = p["Inköpskurs"]
                            try:
                                h = yf.Ticker(vald_for_salj + ".ST").history(period="1d")
                                if not h.empty: pris = h["Close"].iloc[-1]
                            except: pass

                            brutto_sälj = p["Antal"] * pris
                            courtage_sälj = max(1.0, round(brutto_sälj * 0.0025, 2))
                            netto_sälj = round(brutto_sälj - courtage_sälj, 2)
                            
                            st.session_state.kvar_kontanter += netto_sälj
                            manuell_vinst = round(netto_sälj - p["Investerat (kr)"], 2)
                            
                            # Ta bort ur portföljen
                            st.session_state.portfolj.pop(idx)
                            spara_till_disk(st.session_state.kvar_kontanter, st.session_state.portfolj)
                            
                            st.success(f"Sålde {p['Antal']} st {vald_for_salj} manuellt. Netto till kassan: {netto_sälj} kr. Vinst/förlust: {manuell_vinst:+} kr!")
                            st.rerun()
        else:
            st.info("Din portfölj är tom.")

        st.write("")
        if st.button("Nollställ portfölj & återställ kontanter"):
            st.session_state.portfolj = []
            st.session_state.kvar_kontanter = 20000.0
            spara_till_disk(st.session_state.kvar_kontanter, st.session_state.portfolj)
            st.rerun()
    else:
        st.info("Din portfölj är tom. Gå till fliken 'Den Stora Skannern' för att köpa aktier!")

# ==========================================
# FLIK 3: LATHUND
# ==========================================
with flik3:
    st.subheader("📖 Strategi & Lathund")
    st.write("Här har du din kompletta miljö för att skanna, backtesta och följa dina fiktiva placeringar.")
