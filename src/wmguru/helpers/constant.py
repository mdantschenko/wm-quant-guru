"""All constants of the whole project live in this file, grouped in classes by topic.

Nothing else in the project may hold a fixed value of its own. If you need a
path, a column name, a threshold, a default or any other fixed number or text,
put it here and import it. This also holds for a value that is used in exactly
one place.

This file imports nothing from the project itself, so it can never take part in
an import cycle.
"""

from pathlib import Path


class ProjectPath:
    """Folders of the project, derived from where this file lies.

    The path of this file is constant.py inside helpers inside wmguru inside
    src, so the project root is four steps up.
    """

    FOLDERS_UP_TO_THE_PROJECT_ROOT: int = 3
    PROJECT_ROOT: Path = (
        Path(__file__).resolve().parents[FOLDERS_UP_TO_THE_PROJECT_ROOT]
    )
    DATA_ROOT: Path = PROJECT_ROOT / "Data"
    CUSTOM_DATA_ROOT: Path = DATA_ROOT / "Custom_Data"
    CANONICAL_ROOT: Path = DATA_ROOT / "Canonical"
    DOCUMENTATION_ROOT: Path = PROJECT_ROOT / "docs"


class RandomSeed:
    """Fixed seeds, so that every backtest can be repeated with the same result."""

    GLOBAL_RANDOM_SEED: int = 2026


class MatchRecordRule:
    """Limits and defaults of the canonical match schema, concept section 4.1."""

    MINIMUM_GOAL_COUNT: int = 0
    MINIMUM_TEXT_LENGTH: int = 1
    MISSING_TEXT_PLACEHOLDER: str = ""
    PROBLEM_SEPARATOR: str = " | "


class WebRequestSetting:
    """Defaults for every web request the project makes."""

    RESEARCH_USER_AGENT: str = "wm-quant-guru/1.0 (research)"
    BROWSER_USER_AGENT: str = "Mozilla/5.0 (research)"

    SHORT_TIMEOUT_IN_SECONDS: int = 40
    STANDARD_TIMEOUT_IN_SECONDS: int = 60
    LARGE_FILE_TIMEOUT_IN_SECONDS: int = 300
    HUGE_FILE_TIMEOUT_IN_SECONDS: int = 1800
    ENORMOUS_FILE_TIMEOUT_IN_SECONDS: int = 3600

    FAST_POLITE_DELAY_IN_SECONDS: float = 0.2
    SHORT_POLITE_DELAY_IN_SECONDS: float = 0.5
    STANDARD_POLITE_DELAY_IN_SECONDS: float = 1.0

    SINGLE_ATTEMPT: int = 1
    ATTEMPT_WITH_ONE_RETRY: int = 2
    BACKOFF_BEFORE_RETRY_IN_SECONDS: float = 1.0
    PAGE_NOT_FOUND_STATUS_CODE: int = 404


class KaggleSetting:
    """Kaggle serves public datasets without an account over its v1 endpoint."""

    ARCHIVE_DOWNLOAD_BASE_URL: str = "https://www.kaggle.com/api/v1/datasets/download/"
    ZIP_ARCHIVE_FIRST_BYTES: bytes = b"PK"


class EuropeanSoccerDatabaseSource:
    """25000 club matches 2008-2016 with lineups, odds and FIFA attributes."""

    DATASET_REFERENCE: str = "hugomathien/soccer"
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "European Soccer Database (Kaggle)"
    ALREADY_DOWNLOADED_PATTERN: str = "*.sqlite"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.HUGE_FILE_TIMEOUT_IN_SECONDS


class EaSportsFc25RatingSource:
    """EA FC 25 player ratings, closes the gap between FC 24 and FC 26."""

    DATASET_REFERENCE: str = "nyagami/ea-sports-fc-25-database-ratings-and-stats"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "EA Sports FC Ratings (FIFA 15-24)" / "FC25"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS


class EaSportsFc26RatingSource:
    """EA FC 26 player ratings, the scouting state for the 2026 World Cup."""

    DATASET_REFERENCE: str = "justdhia/ea-sports-fc-26-player-ratings"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "EA Sports FC Ratings (FIFA 15-24)" / "FC26"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS


class MatchStatisticSource:
    """Club football 2020-2024 with lineups, coaches and 80000 injury entries."""

    DATASET_REFERENCE: str = "tonygordonjr/football-match-statistics-and-more"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Match Statistics & Injuries (API-Football 2020-2024)"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.HUGE_FILE_TIMEOUT_IN_SECONDS


class WorldCupDatabaseSource:
    """Fjelstul: every World Cup 1930-2022 in 25 normalised tables."""

    DATASET_REFERENCE: str = "joshfjelstul/world-cup-database"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "World Cup Database (Fjelstul, 1930-2022)"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS


class WyscoutEventSource:
    """Pappalardo event data: big five leagues 2017/18, World Cup 2018, Euro 2016."""

    DATASET_REFERENCE: str = "aleespinosa/soccer-match-event-dataset"
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Wyscout Events (Pappalardo 2017-18)"
    ALREADY_DOWNLOADED_PATTERN: str = "events_*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.ENORMOUS_FILE_TIMEOUT_IN_SECONDS


class ClubFootballEngineeredSource:
    """230000 club matches with rating, form, full statistics and odds per match."""

    DATASET_REFERENCE: str = "adamgbor/club-football-match-data-2000-2025"
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Club Football Engineered (2000-2025)"
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS


class UefaCompetitionResultSource:
    """28000 UEFA club matches 1955-2026 plus club coordinates."""

    DATASET_REFERENCE: str = "rtx666x3/all-time-uefa-competitions-results"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT
        / "UEFA Club Competitions (Beat The Bookie)"
        / "all_time_results"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS


class UnderstatLeagueMatchSource:
    """Match level expected goals per big five league since 2014."""

    DATASET_REFERENCE: str = "mexwell/understat-database"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Understat Club xG (2014-)" / "league_matches"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "**/*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.ENORMOUS_FILE_TIMEOUT_IN_SECONDS


class UnderstatPlayerPerGameSource:
    """594000 player match rows with expected goals, expected assists and pressing."""

    DATASET_REFERENCE: str = "codytipton/player-stats-per-game-understat"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Understat Club xG (2014-)" / "player_per_game"
    )
    ALREADY_DOWNLOADED_PATTERN: str = "**/*.csv"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.ENORMOUS_FILE_TIMEOUT_IN_SECONDS


class KaggleArchiveCatalog:
    """Every Kaggle dataset that is downloaded as one ZIP and unpacked as a whole."""

    ALL_SOURCES: tuple[type, ...] = (
        EuropeanSoccerDatabaseSource,
        EaSportsFc25RatingSource,
        EaSportsFc26RatingSource,
        MatchStatisticSource,
        WorldCupDatabaseSource,
        WyscoutEventSource,
        ClubFootballEngineeredSource,
        UefaCompetitionResultSource,
        UnderstatLeagueMatchSource,
        UnderstatPlayerPerGameSource,
    )


class TransfermarktMarketValueSource:
    """Single files of the player-scores dataset, for the squad value feature.

    player_valuations and players carry the market value itself. appearances
    holds the minutes per player and club match, that is the workload.
    transfers holds the moves with date and fee, that is the unrest in a squad
    before a tournament. games holds the club matches with the table position.
    game_lineups holds the line-ups since about 2012.
    """

    DATASET_REFERENCE: str = "davidcariboo/player-scores"
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Transfermarkt Market Values (player-scores)"
    )
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS
    FILE_NAMES: tuple[str, ...] = (
        "player_valuations.csv",
        "players.csv",
        "appearances.csv",
        "transfers.csv",
        "games.csv",
        "game_lineups.csv",
    )


class EaSportsPlayerRatingSource:
    """Single files of the FIFA 15 to FC 24 player dataset.

    male_players holds one row per player and game version. male_teams holds
    the club team ratings per version and contains no national team at all.
    """

    DATASET_REFERENCE: str = "stefanoleone992/ea-sports-fc-24-complete-player-dataset"
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "EA Sports FC Ratings (FIFA 15-24)"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS
    FILE_NAMES: tuple[str, ...] = ("male_players.csv", "male_teams.csv")


class KaggleFileCatalog:
    """Every Kaggle dataset from which only named single files are downloaded."""

    ALL_SOURCES: tuple[type, ...] = (
        TransfermarktMarketValueSource,
        EaSportsPlayerRatingSource,
    )


class FootballManagerSource:
    """Football Manager scouting databases, one edition per tournament era.

    FM17 (November 2016) is the state before the 2018 World Cup, FM20 adds
    current and potential ability, FM21 covers Euro 2021 and Copa 2021, FM23
    appeared two weeks before the 2022 World Cup. There is no free dump for
    FM 24 or FM 26, so the 2014 World Cup and Euro 2016 have no FM state.
    """

    OUTPUT_ROOT: Path = ProjectPath.DATA_ROOT / "Football Manager Database"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.LARGE_FILE_TIMEOUT_IN_SECONDS
    PLAYER_FILE_NAME_TEMPLATE: str = "{edition_name_in_lower_case}_players.csv"

    DATASET_REFERENCE_OF_EDITION: dict[str, str] = {
        "FM17": "ajinkyablaze/football-manager-data",
        "FM20": "ktyptorio/football-manager-2020",
        "FM21": "furkanuluta/football-manager-2021-dataset",
        "FM23": "siddhrajthakor/football-manager-2023-dataset",
    }

    PLAYER_FILE_NAME_INSIDE_ARCHIVE_OF_EDITION: dict[str, str] = {
        "FM17": "dataset.csv",
        "FM20": "datafm20.csv",
        "FM21": "worldfmdata.csv",
        "FM23": "merged_players (1).csv",
    }


class FootballDataSource:
    """football-data.co.uk: club league odds and results, no tournament odds.

    Opening odds exist for the top leagues from about 2002/03, closing odds
    including Pinnacle only from 2012/13. The source covers national club
    leagues only, never World Cup or European Championship matches.

    A main league comes as one CSV file per season. An extra league comes as
    one combined file over all seasons, with another column layout.
    """

    MAIN_LEAGUE_BASE_URL: str = "https://www.football-data.co.uk/mmz4281"
    EXTRA_LEAGUE_BASE_URL: str = "https://www.football-data.co.uk/new"
    OUTPUT_ROOT: Path = (
        ProjectPath.DATA_ROOT / "Football Betting Odds (football-data.co.uk)"
    )
    MAIN_LEAGUE_FOLDER_NAME: str = "main_leagues"
    EXTRA_LEAGUE_FOLDER_NAME: str = "extra_leagues"
    READ_ME_FILE_NAME: str = "README.txt"

    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS
    OLDEST_SEASON_START_YEAR_ON_THE_SITE: int = 1993
    RUNNING_SEASON_START_YEAR: int = 2025

    CSV_HEADER_MARKER: bytes = b"Div,"
    MINIMUM_PLAUSIBLE_FILE_SIZE_IN_BYTES: int = 100
    BYTE_ORDER_MARKER: bytes = b"\xef\xbb\xbf"

    FOLDER_NAME_OF_MAIN_LEAGUE: dict[str, str] = {
        "E0": "E0 (England - Premier League)",
        "E1": "E1 (England - Championship)",
        "E2": "E2 (England - League One)",
        "E3": "E3 (England - League Two)",
        "EC": "EC (England - National League)",
        "SC0": "SC0 (Scotland - Premiership)",
        "SC1": "SC1 (Scotland - Championship)",
        "SC2": "SC2 (Scotland - League One)",
        "SC3": "SC3 (Scotland - League Two)",
        "D1": "D1 (Germany - Bundesliga)",
        "D2": "D2 (Germany - 2. Bundesliga)",
        "I1": "I1 (Italy - Serie A)",
        "I2": "I2 (Italy - Serie B)",
        "SP1": "SP1 (Spain - La Liga)",
        "SP2": "SP2 (Spain - Segunda Division)",
        "F1": "F1 (France - Ligue 1)",
        "F2": "F2 (France - Ligue 2)",
        "N1": "N1 (Netherlands - Eredivisie)",
        "B1": "B1 (Belgium - Jupiler Pro League)",
        "P1": "P1 (Portugal - Primeira Liga)",
        "T1": "T1 (Turkey - Super Lig)",
        "G1": "G1 (Greece - Super League)",
    }

    FILE_NAME_OF_EXTRA_LEAGUE: dict[str, str] = {
        "ARG": "ARG (Argentina - Primera Division)",
        "AUT": "AUT (Austria - Bundesliga)",
        "BRA": "BRA (Brazil - Serie A)",
        "CHN": "CHN (China - Super League)",
        "DNK": "DNK (Denmark - Superliga)",
        "FIN": "FIN (Finland - Veikkausliiga)",
        "IRL": "IRL (Ireland - Premier Division)",
        "JPN": "JPN (Japan - J1 League)",
        "MEX": "MEX (Mexico - Liga MX)",
        "NOR": "NOR (Norway - Eliteserien)",
        "POL": "POL (Poland - Ekstraklasa)",
        "ROU": "ROU (Romania - Liga I)",
        "RUS": "RUS (Russia - Premier League)",
        "SWE": "SWE (Sweden - Allsvenskan)",
        "SWZ": "SWZ (Switzerland - Super League)",
        "USA": "USA (USA - MLS)",
    }


class FootyStatsSource:
    """FootyStats serves tournament match and player files without a login.

    The competition identifiers come from the official league-list endpoint and
    were checked against the content, that is match count, date range and odds
    columns. The same identifiers serve both the odds file and the player file.
    """

    MATCH_DOWNLOAD_BASE_URL: str = "https://footystats.org/c-dl.php?type=matches&comp="
    PLAYER_DOWNLOAD_BASE_URL: str = "https://footystats.org/c-dl.php?type=players&comp="
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS

    MATCH_ODDS_OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Tournament Odds (FootyStats)"
    )
    PLAYER_LIST_OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Tournament Squads (FootyStats)"
    )
    MATCH_ODDS_HEADER_MARKER: bytes = b"odds_ft_home_team_win"
    PLAYER_LIST_HEADER_MARKER: bytes = b"full_name"
    HEADER_SEARCH_LENGTH_IN_BYTES: int = 2000

    COMPETITION_IDENTIFIER_OF_TOURNAMENT: dict[str, int] = {
        "World Cup 2014": 1384,
        "World Cup 2018": 1425,
        "World Cup 2022": 7432,
        "Euro 2016": 1400,
        "Euro 2020 (EM 2021)": 5635,
        "Euro 2024": 11084,
        "Copa America 2019": 1956,
        "Copa America 2021": 5862,
        "Copa America 2024": 12076,
    }


class FootyStatsInternationalSource:
    """Every senior national team competition FootyStats knows, all seasons.

    Unlike club leagues these are downloadable without a login. The list holds
    about 67 competitions with 188 seasons, among them international friendlies
    2015-2026, every World Cup qualification, the Nations League and the Africa
    Cup of Nations.

    Left out are the youth and women competitions, and the club competitions
    that also carry the International label, such as the Club World Cup or the
    CONCACAF Champions League.
    """

    LEAGUE_LIST_URL: str = "https://api.football-data-api.com/league-list?key=example"
    MATCH_DOWNLOAD_BASE_URL: str = "https://footystats.org/c-dl.php?type=matches&comp="
    OUTPUT_ROOT: Path = (
        ProjectPath.DATA_ROOT / "International Matches & Odds (FootyStats)"
    )
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.STANDARD_TIMEOUT_IN_SECONDS
    POLITE_DELAY_IN_SECONDS: float = 1.2

    NAME_PREFIX: str = "International "
    HEADER_MARKER: bytes = b"timestamp"
    HEADER_SEARCH_LENGTH_IN_BYTES: int = 200
    LONG_SEASON_YEAR_LENGTH: int = 8

    EXCLUDED_NAME_PARTS: tuple[str, ...] = (
        "Women",
        "WU",
        "U17",
        "U19",
        "U20",
        "U21",
        "U23",
        "Youth",
        "Club",
        "Champions League",
        "Champions Cup",
    )


