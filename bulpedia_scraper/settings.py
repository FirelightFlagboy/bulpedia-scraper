from dataclasses import dataclass
from pathlib import Path

from requests import Session


@dataclass
class Settings:
    _pokemon_list: Path
    _session: Session

    @property
    def pokemon_list(self) -> Path:
        return self._pokemon_list

    @property
    def session(self) -> Session:
        return self._session


@dataclass
class SettingsBuilder:
    pokemon_list = Path("output/pokemons.json")

    def build(self) -> Settings:
        session = Session()
        session.headers.update({"User-Agent": "Bulpedia scraper/0.1.0"})

        settings = Settings(
            _pokemon_list=self.pokemon_list,
            _session=session,
        )

        return settings
