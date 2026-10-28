"""Country / market matching shared by the paid media and streaming importers.

Ad reports and streaming reports label countries differently ("DE", "Germany",
"DEU", "United Kingdom", "UK", "GB"). Both are matched to an ISO 3166-1 alpha-2
code so the same market lines up across files. Labels that cannot be matched are
kept as typed and flagged; they are never guessed.
"""

from __future__ import annotations

import re

ALL_MARKETS_CODE = "ALL"
ALL_MARKETS_LABEL = "All markets"

_COUNTRIES = """
AF Afghanistan|AX Aland Islands|AL Albania|DZ Algeria|AS American Samoa|AD Andorra|AO Angola|AI Anguilla|AQ Antarctica
AG Antigua and Barbuda|AR Argentina|AM Armenia|AW Aruba|AU Australia|AT Austria|AZ Azerbaijan|BS Bahamas|BH Bahrain
BD Bangladesh|BB Barbados|BY Belarus|BE Belgium|BZ Belize|BJ Benin|BM Bermuda|BT Bhutan|BO Bolivia
BQ Bonaire, Sint Eustatius and Saba|BA Bosnia and Herzegovina|BW Botswana|BV Bouvet Island|BR Brazil
IO British Indian Ocean Territory|BN Brunei|BG Bulgaria|BF Burkina Faso|BI Burundi|CV Cabo Verde|KH Cambodia
CM Cameroon|CA Canada|KY Cayman Islands|CF Central African Republic|TD Chad|CL Chile|CN China|CX Christmas Island
CC Cocos Islands|CO Colombia|KM Comoros|CG Congo|CD Democratic Republic of the Congo|CK Cook Islands|CR Costa Rica
CI Cote d'Ivoire|HR Croatia|CU Cuba|CW Curacao|CY Cyprus|CZ Czechia|DK Denmark|DJ Djibouti|DM Dominica
DO Dominican Republic|EC Ecuador|EG Egypt|SV El Salvador|GQ Equatorial Guinea|ER Eritrea|EE Estonia|SZ Eswatini
ET Ethiopia|FK Falkland Islands|FO Faroe Islands|FJ Fiji|FI Finland|FR France|GF French Guiana|PF French Polynesia
TF French Southern Territories|GA Gabon|GM Gambia|GE Georgia|DE Germany|GH Ghana|GI Gibraltar|GR Greece|GL Greenland
GD Grenada|GP Guadeloupe|GU Guam|GT Guatemala|GG Guernsey|GN Guinea|GW Guinea-Bissau|GY Guyana|HT Haiti
HM Heard Island and McDonald Islands|VA Holy See|HN Honduras|HK Hong Kong|HU Hungary|IS Iceland|IN India|ID Indonesia
IR Iran|IQ Iraq|IE Ireland|IM Isle of Man|IL Israel|IT Italy|JM Jamaica|JP Japan|JE Jersey|JO Jordan|KZ Kazakhstan
KE Kenya|KI Kiribati|KP North Korea|KR South Korea|XK Kosovo|KW Kuwait|KG Kyrgyzstan|LA Laos|LV Latvia|LB Lebanon
LS Lesotho|LR Liberia|LY Libya|LI Liechtenstein|LT Lithuania|LU Luxembourg|MO Macao|MG Madagascar|MW Malawi
MY Malaysia|MV Maldives|ML Mali|MT Malta|MH Marshall Islands|MQ Martinique|MR Mauritania|MU Mauritius|YT Mayotte
MX Mexico|FM Micronesia|MD Moldova|MC Monaco|MN Mongolia|ME Montenegro|MS Montserrat|MA Morocco|MZ Mozambique
MM Myanmar|NA Namibia|NR Nauru|NP Nepal|NL Netherlands|NC New Caledonia|NZ New Zealand|NI Nicaragua|NE Niger
NG Nigeria|NU Niue|NF Norfolk Island|MK North Macedonia|MP Northern Mariana Islands|NO Norway|OM Oman|PK Pakistan
PW Palau|PS Palestine|PA Panama|PG Papua New Guinea|PY Paraguay|PE Peru|PH Philippines|PN Pitcairn|PL Poland
PT Portugal|PR Puerto Rico|QA Qatar|RE Reunion|RO Romania|RU Russia|RW Rwanda|BL Saint Barthelemy
SH Saint Helena|KN Saint Kitts and Nevis|LC Saint Lucia|MF Saint Martin|PM Saint Pierre and Miquelon
VC Saint Vincent and the Grenadines|WS Samoa|SM San Marino|ST Sao Tome and Principe|SA Saudi Arabia|SN Senegal
RS Serbia|SC Seychelles|SL Sierra Leone|SG Singapore|SX Sint Maarten|SK Slovakia|SI Slovenia|SB Solomon Islands
SO Somalia|ZA South Africa|GS South Georgia and the South Sandwich Islands|SS South Sudan|ES Spain|LK Sri Lanka
SD Sudan|SR Suriname|SJ Svalbard and Jan Mayen|SE Sweden|CH Switzerland|SY Syria|TW Taiwan|TJ Tajikistan
TZ Tanzania|TH Thailand|TL Timor-Leste|TG Togo|TK Tokelau|TO Tonga|TT Trinidad and Tobago|TN Tunisia|TR Turkey
TM Turkmenistan|TC Turks and Caicos Islands|TV Tuvalu|UG Uganda|UA Ukraine|AE United Arab Emirates
GB United Kingdom|US United States|UM United States Minor Outlying Islands|UY Uruguay|UZ Uzbekistan|VU Vanuatu
VE Venezuela|VN Vietnam|VG British Virgin Islands|VI U.S. Virgin Islands|WF Wallis and Futuna|EH Western Sahara
YE Yemen|ZM Zambia|ZW Zimbabwe
"""

