# VNA measurement and holdout protocol

This protocol is part of the validation pack. It is intentionally repeatable and
records enough metadata to tell a **fit** capture from a **holdout** capture.

## 1. Calibration and reference plane

1. Warm up the VNA for the manufacturer's recommended time.
2. Perform a full two-port calibration (SOLT or the kit available) at the
   connector plane used for the filter.
3. Record the calibration type, calibration kit, reference plane, cable types,
   adapters and terminations.
4. Do not change cables or adapters between the fit and holdout captures.
5. Keep the filter in the same enclosure, orientation and termination for both
   captures.

## 2. Captures

- Capture **fit.s2p** first.
- Disconnect/reconnect the filter, or repeat the sweep, and capture
  **holdout.s2p** without changing the calibration.
- Use the same frequency grid, power and IF bandwidth for both files.
- Save a `.vna.json` sidecar next to each capture, or at least next to the fit
  capture.

Example metadata:

```json
{
  "vna_model": "NanoVNA V2",
  "calibration": "SOLT",
  "reference_plane": "SMA connector plane",
  "cables": "30 cm RG316",
  "connectors": "SMA",
  "terminations": "50 ohm loads",
  "fixture": "filter in shielded box",
  "temperature_c": 23.0,
  "measured_at": "2026-10-26",
  "operator": "",
  "notes": "repeat capture after reconnect"
}
```

The sidecar path for `fit.s2p` is `fit.s2p.vna.json`.

## 3. Fit and evaluation

```bash
filterdesk tune-vna fit.s2p \
  --holdout holdout.s2p \
  --family chebyshev_type_i --response low_pass --order 4 \
  --cutoff 100M --ripple 0.1 \
  --bound-mode local --json
```

- `fit.s2p` is used to choose component values.
- `holdout.s2p` is **only evaluated after fitting** and never changes the fit.
- The output reports fit RMS, holdout RMS, per-S11/S21 RMS, points and quality
  notes (high RMS, values at bounds, delay at bound, holdout much worse than fit).
- If the metadata sidecar exists, the CLI reads it automatically; `--metadata`
  can point to a different JSON file.

## 4. Interpretation

- Magnitude-only data may not uniquely identify every component.
- Phase/delay fitting is optional and depends on the reference plane and cable
  delay.
- A low fit RMS with a poor holdout RMS is a warning, not a success.
- Component values at a bound are a warning that the fit is constrained.
- The result is a model-based trim, not a guarantee that the physical hardware
  matches the simulation.

## 5. Current status

The workflow and synthetic holdout tests are implemented. The two real captures
are reserved as external holdout data, not used to tune the algorithm. Hardware
validation remains P0 until those captures and their metadata are recorded.
