# Recorded demonstrations

Two silent landscape MP4s accompany the source package as separate media assets:

| File | Content | Duration |
|---|---|---:|
| `laya-solo.mp4` | Original solo view, full-speed real GPU inference | 30.03 s |
| `laya-vs-jev.mp4` | Complete comparison, 100 moves per engine | 45.87 s |

Both are 1920 × 1080 H.264, encoded at 30 frames/s, with fast-start metadata for
web playback. Playback is 1× wall-clock speed. There is no audio track.

## Capture method

These videos capture the live browser interface, not a reconstructed game or
prerecorded model outputs. Browser screenshots were captured at approximately
6 frames/s and encoded using their original wall-clock timestamps. The 30 fps
container repeats captured images between updates; it does not imply 30 unique
captures/s. No motion interpolation, time compression, or simulated predictions
were added. The app itself samples game updates, so not every fast local move
appears as a distinct drawn frame.

The `?capture=1` URL uses a compact layout to fit gameplay and metrics into a
landscape frame. It changes presentation only. A visible `LIVE · 1×` label appears
in that layout. The separate JSON metadata records capture timestamps.

## Configuration and interpretation

- Windows, NVIDIA RTX 4070 SUPER, 12 GB VRAM.
- Local ggmlc Laya v0.9.1 executable and multilingual F16 GGUF.
- TypeSafe model reported by the API: `jev-1.13.0`.
- Board 24 × 16, initial length 6, seed 7, cycle safety enabled.
- Comparison: 100 moves per engine, both uncapped, one request per move.
- Original compact policy asks three questions per move.
- JEV latency includes the network round trip; local Laya is resident in memory.
- Both receive the same initial board. Later paths and prompts can diverge.
- Screen capture shares the computer with inference and can affect performance.

The captured comparison completed at approximately 110.42 moves/s for Laya and
2.58 moves/s for JEV. Median request times were 5.57 ms and 371.16 ms respectively.
These describe one live demonstration under different local/cloud execution
conditions, not a universal model-speed claim. Both scored one food at 100 moves.
Score is food eaten, not the number of steps. The shield and planner contribute
to survival; this does not establish unassisted strategic reasoning.

## Accompanying files

The media bundle includes:

- MP4 videos and JPEG posters.
- `manifest.json` and per-clip `*-capture.json` timestamps.
- `laya-solo-run.json` and `laya-vs-jev-run.json`: actual decision traces.
- `SHA256SUMS.txt` for checking the delivered files.

The solo trace may include the final in-flight move completed immediately after
capture stopped. Comparison traces contain the full 100-move run for each engine.
No API credential or local model-directory path is included in these records.

For publication, upload MP4s as GitHub Release assets or to your chosen video
platform, then add the resulting links to this README and the repository README.
Keep the local/cloud distinction and 1× capture method with the video description.
