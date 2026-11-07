from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "WoundAI — Dokumentasi dan Pemantauan Luka"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://localhost:5432/woundai_db"
    test_database_url: str = ""
    seed_demo_on_startup: bool = False
    storage_dir: str = "storage"
    model_checkpoint_path: str = "ml/checkpoints/best_resnet34_unet_01norm.pth"
    model_normalization: str = "zero_one"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_test_database_url(self) -> str:
        return self.test_database_url or self.database_url


settings = Settings()
