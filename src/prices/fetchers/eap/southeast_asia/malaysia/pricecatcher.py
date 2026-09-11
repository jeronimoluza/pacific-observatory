"""KPDNHEP PriceCatcher (data.gov.my) — Malaysia's official daily price-
monitoring program across 500+ registered premises nationwide (wet markets,
supermarkets, minimarkets, hypermarkets), 758 SKUs (chicken, meat, seafood,
vegetables, fruit, rice, flour, noodles, oils/fats, eggs, dairy/milk powder,
nuts/pulses, spices, sauces, sugar, beverages, plus a minority of non-food
items ridden along on the same monitoring program).

Bulk static files, no auth, no rate limit:
- pricecatcher_{YYYY-MM}.csv  -- daily (date, premise_code, item_code, price)
- lookup_item.csv             -- item_code -> item, unit, item_group, item_category
- lookup_premise.csv          -- premise_code -> premise, address, premise_type,
                                  state, district

Whole-catalog walker: one monthly file per month since cutoff, no filtering.

`_COICOP_MAP` stamps a per-ITEM COICOP-2018 leaf on the emitted row while the
manifest stays `coicop_classification: classifier`. That pairing is deliberate:
`concatenate`'s `_classifier_csv_map` ingests a fetcher's price_observations.csv
ONLY for `classifier` sources, and the per-row code then rides through as
`declared_coicop_codes` and short-circuits the head in `classify`
(`state=narrow_source`, confidence 1.0). Declaring `source_curated` would remove
this file -- 2M rows, the largest fetcher feed in the corpus -- from the corpus
entirely.

The map is keyed on the raw `item` string from lookup_item.csv, NOT on the
composed `item_name`, so a pack-size or unit revision upstream does not orphan
an entry. It covers the 271 items seen in the collected history plus the 69
further items in the current surveyed vocabulary (340 keys against a 797-row
lookup), because the surveyed set rotates brand variants continuously.

Why hand-map a source the classifier already handles: measured 2026-09-11 on
1,335,696 classified rows, the head agreed with this map on 84.7% of rows and
made flat errors on ~76k, several of them keyed on a misleading token --
LOBAK MERAH (carrot) to "Onions and shallots", TERUNG BULAT (round eggplant) to
"Potatoes", DAGING LEMBU TEMPATAN (local beef) to "Meat of goats, lambs and
sheep", and CILI MERAH - MINYAK (a chilli grade) to "Other edible vegetable
oils" because the name contains MINYAK. A further 404,609 rows over 59 items
were never coded at all.

Toiletries, household cleaning products and disposable diapers ride the same
KPDNHEP monitoring program; they are listed in `_NON_COICOP_ITEMS` and keep a
null `coicop_code` rather than being dropped. Under `classifier` a null is
legitimate, the food gate already excludes them, and dropping them would
destroy observations rather than merely leave them unlabelled. An item in
neither collection is logged and also left null, never guessed at.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime, timezone

import pandas as pd

from prices.fetchers.utils import get_scrape_ts, get_session, make_hash

logger = logging.getLogger(__name__)

_BASE = "https://storage.data.gov.my/pricecatcher"
_SOURCE_KEY = "my_pricecatcher"
_IDENT = ["source_key", "observation_date", "item_name", "notes"]

# lookup_item.csv `item` string -> COICOP-2018 leaf
# (src/data/prices/enrich/gold/coicop_leaves.txt).
# lookup_item.csv `item` string -> COICOP-2018 leaf
# (src/data/prices/enrich/gold/coicop_leaves.txt). Keys are the publisher's
# exact strings, mojibake included: item_code 849 really is
# "UDANG PUTIH KECIL (b\t% 61 EKOR SEKILOGRAM)" upstream, where a high-bit
# strip turned U+2265 into b-TAB-%, while neighbouring rows still carry a
# clean U+2265. Normalising the key would stop it matching.
_COICOP_MAP = {
    "100 PLUS (ORIGINAL)": "01.2.6.0.0",
    "ANGGUR HIJAU BERBIJI": "01.1.6.5.1",
    "ANGGUR MERAH BERBIJI": "01.1.6.5.1",
    "ANMUM ESSENTIAL LANGKAH 4 PERISA ASLI (TANPA GULA TAMBAHAN) - KOTAK": "01.1.9.2.1",
    "ASAM JAWA (BERBIJI) PELBAGAI JENAMA": "01.1.9.4.0",
    "ASAM JAWA (TIDAK BERBIJI) ADABI": "01.1.9.4.0",
    "AYAM BELANDA IMPORT": "01.1.2.2.9",
    "AYAM BERSIH - STANDARD": "01.1.2.2.4",
    "AYAM BERSIH - SUPER": "01.1.2.2.4",
    "AYAM HIDUP": "01.1.2.1.4",
    "AYAM TUA HIDUP": "01.1.2.1.4",
    "BABI HIDUP (±100KG / SEEKOR)": "01.1.2.1.2",
    "BAWANG BESAR IMPORT (CHINA)": "01.1.7.4.3",
    "BAWANG BESAR IMPORT (INDIA)": "01.1.7.4.3",
    "BAWANG BESAR IMPORT (PAKISTAN)": "01.1.7.4.3",
    "BAWANG BESAR KUNING/HOLLAND": "01.1.7.4.3",
    "BAWANG KECIL MERAH BIASA IMPORT (INDIA)": "01.1.7.4.3",
    "BAWANG KECIL MERAH IMPORT (CHINA)": "01.1.7.4.3",
    "BAWANG KECIL MERAH IMPORT (HOLLAND)": "01.1.7.4.3",
    "BAWANG KECIL MERAH IMPORT (MYANMAR)": "01.1.7.4.3",
    "BAWANG KECIL MERAH IMPORT (THAILAND)": "01.1.7.4.3",
    "BAWANG KECIL MERAH ROSE IMPORT (INDIA)": "01.1.7.4.3",
    "BAWANG PERAI (LEEK) IMPORT": "01.1.7.4.4",
    "BAWANG PERAI (LEEK) TEMPATAN": "01.1.7.4.4",
    "BAWANG PUTIH IMPORT (CHINA)": "01.1.7.4.2",
    "BAYAM HIJAU": "01.1.7.1.9",
    "BAYAM MERAH": "01.1.7.1.9",
    "BERAS BASMATHI - FAIZA (KASHMIR)": "01.1.1.1.2",
    "BERAS CAP BAO-BAO GOLDEN SARAWAK (SUPER IMPORT)": "01.1.1.1.2",
    "BERAS CAP FAIZA EMAS (SST5%)": "01.1.1.1.2",
    "BERAS CAP GOLDEN SARAWAK (SST5%)": "01.1.1.1.2",
    "BERAS CAP JASMINE (SST5%)": "01.1.1.1.2",
    "BERAS CAP JASMINE SUPER 5 SPECIAL (IMPORT)": "01.1.1.1.2",
    "BERAS CAP JATI (SST5%)": "01.1.1.1.2",
    "BERAS CAP RAMBUTAN (SST5%)": "01.1.1.1.2",
    "BERAS KELAS MAHIR SUPER IMPORT RICE (5%)": "01.1.1.1.2",
    "BERAS PREMIUM CAP 3A BOY (SUPER IMPORT)": "01.1.1.1.2",
    "BERAS PREMIUM CAP UNCLE TAN": "01.1.1.1.2",
    "BERAS PREMIUM CAP UNCLE TAN (SUPER IMPORT)": "01.1.1.1.2",
    "BERAS PULUT THAILAND (BIASA) PELBAGAI JENAMA": "01.1.1.1.2",
    "BERAS PULUT THAILAND (SUSU) PELBAGAI JENAMA": "01.1.1.1.2",
    "BERAS PUTIH CAP FAIZA EMAS (IMPORT)": "01.1.1.1.2",
    "BERAS PUTIH IMPORT SABAH RICE VAGAS TOKOU": "01.1.1.1.2",
    "BERAS SAZARICE SUPER WR (BERAS PUTIH IMPORT)": "01.1.1.1.2",
    "BERAS SUPER CAP 3A BOY (IMPORT)": "01.1.1.1.2",
    "BERAS SUPER CAP ANGGUR SAZARICE 5% (IMPORT THAILAND)": "01.1.1.1.2",
    "BERAS SUPER CAP JATI TWR  5% (IMPORT)": "01.1.1.1.2",
    "BERAS SUPER CAP RAMBUTAN 5% (IMPORT)": "01.1.1.1.2",
    "BERAS SUPER CAP RODA SAZARICE 5% (IMPORT THAILAND)": "01.1.1.1.2",
    "BERAS SUPER HUMA CAP KELISA EMAS (SABAH)": "01.1.1.1.2",
    "BERAS SUPER IMPORT CAP FAMILY": "01.1.1.1.2",
    "BERAS SUPER SAZARICE CAP ANGGUR (BERAS PUTIH IMPORT )": "01.1.1.1.2",
    "BERAS SUPER SAZARICE CAP RODA (BERAS PUTIH IMPORT)": "01.1.1.1.2",
    "BERAS SUPER SPECIAL CAP FAMILI 5%": "01.1.1.1.2",
    "BERAS SUPER SPECIAL TEMPATAN SABAH RICE VAGAS TOKOU": "01.1.1.1.2",
    "BERAS TKC SABAH CAP TQR 5%": "01.1.1.1.2",
    "BERAS TKC SUPER HUMA CAP KELISA EMAS (SABAH)": "01.1.1.1.2",
    "BERAS TQR SABAH CAP TKC 5%": "01.1.1.1.2",
    "BETIK BIASA": "01.1.6.1.6",
    "BIHUN KERING (CAP LONGKOU)": "01.1.1.5.0",
    "BIHUN KERING (CAP SWALLOW KONG MOON)": "01.1.1.5.0",
    "BIHUN KERING IMPORT (CAP BINTANG)": "01.1.1.5.0",
    "BIHUN KERING IMPORT (PELBAGAI JENAMA)": "01.1.1.5.0",
    "BIHUN KERING TEMPATAN (CAP JASMINE)": "01.1.1.5.0",
    "BIHUN KERING TEMPATAN (PELBAGAI JENAMA)": "01.1.1.5.0",
    "BIJI SAWI": "01.1.9.4.0",
    "BROKOLI": "01.1.7.1.3",
    "CILI AKAR HIJAU": "01.1.7.2.1",
    "CILI AKAR MERAH": "01.1.7.2.1",
    "CILI API/PADI HIJAU": "01.1.7.2.1",
    "CILI API/PADI MERAH": "01.1.7.2.1",
    "CILI HIJAU": "01.1.7.2.1",
    "CILI KERING KERINTING (BERTANGKAI/TIDAK BERTANGKAI)": "01.1.9.4.0",
    "CILI KERING LEPER (BERTANGKAI/TIDAK BERTANGKAI)": "01.1.9.4.0",
    "CILI MERAH - KULAI": "01.1.7.2.1",
    "CILI MERAH - MINYAK": "01.1.7.2.1",
    "COCA COLA (BOTOL)": "01.2.6.0.0",
    "COCA COLA (TIN)": "01.2.6.0.0",
    "DADA AYAM (CHICKEN KEEL)": "01.1.2.2.4",
    "DADA AYAM (CHICKEN KEEL) (1KG)": "01.1.2.2.4",
    "DAGING BABI (DAGING & LEMAK / LEAN & FAT)": "01.1.2.2.2",
    "DAGING BABI (ISI DAGING / PURE LEAN)": "01.1.2.2.2",
    "DAGING BABI (PERUT / BELLY)": "01.1.2.2.2",
    "DAGING BABI (RUSUK DENGAN DAGING/ RIBS WITH MEAT)": "01.1.2.2.2",
    "DAGING KAMBING BEBIRI IMPORT BERTULANG (LAMB) (AUSTRALIA - KOTAK) (1KG)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT BERTULANG (LAMB) (NEW ZEALAND - KOTAK)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT BERTULANG (MUTTON) (AUSTRALIA - KOTAK)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT BERTULANG (MUTTON) (NEW ZEALAND - KOTAK)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT TANPA TULANG (LAMB) (TIDAK TERMASUK PAHA - AUSTRALIA)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT TANPA TULANG (LAMB) (TIDAK TERMASUK PAHA - NEW ZEALAND)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT TANPA TULANG (MUTTON) (TIDAK TERMASUK PAHA - AUSTRALIA)": "01.1.2.2.3",
    "DAGING KAMBING BEBIRI IMPORT TANPA TULANG (MUTTON) (TIDAK TERMASUK PAHA - NEW ZEALAND)": "01.1.2.2.3",
    "DAGING KAMBING TEMPATAN BERTULANG": "01.1.2.2.3",
    "DAGING KERBAU IMPORT (INDIA) (BLOCK)": "01.1.2.2.1",
    "DAGING KERBAU IMPORT (INDIA) * (BLADE)": "01.1.2.2.1",
    "DAGING KERBAU IMPORT (INDIA) * (CHUCK)": "01.1.2.2.1",
    "DAGING KERBAU IMPORT (INDIA) * (RUMP)": "01.1.2.2.1",
    "DAGING KERBAU IMPORT (INDIA) * (SILVERSIDE)": "01.1.2.2.1",
    "DAGING KERBAU IMPORT (INDIA) * (TOP SIDE)": "01.1.2.2.1",
    "DAGING KERBAU TEMPATAN": "01.1.2.2.1",
    "DAGING LEMBU IMPORT (BLADE)": "01.1.2.2.1",
    "DAGING LEMBU IMPORT (BLOCK)": "01.1.2.2.1",
    "DAGING LEMBU IMPORT (CHUCKTENDER)": "01.1.2.2.1",
    "DAGING LEMBU IMPORT (KNUCKLE)": "01.1.2.2.1",
    "DAGING LEMBU IMPORT (TOPSIDE)": "01.1.2.2.1",
    "DAGING LEMBU TEMPATAN (BAHAGIAN 1 DAGING PAHA (KECUALI BATANG PINANG - TENDERLOIN)": "01.1.2.2.1",
    "DAGING LEMBU TEMPATAN (BAHAGIAN 2 DAGING PEJAL (KECUALI BATANG PINANG - TENDERLOIN)": "01.1.2.2.1",
    "DAGING PAHA KAMBING BEBIRI IMPORT BERTULANG  (MUTTON) (AUSTRALIA)": "01.1.2.2.3",
    "DAGING PAHA KAMBING BEBIRI IMPORT BERTULANG (LAMB) (AUSTRALIA)": "01.1.2.2.3",
    "DAGING PAHA KAMBING BEBIRI IMPORT BERTULANG (LAMB) (NEW ZEALAND)": "01.1.2.2.3",
    "DAGING PAHA KAMBING BEBIRI IMPORT BERTULANG (MUTTON) (NEW ZEALAND)": "01.1.2.2.3",
    "DESA FRESH MILK (KOTAK)": "01.1.4.1.1",
    "DRAGON FRUIT MERAH": "01.1.6.1.9",
    "DRINHO SOYA (KOTAK)": "01.1.4.4.3",
    "DUMEX DUGRO 3 (1-3 TAHUN) (PELBAGAI PERISA)": "01.1.9.2.1",
    "DUMEX DUGRO 3 (1-3 TAHUN) PERISA ASLI (850G)": "01.1.9.2.1",
    "DUMEX DUPRO 2 (RUMUSAN SUSULAN)": "01.1.9.2.1",
    "DUTCH LADY 123 (BIASA)": "01.1.9.2.1",
    "DUTCH LADY 123 (PELBAGAI PERISA)": "01.1.9.2.1",
    "DUTCH LADY 456 (BIASA)": "01.1.9.2.1",
    "DUTCH LADY 456 (PELBAGAI PERISA)": "01.1.9.2.1",
    "ENFAGROW A+ MIND PRO LANGKAH 3 (PELBAGAI PERISA) (KOTAK)": "01.1.9.2.1",
    "ENFAGROW A+ MIND PRO LANGKAH 3 VANILA (KOTAK)": "01.1.9.2.1",
    "EPAL HIJAU GRANNY SMITH (SAIZ M)": "01.1.6.3.1",
    "EPAL MERAH RED DELICIOUS (SAIZ M)": "01.1.6.3.1",
    "ESEN STAR BRAND 'PELBAGAI PERISA'": "01.1.9.9.0",
    "F&N OREN (BOTOL)": "01.2.6.0.0",
    "F&N OREN (TIN)": "01.2.6.0.0",
    "FERNLEAF 1-3 TAHUN (PELBAGAI PERISA)": "01.1.9.2.1",
    "FERNLEAF 4-6 TAHUN (PELBAGAI PERISA)": "01.1.9.2.1",
    "GARAM HALUS BIASA (PELBAGAI JENAMA)": "01.1.9.3.1",
    "GULA HALUS CASTOR (PELBAGAI JENAMA)": "01.1.8.1.1",
    "GULA MERAH LEMBUT (PELBAGAI JENAMA)": "01.1.8.1.1",
    "GULA PUTIH BERTAPIS HALUS (PELBAGAI JENAMA)": "01.1.8.1.1",
    "GULA PUTIH BERTAPIS KASAR (PELBAGAI JENAMA)": "01.1.8.1.1",
    "HALIA BASAH (TUA)": "01.1.9.4.0",
    "HEINZ APPLE PUREE": "01.1.9.2.3",
    "HEINZ FARLEY RUSKS (ORIGINAL)": "01.1.9.2.9",
    "HEINZ FARLEY RUSKS (PELBAGAI PERISA)": "01.1.9.2.9",
    "IKAN BAWAL HITAM (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN BAWAL PUTIH (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN BILIS GRED B (KOPEK)": "01.1.3.2.9",
    "IKAN CENCARU (ANTARA 4 HINGGA 6 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN DEMUDUK/CUPAK/CERMIN (≤ 3 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN GELAMA (ANTARA 5 HINGGA 10 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN HARUAN (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.1",
    "IKAN JENAHAK (KEPINGAN)": "01.1.3.1.9",
    "IKAN JENAHAK (b	% 1 KILOGRAM SEEKOR)": "01.1.3.1.9",
    "IKAN KELI (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.1",
    "IKAN KEMBUNG (ANTARA 8 HINGGA 12 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN KEMBUNG KECIL/PELALING (ANTARA 10 HINGGA 18 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN KERAPU (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN KERISI (ANTARA 5 HINGGA 10 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN MABUNG (ANTARA 6 HINGGA 10 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN MERAH (KEPINGAN)": "01.1.3.1.9",
    "IKAN MERAH (b	% 1 KILOGRAM SEEKOR)": "01.1.3.1.9",
    "IKAN PARANG (ANTARA 1 HINGGA 3 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN PARANG (KEPINGAN)": "01.1.3.1.6",
    "IKAN PARI (KEPINGAN)": "01.1.3.1.9",
    "IKAN SELAR KUNING (≥ 11 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN SELAR PELATA (≤ 7 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN SELAR/PELATA (≤ 7 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN SELAYANG/SARDIN  (≥ 13 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN SELAYANG/SARDIN (ANTARA 8-12 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN SENANGIN (ANTARA 2 HINGGA 8 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN SIAKAP (ANTARA 2 HINGGA 4 EKOR SEKILOGRAM)": "01.1.3.1.9",
    "IKAN TAMBAN BELURU (ANTARA 10 HINGGA 19 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN TENGGIRI BATANG (ANTARA 1 HINGGA 2 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN TENGGIRI BATANG (KEPINGAN)": "01.1.3.1.6",
    "IKAN TENGGIRI PAPAN (ANTARA 1 HINGGA 2 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN TERUBOK (b	$ 4 EKOR SEKILOGRAM)": "01.1.3.1.6",
    "IKAN TILAPIA HITAM (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.1",
    "IKAN TILAPIA MERAH (ANTARA 2 HINGGA 5 EKOR SEKILOGRAM)": "01.1.3.1.1",
    "IKAN TONGKOL/AYA/KAYU HITAM (ANTARA 1 HINGGA 2 EKOR SEKILOGRAM)": "01.1.3.1.5",
    "IKAN TONGKOL/AYA/KAYU HITAM/PUTIH (ANTARA 1 HINGGA 2 EKOR SEKILOGRAM)": "01.1.3.1.5",
    "INDOCAFE (ORIGINAL BLEND) (PAKET)": "01.2.2.0.1",
    "JAMBU BATU BERBIJI": "01.1.6.1.5",
    "JAMBU BATU TANPA BIJI": "01.1.6.1.5",
    "JEM STRAWBERI LADY'S CHOICE": "01.1.8.3.9",
    "JUS OREN PEEL FRESH (MARIGOLD)": "01.2.1.0.0",
    "KACANG BENDI": "01.1.7.2.6",
    "KACANG BOTOL": "01.1.7.3.9",
    "KACANG BUNCIS": "01.1.7.3.2",
    "KACANG DAL (AUSTRALIA)": "01.1.7.6.4",
    "KACANG DAL BIASA (INDIA)": "01.1.7.6.4",
    "KACANG DAL MALAVI (INDIA)": "01.1.7.6.4",
    "KACANG HIJAU (IMPORT)": "01.1.7.6.9",
    "KACANG MERAH (IMPORT)": "01.1.7.6.1",
    "KACANG PANJANG": "01.1.7.3.2",
    "KACANG SOYA (IMPORT)": "01.1.7.6.9",
    "KACANG TANAH (IMPORT)": "01.1.6.8.8",
    "KAILAN": "01.1.7.1.9",
    "KANGKUNG": "01.1.7.1.9",
    "KELAPA BIJI": "01.1.6.1.8",
    "KELAPA PARUT": "01.1.6.1.8",
    "KELAPA PARUT (BIASA)": "01.1.6.1.8",
    "KEPAK AYAM (CHICKEN WING)": "01.1.2.2.4",
    "KEPAK AYAM (CHICKEN WING) (1KG)": "01.1.2.2.4",
    "KEPALA IKAN JENAHAK": "01.1.3.1.9",
    "KEPALA IKAN MERAH": "01.1.3.1.9",
    "KERANG (SAIZ SEDERHANA)": "01.1.3.4.3",
    "KETAM RENJONG/BUNGA (ANTARA 5 HINGGA 8 EKOR SEKILOGRAM)": "01.1.3.4.2",
    "KETAM RENJONG/BUNGA (≤ 4 EKOR SEKILOGRAM)": "01.1.3.4.2",
    "KICAP LEMAK MANIS CAP KIPAS UDANG": "01.1.9.3.9",
    "KICAP MANIS ADABI": "01.1.9.3.9",
    "KIUB SUP TOM YAM (MAGGI)": "01.1.9.1.6",
    "KORDIAL F&N (PELBAGAI PERISA)": "01.2.9.0.0",
    "KORDIAL F&N (SIRAP ROS)": "01.2.9.0.0",
    "KORDIAL F&N SUN VALLEY (GRENADINE)": "01.2.9.0.0",
    "KORDIAL F&N SUN VALLEY (PELBAGAI PERISA)": "01.2.9.0.0",
    "KORDIAL SUNQUICK (OREN)": "01.2.9.0.0",
    "KRIMER MANIS BERVITAMIN CAP F&N": "01.1.4.3.1",
    "KRIMER MANIS CAP GOLD COIN": "01.1.4.3.1",
    "KRIMER MANIS PEKAT CAP SAJI": "01.1.4.3.1",
    "KUBIS BULAT (TEMPATAN)": "01.1.7.1.2",
    "KUBIS BULAT IMPORT (BEIJING)": "01.1.7.1.2",
    "KUBIS BULAT IMPORT (CHINA)": "01.1.7.1.2",
    "KUBIS BULAT IMPORT (INDONESIA)": "01.1.7.1.2",
    "KUBIS BUNGA (CAULIFLOWER)": "01.1.7.1.3",
    "KUBIS PANJANG (TEMPATAN)": "01.1.7.1.2",
    "KUBIS PANJANG CHINA - BESAR": "01.1.7.1.2",
    "KUETIAU BASAH (PELBAGAI JENAMA)": "01.1.1.5.0",
    "KUNYIT HIDUP": "01.1.9.4.0",
    "LACTOGEN 1 RUMUSAN BAYI (KOTAK)": "01.1.9.2.1",
    "LACTOGEN 2 RUMUSAN SUSULAN (KOTAK)": "01.1.9.2.1",
    "LADA BENGGALA HIJAU (CAPSICUM)": "01.1.7.2.1",
    "LADA BENGGALA KUNING (CAPSICUM)": "01.1.7.2.1",
    "LADA BENGGALA MERAH (CAPSICUM)": "01.1.7.2.1",
    "LAI KUNING (SAIZ M)": "01.1.6.1.9",
    "LENGKUAS": "01.1.9.4.0",
    "LEPAAN BUTTERCUP": "01.1.5.3.0",
    "LIMAU KASTURI": "01.1.6.2.2",
    "LIMAU NIPIS": "01.1.6.2.2",
    "LIVITA WITH HONEY (BOTOL)": "01.2.9.0.0",
    "LOBAK MERAH": "01.1.7.4.1",
    "LOBAK PUTIH (1KG)": "01.1.7.4.9",
    "MAGGI HOT CUP (CURRY)": "01.1.1.5.0",
    "MAGGI MEE CURRY": "01.1.1.5.0",
    "MAGGI MI SEGERA PERISA KARI": "01.1.1.5.0",
    "MAINLAND CHESDALE CHEDDAR CHEESE SPREAD 12 CHEDDAR": "01.1.4.5.0",
    "MARJERIN DAISY": "01.1.5.3.0",
    "MARJERIN PLANTA": "01.1.5.3.0",
    "MAYONIS SEBENAR LADY'S CHOICE": "01.1.9.3.9",
    "MEE KUNING BASAH (PELBAGAI JENAMA)": "01.1.1.5.0",
    "MENTEGA ANCHOR (SALTED)": "01.1.5.2.1",
    "MENTEGA KACANG HALUS LADY'S CHOICE": "01.1.8.4.0",
    "MENTEGA SCS (SALTED)": "01.1.5.2.1",
    "MILNA BISKUT RUSK (ASLI)": "01.1.9.2.9",
    "MILNA BISKUT RUSK (PELBAGAI PERISA)": "01.1.9.2.9",
    "MILO (PAKET)": "01.2.4.0.0",
    "MINYAK JAGUNG CAP DAISY": "01.1.5.1.7",
    "MINYAK JAGUNG CAP MAZOLA": "01.1.5.1.7",
    "MINYAK JAGUNG CAP VECORN": "01.1.5.1.7",
    "MINYAK MASAK PAKET (PELBAGAI JENAMA)": "01.1.5.1.2",
    "MINYAK MASAK SEBATIAN CAP HELANG": "01.1.5.1.9",
    "MINYAK MASAK SEBATIAN CAP KNIFE": "01.1.5.1.9",
    "MINYAK MASAK SEBATIAN CAP PISAU": "01.1.5.1.9",
    "MINYAK MASAK SEBATIAN CAP RED EAGLE": "01.1.5.1.9",
    "MINYAK MASAK TULEN CAP ALIF": "01.1.5.1.2",
    "MINYAK MASAK TULEN CAP BURUH": "01.1.5.1.2",
    "MINYAK MASAK TULEN CAP SAJI": "01.1.5.1.2",
    "MINYAK MASAK TULEN CAP SERI MURNI": "01.1.5.1.2",
    "MINYAK MASAK TULEN CAP VESAWIT": "01.1.5.1.2",
    "MINYAK SAPI CAP QBB": "01.1.5.2.9",
    "MINYAK SAPI CAP WINDMILL GHEEBLEND": "01.1.5.2.9",
    "MIRINDA OREN (BOTOL)": "01.2.6.0.0",
    "NAN LANGKAH 1 RUMUSAN BAYI (KOTAK)": "01.1.9.2.1",
    "NAN LANGKAH 2 RUMUSAN SUSULAN (KOTAK)": "01.1.9.2.1",
    "NENAS BIASA (JOSAPINE/MORRIS/SARAWAK)": "01.1.6.1.7",
    "NESCAFE 3 IN 1 ORIGINAL (AROMATIC & BALANCED)": "01.2.2.0.1",
    "NESCAFE CLASSIC (PAKET)": "01.2.2.0.1",
    "NESTLE CERELAC BERAS - TIN": "01.1.9.2.2",
    "NESTLE CERELAC GANDUM DAN MADU - KOTAK": "01.1.9.2.2",
    "NESTLE COFFEE-MATE": "01.1.9.9.0",
    "OREN VALENCIA (SAIZ M)": "01.1.6.2.3",
    "PAHA AYAM (CHICKEN DRUMSTICK)": "01.1.2.2.4",
    "PEPSI COLA (TIN)": "01.2.6.0.0",
    "PERENCAH NASI GORENG IKAN BILIS SERI AJI": "01.1.9.3.9",
    "PERENCAH TOM YAM ADABI": "01.1.9.3.9",
    "PISANG BERANGAN": "01.1.6.1.2",
    "PISANG EMAS": "01.1.6.1.2",
    "QUAKER OATS INSTANT OATMEALS": "01.1.1.4.0",
    "RED BULL (BOTOL)": "01.2.9.0.0",
    "REFILL ANMUM ESSENTIAL LANGKAH 4 PERISA ASLI (TANPA GULA TAMBAHAN) - KOTAK": "01.1.9.2.1",
    "S-26 RUMUSAN BAYI LANGKAH 1 - (KOTAK)": "01.1.9.2.1",
    "S-26 SMA RUMUSAN BAYI LANGKAH 1 - (KOTAK) (550g)": "01.1.9.2.1",
    "SADERI": "01.1.7.1.9",
    "SANTAN KELAPA JENAMA AYAM BRAND": "01.1.4.4.1",
    "SANTAN KELAPA JENAMA HARMUNI": "01.1.4.4.1",
    "SANTAN KELAPA JENAMA KARA": "01.1.4.4.1",
    "SANTAN KELAPA JENAMA M&S": "01.1.4.4.1",
    "SANTAN KELAPA SEGAR (BIASA)": "01.1.4.4.1",
    "SANTAN KELAPA SEGAR (PEKAT)": "01.1.4.4.1",
    "SARDIN CAP ADABI (SOS TOMATO DENGAN CILI)": "01.1.3.3.2",
    "SARDIN CAP AYAM (SOS TOMATO)": "01.1.3.3.2",
    "SARDIN CAP KING CUP (SOS TOMATO)": "01.1.3.3.2",
    "SAWI HIJAU": "01.1.7.1.9",
    "SAWI PENDEK/JEPUN/SIOW PAK CHOY (1KG)": "01.1.7.1.9",
    "SERBUK CILI BABAS": "01.1.9.4.0",
    "SERBUK KARI AYAM DAN DAGING ADABI": "01.1.9.4.0",
    "SERBUK KARI DAGING BABAS": "01.1.9.4.0",
    "SERBUK KARI IKAN ADABI": "01.1.9.4.0",
    "SERBUK KARI IKAN BABAS": "01.1.9.4.0",
    "SERBUK KUNYIT CAMPURAN (SEBATIAN) ADABI": "01.1.9.4.0",
    "SERBUK NASI GORENG CINA ADABI": "01.1.9.3.9",
    "SERBUK PENAIK ROYAL (TIN)": "01.1.9.9.0",
    "SERBUK PERENCAH SUP ADABI": "01.1.9.3.9",
    "SEVEN UP LEMON & LIME (TIN)": "01.2.6.0.0",
    "SOS CILI LIFE": "01.1.9.3.9",
    "SOS CILI MAGGI": "01.1.9.3.9",
    "SOS TIRAM MAGGI": "01.1.9.3.9",
    "SOS TOMATO MAGGI": "01.1.9.3.9",
    "SOTONG (ANTARA 11 HINGGA17 EKOR SEKILOGRAM)": "01.1.3.4.4",
    "SOTONG (≥ 6 EKOR SEKILOGRAM)": "01.1.3.4.4",
    "SOTONG KERING (SAIZ SERDAHANA)": "01.1.3.5.4",
    "SUSU MARIGOLD HL": "01.1.4.1.1",
    "SUSU SEGAR DUTCH LADY": "01.1.4.1.1",
    "SUSU SEGAR KURMA FARM FRESH": "01.1.4.7.0",
    "SUSU TEPUNG SEGERA DUTCHLADY (BIASA)": "01.1.4.3.2",
    "SUSU TEPUNG SEGERA EVERYDAY": "01.1.4.3.2",
    "TAUGE KACANG HIJAU": "01.1.7.1.9",
    "TAUHU (JENIS KERAS)": "01.1.7.9.5",
    "TEH BOH (UNCANG)": "01.2.3.0.2",
    "TEH LIPTON (UNCANG)": "01.2.3.0.2",
    "TELUR AYAM GRED A": "01.1.4.8.1",
    "TELUR AYAM GRED A (BERAT 65.0 GM HINGGA 69.9 GM SEBIJI)": "01.1.4.8.1",
    "TELUR AYAM GRED B": "01.1.4.8.1",
    "TELUR AYAM GRED B (BERAT 60.0 GM HINGGA 64.9 GM)": "01.1.4.8.1",
    "TELUR AYAM GRED C": "01.1.4.8.1",
    "TELUR AYAM GRED C (BERAT 55.0 GM HINGGA 59.9 GM SEBIJI)": "01.1.4.8.1",
    "TELUR AYAM KAMPUNG": "01.1.4.8.1",
    "TELUR ITIK": "01.1.4.8.1",
    "TELUR MASIN": "01.1.4.8.9",
    "TELUR PUYUH": "01.1.4.8.1",
    "TEMBIKAI MERAH BERBIJI": "01.1.6.5.4",
    "TEMBIKAI MERAH TANPA BIJI": "01.1.6.5.4",
    "TEMBIKAI SUSU": "01.1.6.5.3",
    "TEMPE (BUNGKUSAN PLASTIK)": "01.1.7.9.6",
    "TEPUNG GANDUM CAP KUDA HIJAU": "01.1.1.2.1",
    "TEPUNG GANDUM NGP (BERBUNGKUS, CAP  FAIZA)": "01.1.1.2.1",
    "TEPUNG GANDUM NGP (BERBUNGKUS, CAP MUHIBAH)": "01.1.1.2.1",
    "TEPUNG GANDUM NGP (BERBUNGKUS, CAP SAUH)": "01.1.1.2.1",
    "TEPUNG NAIK SENDIRI CAP 'BLUE KEY'": "01.1.1.2.1",
    "TERUNG BULAT": "01.1.7.2.3",
    "TERUNG PANJANG": "01.1.7.2.3",
    "THIGH AYAM": "01.1.2.2.4",
    "TIMUN": "01.1.7.2.2",
    "TOMATO": "01.1.7.2.4",
    "UBI KENTANG HOLLAND": "01.1.7.5.1",
    "UBI KENTANG IMPORT (CHINA)": "01.1.7.5.1",
    "UBI KENTANG IMPORT (PAKISTAN)": "01.1.7.5.1",
    "UBI KENTANG RUSSET": "01.1.7.5.1",
    "UDANG HARIMAU (ANTARA 20 HINGGA 30 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG KERING": "01.1.3.5.1",
    "UDANG PUTIH BESAR (ANTARA 20 HINGGA 30 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG PUTIH BESAR (BERAT ANTARA 41 EKOR HINGGA 60 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG PUTIH BESAR/BANANA PRAWN (BERAT ANTARA 41 EKOR HINGGA 60 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG PUTIH KECIL (b	% 61 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG PUTIH KECIL (≥ 61 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "UDANG PUTIH/VANNAMEI (TERNAK) (ANTARA 41 HINGGA 60 EKOR SEKILOGRAM)": "01.1.3.4.1",
    "WHOLE LEG AYAM": "01.1.2.2.4",
    "YEO'S LAICI (KOTAK)": "01.2.6.0.0",
    "YEO'S SOYA (KOTAK)": "01.1.4.4.3",
    "YOGURT LACTEL (FAT FREE) (STRAWBERRY)": "01.1.4.6.0",
    "YOGURT MARIGOLD (LOW FAT) (STRAWBERRY)": "01.1.4.6.0",
}

# Toiletries, household cleaning products and disposable diapers monitored by
# the same program -- COICOP divisions 05/12. No division-01/02 leaf applies,
# so these stay uncoded rather than being force-fit or dropped. This lists the
# non-food items the survey is CURRENTLY collecting; ~380 further retired
# non-food labels in lookup_item.csv are not enumerated here, so reactivating
# one produces an unmapped-item warning rather than a silent miscode.
_NON_COICOP_ITEMS = frozenset(
    {
        "BERUS GIGI COLGATE (TWISTER - SOFT)",
        "BERUS GIGI COLGATE (ZIG ZAG - SOFT)",
        "BERUS GIGI ORAL B (COMPLETE EASY CLEAN - SOFT)",
        "DEODORAN NIVEA (EXTRA BRIGHTENING)",
        "DEODORAN NIVEA MAN (BLACK & WHITE INVISIBLE - ORIGINAL)",
        "DEODORAN REXONA (POWDER DRY BRIGHTENING)",
        "DEODORAN REXONA MEN (SPORT DEFENSE)",
        "DRYPERS DRYPANTZ",
        "DRYPERS WEE WEE DRY",
        "HUGGIES DRY PANTS",
        "HUGGIES DRY TAPE",
        "PELEMBUT PAKAIAN - DOWNY (PREMIUM PARFUM PASSION)",
        "PELUNTUR CLOROX (ORIGINAL)",
        "PENCUCI PELBAGAI GUNA AJAX FABULOSO (LAVENDER)",
        "PENCUCI PELBAGAI GUNA DETTOL (LAVENDER)",
        "PENCUCI PELBAGAI GUNA MR MUSCLE (LAVENDER)",
        "PETPET GOLD+",
        "PETPET PANTS GOLD+",
        "SABUN DAIA EXCELLENT WASHING POWER (PELBAGAI JENIS)",
        "SABUN DETERGEN TOP (PELBAGAI JENIS)",
        "SABUN MANDIAN DETTOL (PELBAGAI JENIS)",
        "SABUN MANDIAN LIFEBUOY (PELBAGAI JENIS)",
        "SABUN PENCUCI AXION PASTE (PELBAGAI JENIS)",
        "SABUN PENCUCI KUAT HARIMAU (LEMON)",
        "SABUN PENCUCI SUNLIGHT (PELBAGAI JENIS)",
        "SABUN SERBUK ATTACK (AROMA FRESH + COLOUR)",
        "SABUN SERBUK BREEZE (PELBAGAI JENIS)",
        "SYAMPU HEAD & SHOULDERS (SMOOTH & SILKY)",
        "SYAMPU REJOICE (PELBAGAI JENIS)",
        "SYAMPU SUNSILK (PELBAGAI JENIS)",
        "UBAT GIGI COLGATE (PUDINA SEGAR)",
        "UBAT GIGI DARLIE DOUBLE ACTION (PUDINA ASLI)",
        "UBAT GIGI FRESH & WHITE (PUDINA SEGAR)",
    }
)


def _month_range(cutoff: date, today: date) -> list[tuple[int, int]]:
    months = []
    year, month = cutoff.year, cutoff.month
    while (year, month) <= (today.year, today.month):
        months.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _fetch_csv(session, url: str) -> pd.DataFrame | None:
    try:
        r = session.get(url, timeout=120)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[%s] GET failed for %s: %s", _SOURCE_KEY, url, exc)
        return None
    return pd.read_csv(io.StringIO(r.text), low_memory=False)


def fetch_my_pricecatcher(cutoff: date) -> pd.DataFrame | None:
    session = get_session()

    items = _fetch_csv(session, f"{_BASE}/lookup_item.csv")
    premises = _fetch_csv(session, f"{_BASE}/lookup_premise.csv")
    if items is None or premises is None:
        return None
    items["item_code"] = pd.to_numeric(items["item_code"], errors="coerce")
    premises["premise_code"] = pd.to_numeric(premises["premise_code"], errors="coerce")

    today = datetime.now(timezone.utc).date()
    frames: list[pd.DataFrame] = []
    for year, month in _month_range(cutoff, today):
        url = f"{_BASE}/pricecatcher_{year}-{month:02d}.csv"
        df = _fetch_csv(session, url)
        if df is None or df.empty:
            logger.info("[%s] no data at %s", _SOURCE_KEY, url)
            continue
        df["observation_date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["item_code"] = pd.to_numeric(df["item_code"], errors="coerce")
        df["premise_code"] = pd.to_numeric(df["premise_code"], errors="coerce")
        df = df[
            df["observation_date"].notna()
            & (df["observation_date"] > cutoff)
            & df["price"].notna()
            & (df["price"] > 0)
        ]
        if df.empty:
            continue

        df = df.merge(items, on="item_code", how="left")
        df = df.merge(premises, on="premise_code", how="left")

        item = df["item"].fillna("").astype(str).str.strip()
        unit = df["unit"].fillna("").astype(str).str.strip()
        item_name = (item + " (" + unit + ")").str.strip()

        # lookup_item.csv does not cover every item_code the monthly files use
        # (14 of the 342 codes in 2026-08 were absent). The left join then
        # yields an empty item AND an empty unit, and the composition above
        # used to produce the literal "()" -- 228,496 rows, 11.4% of the
        # source, with no recoverable identity. Worse, "()" is part of _IDENT,
        # so every unresolved item at the same premise on the same date hashed
        # identically: those 228,496 rows carried only 38,475 distinct
        # observation_hash values, and a hash dedup downstream kept one row in
        # six. Naming them by item_code keeps them distinct and lets them be
        # resolved later, when the publisher's lookup catches up.
        unresolved = item == ""
        n_unresolved = int(unresolved.sum())
        if n_unresolved:
            codes = df["item_code"].astype("Int64").astype(str)
            item_name = item_name.mask(unresolved, "UNKNOWN ITEM (item_code=" + codes + ")")
            logger.warning(
                "[%s] %s: %d row(s) over %d item_code(s) absent from "
                "lookup_item.csv -- named by code, left uncoded",
                _SOURCE_KEY,
                url,
                n_unresolved,
                int(df.loc[unresolved, "item_code"].nunique()),
            )

        coicop = item.map(_COICOP_MAP)
        missing = item[coicop.isna() & (item != "") & ~item.isin(_NON_COICOP_ITEMS)]
        if not missing.empty:
            logger.warning(
                "[%s] %s: %d item(s) in neither _COICOP_MAP nor "
                "_NON_COICOP_ITEMS, left uncoded for the classifier: %s",
                _SOURCE_KEY,
                url,
                missing.nunique(),
                sorted(missing.unique()),
            )
        notes = (
            df["item_category"].fillna("").astype(str).str.strip()
            + "/"
            + df["item_group"].fillna("").astype(str).str.strip()
            + "; premise="
            + df["premise"].fillna("").astype(str).str.strip()
            + " ("
            + df["premise_type"].fillna("").astype(str).str.strip()
            + "), "
            + df["state"].fillna("").astype(str).str.strip()
        )

        ts = get_scrape_ts()
        out = pd.DataFrame(
            {
                "observation_date": df["observation_date"].astype(str),
                "period_kind": "daily",
                "country": "malaysia",
                "source_key": _SOURCE_KEY,
                "coicop_code": coicop,
                "item_name": item_name,
                "price_local": df["price"].round(2),
                "currency": "MYR",
                "unit": unit,
                "source_url": url,
                "notes": notes,
                "scrape_ts": ts,
            }
        )
        out["observation_hash"] = out.apply(
            lambda row: make_hash(row.to_dict(), _IDENT), axis=1
        )
        frames.append(out)
        logger.info("[%s] %s -> %d rows", _SOURCE_KEY, url, len(out))

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)
