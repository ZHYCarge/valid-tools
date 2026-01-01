import os
from dataclasses import dataclass


def _default_data_dir() -> str:
    env_dir = os.environ.get("DATA_DIR")
    if env_dir:
        return env_dir
    if os.path.isdir("/data"):
        return "/data"
    return os.path.abspath("data")


@dataclass(frozen=True)
class Settings:
    tsa_url: str
    ots_calendar_urls: list[str]
    btc_block_hash_api: str
    ltc_block_hash_api: str
    btc_explorer_block_url: str
    ltc_explorer_block_url: str
    btc_explorer_height_url: str
    ltc_explorer_height_url: str
    data_dir: str
    db_dir: str
    files_dir: str
    logs_dir: str
    db_path: str
    basic_auth_user: str
    basic_auth_pass: str
    icp_info: str
    mps_info: str


def load_settings() -> Settings:
    data_dir = _default_data_dir()
    db_dir = os.path.join(data_dir, "db")
    files_dir = os.path.join(data_dir, "files")
    logs_dir = os.path.join(data_dir, "logs")
    db_path = os.path.join(db_dir, "evidence.db")
    tsa_url = os.environ.get("TSA_URL", "https://freetsa.org/tsr").strip()
    calendar_default = ",".join(
        [
            "https://a.pool.opentimestamps.org",
            "https://b.pool.opentimestamps.org",
            "https://a.pool.eternitywall.com",
            "https://ots.btc.catallaxy.com",
            "https://alice.btc.calendar.opentimestamps.org/",
        ]
    )
    calendar_env = os.environ.get("OTS_CALENDAR_URLS", calendar_default)
    ots_calendar_urls = [item.strip() for item in calendar_env.split(",") if item.strip()]
    btc_block_hash_api = os.environ.get(
        "BTC_BLOCK_HASH_API",
        "https://blockstream.info/api/block-height/{height}",
    ).strip()
    ltc_block_hash_api = os.environ.get(
        "LTC_BLOCK_HASH_API",
        "https://sochain.com/api/v2/get_block/LTC/{height}",
    ).strip()
    btc_explorer_block_url = os.environ.get(
        "BTC_EXPLORER_BLOCK_URL",
        "https://blockchair.com/bitcoin/block/{hash}",
    ).strip()
    ltc_explorer_block_url = os.environ.get(
        "LTC_EXPLORER_BLOCK_URL",
        "https://blockchair.com/litecoin/block/{hash}",
    ).strip()
    btc_explorer_height_url = os.environ.get(
        "BTC_EXPLORER_HEIGHT_URL",
        "https://blockchair.com/bitcoin/block/{height}",
    ).strip()
    ltc_explorer_height_url = os.environ.get(
        "LTC_EXPLORER_HEIGHT_URL",
        "https://blockchair.com/litecoin/block/{height}",
    ).strip()
    basic_auth_user = os.environ.get("BASIC_AUTH_USER", "admin")
    basic_auth_pass = os.environ.get("BASIC_AUTH_PASS", "admin")
    icp_info = os.environ.get("ICP_INFO") or os.environ.get("ICP-INFO") or ""
    mps_info = os.environ.get("MPS_INFO") or os.environ.get("MPS-INFO") or ""
    return Settings(
        tsa_url=tsa_url,
        ots_calendar_urls=ots_calendar_urls,
        btc_block_hash_api=btc_block_hash_api,
        ltc_block_hash_api=ltc_block_hash_api,
        btc_explorer_block_url=btc_explorer_block_url,
        ltc_explorer_block_url=ltc_explorer_block_url,
        btc_explorer_height_url=btc_explorer_height_url,
        ltc_explorer_height_url=ltc_explorer_height_url,
        data_dir=data_dir,
        db_dir=db_dir,
        files_dir=files_dir,
        logs_dir=logs_dir,
        db_path=db_path,
        basic_auth_user=basic_auth_user,
        basic_auth_pass=basic_auth_pass,
        icp_info=icp_info,
        mps_info=mps_info,
    )
