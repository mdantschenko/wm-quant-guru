"""Population and economic power per country, from the World Bank.

These are the classic talent pool covariates of the tournament forecasting
literature (Bernard and Busse 2004): the size of the population and the
economic power explain a measurable part of national team success. Yearly
values from 2000 until today, for every country.
"""

from typing import Any

from wmguru.helpers.constant import (
    WebRequestSetting,
    WorldBankSource,
)
from wmguru.helpers.utils import (
    CsvFile,
    WebFileDownloader,
)


class WorldBankIndicatorFetcher:
    """One row per country and year, with both indicators."""

    def __init__(self, web_file_downloader: WebFileDownloader) -> None:
        self._web_file_downloader = web_file_downloader

    def fetch_both_indicators(self) -> int:
        """Write the file and return how many country and year rows it holds."""
        population = self._read_indicator(WorldBankSource.POPULATION_INDICATOR_CODE)
        gross_domestic_product = self._read_indicator(
            WorldBankSource.GROSS_DOMESTIC_PRODUCT_INDICATOR_CODE
        )
        country_and_year_keys = sorted(set(population) | set(gross_domestic_product))

        with CsvFile(
            WorldBankSource.OUTPUT_FILE, WorldBankSource.COLUMN_NAMES
        ).writing_writer() as writer:
            for country, year in country_and_year_keys:
                writer.writerow(
                    [
                        country,
                        year,
                        population.get((country, year), ""),
                        gross_domestic_product.get((country, year), ""),
                    ]
                )
        print(
            f"{len(country_and_year_keys)} country and year rows "
            f"-> {WorldBankSource.OUTPUT_FILE}"
        )
        return len(country_and_year_keys)

    def _read_indicator(self, indicator_code: str) -> dict[tuple[str, str], float]:
        """Read the value of one indicator per country and year."""
        answer = self._web_file_downloader.download_json(
            WorldBankSource.API_URL_TEMPLATE.format(indicator_code=indicator_code),
            timeout_in_seconds=WorldBankSource.TIMEOUT_IN_SECONDS,
        )
        series: dict[tuple[str, str], float] = {}
        for row in self._read_value_rows(answer):
            value = row.get("value")
            if value is None:
                continue
            series[(row["country"]["value"], row["date"])] = float(value)
        return series

    def _read_value_rows(self, answer: Any) -> list[dict[str, Any]]:
        """Read the value rows out of the answer, whose second entry holds them."""
        if not isinstance(answer, list):
            return []
        if len(answer) <= WorldBankSource.VALUE_SERIES_POSITION:
            return []
        value_rows = answer[WorldBankSource.VALUE_SERIES_POSITION]
        return value_rows if isinstance(value_rows, list) else []


if __name__ == "__main__":
    WorldBankIndicatorFetcher(
        WebFileDownloader(
            user_agent=WebRequestSetting.RESEARCH_USER_AGENT,
            polite_delay_in_seconds=WebRequestSetting.STANDARD_POLITE_DELAY_IN_SECONDS,
        )
    ).fetch_both_indicators()
