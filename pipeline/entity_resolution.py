"""
entity_resolution.py

Canonical name mapping for investors that appear under multiple names or
spellings across sources (e.g. "IFC" vs. "International Finance
Corporation", "CDC Group" vs. "British International Investment" after its
2022 rebrand).

This must be run BEFORE deduplication and BEFORE investor_type
standardization in the master pipeline, since unmerged name variants will
otherwise be treated as separate investors and prevent duplicate rows
(same investor, same deal, different name spelling) from being caught.

Usage:
    from entity_resolution import resolve_investor_names
    combined["investor_name"] = combined["investor_name"].replace(
        resolve_investor_names()
    )
"""

# Maps every known raw/alternate spelling to its single canonical form.
# Add new entries here as new source data introduces name variants —
# do not create ad-hoc replace() calls elsewhere in the pipeline.
CANONICAL_INVESTOR_NAMES = {
    "IFC": "International Finance Corporation",
    "World Bank Group - IFC": "International Finance Corporation",
    "British International Investment (BII)": "British International Investment",
    "CDC Group": "British International Investment",  # renamed 2022
    "Flat6Labs Cairo": "Flat6Labs",
    "FMO Ventures Program / Endeavor South Africa": "FMO",
    "VestedWorld Rising Star Fund": "VestedWorld",
    # IFC's own early-stage venture platform, not a separate institution.
    "IFC Ventures": "International Finance Corporation",
    # Same trust fund under two names; previously typed inconsistently
    # (blended_vehicle under the long name, impact_fund under the acronym).
    "Global Agriculture and Food Security Programme": "GAFSP",

    # --- Name variants found by audit.py's near-duplicate check. Each pair
    # is the same institution under a formal/short name, a legal suffix, a
    # regional arm, or an acronym expansion. Deliberately NOT merged:
    # Acumen vs. Acumen Resilient Agriculture Fund (ARAF is a separate fund
    # with its own LPs), Finnfund vs. OP Finnfund Global Impact Fund,
    # Norrsken vs. Norrsken22 (distinct GP), and Kepple vs. Emurgo Kepple.
    'Acumen Fund': 'Acumen',
    'Alpha Mundi Group': 'AlphaMundi',
    'BlueOrchard Microfinance Fund': 'BlueOrchard',
    'Cathay AfricInvest Innovation Fund': 'Cathay AfricInvest Innovation',
    'Century Oak Capital GmbH': 'Century Oak Capital',
    'Consonance Investment Managers': 'Consonance',
    'Global Social Impact Investments': 'Global Social Impact',
    'Katapult Accelerator': 'Katapult',
    'Launch Africa Ventures': 'Launch Africa',
    'OPEC Fund for International Development': 'OPEC Fund',
    # Same institutions disclosed under an acronym by some sources and in
    # full by others; left unresolved they split one node in two and, in
    # the OPEC Fund case, counted the same lender twice inside one deal.
    'OFID': 'OPEC Fund',
    # Added when the GWFP Burkina Faso row was created; the dataset
    # already held the accented spelling from the SIFCA deal.
    'Societe Generale': 'Société Générale',
    'Kepple Ventures': 'Kepple Africa Ventures',
    'Disruptech Ventures': 'DisrupTech Ventures',
    'Standard Bank Group': 'Standard Bank',
    'DFC': 'U.S. International Development Finance Corporation',
    'EIB': 'European Investment Bank',
    'SOSV Select Fund': 'SOSV',
    'Samurai Incubate Africa': 'Samurai Incubate',
    'TO Ventures Food': 'TO Ventures',
    'Wamda Capital': 'Wamda',
    'Sahel Capital Social Enterprise Fund for Agriculture in Africa': 'Sahel Capital SEFAA Fund',
    'EFG-EV Fintech': 'EFG EV Fintech',
}

