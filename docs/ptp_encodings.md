# PTP Encodings — Fujifilm Custom Slot

Audit of all PTP integer value mappings for custom-slot (C1–Cn) read operations.
All camera reads are from a Fujifilm X-S10 (2026-03-21) unless noted otherwise.

---

## READ (custom slot → domain value)

Used by `slot_recipe()` in `src/domain/camera/queries.py`.

| Property | Values | Confirmed by camera | Confirmed by source | Unconfirmed |
|---|---|---|---|---|
| FilmSimulation | Provia=1, Velvia=2, Astia=3, Pro Neg. Hi=4, Pro Neg. Std=5, Monochrome STD=6, Monochrome Yellow=7, Monochrome Red=8, Monochrome Green=9, Sepia=10, Classic Chrome=11, Acros STD=12, Acros Yellow=13, Acros Red=14, Acros Green=15, Eterna=16, Classic Negative=17, Eterna Bleach Bypass=18, Reala Ace=20 | | | All |
| WhiteBalance | Auto=0x0002, Auto white priority=0x8020, Auto ambience priority=0x8021, Daylight=0x0004, Incandescent=0x0006, Fluorescent1=0x8001, Fluorescent2=0x8002, Fluorescent3=0x8003, Shade=0x8006, Kelvin=0x8007, Underwater=0x0008, Custom1=0x8008, Custom2=0x8009, Custom3=0x800A | Kelvin=0x8007 (C2 slot) | All others (Fujifilm SDK XAPI.H XSDK_WB_* — validated by Kelvin match) | |
| WB colour temperature | Raw uint16, unit scale (no ×10) | All (4 known slots matched expected Kelvin values) | | |
| WB red fine-tune | int16, unit scale | All (4 known slots) | | |
| WB blue fine-tune | int16, unit scale | All (4 known slots) | | |
| DRangeMode | DR-Auto=0, DR100=100, DR200=200, DR400=400 | | | All — inferred from EXIF `DevelopmentDynamicRange` field; camera may use 0/1/2/3 |
| DRangePriority | Off=0, Weak=1, Strong=2, Auto=0x8000 | All (X-S10 direct reads) | | |
| GrainEffect | Off=6 or 7, Weak+Small=2, Strong+Small=3, Weak+Large=4, Strong+Large=5 | All (X-S10 direct reads) | | Values 6 and 7 both decode to Off |
| ColorEffect | Off=1, Weak=2, Strong=3 | Off=1 (C4), Strong=3 (C1,C2,C3) | Weak=2 (Fujifilm SDK XAPIOpt.H SDK_SHADOWING_P1) | |
| ColorFx | Off=1, Weak=2, Strong=3 | All (C3=Off, C2=Weak, C1=Strong) | | |
| MonochromaticColorWarmCool | int16 ÷ 10 | | | Not read-tested |
| MonochromaticColorMagentaGreen | int16 ÷ 10 | | | Not read-tested |
| ColorMode (saturation) | int16 ÷ 10, range −4..+4 | All (4 known slots) | ×10 scale | |
| Sharpness | int16 ÷ 10, range −4..+4 | All (4 known slots) | ×10 scale | |
| HighLightTone | int16 ÷ 10, range −2..+4 | All (4 known slots) | ×10 scale | |
| ShadowTone | int16 ÷ 10, range −2..+4 | All (4 known slots) | ×10 scale | |
| HighIsoNoiseReduction | 0x5000=+4, 0x6000=+3, 0x0000=+2, 0x1000=+1, 0x2000=0, 0x3000=−1, 0x4000=−2, 0x7000=−3, 0x8000=−4 | All (X-S10 direct reads) | | |
| Definition (clarity) | int16 ÷ 10, range −5..+5 | All (4 known slots) | ×10 scale | |
