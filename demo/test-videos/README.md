# GuardX Test Videos

Free stock videos for local YOLO person-detection testing. All verified with
YOLOv8n (persons detected in every sampled video).

| # | File | Scene | YOLO test |
|---|------|-------|-----------|
| 1 | `1-hotel-entrance-couple-720p.mp4` | Couple walks into luxury hotel entrance (46s, 720p) | 5/5 frames, max 3 persons |
| 2 | `2-hotel-lobby-couple-720p.mp4` | Couple walks into modern hotel lobby (19s, 720p) | 3/5 frames, max 2 persons |
| 3 | `3-university-lobby-4k.mp4` | People walking through university lobby (19s, 4K) | 3/5 frames, max 2 persons |
| 4 | `4-crosswalk-crowd-720p.mp4` | Busy urban pedestrian crosswalk (19s, 720p) | 5/5 frames, max 12 persons |
| 5 | `5-alley-walkers-1080p.mp4` | Two women walk toward static camera, tree-lined street (34s, 1080p) | 5/5 frames, max 7 persons |

## Sources & licenses

- Videos 1–3: Pexels (free license, no attribution required)
  - https://www.pexels.com/video/elegant-hotel-arrival-of-fashionable-couple-33739159/
  - https://www.pexels.com/video/stylish-couple-entering-modern-hotel-interior-33739162/
  - https://www.pexels.com/video/modern-university-campus-lobby-with-people-walking-38469386/
- Videos 4–5: Pixabay (Pixabay Content License, free to use)
  - https://pixabay.com/videos/street-crosswalk-people-walking-173333/
  - https://pixabay.com/videos/alley-people-walk-street-ukraine-39837/

## Usage

Add as a camera in the GuardX dashboard (Vision → + Add camera), paste the
local file path, press Start, draw a restricted zone, and watch incidents fire.
