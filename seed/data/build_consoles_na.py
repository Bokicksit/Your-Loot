"""Author the North American console-variant dataset.

This script IS the dataset — run it to emit consoles-na.json. Authored as
code rather than raw JSON so every entry is one compact line, additions diff
cleanly, and the slug/image conventions are applied in one place instead of
by hand 200 times.

The facts (names, model numbers, years, colours) are compiled fresh from
public knowledge and cross-checked against Wikipedia/Wikidata; facts are not
copyrightable and the resulting dataset is published under CC0. Images are
NOT part of the dataset licence: each is a Wikimedia Commons file — most
from the Evan Amos public-domain collection — referenced by its stable
Special:FilePath URL. verify_images.py checks every one answers before the
dataset is trusted; a wrong filename becomes a null image, never a broken
frame.

Deliberately conservative: NA retail releases, the famous colourways, and
iconic controllers/accessories. Completeness comes by correction — the file
is in the repo so collectors can PR the Toys R Us gold N64 we missed.
"""

import json
import re
import sys

COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s


# (kind, platform, title, model_number, year, commons_file_or_None)
# kind: c = console, p = controller (pad), a = accessory
E = []

# ------------------------------------------------------------- Atari
E += [
    ("c", "Atari 2600", "Atari 2600 (Heavy Sixer)", "CX2600", 1977, "Atari-2600-Wood-4Sw-Set.png"),
    ("c", "Atari 2600", "Atari 2600 Jr.", "CX2600 Jr", 1986, "Atari-2600-Jr-FL.png"),
    ("c", "Atari 5200", "Atari 5200", "CX5200", 1982, "Atari-5200-4-Port-wController-L.jpg"),
    ("c", "Atari 7800", "Atari 7800", "CX7800", 1986, "Atari-7800-wControl-Pad-L.jpg"),
    ("c", "Atari Lynx", "Atari Lynx", "PAG-0200", 1989, "Atari-Lynx-I-Handheld.png"),
    ("c", "Atari Lynx", "Atari Lynx II", "PAG-0401", 1991, "Atari-Lynx-II-Handheld-Angled.jpg"),
    ("c", "Atari Jaguar", "Atari Jaguar", "J8001", 1993, None),
    ("p", "Atari 2600", "Atari CX40 Joystick", "CX40", 1977, "Atari-2600-Joystick.jpg"),
]

# ------------------------------------------------------- early others
E += [
    ("c", None, "Magnavox Odyssey", "1TL200", 1972, "Magnavox-Odyssey-Console-Set.png"),
    ("c", None, "Magnavox Odyssey 2", "BK7600", 1978, "Magnavox-Odyssey-2-Console-01.jpg"),
    ("c", None, "Intellivision", "2609", 1980, "Mattel-Intellivision-Console-FL.jpg"),
    ("c", None, "ColecoVision", None, 1982, "ColecoVision-wController-L.png"),
    ("c", None, "Vectrex", "HP-3000", 1982, None),
]

