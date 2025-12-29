"""Weekly attacker data analysis skeleton.

Questions:
- Most common 3-command sequences
- Sequences correlated with long sessions
- Where Layer 1 fails confidently
- Distribution of discovery patterns
"""

import os
import pandas as pd
from typing import List

DATA_DIR = os.environ.get("APATE_DATA_DIR", "data")
SESSIONS_CSV = os.path.join(DATA_DIR, "sessions.csv")
SEQUENCES_CSV = os.path.join(DATA_DIR, "sequences.csv")
OUTCOMES_CSV = os.path.join(DATA_DIR, "outcomes.csv")


def load_frames():
    sessions = pd.read_csv(SESSIONS_CSV) if os.path.exists(SESSIONS_CSV) else pd.DataFrame()
    sequences = pd.read_csv(SEQUENCES_CSV) if os.path.exists(SEQUENCES_CSV) else pd.DataFrame()
    outcomes = pd.read_csv(OUTCOMES_CSV) if os.path.exists(OUTCOMES_CSV) else pd.DataFrame()
    return sessions, sequences, outcomes


def top_3_command_sequences(sequences: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if sequences.empty:
        return pd.DataFrame()
    # Expect a column 'commands' with space-joined canonical commands
    sequences["triplet"] = sequences["commands"].str.split().apply(lambda cmds: " ".join(cmds[:3]) if len(cmds) >= 3 else None)
    return sequences["triplet"].value_counts().head(top_n).reset_index(name="count").rename(columns={"index": "triplet"})


def long_session_correlated_sequences(sessions: pd.DataFrame, sequences: pd.DataFrame) -> pd.DataFrame:
    if sessions.empty or sequences.empty:
        return pd.DataFrame()
    # Expect bucket column 'session_duration_bucket' and join on session_id
    df = sequences.merge(sessions[["session_id", "session_duration_bucket"]], on="session_id", how="left")
    return df[df["session_duration_bucket"].isin(["15-60m", ">60m"])]["commands"].value_counts().head(10).reset_index(name="count")


def main():
    sessions, sequences, outcomes = load_frames()
    print("Loaded:", {
        "sessions": len(sessions), "sequences": len(sequences), "outcomes": len(outcomes)
    })
    print("Top 3-command sequences:")
    print(top_3_command_sequences(sequences))
    print("Sequences correlated with long sessions:")
    print(long_session_correlated_sequences(sessions, sequences))


if __name__ == "__main__":
    main()
