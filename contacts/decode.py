"""Decode integer-encoded contact fields back to human-readable strings.

These maps must stay in sync with the Go matcher's adif.go.
"""

from datetime import date, timedelta

EPOCH = date(1950, 1, 1)

BANDS = {
    0: "2190m",
    1: "630m",
    2: "560m",
    3: "160m",
    4: "80m",
    5: "60m",
    6: "40m",
    7: "30m",
    8: "20m",
    9: "17m",
    10: "15m",
    11: "12m",
    12: "10m",
    13: "8m",
    14: "6m",
    15: "5m",
    16: "4m",
    17: "2m",
    18: "1.25m",
    19: "70cm",
    20: "33cm",
    21: "23cm",
    22: "13cm",
    23: "9cm",
    24: "6cm",
    25: "3cm",
    26: "1.25cm",
    27: "6mm",
    28: "4mm",
    29: "2.5mm",
    30: "2mm",
    31: "1mm",
    32: "submm",
}

MODES = {
    1: "AM",
    2: "AMTOR",
    3: "AMTORFEC",
    4: "ARDOP",
    5: "ASCI",
    6: "ATV",
    7: "C4FM",
    8: "CHIP",
    9: "CHIP128",
    10: "CHIP64",
    11: "CLO",
    12: "CLOVER",
    13: "CONTESTI",
    14: "CW",
    15: "DATA",
    16: "DIGITALVOICE",
    17: "DOMINO",
    18: "DOMINOF",
    19: "DMR",
    20: "DSTAR",
    21: "DYNAMIC",
    22: "FAX",
    23: "FM",
    24: "FMHELL",
    25: "FSK31",
    26: "FSK441",
    27: "FST4",
    28: "FT4",
    29: "FT8",
    30: "GTOR",
    31: "HELL",
    32: "HELL80",
    33: "HFSK",
    34: "IMAGE",
    35: "ISCAT",
    36: "JT4",
    37: "JT44",
    38: "JT4A",
    39: "JT4B",
    40: "JT4C",
    41: "JT4D",
    42: "JT4E",
    43: "JT4F",
    44: "JT4G",
    45: "JT65",
    46: "JT65A",
    47: "JT65B",
    48: "JT65C",
    49: "JT6M",
    50: "JT9",
    51: "MFSK",
    52: "MFSK16",
    53: "MFSK8",
    54: "MSK144",
    55: "MT63",
    56: "OLIVIA",
    57: "OPERA",
    58: "PAC",
    59: "PAC2",
    60: "PAC3",
    61: "PACKET",
    62: "PACTOR",
    63: "PAX",
    64: "PAX2",
    65: "PCW",
    66: "PHONE",
    67: "PKT",
    68: "PSK",
    69: "PSK10",
    70: "PSK125",
    71: "PSK2K",
    72: "PSK31",
    73: "PSK63",
    74: "PSK63F",
    75: "PSKAM",
    76: "PSKAM10",
    77: "PSKAM31",
    78: "PSKAM50",
    79: "PSKFEC31",
    80: "PSKHELL",
    81: "Q15",
    82: "Q65",
    83: "QPSK125",
    84: "QPSK31",
    85: "QPSK63",
    86: "QRA64",
    87: "ROS",
    88: "RTTY",
    89: "RTTYM",
    90: "SSB",
    91: "SSTV",
    92: "T10",
    93: "THOR",
    94: "THRB",
    95: "THRBX",
    96: "THROB",
    97: "TOR",
    98: "V4",
    99: "VOI",
    100: "WINMOR",
    101: "WSPR",
    102: "FSK",
    103: "MTONE",
}