class StatsBombSource:
    """StatsBomb open data on GitHub: full event data for the big tournaments.

    The competition and season identifiers are taken from competitions.json of
    the open data repository.

    Period 1 and 2 are the ninety minutes, 3 and 4 the extra time. Period 5 is
    the penalty shootout and is always left out, because a shootout penalty is
    worth about 0.78 expected goals and would distort the match total.
    """

    BASE_URL: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.STANDARD_TIMEOUT_IN_SECONDS
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "xG Tournament Data (StatsBomb Open Data)"
    )
    LINEUP_OUTPUT_FILE_NAME: str = "lineups_bench.csv"

    TOURNAMENT_IDENTIFIER: dict[str, tuple[int, int]] = {
        "World Cup 2018": (43, 3),
        "World Cup 2022": (43, 106),
        "Euro 2020 (EM 2021)": (55, 43),
        "Euro 2024": (55, 282),
        "Copa America 2024": (223, 282),
    }

    SHOT_EVENT_NAME: str = "Shot"
    ON_TARGET_OUTCOME_NAMES: tuple[str, ...] = ("Goal", "Saved", "Saved To Post")
    LAST_REGULAR_PERIOD: int = 2
    LAST_EXTRA_TIME_PERIOD: int = 4
    FIRST_PERIOD: int = 1
    PROGRESS_REPORT_EVERY_N_MATCHES: int = 16

    STARTING_ELEVEN_REASON: str = "Starting XI"
    STARTER_ROLE: str = "starter"
    USED_SUBSTITUTE_ROLE: str = "sub_used"
    UNUSED_BENCH_ROLE: str = "bench_unused"
    MATCH_START_MINUTE: str = "0"

    EXPECTED_GOALS_COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "match_date",
        "stage",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "home_xg_90",
        "away_xg_90",
        "home_xg",
        "away_xg",
        "home_shots",
        "away_shots",
        "home_shots_on_target",
        "away_shots_on_target",
        "referee",
        "stadium",
        "kick_off",
    )
    LINEUP_COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "match_id",
        "match_date",
        "team",
        "player",
        "jersey",
        "role",
        "position",
        "minute_on",
        "minute_off",
    )


class WikipediaSource:
    """Wikipedia serves the raw wikitext of a page over its parse endpoint."""

    API_BASE_URL: str = (
        "https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext"
        "&format=json&formatversion=2&page="
    )
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.STANDARD_TIMEOUT_IN_SECONDS


class WikipediaSquadSource:
    """The squads pages list every player as a structured template.

    The template holds shirt number, position, name, date of birth, caps, goals,
    club and the country of the club. This is the reliable source for club
    chemistry and the share of players abroad, because the FootyStats player
    lists name the national team as the current club.
    """

    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Tournament Squads (Wikipedia)"

    PAGE_TITLE_OF_TOURNAMENT: dict[str, str] = {
        "World Cup 2014": "2014 FIFA World Cup squads",
        "World Cup 2018": "2018 FIFA World Cup squads",
        "World Cup 2022": "2022 FIFA World Cup squads",
        "World Cup 2026": "2026 FIFA World Cup squads",
        "Euro 2016": "UEFA Euro 2016 squads",
        "Euro 2020 (EM 2021)": "UEFA Euro 2020 squads",
        "Euro 2024": "UEFA Euro 2024 squads",
        "Copa America 2019": "2019 Copa América squads",
        "Copa America 2021": "2021 Copa América squads",
        "Copa America 2024": "2024 Copa América squads",
    }

    COLUMN_NAMES: tuple[str, ...] = (
        "group",
        "team",
        "number",
        "position",
        "name",
        "date_of_birth",
        "caps",
        "goals",
        "club",
        "club_country",
    )

    PLAYER_TEMPLATE_PATTERN: str = (
        r"\{\{\s*(?:nat fs (?:g )?player|national football squad player)"
    )
    WIKI_LINK_PATTERN: str = r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]"
    GROUP_HEADING_PATTERN: str = r"^==\s*(Group [A-L])\s*==\s*$"
    TEAM_HEADING_PATTERN: str = r"^===\s*([^=]+?)\s*===\s*$"
    NAME_PATTERN: str = r"\|\s*name\s*=\s*(.*?)\s*\|\s*age\s*="
    AGE_SEGMENT_PATTERN: str = r"\|\s*age\s*=\s*(\{\{[^{}]*\}\})"
    DATE_TRIPLE_PATTERN: str = r"(\d{4})\|(\d{1,2})\|(\d{1,2})"
    CLUB_PATTERN: str = r"\|\s*club\s*=\s*(\[\[[^\]]*\]\]|[^|\n}]+)"

    PATTERN_OF_SIMPLE_FIELD: dict[str, str] = {
        "number": r"\|\s*no\s*=\s*(\d+)",
        "position": r"\|\s*pos\s*=\s*([A-Z]{2})",
        "caps": r"\|\s*caps\s*=\s*(\d+)",
        "goals": r"\|\s*goals\s*=\s*(\d+)",
        "club_country": r"\|\s*clubnat\s*=\s*([A-Za-z]{3})",
    }


class WikipediaBaseCampSource:
    """The section "Team base camps" names the training quarter of every team.

    This is the base for a realistic travel model, that is base camp to venue
    and back, instead of stadium to stadium.

    The table gives one line per team that holds its three letter FIFA code,
    written as {{#invoke:flagg|...|ALG|avar=fb}}, followed by two cell lines
    with the hotel and the training ground.
    """

    PAGE_TITLE: str = "2026 FIFA World Cup"
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT / "World Cup 2026 (FootyStats)" / "base_camps.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = ("team_code", "accommodation", "training_site")

    SECTION_PATTERN: str = r"==+\s*Team base camps\s*==+(.*?)(?:\n==[^=])"
    WIKI_LINK_PATTERN: str = r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]"
    REFERENCE_PATTERN: str = r"<ref[^>]*/>|<ref[^>]*>.*?</ref>"
    TEMPLATE_PATTERN: str = r"\{\{[^{}]*\}\}"
    TEAM_CODE_PATTERN: str = r"\{\{#invoke:flagg\|[^}]*?\|([A-Z]{3})\b"
    CELL_TRIM_CHARACTERS: str = " |–-–"
    TABLE_ROW_MARKERS: tuple[str, ...] = ("|-", "|}")
    CELL_MARKER: str = "|"


class OpenLigaDatabaseSource:
    """OpenLigaDB serves both German Bundesliga divisions without a key.

    It carries the final score, the half time score and every goal with scorer,
    minute, penalty flag and own goal flag. That is what football-data.co.uk
    does not have. Coverage is complete from 2010 onwards.
    """

    API_URL_TEMPLATE: str = (
        "https://api.openligadb.de/getmatchdata/{league_code}/{season_start_year}"
    )
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS
    POLITE_DELAY_IN_SECONDS: float = 0.4
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Bundesliga Detail (OpenLigaDB)"
    MATCH_FILE_NAME: str = "bundesliga_matches.csv"
    GOAL_FILE_NAME: str = "bundesliga_goals.csv"

    LEAGUE_CODES: tuple[str, ...] = ("bl1", "bl2")
    FIRST_SEASON_START_YEAR: int = 2010
    LAST_SEASON_START_YEAR: int = 2025
    FINAL_SCORE_RESULT_NAME: str = "Endergebnis"

    MATCH_COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "league",
        "season",
        "matchday",
        "date_utc",
        "home_team",
        "away_team",
        "home_goals",
        "away_goals",
        "finished",
    )
    GOAL_COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "minute",
        "scorer",
        "score_home",
        "score_away",
        "is_penalty",
        "is_own_goal",
    )


class CsvFileSetting:
    """How every CSV file the project writes is opened.

    Attributes:
        IGNORE_BROKEN_CHARACTERS: The Wyscout event files carry a few bytes
            that are not valid UTF-8, and one of them must not stop a run over
            millions of rows.
        WIDEST_ROW_TO_EXPECT: How many fields a row may have before a reader
            gives up on it. Some football-data files carry a stray extra
            field in a row, and the widest of them holds 76.
    """

    ENCODING: str = "utf-8"
    NEW_LINE: str = ""
    WRITE_MODE: str = "w"
    APPEND_MODE: str = "a"
    READ_MODE: str = "r"
    IGNORE_BROKEN_CHARACTERS: str = "ignore"
    LINE_TERMINATOR: str = "\r\n"
    WIDEST_ROW_TO_EXPECT: int = 512


class InternationalResultSource:
    """The Kaggle file with every international match since 1872.

    The neutral column says whether the venue was neutral, so the text FALSE
    means the team named first really played at home.
    """

    RESULT_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "International football results from 1872 to 2026"
        / "results.csv"
    )
    CITY_COLUMN: str = "city"
    COUNTRY_COLUMN: str = "country"
    DATE_COLUMN: str = "date"
    TOURNAMENT_COLUMN: str = "tournament"
    HOME_TEAM_COLUMN: str = "home_team"
    AWAY_TEAM_COLUMN: str = "away_team"
    NEUTRAL_VENUE_COLUMN: str = "neutral"
    NOT_NEUTRAL_TEXT: str = "FALSE"
    HOME_SCORE_COLUMN: str = "home_score"
    AWAY_SCORE_COLUMN: str = "away_score"
    SHOOTOUT_FILE: Path = RESULT_FILE.parent / "shootouts.csv"
    SHOOTOUT_WINNER_COLUMN: str = "winner"


class CanonicalMatchDataset:
    """Every international in the one schema the models are trained on.

    The results file is the backbone of the project: every international
    since 1872, and at the front the fixtures of the next tournament. A
    fixture carries the text NA where a score belongs, which no reader may
    mistake for a played match, so the two are written into two files.

    The score of the source is the one the match ended on, extra time
    included. What the score was after ninety minutes is not in any source,
    so it is only known for a match that could not have gone to extra time.
    Every match that went to a shootout says so through its flag.

    Attributes:
        UNPLAYED_SCORE_TEXT: What the source writes where a fixture has no
            score yet. It is not an empty cell, so a plain emptiness check
            reads a fixture as a played match that ended nil nil.
        STAGE_TOLERANCE_IN_DAYS: The tournament files date a match by its
            kick off in UTC, the results file by the local day, which pulls a
            late kick off in the Americas one day apart.
        MAJOR_TOURNAMENT_NAMES: The competitions a World Cup model can learn
            from. The other 190 in the file are regional cups and islands
            games, which say little about a World Cup.
    """

    OUTPUT_FILE: Path = ProjectPath.CANONICAL_ROOT / "canonical_matches.csv"
    FIXTURE_OUTPUT_FILE: Path = ProjectPath.CANONICAL_ROOT / "canonical_fixtures.csv"
    PROBLEM_OUTPUT_FILE: Path = ProjectPath.CANONICAL_ROOT / "canonical_problems.csv"

    COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "match_date",
        "home_team_name",
        "home_team_is_host",
        "away_team_name",
        "away_team_is_host",
        "home_goals_regular_time",
        "away_goals_regular_time",
        "home_goals_final",
        "away_goals_final",
        "is_regular_time_score_reconstructed_unreliable",
        "is_neutral_venue",
        "tournament_name",
        "tournament_stage",
        "competition_category",
        "city",
        "country",
        "home_shootout_goals",
        "away_shootout_goals",
        "shootout_winner",
    )
    FIXTURE_COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "match_date",
        "home_team_name",
        "home_team_is_host",
        "away_team_name",
        "away_team_is_host",
        "is_neutral_venue",
        "tournament_name",
        "tournament_stage",
        "competition_category",
        "city",
        "country",
    )
    PROBLEM_COLUMN_NAMES: tuple[str, ...] = ("match_id", "problem")

    UNPLAYED_SCORE_TEXT: str = "NA"
    MATCH_IDENTIFIER_SEPARATOR: str = "|"
    REPEATED_IDENTIFIER_SEPARATOR: str = "#"

    STAGE_SOURCE_FOLDER: Path = StatsBombSource.OUTPUT_FOLDER
    STAGE_SOURCE_PATTERN: str = "*.csv"
    STAGE_COLUMN: str = "stage"
    STAGE_DATE_COLUMN: str = "match_date"
    STAGE_TOLERANCE_IN_DAYS: int = 1
    UNKNOWN_STAGE: str = "unknown"

    FRIENDLY_CATEGORY: str = "friendly"
    QUALIFICATION_CATEGORY: str = "qualification"
    MAJOR_TOURNAMENT_CATEGORY: str = "major_tournament"
    NATIONS_LEAGUE_CATEGORY: str = "nations_league"
    OTHER_TOURNAMENT_CATEGORY: str = "other_tournament"

    FRIENDLY_TOURNAMENT_NAME: str = "Friendly"
    QUALIFICATION_MARKER: str = "qualification"
    NATIONS_LEAGUE_MARKER: str = "Nations League"
    MAJOR_TOURNAMENT_NAMES: frozenset[str] = frozenset(
        {
            "FIFA World Cup",
            "UEFA Euro",
            "Copa América",
            "African Cup of Nations",
            "AFC Asian Cup",
            "Gold Cup",
            "Oceania Nations Cup",
            "Confederations Cup",
        }
    )


class GeographySetting:
    """What the project needs to measure a distance on the globe."""

    EARTH_RADIUS_IN_KILOMETRES: float = 6371.0
    DEGREES_PER_TIME_ZONE: float = 15.0


class ComputedFeaturePath:
    """Files that the project computes itself and reads again later."""

    FOLDER: Path = ProjectPath.DATA_ROOT / "Computed Features"
    CITY_GEOCODE_FILE: Path = FOLDER / "match_city_geocodes.csv"
    COUNTRY_CLIMATE_FILE: Path = FOLDER / "country_climate.csv"
    VENUE_ELEVATION_FILE: Path = FOLDER / "venue_country_elevations.csv"
    WORLD_BANK_FILE: Path = FOLDER / "worldbank_population_gdp.csv"


class WorldCupTeamListSource:
    """The list of the 48 teams of the 2026 World Cup, as FootyStats writes it.

    FootyStats appends "National Team" or "Men's National Team" to every name,
    which has to come off before the name can be used in a search query or a
    Wikipedia article title.
    """

    TEAM_FILE: Path = (
        ProjectPath.DATA_ROOT / "World Cup 2026 (FootyStats)" / "teams.csv"
    )
    TEAM_NAME_COLUMN: str = "team_name"
    NATIONAL_TEAM_SUFFIX_PATTERN: str = r"\s+(?:Men'?s\s+)?National\s+Team$"


class OpenMeteoSource:
    """Open-Meteo answers geocoding, weather and elevation without a key."""

    GEOCODING_URL: str = "https://geocoding-api.open-meteo.com/v1/search"
    WEATHER_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
    WEATHER_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"
    ELEVATION_URL: str = "https://api.open-meteo.com/v1/elevation"
    TIMEOUT_IN_SECONDS: int = 30
    POLITE_DELAY_IN_SECONDS: float = 0.15