COUNTRY_NAMES: dict[str, str] = {}
for _entry in _COUNTRIES.replace("\n", "|").split("|"):
    _entry = _entry.strip()
    if _entry:
        _code, _name = _entry.split(" ", 1)
        COUNTRY_NAMES[_code] = _name

_ALIASES = {
    "UK": "GB", "GBR": "GB", "GREAT BRITAIN": "GB", "BRITAIN": "GB", "ENGLAND": "GB", "ENGLAND AND WALES": "GB",
    "USA": "US", "U S A": "US", "U S": "US", "UNITED STATES OF AMERICA": "US", "AMERICA": "US",
    "DEU": "DE", "DEUTSCHLAND": "DE", "FRA": "FR", "ESP": "ES", "ITA": "IT", "NLD": "NL", "HOLLAND": "NL",
    "AUS": "AU", "CAN": "CA", "MEX": "MX", "BRA": "BR", "ARG": "AR", "CHL": "CL", "COL": "CO", "PER": "PE",
    "JPN": "JP", "KOR": "KR", "KOREA": "KR", "REPUBLIC OF KOREA": "KR", "SOUTH KOREA": "KR", "CHN": "CN",
    "IND": "IN", "IDN": "ID", "PHL": "PH", "THA": "TH", "VNM": "VN", "MYS": "MY", "SGP": "SG", "NZL": "NZ",
    "ZAF": "ZA", "NGA": "NG", "KEN": "KE", "EGY": "EG", "SAU": "SA", "ARE": "AE", "UAE": "AE", "TUR": "TR",
    "TURKIYE": "TR", "RUS": "RU", "UKR": "UA", "POL": "PL", "SWE": "SE", "NOR": "NO", "DNK": "DK", "FIN": "FI",
    "IRL": "IE", "PRT": "PT", "BEL": "BE", "AUT": "AT", "CHE": "CH", "GRC": "GR", "CZE": "CZ", "CZECH REPUBLIC": "CZ",
    "HUN": "HU", "ROU": "RO", "HKG": "HK", "TWN": "TW", "ISR": "IL", "PAK": "PK", "BGD": "BD", "VEN": "VE",
    "ECU": "EC", "URY": "UY", "PRY": "PY", "BOL": "BO", "CRI": "CR", "PAN": "PA", "DOM": "DO", "GTM": "GT",
    "PUERTO RICO": "PR", "IVORY COAST": "CI", "COTE D IVOIRE": "CI", "RUSSIAN FEDERATION": "RU",
    "VIET NAM": "VN", "LAO PDR": "LA", "SYRIAN ARAB REPUBLIC": "SY", "TURKEY": "TR", "SWAZILAND": "SZ",
    "MACEDONIA": "MK", "BURMA": "MM", "CAPE VERDE": "CV", "TIMOR LESTE": "TL", "EAST TIMOR": "TL",
    "PALESTINIAN TERRITORY": "PS", "CONGO KINSHASA": "CD", "CONGO BRAZZAVILLE": "CG", "DRC": "CD",
    "MACAU": "MO", "BRUNEI DARUSSALAM": "BN", "IRAN ISLAMIC REPUBLIC OF": "IR", "TAIWAN PROVINCE OF CHINA": "TW",
}

_ROLLUP_LABELS = {
    "ALL", "ALL MARKETS", "ALL COUNTRIES", "GLOBAL", "WORLDWIDE", "WORLD", "TOTAL", "ALL REGIONS", "ROW",
    "REST OF WORLD", "INTERNATIONAL", "UNKNOWN", "UNSPECIFIED", "NOT PROVIDED", "NA", "N A", "NAN", "NONE",
}


def _key(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", " ", str(value).replace("&", " and ")).strip().upper()
    return re.sub(r"\s+", " ", text)


_NAME_INDEX = {_key(name): code for code, name in COUNTRY_NAMES.items()}
_NAME_INDEX.update({_key(code): code for code in COUNTRY_NAMES})
_NAME_INDEX.update({_key(alias): code for alias, code in _ALIASES.items()})
_NAME_INDEX["THE NETHERLANDS"] = "NL"
_NAME_INDEX["THE BAHAMAS"] = "BS"
_NAME_INDEX["THE GAMBIA"] = "GM"


def normalize_market(value: object) -> tuple[str | None, str]:
    """Return ``(code, display_name)``.

    ``code`` is an ISO alpha-2 code, ``"ALL"`` for roll-up labels such as
    "Global" or "Worldwide", or ``None`` when the label is not recognized (the
    display name is then the label exactly as typed).
    """
    if value is None:
        return ALL_MARKETS_CODE, ALL_MARKETS_LABEL
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return ALL_MARKETS_CODE, ALL_MARKETS_LABEL
    key = _key(text)
    if key in _ROLLUP_LABELS and key not in _NAME_INDEX:
        return ALL_MARKETS_CODE, ALL_MARKETS_LABEL
    code = _NAME_INDEX.get(key)
    if code:
        return code, COUNTRY_NAMES[code]
    return None, text


def market_label(code: str | None, fallback: str = "") -> str:
    if code == ALL_MARKETS_CODE:
        return ALL_MARKETS_LABEL
    return COUNTRY_NAMES.get(code or "", fallback)