# Canonical investor_type for each resolved name. Used to overwrite any
# inconsistent/blank investor_type values that crept in from different
# source scripts assigning types independently.
CANONICAL_INVESTOR_TYPES = {
    "Public Investment Corporation": "pe_vc",
    "International Finance Corporation": "DFI",
    "African Development Bank": "DFI",
    "British International Investment": "DFI",
    "FMO": "DFI",
    "Proparco": "DFI",
    "DEG": "DFI",
    "Swedfund": "DFI",
    "EDFI Management Company": "DFI",
    "Acumen Resilient Agriculture Fund": "impact_fund",
    "Mercy Corps Ventures": "impact_fund",
    "Chan Zuckerberg Initiative": "impact_fund",
    "Bill & Melinda Gates Foundation": "impact_fund",
    "Oikocredit": "impact_fund",
    "Shell Foundation": "impact_fund",
    "Ceniarth": "pe_vc",
    "Endeavor Catalyst": "pe_vc",
    "Rabobank": "pe_vc",

    # --- Added when Alexander Poon's co-investment deals were merged. ---
    # Types follow the conventions already present in the dataset: only
    # bilateral and multilateral development finance institutions are "DFI";
    # multi-donor trust funds and concessional facilities are
    # "blended_vehicle" (GAFSP is the existing precedent for keeping such
    # facilities out of the DFI group).
    'KfW': 'DFI',
    'IFU': 'DFI',
    'SIFEM': 'DFI',
    'Ecowas Bank for Investment and Development': 'DFI',
    'IDA Private Sector Window': 'blended_vehicle',
    'Managed Co-Lending Portfolio Program': 'blended_vehicle',
    'Emerging Africa Infrastructure Fund': 'blended_vehicle',
    'Dutch Good Growth Fund': 'blended_vehicle',
    'Green Climate Fund': 'blended_vehicle',
    'Clean Technology Fund': 'blended_vehicle',
    'African Forestry Impact Platform': 'blended_vehicle',
    'European Union': 'blended_vehicle',
    'Aavishkaar Capital': 'impact_fund',
    'Business Partners Limited': 'impact_fund',
    "Children's Investment Fund Foundation": 'impact_fund',
    'Global Social Impact': 'impact_fund',
    'IKEA Foundation': 'impact_fund',
    'Lightrock': 'impact_fund',
    'MEDA': 'impact_fund',
    'OP Finnfund Global Impact Fund': 'impact_fund',
    'Perivoli Innovations': 'impact_fund',
    'Sahara Impact Ventures': 'impact_fund',
    'Schusterman Family Investments': 'impact_fund',
    'Soros Economic Development Fund': 'impact_fund',
    'Stichting DOEN': 'impact_fund',
    'TLG Capital': 'impact_fund',
    'WaterEquity': 'impact_fund',
    'Zebu Investment Partners': 'impact_fund',
    'Norrsken': 'impact_fund',
    'Harambean Prosperity Fund': 'impact_fund',
    'One Acre Ventures': 'impact_fund',
    'Flour Mills of Nigeria': 'corporate',
    'Axian Group': 'corporate',
    'H&S Invest Holding': 'corporate',
    'Intel Capital': 'corporate',
    'Nigeria Sovereign Investment Authority': 'corporate',
    'National Social Security Fund Uganda': 'corporate',
    'Reflect Ventures': 'pe_vc',
    'MSA Capital': 'pe_vc',
    'Timon Capital': 'pe_vc',
    'Uncovered Fund': 'pe_vc',
    'Aruwa Capital': 'pe_vc',
    'Century Oak Capital': 'pe_vc',
    'AfriMobility': 'pe_vc',
    'Africa Internet Ventures': 'pe_vc',
    'Al Khwarizmi Ventures': 'pe_vc',
    'Alumni Ventures': 'pe_vc',
    'Amplo': 'pe_vc',
    'Arcadia Funds': 'pe_vc',
    'Foundation Ventures': 'pe_vc',
    'Firstminute Capital': 'pe_vc',
    'FJ Labs': 'pe_vc',
    'EXEO Capital': 'pe_vc',
    'Dragon Capital': 'pe_vc',
    'DCVC': 'pe_vc',
    'Giant Ventures': 'pe_vc',
    'HAVAIC': 'pe_vc',
    'Hillhouse Capital': 'pe_vc',
    'Koa Labs': 'pe_vc',
    'Kielder Agro': 'pe_vc',
    'Ken Njoroge': 'pe_vc',
    'Lynett Capital': 'pe_vc',
    'Kuramo Capital Management': 'pe_vc',
    'Founder Collective': 'pe_vc',
    'Goodwater Capital': 'pe_vc',
    'Greenhouse Capital': 'pe_vc',
    'GGV Capital': 'pe_vc',
    'MyAsia VC': 'pe_vc',
    'P1 Ventures': 'pe_vc',
    'Pincus Capital': 'pe_vc',
    'Oui Capital': 'pe_vc',
    'Remapped Ventures': 'pe_vc',
    'Rethink Food': 'pe_vc',
    'SOSV Select Fund': 'pe_vc',
    'SPE Capital': 'pe_vc',
    'Raed Ventures': 'pe_vc',
    'Raven One': 'pe_vc',
    'Seedstars International Ventures': 'pe_vc',
    'Ten13 VC': 'pe_vc',
    'V8 Capital Partners': 'pe_vc',
    'VU Venture Partners': 'pe_vc',
    'Vastly Valuable Ventures': 'pe_vc',
    'Verod-Kepple': 'pe_vc',
    'Vertex Ventures': 'pe_vc',
    'Village Global': 'pe_vc',
    'Voltron Capital': 'pe_vc',
    'Zire Africa': 'pe_vc',
    # Fund-vehicle LPs surfaced while researching DFI syndication.
    'Bpifrance': 'DFI',
    'OeEB': 'DFI',
    'Old Mutual': 'commercial_bank',
    'Fawry': 'corporate',
    'Khawarizmi Ventures': 'pe_vc',
    'Vision Ventures': 'pe_vc',
    'CrossFund': 'pe_vc',
    'Roselake Ventures': 'pe_vc',
    'Mo Angels': 'pe_vc',
    'Jedar Capital': 'pe_vc',
    'Saviu Ventures': 'pe_vc',
    'Sayani Investments': 'pe_vc',
    'Afreximbank': 'DFI',
    'Dhow Ventures': 'pe_vc',
    'CrossBoundary': 'pe_vc',
    'Kickoff Africa': 'pe_vc',
    'Future Africa': 'pe_vc',
    'Atacama Ventures': 'pe_vc',
    'Soma Capital': 'pe_vc',
    'Maxula Seed Fund': 'pe_vc',
    'Anava Seed Fund': 'pe_vc',
    'Loyal VC': 'pe_vc',
    'Orange Fab Tunisia': 'corporate',
    'Equitable Ventures': 'pe_vc',
    'Tunisian American Enterprise Fund': 'blended_vehicle',
    'Lateral Capital': 'pe_vc',
    'Bank of Africa': 'commercial_bank',
    'Industrial Development Corporation of South Africa': 'DFI',
    'Agri-Vie Fund': 'impact_fund',
}