class CityGeocodeSource:
    """Every venue of the training data is turned into coordinates and a timezone.

    About 2200 unique city and country pairs come out of 49400 international
    matches. With coordinates and timezone the travel distance, the timezone
    jump, the elevation and the climate can be computed for the whole training
    set, not only for the tournament matches.
    """

    OUTPUT_FILE: Path = ComputedFeaturePath.CITY_GEOCODE_FILE
    CANDIDATE_COUNT: int = 5
    COLUMN_NAMES: tuple[str, ...] = (
        "city",
        "country",
        "latitude",
        "longitude",
        "timezone",
        "resolved_name",
        "resolved_country",
    )
    PROGRESS_REPORT_EVERY_N_CITIES: int = 250


class ElevationSource:
    """Elevation is a physiology factor the market hardly prices.

    Estadio Azteca sits at 2240 metres. A team from the lowlands measurably
    loses performance there, while a team used to altitude, such as Bolivia,
    Ecuador or Mexico, gains. The feature is the elevation difference between
    the venue and home. The endpoint takes coordinates in batches.
    """

    OUTPUT_FILE: Path = ComputedFeaturePath.VENUE_ELEVATION_FILE
    BATCH_SIZE: int = 90
    WORLD_CUP_VENUE_KIND: str = "venue_wc2026"
    HISTORICAL_VENUE_KIND: str = "venue_historical"
    COUNTRY_REFERENCE_KIND: str = "country_reference"
    COLUMN_NAMES: tuple[str, ...] = (
        "kind",
        "name",
        "place",
        "latitude",
        "longitude",
        "elevation_m",
    )

    PLACE_OF_WORLD_CUP_2026_VENUE: dict[str, tuple[str, float, float]] = {
        "MetLife Stadium": ("East Rutherford", 40.81, -74.07),
        "AT&T Stadium": ("Arlington TX", 32.75, -97.09),
        "Arrowhead Stadium": ("Kansas City", 39.05, -94.48),
        "NRG Stadium": ("Houston", 29.68, -95.41),
        "Mercedes-Benz Stadium": ("Atlanta", 33.76, -84.40),
        "Hard Rock Stadium": ("Miami", 25.96, -80.24),
        "Lincoln Financial Field": ("Philadelphia", 39.90, -75.17),
        "Lumen Field": ("Seattle", 47.60, -122.33),
        "Levi's Stadium": ("Santa Clara", 37.40, -121.97),
        "SoFi Stadium": ("Inglewood", 33.95, -118.34),
        "Gillette Stadium": ("Foxborough", 42.09, -71.26),
        "BMO Field": ("Toronto", 43.63, -79.42),
        "BC Place Stadium": ("Vancouver", 49.28, -123.11),
        "Estadio Azteca": ("Mexico City", 19.30, -99.15),
        "Estadio AKRON": ("Guadalajara", 20.68, -103.46),
        "Estadio BBVA Bancomer": ("Monterrey", 25.67, -100.24),
    }


class MatchWeatherSource:
    """Kick off weather of every tournament match, out of the Open-Meteo archive.

    The stadium name of the StatsBomb match files is matched against the table
    below by substring, so the order matters and the more specific key has to
    come first. Every stadium of the 2022 World Cup maps to Doha, because
    Qatar is one single climate.

    The table runs World Cup 2022, World Cup 2018, Euro 2021, Euro 2024 and
    Copa America 2024, in that order.
    """

    SOURCE_FOLDER: Path = StatsBombSource.OUTPUT_FOLDER
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "Match Weather (Open-Meteo)"
        / "tournament_match_weather.csv"
    )
    HOURLY_VARIABLES: str = "temperature_2m,relative_humidity_2m,apparent_temperature"
    TEMPERATURE_VARIABLE: str = "temperature_2m"
    APPARENT_TEMPERATURE_VARIABLE: str = "apparent_temperature"
    HUMIDITY_VARIABLE: str = "relative_humidity_2m"
    FALLBACK_KICK_OFF_HOUR: int = 15
    FIRST_HOUR_OF_DAY: int = 0
    LAST_HOUR_OF_DAY: int = 23
    HOURS_PER_DAY: int = 24

    COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "match_id",
        "match_date",
        "kick_off_local",
        "stadium",
        "city",
        "latitude",
        "longitude",
        "temperature_c",
        "apparent_temperature_c",
        "relative_humidity_pct",
    )

    PLACE_OF_STADIUM_NAME_PART: dict[str, tuple[str, float, float]] = {
        "ahmad bin ali": ("Doha", 25.29, 51.53),
        "al bayt": ("Doha", 25.29, 51.53),
        "al janoub": ("Doha", 25.29, 51.53),
        "al thumama": ("Doha", 25.29, 51.53),
        "education city": ("Doha", 25.29, 51.53),
        "khalifa international": ("Doha", 25.29, 51.53),
        "lusail": ("Doha", 25.29, 51.53),
        "stadium 974": ("Doha", 25.29, 51.53),
        "ak bars": ("Kazan", 55.80, 49.11),
        "ekaterinburg": ("Yekaterinburg", 56.84, 60.61),
        "mordovia": ("Saransk", 54.18, 45.18),
        "fisht": ("Sochi", 43.60, 39.73),
        "otkritie": ("Moscow", 55.75, 37.62),
        "luzhniki": ("Moscow", 55.75, 37.62),
        "rostec": ("Kaliningrad", 54.71, 20.45),
        "rostov": ("Rostov-on-Don", 47.24, 39.71),
        "saint-petersburg": ("Saint Petersburg", 59.94, 30.31),
        "solidarnost": ("Samara", 53.20, 50.15),
        "nizhny novgorod": ("Nizhny Novgorod", 56.33, 44.00),
        "volgograd": ("Volgograd", 48.71, 44.51),
        "allianz": ("Munich", 48.14, 11.58),
        "nationala": ("Bucharest", 44.43, 26.10),
        "baki olimpiya": ("Baku", 40.41, 49.87),
        "cartuja": ("Seville", 37.39, -5.99),
        "estadio olimpico": ("Rome", 41.90, 12.50),
        "hampden": ("Glasgow", 55.86, -4.25),
        "cruijff": ("Amsterdam", 52.37, 4.90),
        "parken": ("Copenhagen", 55.68, 12.57),
        "puskas": ("Budapest", 47.50, 19.04),
        "wembley": ("London", 51.51, -0.13),
        "olympiastadion": ("Berlin", 52.52, 13.40),
        "deutsche bank": ("Frankfurt", 50.11, 8.68),
        "merkur": ("Duesseldorf", 51.23, 6.78),
        "mhparena": ("Stuttgart", 48.78, 9.18),
        "trainingszentrum rb leipzig": ("Leipzig", 51.34, 12.37),
        "red bull arena": ("Leipzig", 51.34, 12.37),
        "rheinenergie": ("Cologne", 50.94, 6.96),
        "signal": ("Dortmund", 51.51, 7.47),
        "veltins": ("Gelsenkirchen", 51.52, 7.10),
        "volksparkstadion": ("Hamburg", 53.55, 9.99),
        "at&t": ("Arlington TX", 32.74, -97.11),
        "allegiant": ("Las Vegas", 36.17, -115.14),
        "arrowhead": ("Kansas City", 39.10, -94.58),
        "mercy park": ("Kansas City", 39.10, -94.58),
        "bank of america": ("Charlotte", 35.23, -80.84),
        "hard rock": ("Miami", 25.96, -80.24),
        "inter&co": ("Orlando", 28.54, -81.38),
        "levi": ("Santa Clara", 37.35, -121.96),
        "mercedes-benz": ("Atlanta", 33.75, -84.39),
        "metlife": ("East Rutherford", 40.81, -74.07),
        "nrg": ("Houston", 29.76, -95.36),
        "q2": ("Austin", 30.27, -97.74),
        "sofi": ("Inglewood", 33.96, -118.34),
        "state farm": ("Glendale AZ", 33.54, -112.19),
    }


class ClubEloSource:
    """Club Elo rates club strength day by day, back to the 1940s.

    It serves as context for player profiles, that is the quality of the club
    a player abroad plays in. One snapshot per year on the first of June holds
    about 630 clubs.
    """

    API_BASE_URL: str = "http://api.clubelo.com/"
    FIRST_SNAPSHOT_YEAR: int = 2000
    SNAPSHOT_MONTH_AND_DAY: str = "06-01"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Club Elo (clubelo.com)"
    FILE_NAME_TEMPLATE: str = "clubelo_{snapshot_day}.csv"
    CSV_HEADER_MARKER: bytes = b"Rank,"


class NationalEloSource:
    """The live rating table of eloratings.net, for the tournament itself.

    The historical dataset ends in 2025, so during the 2026 World Cup this
    snapshot is written before every match day and can be stored with its date.
    """

    RATING_URL: str = "https://eloratings.net/World.tsv"
    TEAM_NAME_URL: str = "https://eloratings.net/en.teams.tsv"
    TIMEOUT_IN_SECONDS: int = 30
    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT
        / "International Football Elo Ratings (1872-2025)"
        / "current"
    )
    FILE_NAME_TEMPLATE: str = "elo_{today}.csv"
    COLUMN_SEPARATOR: str = "\t"
    SMALLEST_USABLE_NAME_ROW: int = 2
    SMALLEST_USABLE_RATING_ROW: int = 4
    COLUMN_NAMES: tuple[str, ...] = ("rank", "team_code", "team_name", "elo")


class WorldBankSource:
    """Population and economic power explain part of national team success.

    These are the classic talent pool covariates of the tournament forecasting
    literature (Bernard and Busse 2004). Yearly values from 2000 until today
    for every country.
    """

    API_URL_TEMPLATE: str = (
        "https://api.worldbank.org/v2/country/all/indicator/{indicator_code}"
        "?format=json&per_page=20000&date=2000:2026"
    )
    TIMEOUT_IN_SECONDS: int = 120
    OUTPUT_FILE: Path = ComputedFeaturePath.WORLD_BANK_FILE
    POPULATION_INDICATOR_CODE: str = "SP.POP.TOTL"
    GROSS_DOMESTIC_PRODUCT_INDICATOR_CODE: str = "NY.GDP.MKTP.CD"
    VALUE_SERIES_POSITION: int = 1
    COLUMN_NAMES: tuple[str, ...] = ("country", "year", "population", "gdp_usd")


class NewsToneSource:
    """News volume and news tone per team, out of the GDELT index.

    A negative tone spike around a national team, such as an association
    crisis, a scandal or a sacked coach, is a signal outside the betting
    markets. The endpoint allows one request every five seconds.
    """

    API_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    TIME_SPAN: str = "12months"
    QUERY_TEMPLATE: str = '"{team_name} national team" sourcelang:eng'
    VOLUME_MODE: str = "timelinevolraw"
    TONE_MODE: str = "timelinetone"
    RATE_LIMIT_IN_SECONDS: float = 5.2
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "Alternative Data (GDELT News Tone)"
        / "gdelt_news_teams.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = ("team", "date", "article_volume", "avg_tone")
    JSON_FIRST_CHARACTERS: tuple[bytes, ...] = (b"{", b"[")
    DATE_LENGTH: int = 8


class RedditActivitySource:
    """Attention of the r/soccer crowd per team, out of the PullPush archive.

    Live data is not reachable without a key, because reddit.com blocks
    anonymous searches with HTTP 403 and the free PullPush archive lags months
    behind. For live attention the Wikipedia pageviews are used instead.

    The counted window runs from the opening to the final of the 2022 World
    Cup, both days included.
    """

    API_URL: str = "https://api.pullpush.io/reddit/search/submission/"
    SUBREDDIT: str = "soccer"
    WINDOW_START_AT_THE_2022_OPENING: str = "2022-11-20"
    WINDOW_END_AT_THE_2022_FINAL: str = "2022-12-18"
    LARGEST_PAGE_SIZE_THE_ARCHIVE_ALLOWS: int = 100
    SECONDS_PER_DAY: int = 86400
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.SHORT_TIMEOUT_IN_SECONDS
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT / "Alternative Data (Reddit)" / "reddit_activity_log.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "fetched_at_utc",
        "team",
        "window_start",
        "window_end",
        "n_submissions",
        "avg_score",
        "max_score",
    )


class WikipediaPageviewSource:
    """Daily article views are an attention index.

    A spike on a player article marks an injury, a ban, a form hype or a
    scandal, often before the odds price it in. Team series start in 2018 for
    the backtest history. The player articles are read straight out of the
    wikitext of the squads page, so no name guessing is needed.

    The endpoint throttles hard, it answers 429 at about four requests per
    second over a longer run, which is why the polite delay is a whole second.
    FootyStats also writes a few country names differently than Wikipedia
    titles them, so those get an override.
    """

    PAGEVIEW_URL_TEMPLATE: str = (
        "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
        "en.wikipedia/all-access/user/{article}/daily/{start_day}/{end_day}"
    )
    SQUAD_PAGE_TITLE: str = "2026 FIFA World Cup squads"
    TIMEOUT_IN_SECONDS: int = 30
    POLITE_DELAY_IN_SECONDS: float = 1.0
    BACKOFF_IN_SECONDS: float = 10.0

    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Alternative Data (Wikipedia Pageviews)"
    )
    TEAM_OUTPUT_FILE_NAME: str = "wikipedia_pageviews_teams.csv"
    PLAYER_OUTPUT_FILE_NAME: str = "wikipedia_pageviews_players.csv"
    TEAM_SERIES_START_DAY: str = "20180101"
    PLAYER_SERIES_START_DAY: str = "20250101"
    DAY_FORMAT: str = "%Y%m%d"
    ARTICLE_TITLE_TEMPLATE: str = "{team_name} national football team"
    COLUMN_NAMES: tuple[str, ...] = ("team", "article", "date", "views")
    TEAM_KEY_COLUMN: str = "team"
    ARTICLE_KEY_COLUMN: str = "article"
    PROGRESS_REPORT_EVERY_N_PLAYERS: int = 100

    TEAM_HEADING_PATTERN: str = r"^===\s*([^=]+?)\s*===\s*$"
    PLAYER_ARTICLE_PATTERN: str = r"\|\s*name\s*=\s*\[\[([^|\]]+)"

    ARTICLE_TITLE_OVERRIDES: dict[str, str] = {
        "United States": "United States men's national soccer team",
        "USA": "United States men's national soccer team",
        "Iran": "Iran national football team",
        "Ireland": "Republic of Ireland national football team",
        "Bosnia Herzegovina": "Bosnia and Herzegovina national football team",
    }


