from __future__ import annotations

import logging
from dataclasses import dataclass

from lxml import etree
from pydantic import BaseModel, TypeAdapter

from bulpedia_scraper.scrape_utils import parse_url_html
from bulpedia_scraper.settings import Settings

BULPEDIA_URL = "https://bulbapedia.bulbagarden.net"
POKEMON_LIST_URL = f"{BULPEDIA_URL}/wiki/Pok%C3%A9mon_category"

logger = logging.getLogger(__name__)


@dataclass
class PokemonUrl:
    id: int
    url: str
    name: str


def fetch_pokemon_list(settings: Settings) -> list[PokemonUrl]:
    root = parse_url_html(POKEMON_LIST_URL, settings.session)
    pokemon_table = root.cssselect("table")[0]
    pokemon_list = pokemon_table.findall("tbody/tr")[1:]  # Skip header row

    def _parse_pokemon_row(row: etree._Element) -> PokemonUrl:
        items = row.findall("td/a")

        id_col = row.find("td")
        assert id_col is not None and id_col.text is not None
        id = int(id_col.text)

        name_col = items[1]
        href = str(name_col.attrib["href"])
        name = name_col.text

        assert name is not None
        return PokemonUrl(id=id, url=BULPEDIA_URL + href, name=name)

    return [_parse_pokemon_row(element) for element in pokemon_list]


PokemonID = int


class PokemonBaseStats(BaseModel):
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int


class Pokemon(BaseModel):
    id: PokemonID
    name: str
    url: str
    base: PokemonBaseStats


Pokemons = TypeAdapter(dict[PokemonID, Pokemon])


def fetch_pokemon(pokemon_url: PokemonUrl, settings: Settings) -> Pokemon:
    log = logger.getChild(f"fetch[{pokemon_url.id:04}:{pokemon_url.name}]")

    log.info(f"Fetching from `{pokemon_url.url}`")
    root = parse_url_html(pokemon_url.url, settings.session)
    log.debug("Received body")

    base_stats_section: list[etree._Element] = []
    for header in ("h4", "h3"):
        # Fetch table the are preceded by a header with a span containing the text "Base stats"
        base_stats_section = root.xpath(
            f"//{header}[contains("
            "translate(span, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'stats')]"
            "/following-sibling::table[1]"
        )  # type: ignore[assignment]
        if base_stats_section:
            break
        else:
            log.warning(f"Failed to find base stats section after {header}.base-stats")

    assert base_stats_section, f"Failed to find base stats section for {pokemon_url.name=}"

    base_stats_table = base_stats_section[0]
    log.debug("Found base stats table")
    try:
        base = _parse_base_stats_table(base_stats_table, log)
    except AssertionError as e:
        log.error(f"Failed to parse base stats table: {e=}")
        raise e

    return Pokemon(id=pokemon_url.id, name=pokemon_url.name, url=pokemon_url.url, base=base)


def _parse_base_stats_table(table: etree._Element, logger: logging.Logger) -> PokemonBaseStats:
    rows = table.findall("tbody/tr")[2:]  # Skip header rows
    assert 6 <= len(rows) < 12, f"Expected 6 rows in base stats table but got {len(rows)}"

    hp = None
    attack = None
    defense = None
    special_attack = None
    special_defense = None
    speed = None

    def _parse_stats_col_header(stats_col: etree._Element) -> str | None:
        span = stats_col.find("a/span")
        return span is not None and span.text or None

    def _parse_stats_col_value(stats_col: etree._Element) -> int | None:
        return stats_col.text is not None and int(stats_col.text)

    for row in rows:
        stats_col = row.findall("th/div")
        if len(stats_col) != 2:
            continue
        stat_name = _parse_stats_col_header(stats_col[0])
        stat_value = _parse_stats_col_value(stats_col[1])
        logger.debug(f"Found stat {stat_name=} {stat_value=}")

        if stat_name is None and stat_value is None:
            continue

        match stat_name:
            case "HP":
                hp = stat_value
            case "Attack":
                attack = stat_value
            case "Defense":
                defense = stat_value
            case "Sp. Atk":
                special_attack = stat_value
            case "Sp. Def":
                special_defense = stat_value
            case "Speed":
                speed = stat_value
            case _:
                continue

    assert (
        hp is not None
        and attack is not None
        and defense is not None
        and special_attack is not None
        and special_defense is not None
        and speed is not None
    ), f"Missing base stats {hp=}, {attack=}, {defense=}, {special_attack=}, {special_defense=}, {speed=}"

    return PokemonBaseStats(
        hp=hp,
        attack=attack,
        defense=defense,
        special_attack=special_attack,
        special_defense=special_defense,
        speed=speed,
    )
