from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="PRESS_")

    printer_host: str = "172.16.1.149"
    printer_raw_port: int = 9100
    printer_lpr_port: int = 515
    printer_ipp_port: int = 631

    safe_print_mode: str = "dry"

    repo_root: Path = Path(__file__).resolve().parent.parent
    jobs_dir: Path = Path(__file__).resolve().parent.parent / "tmp" / "jobs"
    icc_dir: Path = Path(__file__).resolve().parent.parent / "icc"

    estimator_config_csv: Path = (
        Path(__file__).resolve().parent.parent.parent
        / "truecolor-estimator"
        / "data"
        / "tables"
        / "config.v1.csv"
    )

    bind_host: str = "127.0.0.1"
    bind_port: int = 5273

    # Job retention. 0 disables purge. Walks settings.jobs_dir on startup.
    purge_jobs_after_days: int = 30


settings = Settings()
settings.jobs_dir.mkdir(parents=True, exist_ok=True)


def click_rates() -> dict[str, float]:
    rates = {"color": 0.0573, "bw": 0.0117}
    csv = settings.estimator_config_csv
    if not csv.exists():
        return rates
    for line in csv.read_text().splitlines():
        parts = line.split(",", 2)
        if len(parts) < 2:
            continue
        key, val = parts[0].strip(), parts[1].strip()
        if key == "konica_ink_cost_per_sheet":
            try:
                rates["color"] = float(val)
            except ValueError:
                pass
        elif key == "konica_bw_cost_per_sheet":
            try:
                rates["bw"] = float(val)
            except ValueError:
                pass
    return rates