class CoachHistorySource:
    """Wikidata keeps the head coach of every national team with start and end.

    That is the cleanest free source for coach features: time in office at the
    start of a tournament, how often the coach changed, and caretaker spells.
    The team identifiers are resolved over the Wikipedia articles, after that
    one single query returns every coach of every team.

    In the query, P286 is the head coach, P580 the start date and P582 the end
    date.
    """

    WIKIPEDIA_API_URL: str = "https://en.wikipedia.org/w/api.php"
    SPARQL_URL: str = "https://query.wikidata.org/sparql"
    TIMEOUT_IN_SECONDS: int = 90
    LARGEST_TITLE_BATCH_THE_ENDPOINT_TAKES: int = 50
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT / "Tournament Squads (Wikipedia)" / "coach_history.csv"
    )
    ARTICLE_TITLE_TEMPLATE: str = "{country} national football team"
    DATE_LENGTH: int = 10
    COLUMN_NAMES: tuple[str, ...] = ("team", "coach", "start_date", "end_date")
    REPORTED_MISSING_COUNTRY_COUNT: int = 8

    ARTICLE_TITLE_OVERRIDES: dict[str, str] = {
        "United States": "United States men's national soccer team",
        "Ireland": "Republic of Ireland national football team",
    }

    SPARQL_QUERY_TEMPLATE: str = """SELECT ?team ?coachLabel ?start ?end WHERE {{
      VALUES ?team {{ {team_identifiers} }}
      ?team p:P286 ?statement.
      ?statement ps:P286 ?coach.
      OPTIONAL {{ ?statement pq:P580 ?start. }}
      OPTIONAL {{ ?statement pq:P582 ?end. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""


class LiveOddsSource:
    """Live odds of The Odds API, logged in a way that cannot be rewritten.

    Every run stores the raw answer as a time stamped JSON file and appends the
    1X2 odds to an append only log. The key is free at the-odds-api.com and
    belongs in an environment variable, never in the code or in git.

    Before the tournament starts, check the sport key with the sports mode,
    the endpoint renames a competition now and then.
    """

    BASE_URL: str = "https://api.the-odds-api.com/v4"
    API_KEY_ENVIRONMENT_VARIABLE: str = "THE_ODDS_API_KEY"
    TIMEOUT_IN_SECONDS: int = 30

    SPORT_KEY: str = "soccer_fifa_world_cup"
    REGIONS: str = "eu"
    MARKETS: str = "h2h"
    ODDS_FORMAT: str = "decimal"
    DRAW_OUTCOME_NAME: str = "Draw"
    SOCCER_KEY_PREFIX: str = "soccer"

    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Live Odds Snapshots (The Odds API)"
    RAW_SUBFOLDER_NAME: str = "raw"
    LOG_FILE_NAME: str = "odds_log.csv"
    RAW_FILE_NAME_TEMPLATE: str = "odds_{sport_key}_{stamp}.json"
    COLUMN_NAMES: tuple[str, ...] = (
        "fetched_at_utc",
        "sport_key",
        "kickoff_utc",
        "home_team",
        "away_team",
        "bookmaker",
        "odds_home",
        "odds_draw",
        "odds_away",
    )
    SPORTS_MODE: str = "sports"
    ODDS_MODE: str = "odds"


class PredictionMarketSource:
    """Prediction market prices are a crowd forecast outside the bookmakers.

    They serve as a benchmark and as a divergence signal, market against crowd.
    Every run appends a time stamped snapshot to an append only log. Free, no
    key needed.
    """

    POLYMARKET_SEARCH_URL: str = "https://gamma-api.polymarket.com/public-search?q="
    MANIFOLD_SEARCH_URL: str = "https://api.manifold.markets/v0/search-markets?term="
    MANIFOLD_LIMIT_PARAMETER: str = "&limit=50"
    SEARCH_TERMS: tuple[str, ...] = ("World Cup 2026", "2026 FIFA World Cup")
    TITLE_FILTER: str = "world cup"
    TIMEOUT_IN_SECONDS: int = 30
    POLITE_DELAY_IN_SECONDS: float = 0.5
    POLYMARKET_NAME: str = "polymarket"
    MANIFOLD_NAME: str = "manifold"
    MANIFOLD_OUTCOME_NAME: str = "YES"
    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "Alternative Data (Prediction Markets)"
        / "prediction_markets_log.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "fetched_at_utc",
        "source",
        "event",
        "question",
        "outcome",
        "price_or_prob",
        "volume",
    )


class PrematchSource:
    """Everything the system needs shortly before kick off, for one match day.

    That is the confirmed line-ups with formation and coach, the injuries and
    bans per team, and the weather at kick off. Odds are deliberately not part
    of this, LiveOddsSource covers them.

    API-Football needs a free key, its free tier allows 100 requests a day,
    which is enough for one World Cup match day.
    """

    API_BASE_URL: str = "https://v3.football.api-sports.io"
    API_KEY_ENVIRONMENT_VARIABLE: str = "API_FOOTBALL_KEY"
    API_KEY_FILE: Path = ProjectPath.DATA_ROOT / "Live" / "api_football_key.txt"
    API_KEY_HEADER_NAME: str = "x-apisports-key"
    LEAGUE_ENVIRONMENT_VARIABLE: str = "API_FOOTBALL_LEAGUE"
    SEASON_ENVIRONMENT_VARIABLE: str = "API_FOOTBALL_SEASON"
    WORLD_CUP_LEAGUE_IDENTIFIER: str = "1"
    DEFAULT_SEASON: str = "2026"

    FIXTURE_PATH: str = "fixtures"
    LINEUP_PATH: str = "fixtures/lineups"
    INJURY_PATH: str = "injuries"

    TIMEOUT_IN_SECONDS: int = 30
    OUTPUT_FOLDER: Path = ProjectPath.DATA_ROOT / "Live"
    SNAPSHOT_FILE_NAME_TEMPLATE: str = "prematch_{match_day}.json"
    LINEUP_FILE_NAME_TEMPLATE: str = "prematch_lineups_{match_day}.csv"
    INJURY_FILE_NAME_TEMPLATE: str = "prematch_injuries_{match_day}.csv"

    STARTER_ROLE: str = "start"
    SUBSTITUTE_ROLE: str = "sub"
    HOURLY_VARIABLES: str = (
        "temperature_2m,precipitation,wind_speed_10m,relative_humidity_2m"
    )
    WEATHER_TIMEZONE: str = "UTC"
    HOUR_PREFIX_LENGTH: int = 13
    DAY_PREFIX_LENGTH: int = 10
    JSON_INDENT: int = 2

    LINEUP_COLUMN_NAMES: tuple[str, ...] = (
        "fixture_id",
        "kickoff",
        "team",
        "is_home",
        "formation",
        "coach",
        "role",
        "player",
        "number",
        "position",
    )
    INJURY_COLUMN_NAMES: tuple[str, ...] = (
        "fixture_id",
        "team",
        "player",
        "type",
        "reason",
    )


class TimeStampFormat:
    """How the project writes a point in time into a file.

    Every date the project writes is yyyy-mm-dd. The sources write theirs in
    three other ways, which is what the rest of this class is for.

    Attributes:
        LAST_CENTURY_FROM: The odds files reach back to 1993, so a two digit
            year of 90 or more belongs to the last century and anything below
            it to this one.
    """

    UTC_TIME_STAMP: str = "%Y-%m-%dT%H:%M:%SZ"
    ISO_DAY: str = "%Y-%m-%d"
    ISO_DAY_LENGTH: int = 10
    DASH: str = "-"
    SLASH: str = "/"
    LAST_CENTURY_FROM: int = 90
    MONTH_OF_ABBREVIATION: dict[str, int] = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }


class SquadFeatureCalculation:
    """Club chemistry and the share of players in the strong leagues.

    Club chemistry is the Herfindahl index over the clubs of a national squad.
    It shows a block, for example the Bayern block of 2014. The source is the
    Wikipedia squad list, which names the real club. The FootyStats squad list
    is useless here, because its current club is the national team itself.
    """

    SQUAD_FOLDER: Path = WikipediaSquadSource.OUTPUT_FOLDER
    OUTPUT_FILE: Path = ComputedFeaturePath.FOLDER / "club_chemistry_hhi.csv"
    TOP_FIVE_LEAGUE_CODES: frozenset[str] = frozenset(
        {"ENG", "ESP", "GER", "ITA", "FRA"}
    )
    SMALLEST_USABLE_SQUAD: int = 15
    INDEX_DECIMAL_PLACES: int = 4
    SHARE_DECIMAL_PLACES: int = 3

    TEAM_COLUMN: str = "team"
    CLUB_COLUMN: str = "club"
    CLUB_COUNTRY_COLUMN: str = "club_country"

    COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "team",
        "players",
        "clubs",
        "club_concentration",
        "biggest_club",
        "biggest_club_share",
        "top_five_league_share",
    )


class TravelLoadCalculation:
    """How far a team travelled between the matches of a historical tournament.

    The venue chain of every team comes out of the StatsBomb match files. Out
    of it come the kilometres since the last match, the running total, and the
    time zone shifts as a stand in for the body clock.
    """

    SOURCE_FOLDER: Path = StatsBombSource.OUTPUT_FOLDER
    OUTPUT_FILE: Path = ComputedFeaturePath.FOLDER / "travel_load.csv"
    STADIUM_COLUMN: str = "stadium"
    COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "team",
        "match_date",
        "city",
        "kilometres_since_last_match",
        "total_kilometres",
        "time_zone_shift_since_last_match",
        "total_time_zone_shifts",
    )


class WorldCupBurdenCalculation:
    """Travel, time zone and altitude load per team for the 2026 group stage.

    TravelLoadCalculation only covers the historical tournaments and knows
    nothing about altitude. This one builds the 2026 chain out of the 72 group
    matches, whose teams and venues are fixed after the draw, and adds the
    altitude of the venue, the altitude gained since the last match and the
    rest days in between.

    That makes the hidden unfairness of the schedule visible: which team
    crosses the continent, and which one plays in Mexico City at 2254 metres.
    """

    OUTPUT_FOLDER: Path = ProjectPath.CUSTOM_DATA_ROOT
    LEG_FILE_NAME: str = "wc2026_travel_altitude_legs.csv"
    SUMMARY_FILE_NAME: str = "wc2026_team_burden_summary.csv"

    TOURNAMENT_NAME: str = "FIFA World Cup"
    SEASON_PREFIX: str = "2026-"
    HIGH_ALTITUDE_IN_METRES: float = 1500.0
    NO_REST_DAYS_YET: str = ""

    LEG_COLUMN_NAMES: tuple[str, ...] = (
        "team",
        "match_number",
        "date",
        "opponent",
        "city",
        "is_host",
        "timezone",
        "altitude_m",
        "altitude_gain_since_last",
        "km_since_last",
        "cumulative_km",
        "tz_shift_since_last",
        "cumulative_tz_shifts",
        "days_rest",
    )
    SUMMARY_COLUMN_NAMES: tuple[str, ...] = (
        "team",
        "group_matches",
        "total_km",
        "total_tz_shifts",
        "max_altitude_m",
        "high_altitude_matches",
        "first_city",
        "last_city",
    )


class PitchGeometry:
    """The one pitch every source is converted onto, in metres.

    A source counts on its own pitch, StatsBomb on 120 by 80 for instance, so
    nothing can be compared until both are here.
    """

    LENGTH_IN_METRES: float = 105.0
    WIDTH_IN_METRES: float = 68.0


class EventSourceSetting:
    """What the two event sources have in common.

    A feature that both sources can produce lands in one file, with a source
    column saying which one wrote a row. A run of one source keeps the rows of
    the other untouched, so the two never have to run together.
    """

    SOURCE_COLUMN: str = "source"
    WYSCOUT_NAME: str = "wyscout"
    STATSBOMB_NAME: str = "statsbomb"
    COMPETITION_COLUMN: str = "competition"
    SEASON_COLUMN: str = "season"

    FOUL_NAME: str = "fouls"
    YELLOW_NAME: str = "yellow"
    RED_NAME: str = "red"
    SECOND_YELLOW_NAME: str = "second_yellow"


class WyscoutEventFile:
    """The Pappalardo event files, already on disk after the download.

    The action file stores coordinates the SPADL way, attacking towards x=0.
    Everything else in this project attacks towards x=105, so a reader mirrors
    them. The name files store literal escape sequences instead of characters.

    Attributes:
        ACTION_GAME_COLUMN: The action file is the same events again, already
            put into the SPADL shape, one row per action with a start and an
            end point in metres.
        TEAM_ONE_IDENTIFIER_COLUMN: The two teams of a match are numbered, not
            named home and away. Which one played at home is in the side
            column, and in roughly half the matches it is the second one.
        OFFICIAL_LIST_COLUMN: The match file names every official of a match
            in one cell, written as a Python literal. Only the one with the
            main referee role blew the whistle.
        TAG_LIST_COLUMN: Wyscout has no card event. It hangs a tag on the foul
            event of the player who caused it, and the tags sit in one cell as
            a list.
        CARD_TAG_PREFIX: Every card tag starts with these digits, so a cell
            without them can be skipped before its numbers are parsed at all.
    """

    SOURCE_FOLDER: Path = WyscoutEventSource.OUTPUT_FOLDER
    ACTION_FILE_NAME: str = "actions.csv"
    GAME_FILE_NAME: str = "games.csv"
    TEAM_FILE_NAME: str = "teams.csv"
    PLAYER_FILE_NAME: str = "players.csv"
    COMPETITION_FILE_NAME: str = "competitions.csv"
    REFEREE_FILE_NAME: str = "referees.csv"
    PLAYER_GAME_FILE_NAME: str = "player_games.csv"
    MATCH_FILE_PATTERN: str = "matches_*.csv"
    EVENT_FILE_PATTERN: str = "events_*.csv"

    IDENTIFIER_COLUMN: str = "wyId"
    NAME_COLUMN: str = "name"
    SHORT_NAME_COLUMN: str = "shortName"
    PITCH_LENGTH_IN_METRES: float = PitchGeometry.LENGTH_IN_METRES
    PITCH_WIDTH_IN_METRES: float = PitchGeometry.WIDTH_IN_METRES
    ESCAPE_MARKER: str = "\\u"

    MATCH_DATE_COLUMN: str = "dateutc"
    COMPETITION_IDENTIFIER_COLUMN: str = "competitionId"
    SEASON_IDENTIFIER_COLUMN: str = "seasonId"

    TEAM_ONE_IDENTIFIER_COLUMN: str = "team1.teamId"
    TEAM_TWO_IDENTIFIER_COLUMN: str = "team2.teamId"
    TEAM_ONE_SIDE_COLUMN: str = "team1.side"
    HOME_SIDE_NAME: str = "home"

    OFFICIAL_LIST_COLUMN: str = "referees"
    OFFICIAL_ROLE_FIELD: str = "role"
    OFFICIAL_IDENTIFIER_FIELD: str = "refereeId"
    MAIN_REFEREE_ROLE: str = "referee"

    EVENT_NAME_COLUMN: str = "eventName"
    PLAYER_IDENTIFIER_COLUMN: str = "playerId"
    MATCH_IDENTIFIER_COLUMN: str = "matchId"
    TEAM_IDENTIFIER_COLUMN: str = "teamId"
    FOUL_EVENT_NAME: str = "Foul"

    ACTION_GAME_COLUMN: str = "game_id"
    ACTION_TEAM_COLUMN: str = "team_id"
    ACTION_PLAYER_COLUMN: str = "player_id"
    ACTION_TYPE_COLUMN: str = "type_name"
    ACTION_RESULT_COLUMN: str = "result_name"
    ACTION_START_X_COLUMN: str = "start_x"
    ACTION_START_Y_COLUMN: str = "start_y"
    ACTION_END_X_COLUMN: str = "end_x"
    ACTION_END_Y_COLUMN: str = "end_y"
    ACTION_PERIOD_COLUMN: str = "period_id"
    ACTION_SECOND_COLUMN: str = "time_seconds"
    SUCCESSFUL_RESULT_NAME: str = "success"
    OWN_GOAL_RESULT_NAME: str = "owngoal"

    TAG_LIST_COLUMN: str = "tagsList"
    CARD_OF_TAG: dict[int, str] = {
        1702: EventSourceSetting.YELLOW_NAME,
        1701: EventSourceSetting.RED_NAME,
        1703: EventSourceSetting.SECOND_YELLOW_NAME,
    }
    CARD_TAG_PREFIX: str = "170"
    NUMBER_PATTERN: str = r"\d+"


class StatsBombOpenDataSource:
    """The free StatsBomb event data, fetched fresh on every run.

    The events of a match are about four megabytes, so nothing is kept on
    disk. A builder walks competition by competition and writes its file after
    each one, which is what makes a stopped run repeatable.

    Attributes:
        FOUL_EVENT_NAME: A card sits on a foul event, and one shown without a
            foul, such as for dissent, sits on a Bad Behaviour event. Both
            have to be looked at.
    """

    BASE_URL: str = StatsBombSource.BASE_URL
    COMPETITION_FILE_NAME: str = "competitions.json"
    TIMEOUT_IN_SECONDS: int = WebRequestSetting.STANDARD_TIMEOUT_IN_SECONDS
    POLITE_DELAY_IN_SECONDS: float = WebRequestSetting.FAST_POLITE_DELAY_IN_SECONDS
    WANTED_GENDER: str = "male"

    GENDER_FIELD: str = "competition_gender"
    COMPETITION_IDENTIFIER_FIELD: str = "competition_id"
    SEASON_IDENTIFIER_FIELD: str = "season_id"
    COMPETITION_NAME_FIELD: str = "competition_name"
    SEASON_NAME_FIELD: str = "season_name"
    MATCH_DATE_FIELD: str = "match_date"
    DATE_LENGTH: int = 10

    PITCH_LENGTH: float = 120.0
    PITCH_WIDTH: float = 80.0
    PROGRESS_REPORT_EVERY_N_MATCHES: int = 25

    HOME_TEAM_FIELD: str = "home_team"
    HOME_TEAM_NAME_FIELD: str = "home_team_name"
    AWAY_TEAM_FIELD: str = "away_team"
    AWAY_TEAM_NAME_FIELD: str = "away_team_name"
    MATCH_IDENTIFIER_FIELD: str = "match_id"
    REFEREE_FIELD: str = "referee"
    NAME_FIELD: str = "name"
    TYPE_FIELD: str = "type"
    PLAYER_FIELD: str = "player"
    TEAM_FIELD: str = "team"
    LOCATION_FIELD: str = "location"
    END_LOCATION_FIELD: str = "end_location"
    OUTCOME_FIELD: str = "outcome"
    PASS_FIELD: str = "pass"
    CROSS_FIELD: str = "cross"
    SHOT_FIELD: str = "shot"
    DUEL_FIELD: str = "duel"
    DRIBBLE_FIELD: str = "dribble"
    PLAY_PATTERN_FIELD: str = "play_pattern"
    RECIPIENT_FIELD: str = "recipient"
    PERIOD_FIELD: str = "period"
    MINUTE_FIELD: str = "minute"
    SECOND_FIELD: str = "second"

    FOUL_EVENT_NAME: str = "Foul Committed"
    BAD_BEHAVIOUR_EVENT_NAME: str = "Bad Behaviour"
    FOUL_FIELD: str = "foul_committed"
    BAD_BEHAVIOUR_FIELD: str = "bad_behaviour"
    CARD_FIELD: str = "card"
    CARD_OF_NAME: dict[str, str] = {
        "Yellow Card": EventSourceSetting.YELLOW_NAME,
        "Red Card": EventSourceSetting.RED_NAME,
        "Second Yellow": EventSourceSetting.SECOND_YELLOW_NAME,
    }


class PlayerCardFeature:
    """Yellow, red and second yellow cards per player and match.

    Only a player who saw a card in a match appears at all. How each source
    marks a card is written down with that source, in WyscoutEventFile and in
    StatsBombOpenDataSource.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "player_cards.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "team",
        "opponent",
        "player",
        "yellow",
        "red",
        "second_yellow",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "team",
        "player",
    )


