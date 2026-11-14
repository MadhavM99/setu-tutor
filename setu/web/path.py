"""The learning path: the six stages (letters to conversation) as a row of steps, each done, in progress or ahead.

Pure: it reads the three lists `ladder()` returns (done, in progress, later) and writes nothing. A stage counts as
done when every target in it is done; the first stage that is not done is the one in progress, so the learner always
sees exactly one "you are here". A stage with no content yet is shown as ahead, never as done.
"""
BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")


def build(can, now, later) -> list:
    out, current_set = [], False
    for band in BANDS:
        total = sum(1 for t in (*can, *now, *later) if t["band"] == band)
        done = sum(1 for t in can if t["band"] == band) + sum(1 for t in now if t["band"] == band and t["placed"])
        if total and done == total:
            state = "done"
        elif total and not current_set:
            state, current_set = "now", True
        else:
            state = "soon"
        out.append({"band": band, "stage_key": f"stage.{band}", "hint_key": f"path.{band.lower()}_hint",
                    "state": state, "done": done, "total": total})
    return out
