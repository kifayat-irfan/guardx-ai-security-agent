# GuardX test videos / fixtures

Small, freely-usable fixtures for Phase 2 vision tests. **Do not commit
large or copyrighted videos** — generated clips are gitignored (`*.mp4`).

## Fixtures

| File | Source | License | Purpose |
|------|--------|---------|---------|
| `bus.jpg` (810×1080, 134 KB) | https://ultralytics.com/images/bus.jpg — sample image from the Ultralytics docs | Free for demo/test use per Ultralytics (not redistributed commercially) | Real-inference fixture: contains several people; integration tests build a panning clip from it |

## Generated clips

`scripts/make_test_clip.py` builds `person_pan_test.mp4` (~100 KB, 60 frames)
from `bus.jpg` — deterministic, no copyrighted video needed.

Regenerate any time:

```bash
cd ~/workspace/guardx
python3 backend/.venv/bin/python scripts/make_test_clip.py
```