class SubstitutionFeature:
    """Every substitution of every match, from both event sources.

    Wyscout stores them per team as a list inside the match file, written as a
    Python literal. StatsBomb stores them as substitution events with the
    player who went off, the replacement and the minute.

    Attributes:
        TEAM_SIDES: Each side gives its own team column, its substitution
            list, and the column that names the other team.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "substitutions.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "game_id",
        "team",
        "opponent",
        "player_out",
        "player_in",
        "minute",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
        "minute",
    )

    SUBSTITUTION_EVENT_NAME: str = "Substitution"
    SUBSTITUTION_FIELD: str = "substitution"
    REPLACEMENT_FIELD: str = "replacement"
    MINUTE_FIELD: str = "minute"
    PLAYER_OUT_FIELD: str = "playerOut"
    PLAYER_IN_FIELD: str = "playerIn"
    TEAM_SIDES: tuple[tuple[str, str, str], ...] = (
        (
            WyscoutEventFile.TEAM_ONE_IDENTIFIER_COLUMN,
            "team1.formation.substitutions",
            WyscoutEventFile.TEAM_TWO_IDENTIFIER_COLUMN,
        ),
        (
            WyscoutEventFile.TEAM_TWO_IDENTIFIER_COLUMN,
            "team2.formation.substitutions",
            WyscoutEventFile.TEAM_ONE_IDENTIFIER_COLUMN,
        ),
    )


class MatchDisciplineFeature:
    """Fouls and cards per player and per match, with the referee who gave them.

    This is what pairs a strict referee with an undisciplined team, which
    hardly any model does. It writes two files because the two questions are
    different: who collects cards, and how a match was refereed overall.

    A red card in the match file counts a second yellow as well, because both
    end with the same thing, a player leaving the pitch.
    """

    PLAYER_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "player_match_discipline.csv"
    )
    MATCH_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "match_officiating.csv"

    PLAYER_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "game_id",
        "referee",
        "team",
        "opponent",
        "player",
        "fouls",
        "yellow",
        "red",
        "second_yellow",
    )
    MATCH_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "game_id",
        "home",
        "away",
        "referee",
        "home_fouls",
        "away_fouls",
        "home_yellow",
        "home_red",
        "away_yellow",
        "away_red",
        "total_cards",
    )
    PLAYER_SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
        "team",
        "player",
    )
    MATCH_SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
    )

    COUNTED_NAMES: tuple[str, ...] = (
        EventSourceSetting.FOUL_NAME,
        EventSourceSetting.YELLOW_NAME,
        EventSourceSetting.RED_NAME,
        EventSourceSetting.SECOND_YELLOW_NAME,
    )
    CARD_NAMES: tuple[str, ...] = (
        EventSourceSetting.YELLOW_NAME,
        EventSourceSetting.RED_NAME,
        EventSourceSetting.SECOND_YELLOW_NAME,
    )


class MatchStyleFeature:
    """How a team played a match, beyond the goals and the odds.

    Two rows per match, one per team. The numbers say who had the ball, who
    pushed the other side back, how high the defence stood and how a team
    behaved while it was ahead or behind. Section 5.3 of the concept
    (docs/konzept.tex) is what asks for them.

    Only StatsBomb carries expected goals, so those columns stay empty for a
    Wyscout row.

    Attributes:
        PRESSING_PASS_MAXIMUM_X: How far up the pitch a pass of the other side
            still counts as their build up.
        PRESSING_DEFENCE_MINIMUM_X: How far up the pitch a defensive action of
            ours has to be to count as pressing. Together with the pass limit
            above this is what makes passes per defensive action a pressing
            number rather than a foul count.
        CARRY_KIND: Carrying the ball forward is a move of its own, and a
            different thing from a take on, which is a duel against an
            opponent.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "match_style.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "game_id",
        "competition",
        "season",
        "date",
        "team",
        "opponent",
        "is_home",
        "passes",
        "pass_share",
        "field_tilt",
        "passes_per_defensive_action",
        "defensive_action_height_in_metres",
        "passes_into_box",
        "directness_in_metres",
        "set_piece_pass_share",
        "take_on_success_rate",
        "crosses",
        "shots",
        "shots_in_box",
        "expected_goals",
        "non_penalty_expected_goals",
        "expected_goals_per_shot",
        "set_piece_expected_goals_share",
        "expected_goals_against",
        "non_penalty_expected_goals_against",
        "expected_goals_against_per_shot",
        "pass_share_while_leading",
        "pass_share_while_level",
        "pass_share_while_trailing",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
        "is_home",
    )

    FINAL_THIRD_START_X: float = 70.0
    BOX_START_X: float = 88.5
    BOX_MINIMUM_Y: float = 13.84
    BOX_MAXIMUM_Y: float = 54.16
    PRESSING_PASS_MAXIMUM_X: float = 63.0
    PRESSING_DEFENCE_MINIMUM_X: float = 42.0

    SHARE_DECIMAL_PLACES: int = 3
    PRESSING_DECIMAL_PLACES: int = 2
    HEIGHT_DECIMAL_PLACES: int = 1

    OPEN_PASS_KIND: str = "open_pass"
    CROSS_KIND: str = "cross"
    SET_PIECE_PASS_KIND: str = "set_piece_pass"
    CARRY_KIND: str = "carry"
    TAKE_ON_KIND: str = "take_on"
    FOUL_KIND: str = "foul"
    TACKLE_KIND: str = "tackle"
    INTERCEPTION_KIND: str = "interception"
    CLEARANCE_KIND: str = "clearance"
    SHOT_KIND: str = "shot"
    FREE_KICK_SHOT_KIND: str = "free_kick_shot"
    PENALTY_SHOT_KIND: str = "penalty_shot"
    OTHER_KIND: str = "other"

    OPEN_PLAY_PASS_KINDS: tuple[str, ...] = (OPEN_PASS_KIND, CROSS_KIND)
    EVERY_PASS_KIND: tuple[str, ...] = (
        OPEN_PASS_KIND,
        CROSS_KIND,
        SET_PIECE_PASS_KIND,
    )
    PRESSING_DEFENCE_KINDS: tuple[str, ...] = (
        TACKLE_KIND,
        INTERCEPTION_KIND,
        FOUL_KIND,
    )
    DEFENSIVE_LINE_KINDS: tuple[str, ...] = (
        TACKLE_KIND,
        INTERCEPTION_KIND,
        FOUL_KIND,
        CLEARANCE_KIND,
    )
    SHOT_KINDS: tuple[str, ...] = (
        SHOT_KIND,
        FREE_KICK_SHOT_KIND,
        PENALTY_SHOT_KIND,
    )

    SCORED_FOR_THE_ACTING_TEAM: str = "self"
    SCORED_FOR_THE_OTHER_TEAM: str = "opponent"

    KIND_OF_SPADL_TYPE: dict[str, str] = {
        "pass": OPEN_PASS_KIND,
        "cross": CROSS_KIND,
        "throw_in": SET_PIECE_PASS_KIND,
        "freekick_short": SET_PIECE_PASS_KIND,
        "corner_short": SET_PIECE_PASS_KIND,
        "goalkick": SET_PIECE_PASS_KIND,
        "freekick_crossed": SET_PIECE_PASS_KIND,
        "corner_crossed": SET_PIECE_PASS_KIND,
        "dribble": CARRY_KIND,
        "take_on": TAKE_ON_KIND,
        "foul": FOUL_KIND,
        "tackle": TACKLE_KIND,
        "interception": INTERCEPTION_KIND,
        "clearance": CLEARANCE_KIND,
        "shot": SHOT_KIND,
        "shot_freekick": FREE_KICK_SHOT_KIND,
        "shot_penalty": PENALTY_SHOT_KIND,
    }

    KIND_OF_STATSBOMB_EVENT: dict[str, str] = {
        "Dribble": TAKE_ON_KIND,
        "Interception": INTERCEPTION_KIND,
        "Foul Committed": FOUL_KIND,
        "Clearance": CLEARANCE_KIND,
    }
    PASS_EVENT_NAME: str = "Pass"
    SHOT_EVENT_NAME: str = "Shot"
    DUEL_EVENT_NAME: str = "Duel"
    DRIBBLE_EVENT_NAME: str = "Dribble"
    OWN_GOAL_FOR_EVENT_NAME: str = "Own Goal For"
    TACKLE_DUEL_NAME: str = "Tackle"
    COMPLETED_DRIBBLE_NAME: str = "Complete"
    PENALTY_SHOT_NAME: str = "Penalty"
    GOAL_OUTCOME_NAME: str = "Goal"
    EXPECTED_GOALS_FIELD: str = "statsbomb_xg"
    SET_PIECE_PASS_NAMES: frozenset[str] = frozenset(
        {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
    )
    SET_PIECE_SHOT_PATTERNS: frozenset[str] = frozenset(
        {"From Corner", "From Free Kick", "From Throw In"}
    )
    SECONDS_PER_MINUTE: int = 60


class PassingLaneFeature:
    """Every passing line between two players, per team and match.

    This is the whole passing network rather than a summary of it: one row
    per pair of players, with how often the ball went that way and where.

    Wyscout names no receiver, so the next action of the same team is taken
    as the player who got the ball. StatsBomb names the receiver itself.

    Attributes:
        FORWARD_MINIMUM_METRES: A pass only counts as forward when it wins
            ground worth naming.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "passing_lanes.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "game_id",
        "competition",
        "season",
        "date",
        "team",
        "passer",
        "receiver",
        "passes",
        "forward_passes",
        "mean_start_x",
        "mean_end_x",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
        "team",
        "passer",
        "receiver",
    )

    FORWARD_MINIMUM_METRES: float = 5.0
    MEAN_DECIMAL_PLACES: int = 1


class PassingNetworkFeature:
    """What the passing network of a team looked like in one match.

    The passing lane file holds every single edge, this one summarises the
    network: how vertical a team played, how far the ball travelled, and how
    much of the play went through one player.

    Only a pass out of open play counts, no cross and no set piece, because a
    corner says nothing about how a team builds up.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "passing_networks.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "game_id",
        "competition",
        "season",
        "date",
        "team",
        "opponent",
        "is_home",
        "passes",
        "pass_success_rate",
        "forward_pass_share",
        "mean_pass_length_in_metres",
        "mean_forward_gain_in_metres",
        "players_involved",
        "distinct_lanes",
        "unused_lane_share",
        "pass_concentration",
        "top_player_share",
        "top_lane",
        "top_lane_count",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "game_id",
        "is_home",
    )

    FORWARD_MINIMUM_METRES: float = PassingLaneFeature.FORWARD_MINIMUM_METRES
    RATE_DECIMAL_PLACES: int = 4
    LENGTH_DECIMAL_PLACES: int = 2
    LANE_SEPARATOR: str = " -> "


