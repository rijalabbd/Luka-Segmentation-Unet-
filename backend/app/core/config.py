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
    max_upload_size_bytes: int = 10 * 1024 * 1024
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: float = 10.0
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
