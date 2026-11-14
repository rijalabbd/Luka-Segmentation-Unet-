from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WoundAI — Dokumentasi dan Pemantauan Luka"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://localhost:5432/woundai_db"
    test_database_url: str = "postgresql+asyncpg://localhost:5432/woundai_test"
    seed_demo_on_startup: bool = False
    storage_dir: str = "storage"
    model_checkpoint_path: str = "ml/checkpoints/best_resnet34_unet_01norm.pth"
    model_normalization: str = "zero_one"
    model_input_size: int = 256
    model_binary_threshold: float = 0.5
    max_upload_size_bytes: int = 10 * 1024 * 1024
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_temperature: float = 0.3
    gemini_max_output_tokens: int = 800
    gemini_timeout_seconds: float = 10.0
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("model_checkpoint_path")
    @classmethod
    def validate_model_checkpoint_path(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("MODEL_CHECKPOINT_PATH tidak boleh kosong.")
        return cleaned

    @field_validator("model_normalization")
    @classmethod
    def validate_model_normalization(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"zero_one", "imagenet"}:
            raise ValueError(
                f"MODEL_NORMALIZATION tidak valid: '{value}'. Gunakan 'zero_one' atau 'imagenet'."
            )
        return cleaned

    @field_validator("model_input_size")
    @classmethod
    def validate_model_input_size(cls, value: int) -> int:
        if value < 32 or value > 2048 or value % 32 != 0:
            raise ValueError(
                f"MODEL_INPUT_SIZE tidak valid: {value}. Harus kelipatan 32 antara 32 dan 2048."
            )
        return value

    @field_validator("model_binary_threshold")
    @classmethod
    def validate_model_binary_threshold(cls, value: float) -> float:
        if not (0.0 < value < 1.0):
            raise ValueError(
                f"MODEL_BINARY_THRESHOLD tidak valid: {value}. Harus berada di antara 0 dan 1 (eksklusif)."
            )
        return value

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("GEMINI_MODEL tidak boleh kosong.")
        return cleaned

    @field_validator("gemini_temperature")
    @classmethod
    def validate_gemini_temperature(cls, value: float) -> float:
        if not (0.0 <= value <= 2.0):
            raise ValueError(
                f"GEMINI_TEMPERATURE tidak valid: {value}. Harus berada di rentang 0,0 hingga 2,0."
            )
        return value

    @field_validator("gemini_max_output_tokens")
    @classmethod
    def validate_gemini_max_output_tokens(cls, value: int) -> int:
        if value < 64:
            raise ValueError(
                f"GEMINI_MAX_OUTPUT_TOKENS tidak valid: {value}. Minimal 64 token."
            )
        return value

    @field_validator("gemini_timeout_seconds")
    @classmethod
    def validate_gemini_timeout_seconds(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError(
                f"GEMINI_TIMEOUT_SECONDS tidak valid: {value}. Harus lebih besar dari 0 detik."
            )
        return value

    @property
    def resolved_test_database_url(self) -> str:
        candidate = self.test_database_url.strip()
        if not candidate or candidate == self.database_url:
            base, _, dbname = self.database_url.rpartition("/")
            test_db = "woundai_test" if dbname == "woundai_db" else f"{dbname}_test"
            candidate = f"{base}/{test_db}"
        if candidate == self.database_url:
            raise RuntimeError("TEST_DATABASE_URL tidak boleh sama dengan DATABASE_URL aplikasi.")
        return candidate


settings = Settings()
