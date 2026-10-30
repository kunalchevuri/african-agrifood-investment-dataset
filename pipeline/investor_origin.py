# -*- coding: utf-8 -*-
"""
investor_origin.py

Region in which each investor is domiciled, used to ask whether DFIs bridge
African companies to foreign capital or to African capital.

Region, not country, deliberately: multilateral institutions (IFC, GAFSP,
IDA PSW, EIB, AfDB) have no single national domicile, and a country-level
coding would either misattribute them or drop the most central nodes in the
network. "multilateral" is therefore its own category.

Domicile means where the investing entity is headquartered, NOT where it
invests. An Africa-dedicated fund headquartered in London is coded europe;
the whole point of the measure is to separate the source of capital from
its destination. Investors whose domicile could not be established from a
primary source are left "unknown" and reported as such rather than guessed.
"""

ORIGIN = {
    # ---- multilateral: no single national domicile --------------------
    "International Finance Corporation": "multilateral",
    "GAFSP": "multilateral",
    "IDA Private Sector Window": "multilateral",
    "European Investment Bank": "multilateral",
    "African Development Bank": "multilateral",
    "OPEC Fund": "multilateral",
    "Green Climate Fund": "multilateral",
    "SANAD Fund for MSME": "multilateral",
    "Managed Co-Lending Portfolio Program": "multilateral",
    "EDFI Management Company": "multilateral",
    "Fund for Export Development in Africa": "multilateral",
    "Afreximbank": "multilateral",

    # ---- Europe -------------------------------------------------------
    "FMO": "europe", "British International Investment": "europe",
    "Proparco": "europe", "DEG": "europe", "Swedfund": "europe",
    "Norfund": "europe", "BIO": "europe", "Finnfund": "europe",
    "OP Finnfund Global Impact Fund": "europe", "KfW": "europe",
    "DOB Equity": "europe", "Goodwell Investments": "europe",
    "Oikocredit": "europe", "Aqua-Spark": "europe",
    "Dutch Good Growth Fund": "europe", "BlueOrchard": "europe",
    "SIFEM": "europe", "Elea Foundation": "europe",
    "Rabobank": "europe", "Bpifrance": "europe", "Mirova": "europe",
    "Lightrock": "europe", "Shell Foundation": "europe",
    "Orange Ventures": "europe", "Leaps by Bayer": "europe",
    "Delivery Hero Ventures": "europe", "Global Founders Capital": "europe",
    "Katapult": "europe", "Norrsken Accelerator": "europe",
    "Century Oak Capital": "europe", "Anthemis Exponential Ventures": "europe",
    "Électricité de France": "europe", "AgDevCo": "europe",
    "Global Social Impact": "europe", "Ceniarth": "europe",
    "Absa Group": "africa",

    # ---- North America ------------------------------------------------
    "Endeavor Catalyst": "north_america", "Y Combinator": "north_america",
    "Techstars": "north_america", "Mercy Corps Ventures": "north_america",
    "4DX Ventures": "north_america", "DFS Lab": "north_america",
    "Acumen": "north_america", "Acumen Resilient Agriculture Fund":
        "north_america", "Acumen Capital Partners": "north_america",
    "Flourish Ventures": "north_america", "Omidyar Network":
        "north_america", "Goldman Sachs": "north_america",
    "Breyer Capital": "north_america", "VestedWorld": "north_america",
    "Quona Capital": "north_america", "FINCA Ventures": "north_america",
    "Global Partnerships": "north_america", "Accion Venture Lab":
        "north_america", "1776": "north_america",
    "U.S. International Development Finance Corporation": "north_america",
    "FinDev Canada": "north_america", "SOSV": "north_america",
    "Soma Capital": "north_america", "Plug and Play": "north_america",
    "Magic Fund": "north_america", "Hustle Fund": "north_america",
    "Goodwater Capital": "north_america", "Hack VC": "north_america",
    "JAM Fund": "north_america", "Timon Capital": "north_america",
    "Rippleworks": "north_america", "Draper Richards Kaplan Foundation":
        "north_america", "Cox Enterprises": "north_america",
    "Stephen Pagliuca": "north_america", "Livelihood Impact Fund":
        "north_america", "KawiSafi Ventures": "north_america",
    "Creadev": "europe", "Juven": "europe",

    # ---- Africa -------------------------------------------------------
    "Launch Africa": "africa", "Ventures Platform": "africa",
    "Future Africa": "africa", "Voltron Capital": "africa",
    "LoftyInc Capital Management": "africa", "Consonance": "africa",
    "Alitheia Capital": "africa", "EchoVC": "africa",
    "Chandaria Capital": "africa", "Sahel Capital": "africa",
    "Sahel Capital SEFAA Fund": "africa", "Algebra Ventures": "africa",
    "Camel Ventures": "africa", "DisrupTech Ventures": "africa",
    "Nclude": "africa", "EFG EV Fintech": "africa", "A15": "africa",
    "Flat6Labs": "africa", "Outlierz Ventures": "africa",
    "UM6P Ventures": "africa", "Naspers Foundry": "africa",
    "E Squared Investments": "africa", "E4E Africa": "africa",
    "Public Investment Corporation": "africa", "Standard Bank": "africa",
    "AECI": "africa", "AHL Venture Partners": "africa",
    "Golden Palm Investments": "africa", "TO Ventures": "africa",
    # Verified headquarters: TLcom is Nairobi-headquartered (offices in
    # Lagos and London); Partech Africa is based in Dakar although its
    # manager, Partech, is Paris-based. See AFRICA_DEDICATED_FOREIGN_MGR
    # below for why that distinction is tracked separately.
    "TLcom Capital": "africa", "Partech Africa": "africa",
    # Verified headquarters: Novastar is Nairobi-headquartered (offices
    # in Lagos and London); Endure Capital is headquartered in Palo Alto
    # with an office in Cairo, so it is coded north_america despite its
    # Egyptian deal flow.
    "Novastar Ventures": "africa",
    "Endure Capital": "north_america",

    # ---- Middle East --------------------------------------------------
    "Shorooq Partners": "middle_east", "Beco Capital": "middle_east",
    "Wamda": "middle_east", "Plus VC": "middle_east",
    "Silicon Badia": "middle_east",

    # ---- Asia-Pacific -------------------------------------------------
    "Samurai Incubate": "asia", "Uncovered Fund": "asia",
    "MSA Capital": "asia",
}


def origin_of(name):
    return ORIGIN.get(name, "unknown")


# Africa-headquartered vehicles whose manager or capital base sits outside
# Africa. They are coded "africa" above because the investing entity is
# domiciled there, but the distinction matters: the share of capital coded
# African should be read as an UPPER BOUND on genuinely African-sourced
# capital, since limited partners are not observable in public disclosure.
AFRICA_DEDICATED_FOREIGN_MGR = {
    "Partech Africa",
    "Cathay AfricInvest Innovation",
    "Seedstars Africa Ventures",
    "Kepple Africa Ventures",
}
