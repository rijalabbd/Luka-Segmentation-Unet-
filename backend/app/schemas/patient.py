import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RM_REGEX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_]{2,19}$")

PatientTrendBadge = Literal[
    "belum_ada",
    "baseline",
    "menurun",
    "stabil",
    "meningkat",
    "tidak_dapat_dihitung",
]

BULAN_ID = (
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Mei",
    "Jun",
    "Jul",
    "Agu",
    "Sep",
    "Okt",
    "Nov",
    "Des",
)


def format_tanggal_id(d: date | None) -> str:
    if d is None:
        return "Belum ada kunjungan"
    return f"{d.day:02d} {BULAN_ID[d.month]} {d.year}"


class PatientCreate(BaseModel):
    id: str = Field(..., description="Nomor Rekam Medis (contoh: RM-0031)")
    nama: str | None = Field(default=None, max_length=100)
    umur: int | None = Field(default=None, ge=0, le=120)
    jk: str | None = Field(default=None)
    lokasi: str | None = Field(default=None, max_length=120)
    consent: bool = Field(..., description="Persetujuan informed consent wajib dicentang")
    is_demo: bool = Field(default=False)

    @field_validator("id")
    @classmethod
    def validate_rm(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("Nomor rekam medis wajib diisi.")
        if not RM_REGEX.match(cleaned):
            raise ValueError(
                "Gunakan huruf, angka, tanda hubung, atau garis bawah (3 sampai 20 karakter), contoh: RM-0031."
            )
        return cleaned

    @field_validator("nama", "lokasi", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v

    @field_validator("jk", mode="before")
    @classmethod
    def validate_jk(cls, v: str | None) -> str | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        cleaned = v.strip()
        if cleaned not in ("Laki-laki", "Perempuan"):
            raise ValueError("Jenis kelamin harus 'Laki-laki' atau 'Perempuan'.")
        return cleaned

    @field_validator("consent")
    @classmethod
    def validate_consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError(
                "Centang persetujuan terlebih dahulu. Dokumentasi foto luka tidak boleh dilanjutkan tanpa informed consent."
            )
        return v


class PatientSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nama: str | None = None
    umur: int | None = None
    jk: str | None = None
    lokasi: str | None = None
    n: int = 0
    terakhir: str = "Belum ada kunjungan"
    status: PatientTrendBadge = "belum_ada"
    trend_status: str = "Belum ada kunjungan"
    is_demo: bool = False
