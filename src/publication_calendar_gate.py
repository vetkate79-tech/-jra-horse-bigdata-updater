"""Fail-closed publication eligibility, independent of weekly generation state."""
from datetime import date

def publication_eligible(today, state, official_race_keys, weekly_race_keys, sealed_race_keys):
    """Official keys must come from a verified calendar/card source; None means unknown."""
    date.fromisoformat(today)
    if official_race_keys is None:
        raise RuntimeError("OFFICIAL_MEETING_UNKNOWN")
    def unique_keys(keys, source):
        values = list(keys)
        unique = set(values)
        if len(values) != len(unique):
            raise RuntimeError("DUPLICATE_RACE_KEYS:" + source)
        return unique

    official = unique_keys(official_race_keys, "official")
    weekly = unique_keys(weekly_race_keys, "weekly")
    sealed = unique_keys(sealed_race_keys, "sealed")
    if not official:
        if weekly or sealed:
            raise RuntimeError("NON_MEETING_CARD_CONFLICT")
        if state not in ("SEALED", "NO_UPCOMING_RACES"):
            raise RuntimeError("UNRESOLVED_SEAL_STATE")
        return False
    if state != "SEALED" or weekly != official or sealed != official:
        raise RuntimeError("CURRENT_MEETING_INCOMPLETE")
    return True
