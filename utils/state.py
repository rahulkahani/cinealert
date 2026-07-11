import json
import logging
import os
import tempfile

STATE_FILENAME = "state.json"


def load(state_dir: str) -> dict:
    path = os.path.join(state_dir, STATE_FILENAME)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        logging.warning("Could not read state file %s (%s). Starting fresh.", path, e)
        return {}


def save(state_dir: str, data: dict) -> None:
    os.makedirs(state_dir, exist_ok=True)
    path = os.path.join(state_dir, STATE_FILENAME)
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
