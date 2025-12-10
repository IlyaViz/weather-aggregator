import logging
from typing import Any
from fastapi import HTTPException
from ..enums.hour_result_key_enum import HourResultKeyEnum as hrke
from ..enums.day_result_key_enum import DayResultKeyEnum as drke
from ..enums.result_type_key_enum import ResultTypeKeyEnum as rtke
from ..external_api.weather_api_base import WeatherAPIBase
from ..external_api.region_helper import RegionHelper
from ..exceptions.external_api_exceptions import APIResponseException
from ..types.general_weather_api_types import ForecastData
from ..types.weather_aggregator_types import AggregatedData


logger = logging.getLogger(__name__)


class WeatherAggregator:
    @classmethod
    async def get_aggregated_weather(
        cls, region: str, API_classes: list[WeatherAPIBase]
    ) -> AggregatedData:
        try:
            coordinates = await RegionHelper.convert_to_coordinates(region)
        except APIResponseException as e:
            logger.error(f"Weather aggregation failed for region '{region}': {e}")

            raise

        results = {}

        for API_class in API_classes:
            try:
                result = await API_class.get_weather(coordinates)

                results[API_class.__name__] = result
            except APIResponseException as e:
                logger.error(
                    f"Failed to fetch weather data from {API_class.__name__} for region '{region}': {e}"
                )

                continue

        if not results:
            logger.error(f"No valid weather data available for region '{region}'")

            raise APIResponseException(
                f"No valid weather data available for region '{region}'"
            )

        aggregated_result = cls._aggregate_weather(results)

        return aggregated_result

    @classmethod
    def _aggregate_weather(cls, data: dict[str, ForecastData]) -> AggregatedData:
        result = {}

        template_API_result = data[list(data.keys())[0]]

        for day in template_API_result[rtke.DAILY]:
            if not cls._check_dicts_have_time_key(
                [d[rtke.DAILY] for d in data.values()], day
            ):
                continue

            result[day] = {}
            result[day]["indicators"] = {}

            for key in drke:
                result[day]["indicators"][key] = {}

                for API_class in data:
                    value = data[API_class][rtke.DAILY][day].get(key, None)

                    if value is not None:
                        result[day]["indicators"][key][API_class] = value

                if len(result[day]["indicators"][key]) == 0:
                    del result[day]["indicators"][key]
                elif (
                    not isinstance(value, str)
                    and len(result[day]["indicators"][key]) > 1
                ):
                    result[day]["indicators"][key]["average"] = round(
                        sum(result[day]["indicators"][key].values())
                        / len(result[day]["indicators"][key]),
                        2,
                    )

            result[day]["hours"] = {}

            for time in template_API_result[rtke.HOURLY]:
                date, hour = time.split(" ")

                if date != day:
                    continue

                if not cls._check_dicts_have_time_key(
                    [d[rtke.HOURLY] for d in data.values()], time
                ):
                    continue

                result[day]["hours"][hour] = {}

                for key in hrke:
                    result[day]["hours"][hour][key] = {}

                    for API_class in data:
                        value = data[API_class][rtke.HOURLY][time].get(key, None)

                        if value is not None:
                            result[day]["hours"][hour][key][API_class] = value

                    if (
                        not isinstance(value, str)
                        and len(result[day]["hours"][hour][key]) > 1
                    ):
                        result[day]["hours"][hour][key]["average"] = round(
                            sum(result[day]["hours"][hour][key].values())
                            / len(result[day]["hours"][hour][key]),
                            2,
                        )

        return result

    @staticmethod
    def _check_dicts_have_time_key(dicts: list[dict[Any, Any]], key: str) -> bool:
        for d in dicts:
            if key not in d:
                return False

        return True
