
import streamlit as st
import pandas as pd

# -----------------------------
# Streamlit page config & title
# -----------------------------
st.set_page_config(page_title="Green ROI (Invest - Eco - Org)", layout="wide")
st.title("Green ROI – 3 ROI (Investissement, Écologique, Organisationnel)")

# -----------------------------
# Sidebar: global assumptions
# -----------------------------
st.sidebar.markdown("### Hypothèses globales (France)")
prix_carbone = st.sidebar.number_input("Prix interne du carbone (€/kg)", 0.0, 5.0, 0.25, step=0.05)
prix_kwh     = st.sidebar.number_input("Prix élec FR (€/kWh)", 0.0, 2.0, 0.2016, step=0.01)
kg_per_kwh   = st.sidebar.number_input("Intensité FR (kgCO₂/kWh)", 0.0, 1.0, 0.022, step=0.001)  # ~21.7 g/kWh

st.sidebar.markdown("---")
st.sidebar.markdown("### Personas (ROI Organisationnel)")
sal_designer = st.sidebar.number_input("Salaire annuel Designer (€)", 0.0, 200000.0, 80000.0, step=1000.0)
sal_bureau   = st.sidebar.number_input("Salaire annuel Bureau/Mails (€)", 0.0, 200000.0, 50000.0, step=1000.0)
sens_des     = st.sidebar.slider("Sensibilité Designer (max 5%)", 0.0, 0.05, 0.03, step=0.005)
sens_bur     = st.sidebar.slider("Sensibilité Bureau/Mails (max 5%)", 0.0, 0.05, 0.01, step=0.005)

# CPU performance ratio (placeholder if you don't have CPU model mapping yet)
st.sidebar.markdown("### Performance PC (placeholder)")
perf_ratio = st.sidebar.slider("Perf ratio PC (actuel / référence)", 0.1, 1.0, 0.6, step=0.05)

# -----------------------------
# Upload inventory CSV
# -----------------------------
st.subheader("Inventaire : importez le CSV exporté d’Excel")
csv = st.file_uploader("C:\Users\mrahali002\Downloads\UC1_Inputs for ROI calculation.xlsx", type=["csv"])
if not csv:
    st.info("➡️ Chargez votre CSV pour lancer les calculs.")
    st.stop()

df = pd.read_csv(csv)
st.success("Inventaire chargé ✅")
st.dataframe(df.head(15), use_container_width=True)

# -----------------------------
# Helpers (no external datasets)
# -----------------------------
def parse_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default

def parse_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default

def get_col(df, names, default=None):
    """Get first matching column from list of names."""
    for n in names:
        if n in df.columns:
            return n
    return default

# Column name mapping (supports FR/EN based on your screenshot)
col_type   = get_col(df, ["Equipement","Equipment","type"], "Equipement")
col_qty    = get_col(df, ["Current number of equipment","count","Quantité"], "Current number of equipment")
col_life   = get_col(df, ["Initial lifespan","lifespan_months","Durée de vie (mois)"], "Initial lifespan")
col_price  = get_col(df, ["Unit price","unit_price","Prix unitaire"], "Unit price")
col_lease  = get_col(df, ["lease_fee_month","Loyer mensuel"], None)  # optional

# Power defaults (W) and hours per day — fallback if not provided in CSV
# Based on typical values and your Excel (screen on=160W, standby=5W)
DEFAULT_POWER = {
    "laptop":        {"on": 25,  "sb": 2,   "h_on":8, "h_sb":16},
    "smartphone":    {"on": 3.5, "sb": 1.0, "h_on":8, "h_sb":16},
    "tablet":        {"on": 5.0, "sb": 1.0, "h_on":8, "h_sb":16},
    "screen":        {"on": 160, "sb": 5,   "h_on":8, "h_sb":16},  # from your Excel sheet
    "meeting_screen":{"on": 160, "sb": 5,   "h_on":8, "h_sb":16},
    "switch/router": {"on": 120, "sb": 120, "h_on":24,"h_sb":0},
    "landline_phone":{"on": 4.0, "sb": 3.5, "h_on":8, "h_sb":16},
    "refurbished":   {"on": 25,  "sb": 2,   "h_on":8, "h_sb":16},
}

