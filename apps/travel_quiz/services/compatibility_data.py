_COMPATIBLE_MAP: dict[str, str] = {
    "ttt": "tft",
    "ttf": "tff",
    "tft": "ttt",
    "tff": "ttf",
    "ftt": "fft",
    "ftf": "fff",
    "fft": "ftt",
    "fff": "ftf",
}

_INCOMPATIBLE_MAP: dict[str, str] = {
    "ttt": "fff",
    "ttf": "fft",
    "tft": "ftf",
    "tff": "ftt",
    "ftt": "tff",
    "ftf": "tft",
    "fft": "ttf",
    "fff": "ttt",
}
