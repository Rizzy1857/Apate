from enum import Enum

class AgingProfile(Enum):
    STATIC = "STATIC"       # Unchanging (e.g. /bin)
    CONFIG = "CONFIG"       # Rarely changes (e.g. /etc)
    LOG = "LOG"             # Grows steadily (e.g. /var/log)
    CACHE = "CACHE"         # High churn, size fluctuates (e.g. /var/cache)
    TEMP = "TEMP"           # Very high churn, short lived (e.g. /tmp)
    USER_DATA = "USER_DATA" # Moderately dynamic (e.g. /home)

def determine_profile(path: str) -> AgingProfile:
    if path.startswith("/var/log"): return AgingProfile.LOG
    if path.startswith("/var/cache"): return AgingProfile.CACHE
    if path.startswith("/tmp") or path.startswith("/var/tmp"): return AgingProfile.TEMP
    if path.startswith("/home"): return AgingProfile.USER_DATA
    if path.startswith("/etc"): return AgingProfile.CONFIG
    return AgingProfile.STATIC
