from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    google_cloud_project: str
    vertex_location: str = "us-central1"
    vertex_embedding_model: str = "text-embedding-005"
    vertex_embedding_dim: int = 768
    vertex_generation_model: str = "gemini-2.5-flash"
    embed_batch_size: int = 250
    embed_concurrency: int = 5
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {"env_file": ".env"}


settings = Settings()
