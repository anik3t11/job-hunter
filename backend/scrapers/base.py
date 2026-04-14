from __future__ import annotations
from abc import ABC, abstractmethod


class BaseScraper(ABC):
    @abstractmethod
    def search(
        self,
        role: str,
        location: str,
        locations: list,
        country: str,
        salary_target: int,
        experience_years: float,
    ) -> tuple:
        """
        Returns (jobs: list[dict], error_message: str | None).
        Always return whatever jobs were collected even if an error occurred.
        """
