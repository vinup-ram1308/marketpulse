"""Environment-backed application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
	"""Configuration required to address the MarketPulse BigQuery RAW table."""

	project_id: str
	dataset_id: str
	table_id: str
	location: str

	@property
	def fully_qualified_table_id(self) -> str:
		"""Return the BigQuery table identifier in project.dataset.table form."""
		return f"{self.project_id}.{self.dataset_id}.{self.table_id}"

	@classmethod
	def from_env(cls) -> Settings:
		"""Load settings from the environment, reading a local .env when present."""
		load_dotenv()
		environment_names = {
			"project_id": "GCP_PROJECT_ID",
			"dataset_id": "BIGQUERY_DATASET",
			"table_id": "BIGQUERY_TABLE",
			"location": "BIGQUERY_LOCATION",
		}
		values = {
			setting: os.getenv(environment_name, "").strip()
			for setting, environment_name in environment_names.items()
		}
		missing = [
			environment_names[setting]
			for setting, value in values.items()
			if not value
		]
		if missing:
			raise ValueError(
				"Missing required environment variable(s): " + ", ".join(missing)
			)
		return cls(**values)


def get_settings() -> Settings:
	"""Load and return the current application settings."""
	return Settings.from_env()