# Embedded (manufacturing) CO2 (kg CO2e) — placeholders; adjust later when you connect APIs
EMBED_CO2 = {
    "laptop":         300,   # placeholder
    "smartphone":     57,    # placeholder
    "tablet":         80,    # placeholder
    "screen":         200,   # placeholder (office monitor)
    "meeting_screen": 350,   # placeholder (large display)
    "switch/router":  200,   # placeholder
    "landline_phone": 25,    # placeholder
    "refurbished":    60,    # placeholder (lighter than new)
}

def classify_type(name: str) -> str:
    n = name.lower()
    if "meeting" in n and "screen" in n: return "meeting_screen"
    if "switch" in n or "router" in n:   return "switch/router"
    if "phone" in n and "landline" in n: return "landline_phone"
    if "smartphone" in n:                return "smartphone"
    if "tablet" in n:                    return "tablet"
    if "laptop" in n:                    return "laptop"
    if "screen" in n:                    return "screen"
    if "refurbished" in n:               return "refurbished"
    return "laptop"  # default

def annual_kwh(w_on, h_on, w_sb, h_sb):
    return ((w_on*h_on) + (w_sb*h_sb)) * 365 / 1000.0

def carbon_eur(co2_fab_annual_kg, co2_use_kg, price_eur_per_kg):
    return (co2_fab_annual_kg + co2_use_kg) * price_eur_per_kg

def annual_capex(price, life_years, resale_years):
    resale = price * (0.75 ** resale_years)  # simple rule: -25%/year
    return max(0.0, (price - resale) / max(life_years, 1.0))

def tco_achat_12m(price, life_years, resale_years, energy_eur, carbon_eur, maint_eur=0.0, eol_eur=0.0):
    return annual_capex(price, life_years, resale_years) + energy_eur + carbon_eur + maint_eur + eol_eur

def tco_leasing_12m(lease_fee_month, energy_eur, carbon_eur, maint_eur=0.0, end_fees_eur=0.0):
    return lease_fee_month*12 + energy_eur + carbon_eur + maint_eur + end_fees_eur

def productivity_cost(perf_ratio, salary, sensitivity):
    # cost = salary * sensitivity * (1 - perf_ratio), capped at 5%
    loss_pct = min(0.05, max(0.0, sensitivity*(1.0 - perf_ratio)))
    return salary * loss_pct

def recommend(tco_keep, tco_buy, tco_lease, eco_kg, org_eur, weights=(0.4,0.35,0.25)):
    inv = {"KEEP":tco_keep, "BUY":tco_buy, "LEASE":tco_lease}
    eco = {"KEEP":eco_kg["KEEP"], "BUY":eco_kg["BUY"], "LEASE":eco_kg["LEASE"]}
    org = {"KEEP":org_eur["KEEP"], "BUY":org_eur["BUY"], "LEASE":org_eur["LEASE"]}
    best_inv = min(inv, key=inv.get); best_eco = min(eco, key=eco.get); best_org = min(org, key=org.get)
    votes = {"KEEP":0,"BUY":0,"LEASE":0}
    votes[best_inv]+=weights[0]; votes[best_eco]+=weights[1]; votes[best_org]+=weights[2]
    return sorted(votes.items(), key=lambda x:x[1], reverse=True)[0][0], {"invest":best_inv,"eco":best_eco,"org":best_org}

