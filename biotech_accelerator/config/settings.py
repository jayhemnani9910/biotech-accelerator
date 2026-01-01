"""Configuration settings for Biotech Research Accelerator."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AdapterConfig:
    """Configuration for an API adapter."""

    timeout: float = 30.0
    max_retries: int = 3
    backoff_base: float = 1.0
    cache_ttl: int = 86400  # 24 hours in seconds


@dataclass
class PubMedConfig(AdapterConfig):
    """PubMed-specific configuration."""

    email: str = "biotech-accelerator@example.com"
    rate_limit_interval: float = 0.4  # 400ms between requests
    api_key: Optional[str] = None


@dataclass
class PDBConfig(AdapterConfig):
    """PDB-specific configuration."""

    timeout: float = 60.0  # Larger timeout for structure downloads
    cache_dir: str = ".pdb_cache"


@dataclass
class ChEMBLConfig(AdapterConfig):
    """ChEMBL-specific configuration."""

    max_results: int = 100


@dataclass
class UniProtConfig(AdapterConfig):
    """UniProt-specific configuration."""

    pass


@dataclass
class Settings:
    """Global settings for the application."""

    pubmed: PubMedConfig = field(default_factory=PubMedConfig)
    pdb: PDBConfig = field(default_factory=PDBConfig)
    chembl: ChEMBLConfig = field(default_factory=ChEMBLConfig)
    uniprot: UniProtConfig = field(default_factory=UniProtConfig)

    # Query settings
    max_query_length: int = 2000
    max_literature_results: int = 15
    max_drug_results: int = 10

    @classmethod
    def from_env(cls) -> "Settings":
        """Create settings from environment variables."""
        settings = cls()

        # Override from environment if set
        if email := os.getenv("PUBMED_EMAIL"):
            settings.pubmed.email = email
        if api_key := os.getenv("PUBMED_API_KEY"):
            settings.pubmed.api_key = api_key
        if cache_dir := os.getenv("PDB_CACHE_DIR"):
            settings.pdb.cache_dir = cache_dir

        return settings


# Global settings instance
settings = Settings.from_env()
