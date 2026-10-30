# FilterDesk — Master Backlog

**Purpose:** single actionable list of outstanding work, current status and
decisions. It is the first document to update when a feature, menu path, test
count or release changes.  
**Status:** living document.  
**Last verified:** 2026-10-29 · **App version:** 0.37.1 · **Released:**
[v0.37.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.37.0) ·
**Previous:**
[v0.36.0](https://github.com/fsclavo/filter-desk/releases/tag/v0.36.0) ·
**Next:** v0.37.1 release (shared frequency axis, pending CI/tag).

**Verification:** local suite **1123 passed**, 4 skipped (ngspice unavailable); coverage **82.85 %**.
Main CI: https://github.com/fsclavo/filter-desk/actions/runs/40984946178
Release workflow: https://github.com/fsclavo/filter-desk/actions/runs/40985903086

Legend: **P0** blocks release/correctness · **P1** completes a shipped feature ·
**P2** future/optional. Effort: **S** ≤ ½ day · **M** 1–3 days · **L** > 3 days.

---

## 1. Current GUI map

- **Design** — filter-only workflow: Synthesize + Analyze, Band filter wizard,
  Snap to E-series, Apply parasitics/Q, Monte-Carlo, Scale response, Optimize to limits,
  Component sensitivity, Parameter sweep, Check spec compliance, Tune to VNA,
  **Distributed microstrip realization**, Component submenu.
- **Tools** — independent calculators: Matching network, Attenuator pad, Coil
  calculator, **Transformer / balun / unun**, Microstrip line.
- **File** — project/Touchstone import and exports: BOM, SPICE, LTspice, Qucs,
  CSV and Smith chart; **Recent projects** for the last ten files.
- **Help** — Model confidence inventory and user manual.
- The transformer/balun/unun designer has only **Design** and **Model** tabs;
  winding diagrams were removed.

---

## 2. Completed after v0.11.0

- [x] Flags table: stretched/wrapped column, full tooltip and visible legend for
      `LF`, `SAT`, `FIT`, `HF`, `THERMAL`.
- [x] Removed the Winding diagram tab/SVG/build-sheet sidecar; only Design and
      Model remain.
- [x] Contextual filter **Model status** strip (synthesis, analysis, components,
      T1/BAL1).
- [x] Central confidence registry, Help → Model confidence, confidence badges in
      transformer/microstrip/VNA dialogs.
- [x] Build-sheet **Assumptions** section.
- [x] Cross-backend validation matrix (10 synthesis paths), ngspice CI job and
      `docs/validation-matrix.md`.
- [x] VNA measurement metadata sidecar, CLI holdout evaluation, fit-quality notes
      and `docs/vna-measurement-protocol.md`. Real captures remain P0.
- [x] Manual **Update spec from circuit** action: derives cutoff/center/bandwidth
      from the response while preserving family/order/topology; circuit untouched,
      undoable, with explicit preview.
- [x] Unified band filter wizard: Quick LP/HP/BP/BS presets plus a Guided
      requirements → candidate-order table workflow for every amateur and AM/FM
      broadcast preset; optional E24 snap; equal-port BPF/BSF use odd orders.
- [x] VHF/UHF presets: 2 m (144–148 MHz), 1.25 m (222–225 MHz, Region 2) and
      70 cm (420–450 MHz) added to the wizard and CLI.
- [x] Plot-state hardening: full preset-matrix regression verifies current
      harmonics, hidden cursors and data range at auto-fit time.
- [x] 4-port S-parameter foundation: `.s4p` mixed-mode transform with
      differential, common and cross-mode blocks (`filterdesk mixed-mode`).
- [x] 4-port GUI: **Tools → 4-port mixed-mode…** imports `.s4p`, shows the
      mixed-mode table and handles large files with a sampled view.
- [x] 4-port GUI plot: Sdd21/Sdc21/Scd21/Scc21 versus frequency.
- [x] 4-port export: full mixed-mode CSV and JSON from the GUI.
- [x] Contextual help: tooltips/status tips for Specification fields, plot
      tabs and main menu actions.
- [x] Debian build hygiene: `.deb` under `dist/` and automatic staging cleanup.
- [x] Coaxial stub notch: λ/4 open / λ/2 shorted cable calculator and CLI.
- [x] Coax cable presets and estimated notch depth/bandwidth/Q.
- [x] Coax notch response plot and CSV export.
- [x] Coax plot uses the shared SI/log-frequency axis with plain tick numbers.
- [x] Unsaved-changes close guard with Save / Discard / Cancel.
- [x] Measured-overlay legends are hidden until a Touchstone file is loaded;
      Smith chart and response plots no longer advertise empty `meas` traces.
- [x] Distributed microstrip v1: line/stub domain elements, ABCD/skrf, project
      v2, BOM geometry, schematic, experimental LP synthesis (order ≤ 3) and CLI.
- [x] **File → Recent projects** (up to ten files, persisted, missing-entry
      cleanup and clear action).
- [x] **Band Preset → Band Pass** uses order 5 so 50 Ω ports stay equal and no
      ideal output transformer T1 is inserted.
- [x] **Power stress** now uses a nodal solve with source/load, T1/BAL1 and
      distributed line/stub elements; Vpk/Ipk are no longer a constant-arm
      rule of thumb.
- [x] **Ruthroff 1:4 SPICE:** bootstrap TEM test netlist with floating balanced
      load, ngspice low-frequency validation and CLI/GUI export.
- [x] **Core AL audit:** FT37/FT50/FT82 sizes added for 31/52/61; all ferrite AL
      entries checked against Fair-Rite μi and nominal dimensions.
- [x] **Thermal guard:** suppression mixes 31/43/52 no longer extrapolate
      low-flux μ'' to a thermal rise; mix 61 remains estimated.
- [x] Measured-vs-simulated cursor readout with complex interpolation and
      `ΔS21`/`ΔS11`/`ΔVSWR`/`Δ∠S21`, hidden unless the measured overlay is shown.

---

## 3. v0.37.0 release

- [x] Plot estimated S21/S11 in the coax notch dialog.
- [x] Export full notch response to CSV with design metadata.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.37.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 4. v0.36.0 release

- [x] Add typical coax cable presets with frequency-dependent loss.
- [x] Add estimated notch response, depth, −3 dB bandwidth and loaded Q.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.36.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 5. v0.35.0 release

- [x] Add coax stub notch calculator and CLI (`open λ/4`, `short λ/2`).
- [x] Add Tools dialog with velocity factor, cable loss and physical length.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.35.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 6. v0.34.1 release

- [x] Write `.deb` output under `dist/`.
- [x] Remove the staging tree after each build; keep it only with `KEEP_DEB_STAGE=1`.
- [x] Clean the accumulated local `build/deb` artifacts.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.34.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 7. v0.34.0 release

- [x] Add Specification field and plot-tab tooltips.
- [x] Add status tips for main menu actions.
- [x] Translate all new help text to Spanish.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.34.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 8. v0.33.0 release

- [x] Add CSV/JSON export for 4-port mixed-mode results.
- [x] Export full frequency set with dB metrics and JSON references.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.33.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 9. v0.32.0 release

- [x] Add mixed-mode plot tab to the 4-port dialog.
- [x] Keep the table and sampled-view behavior.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.32.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 10. v0.31.1 release

- [x] Ask Save / Discard / Cancel when closing with unsaved changes.
- [x] Cancel a failed/cancelled save and keep the application open.
- [x] Keep headless package self-test from blocking on the prompt.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.31.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 11. v0.31.0 release

- [x] Add **Tools → 4-port mixed-mode…** with `.s4p` import and table.
- [x] Show Sdd21/Sdc21/Scd21/Scc21 and mixed-mode reference impedances.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.31.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 12. v0.30.0 release

- [x] Add 4-port `.s4p` mixed-mode transform and `filterdesk mixed-mode`.
- [x] Expose Sdd/Sdc/Scd/Scc with differential/common reference impedances.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.30.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 13. v0.29.4 release

- [x] Add all-preset plot-state regression matrix.
- [x] Verify current harmonics, hidden cursors and data range at auto-fit.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.29.4.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 14. v0.29.3 release

- [x] Hide stale cursor lines before the auto plot fit.
- [x] Add regression coverage for a cursor outside the new sweep.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.29.3.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 15. v0.29.2 release

- [x] Refresh harmonic markers before running the auto plot fit.
- [x] Add regression coverage for sequential presets with stale harmonics.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.29.2.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 16. v0.29.1 release

- [x] Refit the plot when the data frequency span changes and Auto is on.
- [x] Keep zoom when reanalysing the same sweep; skip fitting hidden panels.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.29.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 17. v0.29.0 release

- [x] Add Auto sweep mode with suggested ranges per filter response.
- [x] Preserve custom ranges and band-wizard sweeps; infer Auto on project load.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.29.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 18. v0.28.2 release

- [x] Refit plots after deliberate synthesis, wizard apply, scale or project load.
- [x] Keep manual zoom for tuning until the next deliberate synthesis.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.28.2.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 19. v0.28.1 release

- [x] Use resonance-preserving snap in the wizard with E24/E48/E96 choice.
- [x] Default to E96 above 100 MHz and warn when the snapped response misses target.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.28.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 20. v0.28.0 release

- [x] Add 2 m, 1.25 m (Region 2) and 70 cm band presets.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.28.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 21. v0.27.1 release

- [x] Apply the wizard band sweep to the visible range controls and undo.
- [x] Restrict AM/FM broadcast presets to Band-stop in the GUI.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.27.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 22. v0.27.0 release

- [x] Add unified Band filter wizard (Quick and Guided LP/HP/BP/BS).
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.27.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 23. v0.26.0 release

- [x] Add self-contained Debian/Ubuntu amd64 package and clean-container check.
- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.26.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage/`.deb` assets.
- [x] Release URL recorded above.

---

## 24. v0.25.1 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.25.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 25. v0.25.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.25.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 26. v0.24.1 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.24.1.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 27. v0.24.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.24.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 28. v0.23.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.23.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 29. v0.22.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.22.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 30. v0.21.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.21.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 31. v0.20.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.20.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 32. v0.19.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.19.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 33. v0.18.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.18.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 34. v0.17.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.17.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 35. v0.16.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.16.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 36. v0.15.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.15.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 37. v0.14.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.14.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 38. v0.13.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.13.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 39. v0.12.0 release

- [x] Bump `pyproject.toml`/`filterdesk.__version__` to 0.12.0.
- [x] CHANGELOG/manual/backlog updated.
- [x] Tag, publish and verify Windows/Linux/AppImage assets.
- [x] Release URL recorded above.

---

## 40. Open backlog

### P0 — release quality

- [x] **Clean-machine package acceptance:** AppImage and Windows installer run a
      headless `--self-test` on clean CI runners (GUI construction, synthesize,
      Touchstone import/export, BOM, project round-trip). Physical-desktop
      visual check remains the only manual residue. (S)
- [ ] **LTspice/Qucs external validation:** open representative netlists/schematics
      and confirm syntax, transformer ratio orientation and node mapping. (M)
- [ ] **VNA holdout (hardware):** run the two real captures through the new
      protocol and record calibration/reference-plane metadata. The tooling and
      synthetic holdout tests are ready. (M)

### P1 — validation / model depth

- [ ] **High-flux thermal validation:** replace low-flux μ'' estimates with vendor
      high-flux curves or measurements; validate FT140/FT240 temperature rise. (M/L)
      - 2026-10-28 audit: Fair-Rite's public power-loss-vs-flux curves cover
        power mixes (61/77/78/80/85); 31/43/52 are suppression mixes without
        public high-flux curves. Do not invent coefficients; wait for measured
        data or vendor curves.
      - 2026-10-28 guard: 31/43/52 now report thermal as not evaluated; only 61
        keeps the estimated low-flux thermal model.
- [x] **Guanella multi-line:** integer 1:N² Guanella ratios now use an explicit
      N-line parallel/series network.
- [x] **1:4 Ruthroff depth:** equal-delay bootstrap ABCD; other ratios remain
      first-order.
- [x] **Choke common-mode estimate:** series-choke `Zcm` and attenuation at
      `f_min` are reported separately from the differential 2-port.
- [x] **Choke common-mode sweep:** five-point `Zcm`/attenuation table and CLI
      JSON, separate from the differential 2-port.
- [x] **Mixed-mode 3-port + Guanella SPICE:** block-diagonal `Sdd/Scc`, GUI/CLI
      reporting and ngspice-validated Guanella differential export.
- [x] **Ruthroff 1:4 SPICE:** single bootstrap TEM line, floating load and
      ngspice low-frequency check.
- [ ] **Asymmetric 4-port/EM:** full cross-mode and 4-port behavior remain
      future work. (L)
      - 2026-10-29 v0.30.0: added the `.s4p` mixed-mode transform and CLI
        (`Sdd/Sdc/Scd/Scc`); v0.31.0 adds the GUI import/table. A physical
        asymmetric/EM device model remains future work.
- [x] **Distributed netlist v1:** line/stub elements are integrated into the
      domain, ABCD/skrf, project v2, BOM and an experimental order-1–3 LP
      synthesis. Full response coverage, higher orders, stub-only/Kuroda
      topologies and EM remain future work. (L)
- [x] **Installed-package regression:** CI now exercises Linux bundle/AppImage
      and the installed Windows app headlessly; see `docs/packaging.md`. (M)

### P1 — distribution / UX completeness

- [x] **Debian/Ubuntu `.deb` package (amd64):** build a self-contained package
      (Python, Qt and the scientific stack bundled, like the AppImage) targeting
      Ubuntu 22.04+/Debian 12+ (glibc 2.35 baseline), built in CI and attached
      automatically to the tag-triggered GitHub release as
      `FilterDesk-<ver>-amd64.deb`. Install to `/opt/filterdesk` with a
      `/usr/bin/filterdesk` symlink, a `.desktop` entry and the app icon;
      package name `filterdesk`, license Apache-2.0, maintainer
      "FilterDesk contributors" with the GitHub repository URL (no email).
      Add a clean-container install/uninstall check to the release workflow.
      Out of scope for now: `arm64`; macOS packaging is deferred (needs
      signing/notarization decisions). (M)
      - 2026-10-28 released in v0.26.0: `packaging/debian/build_deb.sh` and
        `verify_deb.sh`; release/acceptance workflows build the `.deb` and run
        install/self-test/removal in `ubuntu:22.04`.

- [x] **Unify Band Preset and HF band wizard:** replace the
      `Design → Band preset…` dialog with a single band-filter wizard (e.g.
      `Design → Band filter wizard…`) covering every preset kind
      (LPF/HPF/BPF/BSF) and the AM/FM broadcast rejection bands, with two modes:
      **Quick** (today's fixed Chebyshev-I order-5 preset) and **Guided**
      (requirements → candidate-order table → apply), keeping the optional E24
      snap. Chebyshev-I only for now. Requirements per kind: LPF/HPF use
      pass/stop edges + max IL/ripple + min attenuation; BPF uses the allocation
      as passband + guard + max IL/min attenuation; BSF/notch (including AM/FM)
      uses the allocation as stopband + guard + max IL/min attenuation. TX LPF
      candidates also report harmonic rejection at 2f/3f. Keep the order search
      2…12 and odd orders for equal ports (avoid the ideal T1). Update the
      Design menu, i18n, manual and tests; remove the old Band Preset dialog and
      menu action. (M/L)
      - Acceptance: every band×kind combination produces a valid spec/candidate
        table; Quick matches today's preset; Guided selects the lowest valid
        order; AM/FM notches included; the existing HF receive-BPF workflow is
        preserved as Guided BPF.
      - 2026-10-28 implemented in v0.27.0; the service supports all 52
        band×kind defaults, with LPF/HPF harmonic readout and odd-order BPF/BSF.
      - 2026-10-28 v0.27.1: the GUI restricts AM/FM broadcast presets to
        Band-stop (notch); the wizard now applies its band sweep to the visible
        range controls and restores them on undo.
      - 2026-10-28 v0.28.0: added 2 m, 1.25 m (Region 2) and 70 cm presets.
      - 2026-10-28 v0.28.1: wizard snap uses preserve-resonance strategy,
        offers E24/E48/E96 (E96 default above 100 MHz) and warns on degradation.
      - 2026-10-28 v0.28.2: one-shot plot auto-fit after deliberate synthesis,
        wizard apply, scale or project load; manual zoom is kept for tuning.

- [x] **Automatic sweep fit:** suggest a plotting range per filter kind
      (e.g. HPF 140 MHz ≈ 50 M–1 G), including harmonic coverage for TX LPF,
      and apply it only when the user has not customized the range (explicit
      **Auto** mode or equivalent). Preserve custom ranges used for VNA,
      limits and saved projects; update UI/session together and cover
      redo/undo. Keep the wizard's band-specific range. (M)
      - 2026-10-28 v0.29.0: Auto checkbox, suggested ranges per response,
        wizard band sweep preserved, custom ranges kept when Auto is off.
      - 2026-10-29 v0.29.1: Auto view also refits when a new result has a
        different frequency span; same-span reanalysis keeps the zoom.

### P2 — data / ergonomics

- [x] **Distributed SPICE export:** microstrip lines and stubs now export as
      lossless SPICE `T` elements, with open/short stub terminations; LTspice
      `.asc`/Qucs remain unsupported.
- [x] **Distributed LP orders 4–5:** bounded numerical fit with strict
      passband/stopband gates (post-v0.13.0, in `Unreleased`).
- [x] **Guanella multi-line model:** integer 1:N² ratios use an explicit N-line
      parallel/series network (post-v0.13.0).
- [x] **1:4 Ruthroff and choke common-mode estimate:** equal-delay bootstrap
      network plus separate `Zcm`/attenuation (post-v0.14.0).
- [x] **ABCD edge cases:** exact open/short/resonant arms are clamped to finite
      stand-ins; stress handles an open shunt without warnings.
- [x] **Winding realism:** DCR low/high, leakage and the selected option are
      persisted and shown in GUI/CLI/BOM.
- [x] **QA hardening:** SciPy independent LP/HP/BP/BS oracle, semantic
      diagram/SVG checks, Smith image baseline and `docs/qa-matrix.md`.
- [x] **Microstrip dispersion:** Kirschning-Jansen `eeff(f)`/`Z0(f)` for line and
      stub analysis.
- [x] **Open-end fringing:** Hammerstad open-stub length correction.
- [ ] **Distributed synthesis depth:** all-response distributed design,
      stub-only/Kuroda topologies, step discontinuities and hardware validation. (L)
      - 2026-10-28 spike: shunt-only unit-element/stub topologies reproduce a
        low-order BP passband numerically but not the stopband; HP/BS fail
        because they require series stubs (Kuroda) or coupled lines. Do not ship
        HP/BP/BS until series-stub/Kuroda support and a stopband gate exist.
      - 2026-10-28: deferred. The analytic lambda/4 shunt-stub BP also failed the
        stopband gate (lower selectivity than the lumped BP); IL limits do not
        fix it. Revisit only with coupled-line or lambda/2 resonator synthesis.

- [x] Confirm the estimated FT114/FT140-31 AL values and add more 31/52/61 core
      sizes with vendor-consistent material data. (M)
- [x] Persist the selected winding option in project/BOM notes.
- [x] Add DCR/leakage estimates per winding option (DCR at 20 °C; leakage from
      the coupling model).

### Parked by design

- Even-order elliptic synthesis (needs general unequal-R Darlington/Cauer).
- `.lct` import (no reliable oracle).
- Mid-ladder transformers/baluns (boundary insertion only).
- Full EM/3-D or coupled-inductor modeling.
- Physical winding drawings (removed; not considered reliable).

---

## 41. Ham-radio onboarding and discoverability

- [x] README/manual onboarding sections for radio amateurs: first-five-minute
      path, common tasks, glossary, Spanish introduction and natural search
      terms.
- [x] Package metadata description/keywords include amateur radio, homebrew,
      toroid, balun and VNA.

## 42. Maintenance rule

Every change must update, in the same commit:

1. `docs/BACKLOG.md` — status/checkboxes, test count, GUI/CLI paths.
2. `docs/user-manual.md` — user-facing workflow and limits.
3. `CHANGELOG.md` — user-visible changes, especially release entries.
4. `README.md` — feature bullets when the visible feature set changes.
5. Tests, i18n and `docs/validation-matrix.md` when models/validation change.