# -----------------------------
# Row-by-row computation
# -----------------------------
rows = []
for _, r in df.iterrows():
    equip_name = str(r.get(col_type, ""))
    qty        = parse_int(r.get(col_qty, 1), 1)
    life_m     = parse_int(r.get(col_life, 60), 60)
    life_y     = max(1, life_m/12)
    price      = parse_float(r.get(col_price, 0.0), 0.0)
    lease_m    = parse_float(r.get(col_lease, 0.0), 0.0) if col_lease else 0.0

    typ = classify_type(equip_name)
    p   = DEFAULT_POWER.get(typ, DEFAULT_POWER["laptop"])
    w_on, w_sb, h_on, h_sb = p["on"], p["sb"], p["h_on"], p["h_sb"]

    # Energy/CO2 usage
    kwh_unit  = annual_kwh(w_on, h_on, w_sb, h_sb)
    co2_use   = kwh_unit * kg_per_kwh
    energy_eu = kwh_unit * prix_kwh

    # Manufacturing CO2 (amortized per year)
    co2_fab_total = EMBED_CO2.get(typ, 150.0)
    co2_fab_annual= co2_fab_total / life_y
    carbon_eu     = carbon_eur(co2_fab_annual, co2_use, prix_carbone)

    # TCO 12m
    tco_keep  = energy_eu + carbon_eu
    tco_buy   = tco_achat_12m(price, life_y, life_y, energy_eu, carbon_eu)
    tco_lease = tco_leasing_12m(lease_m, energy_eu, carbon_eu)

    # ROI organisationnel (Designer vs Bureau) -- per unit
    org_des = productivity_cost(perf_ratio, sal_designer, sens_des)
    org_bur = productivity_cost(perf_ratio, sal_bureau,   sens_bur)

    # Eco kg for decision (usage + manufacturing annual)
    eco_keep_kg  = co2_use + co2_fab_annual
    eco_buy_kg   = co2_use + co2_fab_annual
    eco_lease_kg = co2_use + co2_fab_annual

    # Organisational cost per decision (same baseline, you can adjust later)
    org_map = {"KEEP":org_des, "BUY":org_des, "LEASE":org_des}  # e.g. same penalty if perf is low
    eco_map = {"KEEP":eco_keep_kg, "BUY":eco_buy_kg, "LEASE":eco_lease_kg}
    action, vote = recommend(tco_keep, tco_buy, tco_lease, eco_map, org_map)

    rows.append({
        "Type": equip_name, "Quantité": qty,
        "kWh/an (unité)": round(kwh_unit,1),
        "CO₂ usage (kg/an)": round(co2_use,1),
        "CO₂ fabrication (kg/an)": round(co2_fab_annual,1),
        "Énergie € (12m/unité)": round(energy_eu,1),
        "Carbone € (12m/unité)": round(carbon_eu,1),
        "TCO Garder (€/12m/unité)": round(tco_keep,1),
        "TCO Achat (€/12m/unité)": round(tco_buy,1),
        "TCO Leasing (€/12m/unité)": round(tco_lease,1),
        "ROI Orga Designer (€/unité)": round(org_des,0),
        "ROI Orga Bureau (€/unité)": round(org_bur,0),
        "Action (unité)": action,
        "Votes": vote,
    })

out = pd.DataFrame(rows)
st.subheader("Résultats par équipement (unité)")
st.dataframe(out, use_container_width=True)

# Fleet-level KPIs (multiply by quantities)
out["kWh total/an"]        = out["kWh/an (unité)"]        * pd.Series(df[col_qty]).fillna(1).astype(int)
out["Énergie € total (12m)"]= out["Énergie € (12m/unité)"]* pd.Series(df[col_qty]).fillna(1).astype(int)
out["Carbone € total (12m)"]= out["Carbone € (12m/unité)"]* pd.Series(df[col_qty]).fillna(1).astype(int)
out["CO₂ total (kg/an)"]    = (out["CO₂ usage (kg/an)"]+out["CO₂ fabrication (kg/an)"]) \
                              * pd.Series(df[col_qty]).fillna(1).astype(int)

st.subheader("KPIs flotte")
st.metric("kWh total/an", f"{round(out['kWh total/an'].sum(),1)}")
st.metric("€ énergie (12m)", f"{round(out['Énergie € total (12m)'].sum(),1)}")
st.metric("€ carbone (12m)", f"{round(out['Carbone € total (12m)'].sum(),1)}")
st.metric("CO₂ total (kg/an)", f"{round(out['CO₂ total (kg/an)'].sum(),1)}")

# Download results
st.download_button("Télécharger les résultats (CSV)", out.to_csv(index=False), "green_roi_results.csv", "text/csv")

# -----------------------------
# Cloud emissions uploader (AWS/Azure/Alibaba exports)
# -----------------------------
st.subheader("Émissions Cloud (uploader CSV fournisseur)")
cloud_csv = st.file_uploader("Importer un export cloud (doit contenir une colonne 'kgCO2' ou similaire)", type=["csv"], key="cloud")
if cloud_csv:
    cdf = pd.read_csv(cloud_csv)
    cloud_cols = [c for c in cdf.columns if "kg" in c.lower() and "co2" in c.lower()]
    if cloud_cols:
        total_cloud_kg = float(cdf[cloud_cols[0]].sum())
        st.metric("Cloud CO₂ (kg/an)", f"{round(total_cloud_kg,1)}")
        st.metric("Cloud Carbone € (12m)", f"{round(total_cloud_kg * prix_carbone,1)}")
       else:

