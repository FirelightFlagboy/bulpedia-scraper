import logging
import multiprocessing.pool
import time
from multiprocessing import Pool
from pathlib import Path

import pydantic

from bulpedia_scraper.pokemon import (
    Pokemon,
    PokemonID,
    Pokemons,
    PokemonUrl,
    fetch_pokemon,
    fetch_pokemon_list,
)
from bulpedia_scraper.scrape_utils import HTTPError, ParseError
from bulpedia_scraper.settings import Settings, SettingsBuilder


def _fetch_pokemon(data: tuple[PokemonUrl, Settings]) -> Pokemon:
    pokemon, settings = data
    return fetch_pokemon(pokemon, settings)


def fetch_missing_pokemon_in_batch(
    missing_pokemon: list[PokemonUrl], pool: multiprocessing.pool.Pool, settings: Settings
) -> list[Pokemon]:
    pokemons = []
    BATCH_SIZE = 10

    while missing_pokemon:
        cutout = min(len(missing_pokemon), BATCH_SIZE)

        try:
            pokemons.extend(
                pool.map(
                    _fetch_pokemon, ((to_fetch, settings) for to_fetch in missing_pokemon[:cutout])
                )
            )
        except (HTTPError, ParseError, KeyboardInterrupt, AssertionError) as e:
            logging.error(f"Failed to fetch {cutout} pokemons: {e=}")
            return pokemons

        missing_pokemon = missing_pokemon[cutout:]

        if missing_pokemon:
            pause_duration = BATCH_SIZE / 2
            logging.debug(
                f"Pausing for {pause_duration}s before continuing to fetch {len(missing_pokemon)} pokemons"
            )
            try:
                time.sleep(pause_duration)
            except KeyboardInterrupt:
                logging.warning("Interrupted. Returning fetched pokemons")
                return pokemons

    return pokemons


def read_pokemons_file(pokemon_file: Path) -> dict[PokemonID, Pokemon]:
    pokemon_data = {}

    try:
        with open(pokemon_file) as f:
            raw_data = f.read()
            pokemon_data = Pokemons.validate_json(raw_data)
    except FileNotFoundError:
        pass
    except pydantic.ValidationError:
        logging.warning("Invalid JSON file. Will be overwritten.")
        pass
    return pokemon_data


def write_pokemons_file(pokemons_file: Path, pokemon_data: dict[PokemonID, Pokemon]) -> None:
    if not pokemons_file.parent.exists():
        pokemons_file.parent.mkdir(parents=True)

    with open(pokemons_file, "wb") as f:
        f.write(Pokemons.dump_json(pokemon_data, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    settings = SettingsBuilder().build()

    pokemon_data = read_pokemons_file(settings.pokemon_list)
    already_fetched_ids = set(pokemon_data.keys())

    logging.debug(f"Already fetched {already_fetched_ids=}")

    with Pool(processes=2) as p:
        res = p.apply(fetch_pokemon_list, args=[settings])
        logging.debug(f"Found {len(res)} pokemons")

        pokemon_to_fetch = list(filter(lambda pokemon: pokemon.id not in already_fetched_ids, res))

        pokemons = fetch_missing_pokemon_in_batch(pokemon_to_fetch, p, settings)

    logging.info(f"Fetched {len(pokemons)} pokemons")
    pokemon_data |= {pokemon.id: pokemon for pokemon in pokemons}

    write_pokemons_file(settings.pokemon_list, pokemon_data)
