from pipeline.ingestion.pipeline import run_ingestion
from pipeline.shared.config import settings
from pipeline.shared.logger import logger


def main() -> None:
    """Run legacy URL-based ingestion (primeira entrega)."""
    url = settings.scrape_url
    result = run_ingestion(url)
    logger.info("Ingestion completed | result=%s", result.model_dump())


if __name__ == "__main__":
    main()