# Entities that appear in investor fields but are not investors, and are
# therefore removed from the dataset entirely. This mirrors the
# company-level "out_of_scope" mechanism in classified_with_dealids.csv:
# same test, applied to the other side of the investor-deal row.
OUT_OF_SCOPE_INVESTORS = {
    # A startup pitch competition run by CTA/Heifer, awarding prize money
    # rather than taking an investment position. Not an investor.
    "Pitch AgriHack",
}


# Investee company name variants. deal_id is hash(company + country +
# year), so an unmerged variant splits one financing into two deals, each
# holding part of the syndicate. Found by a normalised near-duplicate scan
# over company_name (audit.py only checked investor names).
#
# Only same-entity variants are listed: legal-suffix differences, case
# differences, and short/long forms. AfDB regional programmes that share a
# title across countries (for example "Strengthening Emergency
# Preparedness" in Burundi, Comoros and South Sudan) are genuinely
# separate country operations and are deliberately NOT merged.
CANONICAL_COMPANY_NAMES = {
    # IFC files this JV under its Dutch sponsor; the investee is the
    # Rwandan operating company jointly held by DSM, IFC, FMO and CDC.
    "Koninklijke DSM N.V.": "Africa Improved Foods",
    # Same Mozambican avocado project disclosed under three spellings.
    "WESTFALIA FRUTO MOZAMBIQUE LIMITADA": "Westfalia Fruto Mozambique",
    "Westfalia Fruto Mozambique Limitada": "Westfalia Fruto Mozambique",
    "ROBUST INTERNATIONAL PTE. LTD.": "Robust International",
    "GRAINPULSE LIMITED": "Grainpulse",
    "ENDA TAMWEEL SA": "Enda Tamweel",
    "Twiga Foods Limited": "Twiga Foods",
    "SUCRES ET DENREES": "Sucres et Denrees",
    "Valency International DMCC": "Valency International Group",
    "VALENCY INTERNATIONAL TRADING PTE LTD": "Valency International Group",
    "ECOM AGROINDUSTRIAL CORP. LIMITED": "ECOM Agroindustrial",
    "KUNE": "Kune",
    "PULA ADVISORS GMBH": "Pula",
    "Pula Advisors": "Pula",
    "Pricepally.com": "Pricepally",
    "SOCIETE GENERALE GHANA LTD": "Societe Generale Ghana",
}


def resolve_company_names() -> dict:
    """Return the raw_name -> canonical_name mapping for investee
    companies, for use with DataFrame.replace()."""
    return CANONICAL_COMPANY_NAMES


def resolve_investor_names() -> dict:
    """Return the raw_name -> canonical_name mapping for use with
    DataFrame.replace()."""
    return CANONICAL_INVESTOR_NAMES


def get_canonical_type(investor_name: str) -> str:
    """Look up the canonical investor_type for a given (already-resolved)
    investor name. Falls back to 'unknown' if not in the lookup table —
    that row should then be manually reviewed and added above."""
    return CANONICAL_INVESTOR_TYPES.get(investor_name, "unknown")


def standardize_investor_types(df):
    """Apply a single canonical investor_type per investor_name across the
    whole dataframe, using majority vote among non-unknown values already
    present, falling back to the CANONICAL_INVESTOR_TYPES table."""
    import pandas as pd

    def get_type_for_group(group):
        # Guard against NaN as well as the literal "unknown": a blank
        # investor_type in a source file reads back as NaN, which is not
        # equal to "unknown" and previously reached .mode()[0] on an empty
        # Series and raised KeyError.
        non_unknown = group[group.notna() & (group != "unknown")]
        if len(non_unknown) > 0:
            return non_unknown.mode().iloc[0]
        return "unknown"

    inferred_types = df.groupby("investor_name")["investor_type"].apply(get_type_for_group)
    df["investor_type"] = df["investor_name"].map(inferred_types)

    # Fall back to the curated table for investors whose every row arrived
    # untyped. Without this the table above was never consulted at all, and
    # any investor introduced by a new source stayed "unknown" forever.
    still_unknown = df["investor_type"] == "unknown"
    df.loc[still_unknown, "investor_type"] = (
        df.loc[still_unknown, "investor_name"]
        .map(CANONICAL_INVESTOR_TYPES)
        .fillna("unknown")
    )
    return df
