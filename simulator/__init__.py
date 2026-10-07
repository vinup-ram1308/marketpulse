"""Local market-data simulation utilities."""

from typing import TYPE_CHECKING, Any

__all__ = ["MarketSimulator", "SimulationParameters"]

if TYPE_CHECKING:
	from .market_simulator import MarketSimulator, SimulationParameters


def __getattr__(name: str) -> Any:
	"""Load the public API lazily so the module CLI starts cleanly."""
	if name in __all__:
		from .market_simulator import MarketSimulator, SimulationParameters

		return {
			"MarketSimulator": MarketSimulator,
			"SimulationParameters": SimulationParameters,
		}[name]
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")