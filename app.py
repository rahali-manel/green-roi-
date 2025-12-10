
import streamlit as st
import pandas as pd
import requests

# --- Config UI ---
st.set_page_config(page_title="Green ROI (Invest - Eco - Org)", layout="wide")
st.title("Green ROI – 3 ROI (Investissement, Écologique, Organisationnel)")

# --- Hypothèses FR (modifiables) ---
prix_carbone = st.sidebar.number_input("Prix interne du carbone (€/kg)", 0.0, 5.0, 0.25, step=0.05)
prix_kwh     = st.sidebar.number_input("Prix élec FR (€/kWh)", 0.0, 2.0, 0.2016, step=0.01)
kg_per_kwh   = st.sidebar.number_input("Intensité FR (kgCO₂/kWh)", 0.0, 1.0, 0.022, step=0.001)  # ≈21,7 g/kWh

# --- Personas (organisationnel) ---
st.sidebar.markdown("### Personas")
sal_designer = st.sidebar.number_input("Salaire Designer (€)", 0.0, 200000.0, 80000.0, step=1000.0)
sal_bureau   = st.sidebar.number_input("Salaire Bureau/Mails (€)", 0.0, 200000.0, 50000.0, step=1000.0)
sens_design  = st.sidebar.slider("Sensibilité Designer", 0.0, 0.05, 0.03, step=0.005)
sens_bureau  = st.sidebar.slider("Sensibilité Bureau/Mails", 0.0, 0.05, 0.01, step=0.005)

# --- Uploader CSV inventaire ---
csv = st.file_uploader("UC1_Inputs for ROI calculation.xlsx", type=["csv"])
if not csv:
    st.info("➡️ Chargez votre CSV pour lancer les calculs.")
    st.stop()

df = pd.read_csv(csv)
st.success("Inventaire chargé ✅")
st.dataframe(df.head(15), use_container_width=True)

# --- Fallback puissance écrans (si non fournie) ---
def watts_for_row(equipement):
    if "screen" in str(equipement).lower():
        return 160, 5, 8, 16  # (W on, W veille, h_on, h_veille) d'après ton Excel
    elif "meeting" in str(equipement).lower():
        return 160, 5, 8, 16
    elif "laptop" in str(equipement).lower():
        return 25, 2, 8, 16
    else:
        return 25, 2, 8, 16

# --- Boavizta API (fabrication CO2) ---
# Doc: https://api.boavizta.org/docs
def boavizta_fabrication_kg(device_type: str):
    try:
        payload = {"device_type": device_type}
        r = requests.post("https://api.boavizta.org/v1/device", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        return float(data.get("impacts", {}).get("gwp", {}).get("manufacturing", 0.0))  # kg CO2e
    except Exception:
        defaults = {"laptop": 300, "smartphone": 57, "tablet": 80, "screen": 200}
        return defaults.get(device_type.lower(), 150.0)

def annual_kwh(w_on, h_on, w_sb, h_sb):
    return ((w_on*h_on)+(w_sb*h_sb))*365/1000.0

# --- Calculs par ligne ---
rows = []
for _, r in df.iterrows():
    equip = str(r.get("Equipement", r.get("equipment",""))).lower()
    qty   = int(r.get("Current number of equipment", r.get("count", 1)))
    life_m= int(r.get("Initial lifespan", r.get("lifespan_months", 60))) if pd.notna(r.get("Initial lifespan", r.get("lifespan_months", None))) else 60
    life_y= max(1, life_m/12)
    price = float(r.get("Unit price", r.get("unit_price", 0.0)))

    w_on, w_sb, h_on, h_sb = watts_for_row(equip)
    kwh = annual_kwh(w_on, h_on, w_sb, h_sb)
    co2_use = kwh * kg_per_kwh
    energy_eur = kwh * prix_kwh

    # Type Boavizta
    if "laptop" in equip: dev_type = "laptop"
    elif "smartphone" in equip or "phone" in equip: dev_type = "smartphone"
    elif "tablet" in equip: dev_type = "tablet"
    elif "screen" in equip: dev_type = "screen"
    else: dev_type = "laptop"

    co2_fab = boavizta_fabrication_kg(dev_type)  # kg CO2 total fabrication
    fab_annual_kg = co2_fab / life_y
    carbon_eur = (co2_use + fab_annual_kg) * prix_carbone

    # TCO Achat vs Leasing vs Garder (12 mois)
    resale_y = life_y
    capex_annual = max(0.0, (price - price*(0.75**resale_y))/life_y)
    tco_buy   = capex_annual + energy_eur + carbon_eur
    lease_m   = float(r.get("lease_fee_month", 0.0))
    tco_lease = lease_m*12 + energy_eur + carbon_eur
    tco_keep  = energy_eur + carbon_eur

    # ROI organisationnel (perf_ratio placeholder = 0.6; à remplacer par PassMark/Geekbench)
    perf_ratio = 0.6
    org_des = sal_designer * min(0.05, max(0.0, sens_design * (1.0 - perf_ratio)))
    org_bur = sal_bureau   * min(0.05, max(0.0, sens_bureau  * (1.0 - perf_ratio)))

    rows.append({
        "Type": r.get("Equipement", r.get("equipment","")),
        "Quantité": qty,
        "kWh/an (unité)": round(kwh,1),
        "CO₂ usage (kg/an)": round(co2_use,1),
        "CO₂ fabrication (kg)": round(co2_fab,1),
        "Énergie € (12m)": round(energy_eur,1),
        "Carbone € (12m)": round(carbon_eur,1),
        "TCO Garder (€/12m)": round(tco_keep,1),
        "TCO Achat (€/12m)": round(tco_buy,1),
        "TCO Leasing (€/12m)": round(tco_lease,1),
        "ROI orga Designer (€)": round(org_des,0),
        "ROI orga Bureau (€)": round(org_bur,0),
    })

out = pd.DataFrame(rows)
st.subheader("Résultats par équipement")
st.dataframe(out, use_container_width=True)

st.subheader("KPIs")
st.metric("kWh total/an", f"{round(out['kWh/an (unité)'].sum(),1)}")
st.metric("€ énergie (12m)", f"{round(out['Énergie € (12m)'].sum(),1)}")
# CO2 total: usage + fabrication amortie (approximé ici par co2_fab moyen / vie)
st.metric("€ carbone (12m)", f"{round(out['Carbone € (12m)'].sum(),1)}")

# --- Uploader Cloud (exports AWS/Azure/Alibaba) ---
st.subheader("Émissions Cloud (uploader CSV fournisseur)")
cloud_csv = st.file_uploader("Importer un export cloud (colonne kgCO2)", type=["csv"], key="cloud")
if cloud_csv:
    cdf = pd.read_csv(cloud_csv)
    col = [c for c in cdf.columns if "kg" in c.lower()]
    total_cloud_kg = float(cdf[col[0]].sum()) if col else 0.0
    st.metric("Cloud CO₂ (kg/an)", f"{round(total_cloud_kg,1)}")
    st.metric("Cloud Carbone € (12m)", f"{round(total_cloud_kg * prix_carbone,1)}")

st.info("➡️ Étapes suivantes : brancher ENERGY STAR pour les écrans, et PassMark/Geekbench pour perf CPU (personas).")
