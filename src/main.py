from pipeline.ingestion.pipeline import run_ingestion
from pipeline.shared.config import settings
from pipeline.shared.logger import logger


def main() -> None:
    logger.info("Starting ingestion for %s", settings.scrape_url)
    run_ingestion(settings.scrape_url)


if __name__ == "__main__":
    main()