SUB_MODES = {
    1: "8PSK1000",
    2: "8PSK1000F",
    3: "8PSK1200F",
    4: "8PSK125",
    5: "8PSK125F",
    6: "8PSK125FL",
    7: "8PSK250",
    8: "8PSK250F",
    9: "8PSK250FL",
    10: "8PSK500",
    11: "8PSK500F",
    12: "AMTORFEC",
    13: "ASCI",
    14: "C4FM",
    15: "CHIP128",
    16: "CHIP64",
    17: "DMR",
    18: "DOM-M",
    19: "DOM11",
    20: "DOM16",
    21: "DOM22",
    22: "DOM4",
    23: "DOM44",
    24: "DOM5",
    25: "DOM8",
    26: "DOM88",
    27: "DOMINOEX",
    28: "DOMINOF",
    29: "DSTAR",
    30: "FMHELL",
    31: "FREEDV",
    32: "FSK31",
    33: "FSKHELL",
    34: "FSQCALL",
    35: "FST4",
    36: "FST4W",
    37: "FT4",
    38: "GTOR",
    39: "HELL80",
    40: "HELLX5",
    41: "HELLX9",
    42: "HFSK",
    43: "ISCAT-A",
    44: "ISCAT-B",
    45: "JS8",
    46: "JT4A",
    47: "JT4B",
    48: "JT4C",
    49: "JT4D",
    50: "JT4E",
    51: "JT4F",
    52: "JT4G",
    53: "JT65A",
    54: "JT65B",
    55: "JT65B2",
    56: "JT65C",
    57: "JT65C2",
    58: "JT9-1",
    59: "JT9-10",
    60: "JT9-2",
    61: "JT9-30",
    62: "JT9-5",
    63: "JT9A",
    64: "JT9B",
    65: "JT9C",
    66: "JT9D",
    67: "JT9E",
    68: "JT9E FAST",
    69: "JT9F",
    70: "JT9F FAST",
    71: "JT9G",
    72: "JT9G FAST",
    73: "JT9H",
    74: "JT9H FAST",
    75: "JTMS",
    76: "LSB",
    77: "M17",
    78: "MFSK11",
    79: "MFSK128",
    80: "MFSK128L",
    81: "MFSK16",
    82: "MFSK22",
    83: "MFSK31",
    84: "MFSK32",
    85: "MFSK4",
    86: "MFSK64",
    87: "MFSK64L",
    88: "MFSK8",
    89: "NAVTEX",
    90: "OLIVIA 16/1000",
    91: "OLIVIA 16/500",
    92: "OLIVIA 32/1000",
    93: "OLIVIA 4/125",
    94: "OLIVIA 4/250",
    95: "OLIVIA 8/250",
    96: "OLIVIA 8/500",
    97: "OPERA-BEACON",
    98: "OPERA-QSO",
    99: "PAC2",
    100: "PAC3",
    101: "PAC4",
    102: "PAX2",
    103: "PCW",
    104: "PSK10",
    105: "PSK1000",
    106: "PSK1000RC2",
    107: "PSK125",
    108: "PSK125RC10",
    109: "PSK125RC12",
    110: "PSK125RC16",
    111: "PSK125RC4",
    112: "PSK125RC5",
    113: "PSK250",
    114: "PSK250RC2",
    115: "PSK250RC3",
    116: "PSK250RC5",
    117: "PSK250RC6",
    118: "PSK250RC7",
    119: "PSK31",
    120: "PSK500",
    121: "PSK500RC2",
    122: "PSK500RC3",
    123: "PSK500RC4",
    124: "PSK63",
    125: "PSK63F",
    126: "PSK63RC10",
    127: "PSK63RC20",
    128: "PSK63RC32",
    129: "PSK63RC4",
    130: "PSK63RC5",
    131: "PSK800RC2",
    132: "PSKAM10",
    133: "PSKAM31",
    134: "PSKAM50",
    135: "PSKFEC31",
    136: "PSKHELL",
    137: "Q65",
    138: "QPSK125",
    139: "QPSK250",
    140: "QPSK31",
    141: "QPSK500",
    142: "QPSK63",
    143: "QRA64A",
    144: "QRA64B",
    145: "QRA64C",
    146: "QRA64D",
    147: "QRA64E",
    148: "ROS-EME",
    149: "ROS-HF",
    150: "ROS-MF",
    151: "SIM31",
    152: "SITORB",
    153: "SLOWHELL",
    154: "THOR-M",
    155: "THOR100",
    156: "THOR11",
    157: "THOR16",
    158: "THOR22",
    159: "THOR25X4",
    160: "THOR4",
    161: "THOR5",
    162: "THOR50X1",
    163: "THOR50X2",
    164: "THOR8",
    165: "THRBX",
    166: "THRBX1",
    167: "THRBX2",
    168: "THRBX4",
    169: "THROB1",
    170: "THROB2",
    171: "THROB4",
    172: "USB",
    173: "VARA FM 1200",
    174: "VARA FM 9600",
    175: "VARA HF",
    176: "VARA SATELLITE",
    177: "FSKH105",
    178: "FSKH245",
    179: "SCAMP_FAST",
    180: "SCAMP_SLOW",
    181: "SCAMP_VSLOW",
    182: "SCAMP_OO",
    183: "SCAMP_OO_SLW",
}


def decode_date(days: int) -> date:
    return EPOCH + timedelta(days=days)


def decode_time(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def decode_band(code: int) -> str:
    return BANDS.get(code, f"?{code}")


def decode_mode(code: int, sub_code: int = 0) -> str:
    if sub_code and (sub := SUB_MODES.get(sub_code)):
        return sub
    return MODES.get(code, f"?{code}")


def decode_dxcc(code: int) -> str:
    from contacts.dxcc import DXCC_ENTITIES

    return DXCC_ENTITIES.get(code, f"?{code}")


def decode_grid(number: int, length: int) -> str:
    """Decode an integer-encoded Maidenhead grid locator back to a string.

    Must stay in sync with the Go matcher's numberToMaidenhead in maidenhead.go.
    """
    if number == 0 or length < 4:
        return ""

    n = number - 1

    p6d1 = p6d2 = 0
    if length >= 12:
        p6d2 = n % 10
        n //= 10
        p6d1 = n % 10
        n //= 10

    p5l1 = p5l2 = 0
    if length >= 10:
        p5l2 = n % 24
        n //= 24
        p5l1 = n % 24
        n //= 24

    p4d1 = p4d2 = 0
    if length >= 8:
        p4d2 = n % 10
        n //= 10
        p4d1 = n % 10
        n //= 10

    p3l1 = p3l2 = 0
    if length >= 6:
        p3l2 = n % 24
        n //= 24
        p3l1 = n % 24
        n //= 24

    p2d2 = n % 10
    n //= 10
    p2d1 = n % 10
    n //= 10

    p1l1 = n // 18
    p1l2 = n % 18

    result = f"{chr(65 + p1l1)}{chr(65 + p1l2)}{p2d1}{p2d2}"

    if length >= 6:
        result += f"{chr(65 + p3l1)}{chr(65 + p3l2)}"
    if length >= 8:
        result += f"{p4d1}{p4d2}"
    if length >= 10:
        result += f"{chr(65 + p5l1)}{chr(65 + p5l2)}"
    if length >= 12:
        result += f"{p6d1}{p6d2}"

    return result