# ------------------------------------------------------------ Nintendo home
E += [
    ("c", "NES", "NES Control Deck", "NES-001", 1985, "NES-Console-Set.png"),
    ("c", "NES", "NES Top Loader", "NES-101", 1993, "NES-101-Console-Set.jpg"),
    ("c", "SNES", "Super Nintendo", "SNS-001", 1991, "Nintendo-Super-NES-Console-FL.jpg"),
    ("c", "SNES", "Super Nintendo (Mini)", "SNS-101", 1997, "SNES-Model-2-Set.png"),
    ("c", "Nintendo 64", "Nintendo 64", "NUS-001", 1996, "N64-Console-Set.png"),
    ("c", "Nintendo 64", "Nintendo 64 — Atomic Purple (Funtastic)", "NUS-101", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Jungle Green (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Fire Orange (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Ice Blue (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Grape Purple (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Smoke Grey (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 — Watermelon Red (Funtastic)", "NUS-001", 1999, None),
    ("c", "Nintendo 64", "Nintendo 64 Pikachu Edition", "NUS-101", 2000, None),
    ("c", "GameCube", "GameCube — Indigo", "DOL-001", 2001, "GameCube-Set.jpg"),
    ("c", "GameCube", "GameCube — Jet Black", "DOL-001", 2001, None),
    ("c", "GameCube", "GameCube — Platinum", "DOL-001", 2002, None),
    ("c", "GameCube", "GameCube — Spice Orange", "DOL-001", 2002, None),
    ("c", "Wii", "Wii — White", "RVL-001", 2006, "Wii-Console.png"),
    ("c", "Wii", "Wii — Black", "RVL-001", 2010, None),
    ("c", "Wii", "Wii Mini", "RVL-201", 2013, "Wii-Mini-Console-Set-H.jpg"),
    ("c", "Wii U", "Wii U Basic (White)", "WUP-001", 2012, "Nintendo-Wii-U-Console-FL.jpg"),
    ("c", "Wii U", "Wii U Deluxe (Black)", "WUP-101", 2012, None),
    ("c", "Switch", "Nintendo Switch", "HAC-001", 2017, "Nintendo-Switch-Console-Docked-wJoyConRB.jpg"),
    ("c", "Switch", "Nintendo Switch (V2)", "HAC-001(-01)", 2019, None),
    ("c", "Switch", "Nintendo Switch — OLED White", "HEG-001", 2021, None),
    ("c", "Switch", "Nintendo Switch — OLED Neon", "HEG-001", 2021, None),
    ("c", "Switch", "Nintendo Switch Lite — Turquoise", "HDH-001", 2019, None),
    ("c", "Switch", "Nintendo Switch Lite — Grey", "HDH-001", 2019, None),
    ("c", "Switch", "Nintendo Switch Lite — Yellow", "HDH-001", 2019, None),
    ("c", "Switch", "Nintendo Switch Lite — Coral", "HDH-001", 2020, None),
    ("c", "Switch", "Nintendo Switch Lite — Blue", "HDH-001", 2021, None),
    ("c", "Switch 2", "Nintendo Switch 2", None, 2025, None),
]

# -------------------------------------------------------- Nintendo handheld
E += [
    ("c", "Game Boy", "Game Boy", "DMG-01", 1989, "Game-Boy-FL.png"),
    ("c", "Game Boy", "Game Boy Play It Loud — Red", "DMG-01", 1995, None),
    ("c", "Game Boy", "Game Boy Play It Loud — Yellow", "DMG-01", 1995, None),
    ("c", "Game Boy", "Game Boy Play It Loud — Black", "DMG-01", 1995, None),
    ("c", "Game Boy", "Game Boy Pocket — Silver", "MGB-001", 1996, "Game-Boy-Pocket-FL.png"),
    ("c", "Game Boy", "Game Boy Pocket — Red", "MGB-001", 1996, None),
    ("c", "Game Boy", "Game Boy Pocket — Black", "MGB-001", 1996, None),
    ("c", "Game Boy Color", "Game Boy Color — Berry", "CGB-001", 1998, None),
    ("c", "Game Boy Color", "Game Boy Color — Grape", "CGB-001", 1998, None),
    ("c", "Game Boy Color", "Game Boy Color — Kiwi", "CGB-001", 1998, None),
    ("c", "Game Boy Color", "Game Boy Color — Teal", "CGB-001", 1998, "Nintendo-Game-Boy-Color-FL.jpg"),
    ("c", "Game Boy Color", "Game Boy Color — Dandelion", "CGB-001", 1998, None),
    ("c", "Game Boy Color", "Game Boy Color — Atomic Purple", "CGB-001", 1998, None),
    ("c", "Game Boy Advance", "Game Boy Advance — Indigo", "AGB-001", 2001, "Nintendo-Game-Boy-Advance-Purple-FL.jpg"),
    ("c", "Game Boy Advance", "Game Boy Advance — Arctic White", "AGB-001", 2001, None),
    ("c", "Game Boy Advance", "Game Boy Advance — Glacier", "AGB-001", 2001, None),
    ("c", "Game Boy Advance", "Game Boy Advance — Fuchsia", "AGB-001", 2001, None),
    ("c", "Game Boy Advance", "Game Boy Advance SP — Cobalt", "AGS-001", 2003, "Nintendo Game Boy Advance SP.png"),
    ("c", "Game Boy Advance", "Game Boy Advance SP — Platinum", "AGS-001", 2003, None),
    ("c", "Game Boy Advance", "Game Boy Advance SP — Onyx", "AGS-001", 2003, None),
    ("c", "Game Boy Advance", "Game Boy Advance SP — Flame Red", "AGS-001", 2003, None),
    ("c", "Game Boy Advance", "Game Boy Advance SP (Backlit)", "AGS-101", 2005, None),
    ("c", "Game Boy Advance", "Game Boy Micro", "OXY-001", 2005, None),
    ("c", "Nintendo DS", "Nintendo DS", "NTR-001", 2004, "Nintendo-DS-Fat-Blue.png"),
    ("c", "Nintendo DS", "Nintendo DS Lite", "USG-001", 2006, "Nintendo-DS-Lite-Black-Open.png"),
    ("c", "Nintendo DS", "Nintendo DSi", "TWL-001", 2009, "Nintendo DSi Photo.jpg"),
    ("c", "Nintendo DS", "Nintendo DSi XL", "UTL-001", 2010, None),
    ("c", "Nintendo 3DS", "Nintendo 3DS", "CTR-001", 2011, "Nintendo-3DS-AquaOpen.png"),
    ("c", "Nintendo 3DS", "Nintendo 3DS XL", "SPR-001", 2012, "Nintendo-3DS-XL-angled.png"),
    ("c", "Nintendo 3DS", "Nintendo 2DS", "FTR-001", 2013, "Nintendo-2DS-angle.jpg"),
    ("c", "Nintendo 3DS", "New Nintendo 3DS XL", "RED-001", 2015, None),
    ("c", "Nintendo 3DS", "New Nintendo 2DS XL", "JAN-001", 2017, None),
    ("c", None, "Virtual Boy", "VUE-01", 1995, "Virtual-Boy-Set.png"),
]

# ---------------------------------------------- Nintendo pads & accessories
E += [
    ("p", "NES", "NES Controller", "NES-004", 1985, "Nintendo-Entertainment-System-NES-Controller-FL.jpg"),
    ("p", "NES", "NES Zapper", "NES-005", 1985, "Nintendo-Entertainment-System-NES-Zapper-Gray-R.jpg"),
    ("a", "NES", "NES R.O.B.", "NES-012", 1985, None),
    ("p", "SNES", "Super Nintendo Controller", "SNS-005", 1991, "SNES-Controller.jpg"),
    ("p", "SNES", "Super Scope", "SNS-013", 1992, "Nintendo-SNES-Super-Scope-L.jpg"),
    ("p", "SNES", "SNES Mouse", "SNS-016", 1992, "SNES-Mouse-and-Pad.jpg"),
    ("p", "Nintendo 64", "Nintendo 64 Controller — Grey", "NUS-005", 1996, "N64-Controller-Gray.jpg"),
    ("p", "Nintendo 64", "Nintendo 64 Controller — Atomic Purple", "NUS-005", 1999, None),
    ("a", "Nintendo 64", "N64 Rumble Pak", "NUS-013", 1997, "N64-Rumble-Pak.jpg"),
    ("a", "Nintendo 64", "N64 Expansion Pak", "NUS-007", 1998, "N64-Expansion-Pak.jpg"),
    ("a", "Nintendo 64", "N64 Controller Pak", "NUS-004", 1996, None),
    ("a", "Nintendo 64", "N64 Transfer Pak", "NUS-019", 1999, "N64-Transfer-Pak.jpg"),
    ("p", "GameCube", "GameCube Controller — Indigo", "DOL-003", 2001, None),
    ("p", "GameCube", "WaveBird Wireless Controller", "DOL-004", 2002, "Nintendo-GameCube-Wavebird-Silver.jpg"),
    ("a", "GameCube", "GameCube Memory Card 59", "DOL-008", 2001, None),
    ("a", "GameCube", "Game Boy Player", "DOL-017", 2003, "GameCube-Game-Boy-Player.jpg"),
    ("p", "Wii", "Wii Remote — White", "RVL-003", 2006, "Nintendo-Wii-Remote-wNunchuck.jpg"),
    ("p", "Wii", "Wii Nunchuk", "RVL-004", 2006, None),
    ("p", "Wii", "Wii Classic Controller", "RVL-005", 2006, "Wii-Classic-Controller-White.jpg"),
    ("a", "Wii", "Wii Balance Board", "RVL-021", 2008, None),
    ("p", "Wii U", "Wii U GamePad", "WUP-010", 2012, None),
    ("p", "Wii U", "Wii U Pro Controller", "WUP-005", 2012, "Nintendo-Wii-U-Pro-Controller-Black.jpg"),
    ("p", "Switch", "Joy-Con Pair — Grey", "HAC-015/016", 2017, "Nintendo Switch Joy-Con Controllers.png"),
    ("p", "Switch", "Joy-Con Pair — Neon Red/Blue", "HAC-015/016", 2017, None),
    ("p", "Switch", "Switch Pro Controller", "HAC-013", 2017, "Nintendo-Switch-Pro-Controller-FL.jpg"),
    ("a", "Game Boy", "Game Boy Camera", "MGB-006", 1998, "Game-Boy-Camera.jpg"),
    ("a", "Game Boy", "Game Boy Printer", "MGB-007", 1998, "Game Boy Printer.jpg"),
    ("a", "NES", "NES Advantage", "NES-026", 1987, "Nintendo-NES-Advantage-Controller.jpg"),
]

# ---------------------------------------------------------------- Sega
E += [
    ("c", "Master System", "Sega Master System", "3010", 1986, "Sega-Master-System-Set.png"),
    ("c", "Master System", "Sega Master System II", "3010-A", 1990, "Sega-Master-System-MkII-Console-FL.png"),
    ("c", "Genesis", "Sega Genesis (Model 1)", "1601", 1989, "Sega-Genesis-Mod1-Set.jpg"),
    ("c", "Genesis", "Sega Genesis (Model 2)", "MK-1631", 1993, "Sega-Genesis-Mod2-Set.png"),
    ("c", "Genesis", "Sega Genesis (Model 3)", "MK-1461", 1998, "Sega-Genesis-3-Console-FL.jpg"),
    ("c", "Genesis", "Sega CD (Model 1)", "MK-4102", 1992, "Sega-Genesis-CD-Model-1-Bare.jpg"),
    ("c", "Genesis", "Sega CD (Model 2)", "MK-4102A", 1993, "Sega-CD-Model2-Set.png"),
    ("c", "Genesis", "Sega 32X", "MK-84000", 1994, "Sega-Genesis-Model2-32X.jpg"),
    ("c", "Genesis", "Sega Nomad", "MK-6100", 1995, "Sega-Nomad-Front.jpg"),
    ("c", "Saturn", "Sega Saturn (Model 1)", "MK-80000", 1995, "Sega-Saturn-Console-Set-Mk1.png"),
    ("c", "Saturn", "Sega Saturn (Model 2)", "MK-80000A", 1996, "Sega-Saturn-Mk-II-NA-BR.jpg"),
    ("c", "Dreamcast", "Sega Dreamcast", "HKT-3020", 1999, "Sega-Dreamcast-Console-FL.jpg"),
    ("c", "Game Gear", "Sega Game Gear", "2110", 1991, "Game-Gear-Handheld.jpg"),
    ("p", "Genesis", "Genesis 3-Button Controller", "1650", 1989, None),
    ("p", "Genesis", "Genesis 6-Button Controller", "MK-1653", 1993, "Sega-Genesis-6But-Cont.jpg"),
    ("p", "Dreamcast", "Dreamcast Controller", "HKT-7700", 1999, "Sega-Dreamcast-Controller-FL.jpg"),
    ("a", "Dreamcast", "Dreamcast VMU", "HKT-7000", 1999, "Sega-Dreamcast-VMU.jpg"),
]

# ---------------------------------------------------------------- Sony
E += [
    ("c", "PlayStation", "PlayStation", "SCPH-1001", 1995, "PSX-Console-wController.png"),
    ("c", "PlayStation", "PlayStation (Dual Shock bundle)", "SCPH-7501", 1997, None),
    ("c", "PlayStation", "PSone", "SCPH-101", 2000, "Sony-PSone-Console-FL.jpg"),
    ("c", "PlayStation 2", "PlayStation 2", "SCPH-30001", 2000, "PS2-Fat-Console-Set.png"),
    ("c", "PlayStation 2", "PlayStation 2 Slim", "SCPH-70012", 2004, "Sony-PlayStation-2-70001-Console-FL.jpg"),
    ("c", "PlayStation 2", "PlayStation 2 Slim — Silver", "SCPH-79001", 2007, None),
    ("c", "PlayStation 3", "PlayStation 3 (60GB, backwards compatible)", "CECHA01", 2006, "Sony-PlayStation-3-CECHA01-wController-L.jpg"),
    ("c", "PlayStation 3", "PlayStation 3 Slim", "CECH-2001A", 2009, "Sony-PlayStation-PS3-Slim-Console-FL.jpg"),
    ("c", "PlayStation 3", "PlayStation 3 Super Slim", "CECH-4001B", 2012, "Sony-PlayStation-PS3-SuperSlim-Console-FL.jpg"),
    ("c", "PlayStation 4", "PlayStation 4", "CUH-1001A", 2013, "Sony-PlayStation-4-wController.jpg"),
    ("c", "PlayStation 4", "PlayStation 4 Slim", "CUH-2015A", 2016, None),
    ("c", "PlayStation 4", "PlayStation 4 Pro", "CUH-7015B", 2016, "Sony-PlayStation4-Pro-Console-FL.png"),
    ("c", "PlayStation 5", "PlayStation 5 (Disc)", "CFI-1015A", 2020, None),
    ("c", "PlayStation 5", "PlayStation 5 Digital Edition", "CFI-1015B", 2020, None),
    ("c", "PlayStation 5", "PlayStation 5 Slim (Disc)", "CFI-2015", 2023, None),
    ("c", "PlayStation 5", "PlayStation 5 Pro", "CFI-7019", 2024, None),
    ("c", "PSP", "PSP-1000", "PSP-1001", 2005, "Psp-1000.jpg"),
    ("c", "PSP", "PSP-2000 (Slim & Lite)", "PSP-2001", 2007, None),
    ("c", "PSP", "PSP-3000", "PSP-3001", 2008, None),
    ("c", "PSP", "PSP Go", "PSP-N1001", 2009, "PSP-Go-FL-Open.jpg"),
    ("c", "PS Vita", "PlayStation Vita (OLED)", "PCH-1001", 2012, "PlayStation-Vita-1101-FL.png"),
    ("c", "PS Vita", "PlayStation Vita Slim", "PCH-2001", 2014, None),
    ("p", "PlayStation", "PlayStation Controller", "SCPH-1080", 1995, "PSX-Original-Controller.png"),
    ("p", "PlayStation", "DualShock", "SCPH-1200", 1998, "PSX-DualShock-Controller.jpg"),
    ("p", "PlayStation 2", "DualShock 2", "SCPH-10010", 2000, "DualShock 2.jpg"),
    ("p", "PlayStation 3", "DualShock 3", "CECHZC2U", 2007, "DualShock 3.jpg"),
    ("p", "PlayStation 4", "DualShock 4", "CUH-ZCT1U", 2013, "DualShock 4.jpg"),
    ("p", "PlayStation 5", "DualSense", "CFI-ZCT1W", 2020, None),
    ("a", "PlayStation", "PS1 Memory Card", "SCPH-1020", 1995, "PSX-Memory-Card.jpg"),
    ("a", "PlayStation 2", "PS2 Memory Card (8MB)", "SCPH-10020", 2000, "PS2-8MB-Mem-Card.jpg"),
    ("a", "PlayStation", "PS1 Multitap", "SCPH-1070", 1996, None),
]

# ------------------------------------------------------------- Microsoft
E += [
    ("c", "Xbox", "Xbox", None, 2001, "Xbox-console.jpg"),
    ("c", "Xbox 360", "Xbox 360 (Pro)", None, 2005, "Microsoft-Xbox-360-Pro-Flat-wController-L.jpg"),
    ("c", "Xbox 360", "Xbox 360 S", "1439", 2010, "Xbox-360S-Console-Set.png"),
    ("c", "Xbox 360", "Xbox 360 E", "1538", 2013, "Microsoft-Xbox-360-E-wController.jpg"),
    ("c", "Xbox One", "Xbox One", "1540", 2013, "Microsoft-Xbox-One-Console-Set-wKinect.jpg"),
    ("c", "Xbox One", "Xbox One S", "1681", 2016, "Microsoft-Xbox-One-S-Console-FL.png"),
    ("c", "Xbox One", "Xbox One X", "1787", 2017, "Microsoft-Xbox-One-X-Console.png"),
    ("c", "Xbox Series X", "Xbox Series X", "1882", 2020, None),
    ("c", "Xbox Series X", "Xbox Series S", "1883", 2020, None),
    ("p", "Xbox", "Xbox Controller (Duke)", None, 2001, "Xbox-Controller-Duke-FL.jpg"),
    ("p", "Xbox", "Xbox Controller S", None, 2002, "Xbox-s-controller.jpg"),
    ("p", "Xbox 360", "Xbox 360 Wireless Controller", None, 2005, "Xbox-360-S-Controller.png"),
    ("p", "Xbox One", "Xbox One Wireless Controller", "1537", 2013, "Microsoft-Xbox-One-controller.jpg"),
    ("p", "Xbox Series X", "Xbox Wireless Controller (Series)", "1914", 2020, None),
    ("a", "Xbox 360", "Xbox 360 Kinect", "1414", 2010, "Xbox-360-Kinect-Standalone.png"),
]

# --------------------------------------------------------------- others
E += [
    ("c", "TurboGrafx-16", "TurboGrafx-16", "PI-TG001", 1989, "TurboGrafx16-Console-Set.png"),
    ("c", None, "Neo Geo AES", "NEO-AES", 1990, "Neo-Geo-AES-FL.jpg"),
    ("c", None, "3DO (Panasonic FZ-1)", "FZ-1", 1993, None),
    ("c", None, "3DO (Panasonic FZ-10)", "FZ-10", 1994, "3DO-FZ-10-Console-FL.png"),
]


def main() -> None:
    seen = set()
    out = []
    kinds = {"c": "console", "p": "controller", "a": "accessory"}
    for kind, platform, title, model, year, image in E:
        slug = slugify(title)
        if slug in seen:
            print(f"DUPLICATE SLUG: {slug}", file=sys.stderr)
            sys.exit(1)
        seen.add(slug)
        out.append({
            "slug": slug,
            "title": title,
            "kind": kinds[kind],
            "platform": platform,
            "model_number": model,
            "release_year": year,
            "image": (COMMONS + image) if image else None,
        })
    with open("consoles-na.json", "w", encoding="utf-8") as f:
        json.dump({
            "name": "yourloot-consoles-na",
            "version": 1,
            "region": "NA",
            "license": "CC0-1.0 (facts); images are Wikimedia Commons files under their own licences",
            "entries": out,
        }, f, indent=1)
    counts = {}
    for e in out:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    print(f"{len(out)} entries — {counts} — {sum(1 for e in out if e['image'])} with images")


if __name__ == "__main__":
    main()