class PlayerMatchMetricFeature:
    """What one player did in one single match.

    Deliberately one row per player and match, with raw counts and the
    minutes played and no minimum, so any aggregation is still possible
    later: by season, by rolling window, by league.

    The goalkeeper columns are what makes this different from the usual
    player statistics. A keeper who plays as an eleventh outfielder shows up
    here, which is the thing that decided the 2014 World Cup and that no
    standard rating carries.

    Attributes:
        ROLE_COLUMN: The Wyscout player table writes the whole role as a
            Python literal in one cell, and the two letter code inside it is
            the part we want.
        ROLE_OF_POSITION_WORD: The words StatsBomb uses in a position name,
            and the role each stands for. The order matters, a wing back is a
            defender rather than a forward.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "player_metrics.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "team",
        "opponent",
        "player",
        "role",
        "minutes",
        "passes",
        "completed_passes",
        "progressive_passes",
        "passes_into_box",
        "deep_completions",
        "progression_value",
        "defensive_actions",
        "defensive_action_height_in_metres",
        "high_ball_recoveries",
        "take_ons",
        "take_ons_won",
        "shots",
        "shots_in_box",
        "goalkeeper_actions",
        "goalkeeper_actions_outside_box",
        "goalkeeper_action_height_in_metres",
        "goalkeeper_long_passes",
        "goalkeeper_passes",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "team",
        "player",
    )

    PENALTY_AREA_LENGTH_IN_METRES: float = 16.5
    DEEP_COMPLETION_START_X: float = 85.0
    PROGRESSIVE_PASS_MINIMUM_METRES: float = 15.0
    HIGH_RECOVERY_START_X: float = 60.0
    LONG_PASS_MINIMUM_METRES: float = 30.0
    PROGRESSION_DECIMAL_PLACES: int = 2
    HEIGHT_DECIMAL_PLACES: int = 1

    GOALKEEPER_ROLE: str = "GK"
    DEFENDER_ROLE: str = "DF"
    MIDFIELDER_ROLE: str = "MF"
    FORWARD_ROLE: str = "FW"

    ROLE_COLUMN: str = "role"
    ROLE_CODE_PATTERN: str = r"'code2':\s*'([A-Z]{2})'"

    APPEARANCE_FILE_NAME: str = "player_games.csv"
    MINUTES_COLUMN: str = "minutes_played"
    PLAYER_NAME_COLUMN: str = "player_name"

    STARTING_LINE_UP_EVENT_NAME: str = "Starting XI"
    TACTICS_FIELD: str = "tactics"
    LINE_UP_FIELD: str = "lineup"
    POSITION_FIELD: str = "position"
    IDENTIFIER_FIELD: str = "id"
    FULL_MATCH_MINUTES: int = 90
    ROLE_OF_POSITION_WORD: tuple[tuple[str, str], ...] = (
        ("Goalkeeper", GOALKEEPER_ROLE),
        ("Back", DEFENDER_ROLE),
        ("Midfield", MIDFIELDER_ROLE),
        ("Forward", FORWARD_ROLE),
        ("Wing", FORWARD_ROLE),
        ("Striker", FORWARD_ROLE),
    )


class ExpectedThreatFeature:
    """How much a team moved the ball towards a goal, per player and match.

    Every cell of the pitch gets a value saying how likely a goal follows
    from standing there, after the method of Karun Singh. Moving the ball
    from one cell to a better one is then worth the difference, which is what
    measures build up play that no goal or shot count ever shows.

    The grid is learned on the Wyscout data and written down, so the
    StatsBomb half applies the very same one and the two stay comparable.

    Only open play counts. A corner or a penalty would push the goal rate of
    its cell far above what that place on the pitch is really worth.

    Attributes:
        SOLVING_ROUNDS: The value of a cell depends on the cells the ball can
            reach from it, which depend on it in turn. Six passes through the
            grid are enough for the values to stop moving.
        SHOT_KINDS: Only a shot out of open play. A free kick or a penalty
            says more about the foul that led to it than about the place it
            was taken from.
        CARRY_EVENT_NAME: StatsBomb has an event for running with the ball
            that Wyscout has not.
    """

    GRID_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "xt_grid.csv"
    PLAYER_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "xt_player_match.csv"
    TEAM_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "xt_team_match.csv"

    GRID_COLUMN_NAMES: tuple[str, ...] = (
        "grid_column",
        "grid_row",
        "expected_threat",
    )
    PLAYER_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "team",
        "opponent",
        "player",
        "moves",
        "expected_threat_added",
        "expected_threat_added_per_move",
    )
    TEAM_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "team",
        "opponent",
        "is_home",
        "moves",
        "expected_threat_for",
        "expected_threat_against",
        "expected_threat_net",
    )
    PLAYER_SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "team",
        "player",
    )
    TEAM_SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "team",
    )

    COLUMN_COUNT: int = 16
    ROW_COUNT: int = 12
    SOLVING_ROUNDS: int = 6

    GRID_DECIMAL_PLACES: int = 6
    TOTAL_DECIMAL_PLACES: int = 4
    PER_MOVE_DECIMAL_PLACES: int = 5

    MOVE_KINDS: tuple[str, ...] = (
        MatchStyleFeature.OPEN_PASS_KIND,
        MatchStyleFeature.CROSS_KIND,
        MatchStyleFeature.CARRY_KIND,
    )
    SHOT_KINDS: tuple[str, ...] = (MatchStyleFeature.SHOT_KIND,)
    CARRY_EVENT_NAME: str = "Carry"
    CARRY_FIELD: str = "carry"


class PressResistanceFeature:
    """How well a player keeps the ball with an opponent closing in.

    StatsBomb marks an action as played under pressure, which is what makes
    this measurable at all. Wyscout has no such mark and guessing it from the
    positions would be far too noisy, so this feature stays on one source.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "press_resistance.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "season",
        "team",
        "opponent",
        "player",
        "passes",
        "completed_passes",
        "pressured_passes",
        "completed_pressured_passes",
        "carries",
        "pressured_carries",
        "take_ons",
        "take_ons_won",
        "times_dispossessed",
        "miscontrols",
        "pressured_pass_completion",
        "pressured_share",
    )
    SORT_KEY_NAMES: tuple[str, ...] = (
        "competition",
        "season",
        "date",
        "team",
        "player",
    )

    UNDER_PRESSURE_FIELD: str = "under_pressure"
    DISPOSSESSED_EVENT_NAME: str = "Dispossessed"
    MISCONTROL_EVENT_NAME: str = "Miscontrol"
    RATE_DECIMAL_PLACES: int = 4


class TeamStyleStabilityCalculation:
    """How much a team's style swings from match to match.

    A team with a steady profile is predictable, one that swings either
    adapts to the opponent or is simply unstable. Both are worth knowing
    before a tournament.

    The dimensions are on wildly different scales, a share against a distance
    in metres, so each is standardised within its competition and season
    before the swing is measured. The swing of a team is then the average
    spread of those standardised values over its matches.

    Attributes:
        MINIMUM_VALUES_FOR_A_SCALE: Two values are the fewest a spread can be
            worked out from at all.
        COLUMN_NAMES: Two columns per dimension, written out rather than
            built, so the file can be read here without running anything. A
            test holds them to the dimensions above.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "team_style_stability.csv"
    MINIMUM_MATCHES: int = 5
    DECIMAL_PLACES: int = 4
    MINIMUM_VALUES_FOR_A_SCALE: int = 2

    DIMENSIONS: tuple[str, ...] = (
        "pass_share",
        "field_tilt",
        "passes_per_defensive_action",
        "defensive_action_height_in_metres",
        "directness_in_metres",
        "set_piece_pass_share",
        "take_on_success_rate",
    )
    MEAN_SUFFIX: str = "_mean"
    VOLATILITY_SUFFIX: str = "_volatility"
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "competition",
        "season",
        "team",
        "matches",
        "pass_share_mean",
        "pass_share_volatility",
        "field_tilt_mean",
        "field_tilt_volatility",
        "passes_per_defensive_action_mean",
        "passes_per_defensive_action_volatility",
        "defensive_action_height_in_metres_mean",
        "defensive_action_height_in_metres_volatility",
        "directness_in_metres_mean",
        "directness_in_metres_volatility",
        "set_piece_pass_share_mean",
        "set_piece_pass_share_volatility",
        "take_on_success_rate_mean",
        "take_on_success_rate_volatility",
        "style_volatility",
    )


class RefereeEscalationCalculation:
    """Whether cards add up or multiply when a hard team meets a strict referee.

    The usual assumption is that they add up: the cards to expect are the
    average of the team plus the average of the referee. This checks whether
    the two instead feed off each other, so that the combination gives more
    cards than the two parts together.

    The strictness of a referee is the cards they gave per foul over every
    match they took charge of.

    Attributes:
        MINIMUM_MATCHES: A referee with fewer matches than this has a ratio
            that says more about the two matches they happened to get than
            about how they referee.
    """

    STRICTNESS_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "referee_strictness.csv"
    )
    ESCALATION_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "referee_escalation.csv"
    )
    STRICTNESS_COLUMN_NAMES: tuple[str, ...] = (
        "referee",
        "matches",
        "fouls",
        "cards",
        "cards_per_foul",
    )
    ESCALATION_COLUMN_NAMES: tuple[str, ...] = (
        "aggression_band",
        "strictness_band",
        "team_matches",
        "mean_fouls",
        "mean_cards",
    )

    MINIMUM_MATCHES: int = 8
    MINIMUM_VALUES_FOR_A_SCALE: int = 2
    HIGH_BAND_FROM: float = 0.5
    LOW_BAND_UP_TO: float = -0.5
    HIGH_BAND_NAME: str = "high"
    MIDDLE_BAND_NAME: str = "medium"
    LOW_BAND_NAME: str = "low"
    BAND_ORDER: tuple[str, ...] = (LOW_BAND_NAME, MIDDLE_BAND_NAME, HIGH_BAND_NAME)
    RATIO_DECIMAL_PLACES: int = 4
    FOUL_DECIMAL_PLACES: int = 2
    CARD_DECIMAL_PLACES: int = 3


class StyleMatchupCalculation:
    """Which style of play beats which, measured rather than assumed.

    Some teams take a deep block apart and fall over against a high press.
    This is that rock paper scissors effect in numbers: every team gets a
    style archetype out of its standardised style values, and every pairing
    of archetypes gets the expected goals it produced and conceded.

    The matrix rests on expected goals, so it mostly covers the StatsBomb
    competitions. Wyscout carries none.
    """

    ARCHETYPE_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "team_style_archetype.csv"
    )
    MATRIX_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "style_matchup_matrix.csv"
    ARCHETYPE_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "competition",
        "season",
        "team",
        "matches",
        "pass_share_standardised",
        "field_tilt_standardised",
        "passes_per_defensive_action_standardised",
        "directness_standardised",
        "defensive_action_height_standardised",
        "archetype",
        "has_empty_possession",
    )
    MATRIX_COLUMN_NAMES: tuple[str, ...] = (
        "archetype_for",
        "archetype_against",
        "matches",
        "mean_expected_goals_for",
        "mean_expected_goals_against",
        "mean_expected_goals_difference",
    )

    DIMENSIONS: tuple[str, ...] = (
        "pass_share",
        "field_tilt",
        "passes_per_defensive_action",
        "directness_in_metres",
        "defensive_action_height_in_metres",
    )
    MINIMUM_MATCHES: int = 5
    MINIMUM_VALUES_FOR_A_SCALE: int = 2
    HIGH_FROM: float = 0.5
    LOW_UP_TO: float = -0.5
    STANDARDISED_DECIMAL_PLACES: int = 2
    EXPECTED_GOALS_DECIMAL_PLACES: int = 3

    POSSESSION_DOMINANCE_NAME: str = "possession dominance"
    EMPTY_POSSESSION_NAME: str = "empty possession"
    DIRECT_AND_PHYSICAL_NAME: str = "direct and physical"
    DEEP_BLOCK_AND_COUNTER_NAME: str = "deep block and counter"
    BALANCED_NAME: str = "balanced"


class CountryClimateCalculation:
    """What summer feels like at home, and how far a venue is from that.

    A team from a cool country playing at thirty five degrees is at a
    disadvantage that no rating carries. The measure is the difference
    between the temperature at kick off and what June and July are normally
    like where the team comes from.

    The normal is taken at the largest city of the country over ten years,
    which is a rough stand in for a whole country but close enough to tell a
    Norwegian summer from a Qatari one.

    Attributes:
        ARCHIVE_DELAY_IN_SECONDS: A ten year query is heavy, so this source
            throttles harder than the others.
        RETRY_WAIT_IN_SECONDS: How long to wait before the one retry that is
            worth taking when the archive has throttled.
        PLACE_OF_TEAM_NAME: Team names that are no sovereign country, or that
            no geocoder finds, pointed at a place it does find.
    """

    OUTPUT_FILE: Path = ComputedFeaturePath.COUNTRY_CLIMATE_FILE
    DISTANCE_OUTPUT_FILE: Path = (
        ComputedFeaturePath.FOLDER / "match_climate_distance.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "country",
        "reference_place",
        "latitude",
        "longitude",
        "june_july_mean_temperature",
    )
    DISTANCE_COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "match_id",
        "match_date",
        "city",
        "apparent_temperature_c",
        "home_team",
        "home_climate_delta_c",
        "away_team",
        "away_climate_delta_c",
    )

    TOURNAMENT_FOLDER: Path = StatsBombSource.OUTPUT_FOLDER
    MATCH_FILE_PATTERN: str = "*.csv"
    WORLD_CUP_SQUAD_FILE: Path = (
        WikipediaSquadSource.OUTPUT_FOLDER / "World Cup 2026.csv"
    )
    WEATHER_FILE: Path = MatchWeatherSource.OUTPUT_FILE

    FIRST_CLIMATE_YEAR: int = 2015
    LAST_CLIMATE_YEAR: int = 2024
    SUMMER_MONTHS: tuple[str, ...] = ("06", "07")
    DAILY_TEMPERATURE_VARIABLE: str = "temperature_2m_mean"
    ARCHIVE_DELAY_IN_SECONDS: float = 1.2
    RETRY_WAIT_IN_SECONDS: float = 10.0
    TEMPERATURE_DECIMAL_PLACES: int = 2
    DELTA_DECIMAL_PLACES: int = 1

    PLACE_OF_TEAM_NAME: dict[str, str] = {
        "England": "London",
        "Scotland": "Glasgow",
        "Wales": "Cardiff",
        "Northern Ireland": "Belfast",
        "South Korea": "Seoul",
        "Korea Republic": "Seoul",
        "North Korea": "Pyongyang",
        "United States": "Washington",
        "USA": "Washington",
        "Ivory Coast": "Abidjan",
        "Cote d'Ivoire": "Abidjan",
        "DR Congo": "Kinshasa",
        "Czech Republic": "Prague",
        "Czechia": "Prague",
        "Bosnia and Herzegovina": "Sarajevo",
        "Curacao": "Willemstad",
        "Cape Verde": "Praia",
        "New Zealand": "Auckland",
        "Republic of Ireland": "Dublin",
        "Turkey": "Ankara",
        "China PR": "Beijing",
        "IR Iran": "Tehran",
    }


class EloRatingCalculation:
    """The rating of every national team before every match it ever played.

    The downloaded Elo dataset holds only about 400 snapshot days, but the
    concept needs the rating as it stood before each match, so this engine
    computes the whole history itself out of the results file, following the
    method of eloratings.net.

    The K factor says how much one match may move a rating: a World Cup final
    round counts triple a friendly. The goal multiplier raises that again for
    a clear win. The home advantage falls away on a neutral pitch.
    """

    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "International Football Elo Ratings (1872-2025)"
    )
    HISTORY_FILE_NAME: str = "elo_prematch_history.csv"
    SNAPSHOT_FILE_NAME: str = "elo_computed_latest.csv"

    START_RATING: float = 1500.0
    HOME_ADVANTAGE: float = 100.0
    RATING_SCALE: float = 400.0
    LOGISTIC_BASE: float = 10.0
    RATING_DECIMAL_PLACES: int = 1

    K_FACTOR_WORLD_CUP: float = 60.0
    K_FACTOR_CONTINENTAL_FINALS: float = 50.0
    K_FACTOR_QUALIFIER: float = 40.0
    K_FACTOR_OTHER_TOURNAMENT: float = 30.0
    K_FACTOR_FRIENDLY: float = 20.0

    WORLD_CUP_NAME: str = "FIFA World Cup"
    FRIENDLY_NAME: str = "friendly"
    QUALIFIER_NAME_PARTS: tuple[str, ...] = ("qualification", "nations league")
    CONTINENTAL_FINALS_NAMES: tuple[str, ...] = (
        "UEFA Euro",
        "Copa América",
        "African Cup of Nations",
        "Africa Cup of Nations",
        "AFC Asian Cup",
        "CONCACAF Championship",
        "Gold Cup",
        "Confederations Cup",
        "Oceania Nations Cup",
    )

    NARROW_GOAL_DIFFERENCE: int = 1
    TWO_GOAL_DIFFERENCE: int = 2
    MULTIPLIER_NARROW: float = 1.0
    MULTIPLIER_TWO_GOALS: float = 1.5
    MULTIPLIER_OFFSET: float = 11.0
    MULTIPLIER_DIVISOR: float = 8.0

    WIN_SCORE: float = 1.0
    DRAW_SCORE: float = 0.5
    LOSS_SCORE: float = 0.0
    MISSING_SCORE_TEXTS: tuple[str, ...] = ("NA", "")
    HOME_SCORE_COLUMN: str = "home_score"
    AWAY_SCORE_COLUMN: str = "away_score"

    HISTORY_COLUMN_NAMES: tuple[str, ...] = (
        "date",
        "home_team",
        "away_team",
        "tournament",
        "neutral",
        "elo_home_pre",
        "elo_away_pre",
    )
    SNAPSHOT_COLUMN_NAMES: tuple[str, ...] = ("rank", "team", "elo")


class CrowdTipPriorCalculation:
    """What the other players will most likely tip, before anybody has tipped.

    Mode B2 of the concept (docs/konzept.tex, section 9) needs a distribution
    over the scorelines the other players pick. They do not pick at random:
    they crowd onto a handful of results that simply feel right, a narrow win
    for the favourite and round numbers.

    The prior mixes what really happens with that known preference. Where the
    two disagree most is where a contrarian tip is worth the most.

    Attributes:
        HEURISTIC_WEIGHT: How much of the prior is the known crowd preference
            rather than what really happens. Half and half, until live tips
            say otherwise.
        HEURISTIC_WEIGHT_OF_SCORELINE: The scorelines casual players pick far
            more often than they happen, written as favourite goals against
            underdog goals.
    """

    BY_BAND_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "crowd_tip_prior_by_band.csv"
    )
    SUMMARY_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "crowd_tip_prior_summary.csv"
    )
    BY_BAND_COLUMN_NAMES: tuple[str, ...] = (
        "favorite_band",
        "favorite_goals",
        "underdog_goals",
        "empirical_probability",
        "heuristic_probability",
        "crowd_prior_probability",
    )
    SUMMARY_COLUMN_NAMES: tuple[str, ...] = (
        "favorite_band",
        "matches",
        "crowd_distortion",
        "top_crowd_scoreline",
        "top_crowd_probability",
    )

    RESULT_FILE: Path = InternationalResultSource.RESULT_FILE
    ELO_HISTORY_FILE: Path = (
        EloRatingCalculation.OUTPUT_FOLDER / EloRatingCalculation.HISTORY_FILE_NAME
    )
    HOME_ADVANTAGE: float = EloRatingCalculation.HOME_ADVANTAGE
    RATING_SCALE: float = EloRatingCalculation.RATING_SCALE
    LOGISTIC_BASE: float = EloRatingCalculation.LOGISTIC_BASE
    HIGHEST_GOALS_IN_THE_GRID: int = 5
    HEURISTIC_WEIGHT: float = 0.5
    BAND_EDGES: tuple[float, ...] = (0.50, 0.60, 0.70, 0.80, 0.90, 1.001)
    PROBABILITY_DECIMAL_PLACES: int = 4
    SCORELINE_SEPARATOR: str = ":"

    HEURISTIC_WEIGHT_OF_SCORELINE: dict[tuple[int, int], float] = {
        (1, 0): 0.22,
        (2, 1): 0.20,
        (2, 0): 0.17,
        (1, 1): 0.12,
        (3, 1): 0.10,
        (3, 0): 0.08,
        (0, 0): 0.06,
        (2, 2): 0.05,
    }


class ResidualFeatureCalculation:
    """What a team did beyond what was to be expected of it.

    Subtracting the expectation leaves two signals that strength alone hides.
    Form, as points won against what the rating said, which a strong team can
    be short of just as easily as a weak one. And finishing, as goals scored
    against the chances created, which swings back to the average sooner or
    later while the market keeps looking at the goals.

    Every row carries the smoothed state as it stood before its own match, so
    nothing in it was known only afterwards.

    Attributes:
        FADING_WEIGHT: How heavily the latest match counts against everything
            before it.
        WINDOW_LENGTH: How many of the most recent matches the second average
            runs over.
    """

    FORM_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "elo_form_residuals.csv"
    FINISHING_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "xg_finishing_residuals.csv"
    )
    FORM_COLUMN_NAMES: tuple[str, ...] = (
        "date",
        "tournament",
        "team",
        "opponent",
        "is_home",
        "neutral",
        "result",
        "elo_expected",
        "elo_residual",
        "prematch_form_faded_average",
        "prematch_form_mean_of_last_five",
        "prematch_matches",
    )
    FINISHING_COLUMN_NAMES: tuple[str, ...] = (
        "match_date",
        "tournament",
        "team",
        "opponent",
        "is_home",
        "goals_for",
        "expected_goals_for",
        "goals_against",
        "expected_goals_against",
        "finishing_residual",
        "defensive_residual",
        "prematch_finishing_faded_average",
        "prematch_finishing_mean_of_last_five",
        "prematch_matches",
    )

    TOURNAMENT_FOLDER: Path = StatsBombSource.OUTPUT_FOLDER
    MATCH_FILE_PATTERN: str = "*.csv"
    HOME_EXPECTED_GOALS_COLUMN: str = "home_xg_90"
    AWAY_EXPECTED_GOALS_COLUMN: str = "away_xg_90"

    FADING_WEIGHT: float = 0.4
    WINDOW_LENGTH: int = 5
    FORM_DECIMAL_PLACES: int = 4
    GOAL_DECIMAL_PLACES: int = 3

    WIN_POINTS: float = 1.0
    DRAW_POINTS: float = 0.5
    LOSS_POINTS: float = 0.0
    NEUTRAL_TEXT: str = "TRUE"


class LineMovementCalculation:
    """How the odds moved between the first price and the last one.

    The opening price is what the market thought early, the closing price is
    what it thought after the informed money had gone in. The difference
    between the two, once the bookmaker margin is out, is the clearest trace
    of that money there is, and the ground every closing line value check
    stands on.

    Only two sources carry both prices. The others give one snapshot, which
    can show no movement at all.

    Attributes:
        OPENING_COLUMNS: Pinnacle, because it is the sharpest book in the file
            and the only one that carries both an opening and a closing price.
        PROBABILITY_FLOOR: A probability of zero would make the log loss
            infinite, so it is kept just above zero.
    """

    OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "line_movement_clv.csv"
    SUMMARY_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "line_movement_league_summary.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "league",
        "season",
        "date",
        "home",
        "away",
        "result",
        "opening_home_probability",
        "opening_draw_probability",
        "opening_away_probability",
        "closing_home_probability",
        "closing_draw_probability",
        "closing_away_probability",
        "home_movement",
        "draw_movement",
        "away_movement",
        "total_movement",
        "movement_towards_the_result",
    )
    SUMMARY_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "league",
        "matches",
        "opening_log_loss",
        "closing_log_loss",
        "log_loss_improvement",
        "mean_total_movement",
        "share_moved_towards_the_result",
    )

    FOOTBALL_DATA_FOLDER: Path = FootballDataSource.OUTPUT_ROOT
    BEAT_THE_BOOKIE_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "International & Tournament Odds (Beat The Bookie 2005-2015)"
        / "international_open_close_odds_2016.csv"
    )
    COVERAGE_FILE_NAME: str = "coverage_report.csv"
    SCORE_SEPARATOR: str = ":"

    OPENING_COLUMNS: tuple[str, str, str] = ("PSH", "PSD", "PSA")
    CLOSING_COLUMNS: tuple[str, str, str] = ("PSCH", "PSCD", "PSCA")
    BEAT_THE_BOOKIE_OPENING_COLUMNS: tuple[str, str, str] = (
        "avg_open_home",
        "avg_open_draw",
        "avg_open_away",
    )
    BEAT_THE_BOOKIE_CLOSING_COLUMNS: tuple[str, str, str] = (
        "avg_close_home",
        "avg_close_draw",
        "avg_close_away",
    )
    RESULT_COLUMN: str = "FTR"
    RESULT_LETTERS: tuple[str, str, str] = ("H", "D", "A")
    LOWEST_SENSIBLE_ODDS: float = 1.0
    PROBABILITY_FLOOR: float = 1e-12
    DECIMAL_PLACES: int = 4
    FOOTBALL_DATA_NAME: str = "football-data"
    BEAT_THE_BOOKIE_NAME: str = "beat-the-bookie"
    BEAT_THE_BOOKIE_SEASON: str = "2016"


class FavoriteLongshotCalculation:
    """Whether the market prices favourites and outsiders fairly.

    The known pattern is that it does not: an outsider is priced as if it won
    more often than it really does, and a strong favourite as if it won less.
    This checks that on every match with a three way price, per band of how
    strong the favourite was.

    The flat return is what betting one unit on every match of a band would
    have paid back, which turns the calibration gap into money.

    Attributes:
        ODDS_COLUMNS_BY_PREFERENCE: The books of the football-data files,
            sharpest first. The first one that carries a full price for a
            match is the one that is used.
    """

    MATCH_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "favorite_longshot_matches.csv"
    )
    BAND_OUTPUT_FILE: Path = ProjectPath.CUSTOM_DATA_ROOT / "favorite_longshot_bias.csv"
    BY_SOURCE_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "favorite_longshot_bias_by_source.csv"
    )
    MATCH_COLUMN_NAMES: tuple[str, ...] = (
        "source",
        "date",
        "competition",
        "home",
        "away",
        "result",
        "home_odds",
        "draw_odds",
        "away_odds",
        "favorite",
        "implied_favorite_probability",
        "favorite_won",
        "favorite_odds",
        "favorite_band",
        "favorite_profit",
    )
    BAND_COLUMN_NAMES: tuple[str, ...] = (
        "favorite_band",
        "matches",
        "mean_implied_favorite_probability",
        "actual_favorite_win_rate",
        "calibration_gap",
        "favorite_flat_return_percent",
        "longshot_flat_return_percent",
    )
    BY_SOURCE_COLUMN_NAMES: tuple[str, ...] = ("source",) + BAND_COLUMN_NAMES

    CLUB_ENGINEERED_FILE: Path = (
        ProjectPath.DATA_ROOT / "Club Football Engineered (2000-2025)" / "Matches.csv"
    )
    FOOTYSTATS_FOLDERS: tuple[Path, ...] = (
        ProjectPath.DATA_ROOT / "International Matches & Odds (FootyStats)",
        ProjectPath.DATA_ROOT / "Tournament Odds (FootyStats)",
    )
    CLOSING_ODDS_FILE: Path = (
        ProjectPath.DATA_ROOT
        / "International & Tournament Odds (Beat The Bookie 2005-2015)"
        / "international_closing_odds.csv"
    )

    ODDS_COLUMNS_BY_PREFERENCE: tuple[tuple[str, str, str], ...] = (
        ("PSCH", "PSCD", "PSCA"),
        ("PSH", "PSD", "PSA"),
        ("B365H", "B365D", "B365A"),
        ("AvgH", "AvgD", "AvgA"),
    )
    CLUB_ENGINEERED_ODDS_COLUMNS: tuple[str, str, str] = (
        "OddHome",
        "OddDraw",
        "OddAway",
    )
    FOOTYSTATS_ODDS_COLUMNS: tuple[str, str, str] = (
        "odds_ft_home_team_win",
        "odds_ft_draw",
        "odds_ft_away_team_win",
    )
    CLOSING_ODDS_COLUMNS: tuple[str, str, str] = (
        "avg_odds_home_win",
        "avg_odds_draw",
        "avg_odds_away_win",
    )

    OUTCOME_NAMES: tuple[str, str, str] = ("home", "draw", "away")
    BAND_EDGES: tuple[float, ...] = (
        0.35,
        0.45,
        0.55,
        0.65,
        0.75,
        0.85,
        0.90,
        0.95,
        1.0001,
    )
    EVERY_BAND_NAME: str = "all"
    CLUB_ENGINEERED_NAME: str = "club-engineered"
    FOOTYSTATS_NAME: str = "footystats"
    COMPLETE_STATUS: str = "complete"
    PROBABILITY_DECIMAL_PLACES: int = 4
    PERCENT_DECIMAL_PLACES: int = 2
    ONE_UNIT_STAKE: float = 1.0


class ConfederationCalibration:
    """What the Elo ratings get wrong between the confederations.

    National teams play mostly inside their own confederation, so how the
    confederations stand against each other is barely in the ratings at all.
    That is exactly the comparison a World Cup turns on.

    The signal is in the rare matches across confederations: what the home
    side really took out of them against what the rating expected. The
    average of that, per pair and era, says which confederation the rating
    systematically over or under rates.

    A positive offset means the confederation is under rated, its matches are
    explained better with a higher effective rating. UEFA is held at zero,
    because the offsets can only ever be read against each other.

    Attributes:
        MINIMUM_MATCHES_FOR_A_FIT: An era with fewer cross confederation
            matches than this gives an offset that says more about the handful
            of matches than about the era.
        FITTING_ROUNDS: The loss surface is very flat, one Elo point barely
            moves a probability, so the step scales itself by the curvature.
            Sixty rounds are far more than it needs to settle.
        ERA_EDGES: Where one era ends and the next begins, and what each is
            called.
        MEMBERS_OF_CONFEDERATION: Every national team by confederation,
            spelled the way the results file spells them. A team that no
            longer exists is put with whoever took its place on the map.
    """

    PAIR_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "confederation_pair_residuals.csv"
    )
    OFFSET_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "confederation_elo_offsets.csv"
    )
    TEAM_MAP_OUTPUT_FILE: Path = (
        ProjectPath.CUSTOM_DATA_ROOT / "team_confederation_map.csv"
    )

    REFERENCE_CONFEDERATION: str = "UEFA"
    OFFSET_COLUMN: str = "elo_offset_vs_" + REFERENCE_CONFEDERATION
    PAIR_COLUMN_NAMES: tuple[str, ...] = (
        "era",
        "confederation_home",
        "confederation_away",
        "matches",
        "mean_result_residual",
        "mean_elo_expected",
        "mean_goal_difference",
    )
    OFFSET_COLUMN_NAMES: tuple[str, ...] = (
        "era",
        "confederation",
        OFFSET_COLUMN,
        "matches_in_era",
    )
    TEAM_MAP_COLUMN_NAMES: tuple[str, ...] = ("team", "confederation", "matches")

    UNMAPPED_NAME: str = "UNMAPPED"
    EVERY_ERA_NAME: str = "all_time"
    MINIMUM_MATCHES_FOR_A_FIT: int = 40
    FITTING_ROUNDS: int = 60
    SMALLEST_USABLE_CURVATURE: float = 1e-9
    RESIDUAL_DECIMAL_PLACES: int = 4
    GOAL_DECIMAL_PLACES: int = 3
    OFFSET_DECIMAL_PLACES: int = 1

    ERA_EDGES: tuple[tuple[int, str], ...] = (
        (1990, "pre_1990"),
        (2000, "1990_1999"),
        (2010, "2000_2009"),
        (2020, "2010_2019"),
    )
    LATEST_ERA_NAME: str = "2020_2026"

    MEMBERS_OF_CONFEDERATION: dict[str, tuple[str, ...]] = {
        "UEFA": (
            "Albania",
            "Andorra",
            "Armenia",
            "Austria",
            "Azerbaijan",
            "Belarus",
            "Belgium",
            "Bosnia and Herzegovina",
            "Bulgaria",
            "Croatia",
            "Cyprus",
            "Czech Republic",
            "Czechia",
            "Denmark",
            "England",
            "Estonia",
            "Faroe Islands",
            "Finland",
            "France",
            "Georgia",
            "Germany",
            "Gibraltar",
            "Greece",
            "Hungary",
            "Iceland",
            "Israel",
            "Italy",
            "Kazakhstan",
            "Kosovo",
            "Latvia",
            "Liechtenstein",
            "Lithuania",
            "Luxembourg",
            "Malta",
            "Moldova",
            "Montenegro",
            "Netherlands",
            "North Macedonia",
            "Macedonia",
            "Northern Ireland",
            "Norway",
            "Poland",
            "Portugal",
            "Republic of Ireland",
            "Ireland",
            "Romania",
            "Russia",
            "San Marino",
            "Scotland",
            "Serbia",
            "Slovakia",
            "Slovenia",
            "Spain",
            "Sweden",
            "Switzerland",
            "Turkey",
            "Ukraine",
            "Wales",
            "Soviet Union",
            "CIS",
            "Yugoslavia",
            "Serbia and Montenegro",
            "Czechoslovakia",
            "East Germany",
            "German DR",
            "West Germany",
            "Saar",
        ),
        "CONMEBOL": (
            "Argentina",
            "Bolivia",
            "Brazil",
            "Chile",
            "Colombia",
            "Ecuador",
            "Paraguay",
            "Peru",
            "Uruguay",
            "Venezuela",
        ),
        "CONCACAF": (
            "United States",
            "USA",
            "Mexico",
            "Canada",
            "Costa Rica",
            "Honduras",
            "Panama",
            "Jamaica",
            "Trinidad and Tobago",
            "El Salvador",
            "Guatemala",
            "Haiti",
            "Cuba",
            "Curacao",
            "Suriname",
            "Guyana",
            "Nicaragua",
            "Belize",
            "Antigua and Barbuda",
            "Aruba",
            "Bahamas",
            "Barbados",
            "Bermuda",
            "British Virgin Islands",
            "Cayman Islands",
            "Dominica",
            "Dominican Republic",
            "Grenada",
            "Montserrat",
            "Puerto Rico",
            "Saint Kitts and Nevis",
            "Saint Lucia",
            "Saint Vincent and the Grenadines",
            "Sint Maarten",
            "Turks and Caicos Islands",
            "US Virgin Islands",
            "Anguilla",
            "Martinique",
            "Guadeloupe",
            "French Guiana",
            "Bonaire",
            "Netherlands Antilles",
        ),
        "AFC": (
            "Afghanistan",
            "Australia",
            "Bahrain",
            "Bangladesh",
            "Bhutan",
            "Brunei",
            "Cambodia",
            "China PR",
            "China",
            "Chinese Taipei",
            "Taiwan",
            "Guam",
            "Hong Kong",
            "India",
            "Indonesia",
            "Iran",
            "IR Iran",
            "Iraq",
            "Japan",
            "Jordan",
            "Kuwait",
            "Kyrgyzstan",
            "Laos",
            "Lebanon",
            "Macau",
            "Malaysia",
            "Maldives",
            "Mongolia",
            "Myanmar",
            "Burma",
            "Nepal",
            "North Korea",
            "Korea DPR",
            "Oman",
            "Pakistan",
            "Palestine",
            "Philippines",
            "Qatar",
            "Saudi Arabia",
            "Singapore",
            "South Korea",
            "Korea Republic",
            "Sri Lanka",
            "Syria",
            "Tajikistan",
            "Thailand",
            "Timor-Leste",
            "Turkmenistan",
            "United Arab Emirates",
            "Uzbekistan",
            "Vietnam",
            "Vietnam Republic",
            "South Vietnam",
            "Yemen",
            "South Yemen",
            "North Yemen",
            "Yemen DPR",
        ),
        "CAF": (
            "Algeria",
            "Angola",
            "Benin",
            "Dahomey",
            "Botswana",
            "Burkina Faso",
            "Upper Volta",
            "Burundi",
            "Cameroon",
            "Cape Verde",
            "Cabo Verde",
            "Central African Republic",
            "Chad",
            "Comoros",
            "Congo",
            "DR Congo",
            "Congo DR",
            "Zaire",
            "Djibouti",
            "Egypt",
            "Equatorial Guinea",
            "Eritrea",
            "Eswatini",
            "Swaziland",
            "Ethiopia",
            "Gabon",
            "Gambia",
            "Ghana",
            "Guinea",
            "Guinea-Bissau",
            "Ivory Coast",
            "Cote d'Ivoire",
            "Kenya",
            "Lesotho",
            "Liberia",
            "Libya",
            "Madagascar",
            "Malawi",
            "Mali",
            "Mauritania",
            "Mauritius",
            "Morocco",
            "Mozambique",
            "Namibia",
            "Niger",
            "Nigeria",
            "Rwanda",
            "Sao Tome and Principe",
            "Senegal",
            "Seychelles",
            "Sierra Leone",
            "Somalia",
            "South Africa",
            "South Sudan",
            "Sudan",
            "Tanzania",
            "Togo",
            "Tunisia",
            "Uganda",
            "Zambia",
            "Zimbabwe",
            "Reunion",
            "Mayotte",
            "Zanzibar",
        ),
        "OFC": (
            "American Samoa",
            "Cook Islands",
            "Fiji",
            "New Caledonia",
            "New Zealand",
            "Papua New Guinea",
            "Samoa",
            "Western Samoa",
            "Solomon Islands",
            "Tahiti",
            "Tonga",
            "Tuvalu",
            "Vanuatu",
        ),
    }


class OddsCoverageReport:
    """From which season on a league actually carries the prices we need.

    A column can stand in the header and still be empty in most rows, so it
    only counts as present when it is filled in at least half of the matches.
    Without a closing price there is no closing line value to measure, which
    decides how far back a backtest can reach.

    Attributes:
        OPENING_COLUMNS: The home win column of each book stands in for the
            whole three way price, because a book that priced the home win
            priced the other two as well.
    """

    LEAGUE_FOLDER: Path = FootballDataSource.OUTPUT_ROOT / "main_leagues"
    OUTPUT_FILE: Path = (
        FootballDataSource.OUTPUT_ROOT / LineMovementCalculation.COVERAGE_FILE_NAME
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "league",
        "season",
        "matches",
        "has_opening",
        "has_closing",
        "has_pinnacle_closing",
    )

    NO_SEASON_TEXT: str = "-"
    LOWEST_USABLE_FILL_RATE: float = 0.5
    OPENING_COLUMNS: tuple[str, ...] = ("PSH", "B365H", "AvgH")
    CLOSING_COLUMNS: tuple[str, ...] = ("PSCH", "B365CH", "AvgCH")
    PINNACLE_CLOSING_COLUMN: str = "PSCH"
    DATE_COLUMN: str = "Date"


class SquadValueCalculation:
    """The market value of a national squad, per country and per key date.

    This is the market value feature of the concept. Per country and half year
    it sums the value of the most valuable players of that citizenship, using
    only valuations dated on or before the key date, so nothing from the future
    leaks in. A valuation older than the look back is dropped as stale.

    Attributes:
        SMALLEST_USABLE_PLAYER_COUNT: Six rather than ten, so a thinly covered
            World Cup team such as Jordan still gets a value at all.
        COUNTRY_ALIASES: The Transfermarkt spellings, pointed at the names the
            Wikipedia squads use.
    """

    SOURCE_FOLDER: Path = TransfermarktMarketValueSource.OUTPUT_FOLDER
    VALUATION_FILE_NAME: str = "player_valuations.csv"
    PLAYER_FILE_NAME: str = "players.csv"
    OUTPUT_FILE_NAME: str = "national_squad_values.csv"

    FIRST_KEY_DATE_YEAR: int = 2005
    KEY_DATE_MONTHS: tuple[int, ...] = (1, 7)
    KEY_DATE_FREQUENCY: str = "6MS"
    FIRST_DAY_OF_MONTH: int = 1
    KEY_DATE_FORMAT: str = "%Y-%m-%d"
    SQUAD_SIZE: int = 26
    LOOK_BACK_IN_DAYS: int = 540
    SMALLEST_USABLE_PLAYER_COUNT: int = 6

    CITIZENSHIP_COLUMN: str = "country_of_citizenship"
    PLAYER_IDENTIFIER_COLUMN: str = "player_id"
    VALUE_COLUMN: str = "market_value_in_eur"
    DATE_COLUMN: str = "date"

    COLUMN_NAMES: tuple[str, ...] = (
        "as_of_date",
        "country",
        "squad_value_eur",
        "players",
    )

    COUNTRY_ALIASES: dict[str, str] = {
        "Bosnia-Herzegovina": "Bosnia and Herzegovina",
        "Korea, South": "South Korea",
        "Korea, North": "North Korea",
        "Cote d'Ivoire": "Ivory Coast",
        "Curacao": "Curaçao",
    }


class RefereeProfileCalculation:
    """Card and foul rates per referee, over every finished tournament match.

    This is the base for the strictness feature: a referee who lets play run
    against one who blows for everything. Only a match the source marks as
    complete counts.
    """

    SOURCE_FOLDER: Path = FootyStatsSource.MATCH_ODDS_OUTPUT_FOLDER
    OUTPUT_FILE: Path = ComputedFeaturePath.FOLDER / "referee_profiles.csv"

    REFEREE_COLUMN: str = "referee"
    STATUS_COLUMN: str = "status"
    COMPLETE_STATUS: str = "complete"
    MISSING_REFEREE_TEXTS: tuple[str, ...] = ("", "N/A")
    YELLOW_CARD_COLUMNS: tuple[str, ...] = (
        "home_team_yellow_cards",
        "away_team_yellow_cards",
    )
    RED_CARD_COLUMNS: tuple[str, ...] = (
        "home_team_red_cards",
        "away_team_red_cards",
    )
    FOUL_COLUMNS: tuple[str, ...] = ("home_team_fouls", "away_team_fouls")

    YELLOW_DECIMAL_PLACES: int = 2
    RED_DECIMAL_PLACES: int = 3
    FOUL_DECIMAL_PLACES: int = 1
    TOURNAMENT_SEPARATOR: str = "; "

    COLUMN_NAMES: tuple[str, ...] = (
        "referee",
        "matches",
        "mean_yellow_cards",
        "mean_red_cards",
        "mean_fouls",
        "tournaments",
    )


class BeatTheBookieSource:
    """The Beat The Bookie dataset, the odds base for the older tournaments.

    The closing odds file covers 2005 to 2015. Series B covers March to
    November 2016 as odds time series, 32 bookmakers with 72 hourly points
    before kick off, and holds the complete Euro 2016.

    A column of the series is named like home_b3_17, that is outcome,
    bookmaker and hour.

    The series files carry French team names and are encoded latin-1, not
    UTF-8. Should a decoding error or a broken accent turn up in the closing
    odds file as well, set CLOSING_ODDS_ENCODING to the same value.
    """

    SOURCE_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "Beat The Bookie Odds Series Football Dataset"
    )
    CLOSING_ODDS_FILE: Path = SOURCE_FOLDER / "closing_odds.csv.gz"
    SERIES_MATCH_FILE: Path = SOURCE_FOLDER / "odds_series_b_matches.csv.gz"
    SERIES_ODDS_FILE: Path = SOURCE_FOLDER / "odds_series_b.csv.gz"

    CLOSING_ODDS_ENCODING: str = "utf-8"
    SERIES_ENCODING: str = "latin-1"
    READ_TEXT_MODE: str = "rt"

    LEAGUE_COLUMN: str = "league"
    MATCH_DATE_COLUMN: str = "match_date"
    OUTCOMES: tuple[str, ...] = ("home", "draw", "away")

    SMALLEST_USABLE_MATCH_ROW: int = 7
    MATCH_IDENTIFIER_POSITION: int = 0
    LEAGUE_POSITION: int = 1
    HOME_TEAM_POSITION: int = 2
    AWAY_TEAM_POSITION: int = 3
    SCORE_POSITION: int = 4
    KICK_OFF_POSITION: int = 6

    COLUMN_NAME_PART_COUNT: int = 3
    BOOKMAKER_PREFIX: str = "b"
    LOWEST_POSSIBLE_ODDS: float = 1.0
    MISSING_VALUE_TEXTS: tuple[str, ...] = ("", "nan")
    DECIMAL_PLACES: int = 4
    YEAR_PATTERN: str = r"(\d{4})"
    UNKNOWN_YEAR: str = "?"

    OPEN_CLOSE_BASE_COLUMN_NAMES: tuple[str, ...] = (
        "match_id",
        "league",
        "match_datetime",
        "home_team",
        "away_team",
        "score",
        "n_bookies",
    )


class InternationalOddsExtract:
    """Senior men national team matches out of the Beat The Bookie dataset.

    The competition name has to match exactly, otherwise Euro would also catch
    Europa League or Euro U21.
    """

    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT
        / "International & Tournament Odds (Beat The Bookie 2005-2015)"
    )
    CLOSING_OUTPUT_FILE: Path = OUTPUT_FOLDER / "international_closing_odds.csv"
    OPEN_CLOSE_OUTPUT_FILE: Path = (
        OUTPUT_FOLDER / "international_open_close_odds_2016.csv"
    )

    COMPETITIONS: frozenset[str] = frozenset(
        {
            "world cup",
            "euro",
            "friendly international",
            "africa cup of nations",
            "asian cup",
            "copa america",
            "fifa confederations cup",
            "gold cup",
            "nations league",
        }
    )


class UefaClubOddsExtract:
    """UEFA club competitions out of the same dataset.

    The international extract filters these out on purpose, so they get their
    own files. football-data.co.uk carries no UEFA competition at all.
    """

    OUTPUT_FOLDER: Path = (
        ProjectPath.DATA_ROOT / "UEFA Club Competitions (Beat The Bookie)"
    )
    CLOSING_OUTPUT_FILE: Path = OUTPUT_FOLDER / "uefa_club_closing_odds_2005_2015.csv"
    OPEN_CLOSE_OUTPUT_FILE: Path = OUTPUT_FOLDER / "uefa_club_open_close_2016.csv"

    COMPETITIONS: frozenset[str] = frozenset(
        {
            "champions league",
            "europa league",
            "uefa cup",
            "uefa super cup",
            "intertoto cup",
        }
    )


class RefereeCountryExtract:
    """The country of the referee of every tournament match.

    This is the base for a confederation bias feature. A referee from South
    America statistically allows a different game than one from Europe, and the
    pairing of referee confederation with team confederation is in hardly any
    model.
    """

    OUTPUT_FILE: Path = ComputedFeaturePath.FOLDER / "referee_countries.csv"
    COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "match_id",
        "match_date",
        "referee",
        "referee_country",
    )


class TournamentCoachExtract:
    """The head coach of every squad on the Wikipedia squads pages.

    That is the base for coach features, that is a coach from abroad and how
    long a coach stays across tournaments. Only a line that starts with the
    word Coach or Manager counts, wiki markup in front of it is allowed. World
    Cup pages write Coach, European Championship pages write Manager. Matching
    only at the start keeps prose and association links out.
    """

    OUTPUT_FILE: Path = (
        ProjectPath.DATA_ROOT / "Tournament Squads (Wikipedia)" / "coaches.csv"
    )
    COLUMN_NAMES: tuple[str, ...] = (
        "tournament",
        "team",
        "coach",
        "coach_country",
        "foreign_coach",
    )

    TEAM_HEADING_PATTERN: str = r"^===\s*([^=]+?)\s*===\s*$"
    COACH_LINE_PATTERN: str = (
        r"^[;:'*\s]*(?:Head\s+)?(?:[Cc]oach|[Mm]anager)\s*:\s*(.+)$"
    )
    COUNTRY_FLAG_PATTERN: str = r"\{\{(?:flagicon|fb)\|([A-Za-z ]{2,20})\}\}"
    WIKI_LINK_PATTERN: str = r"\[\[[^\]]+\]\]"
    READABLE_LINK_PATTERN: str = r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]"
