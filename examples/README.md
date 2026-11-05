# FilterDesk example files

## Component library with manufacturer models

`component_library_models.json` contains the 23 starter parts and optional
frequency-dependent data:

- **Coilcraft 0603CS** inductors: 18 values from 3.9 nH to 270 nH with Q(f)
  points from the public Coilcraft 0603CS datasheet (Document 195-2, revised
  06/26/24). The lowest-frequency point is Qmin at the datasheet test
  frequency; the 900 MHz and 1.7 GHz points are typical.
- **Murata GRM1885C1H** C0G capacitors: catalog data only (`model: null`).
  No ESR curve is published in the starter source, so no curve was invented.

Load it with **Tools → Component library… → Load library…**, select a part and
inspect **Model**, **Q curve points**, **Source** and **Notes**. Then use
**Tools → Diplexer / multiplexer designer… → Assign parts… → Apply assigned
parts** to apply the model to simple L/C arms.

The JSON is a catalog-level, datasheet-derived example. Verify the current
manufacturer datasheet and your measurement setup before production. No vendor
SPICE/model deck is redistributed.

## Q/ESR curve CSV template

`component_curve_template.csv` shows the two-column format accepted by
**Tools → Component library… → Import Q/ESR curve…** and by
`filterdesk component-curve`:

```csv
frequency_hz,value
1M,100
10M,60
50M,35
```

Comments start with `#` or `!`, the header row is optional, and SI suffixes are
accepted (`1M`, `100m`). The curve is attached to the selected part as Q data
for an inductor or ESR data for a capacitor.

The same CSV format is accepted by **Model vs measurement…** and
`filterdesk component-compare`, which compare measured points with the selected
part's Q/ESR model and report RMS, maximum and relative error.

## Tutorial projects

The ready-to-open tutorial projects live in the packaged application assets:

`src/filterdesk/assets/examples/`

- `rx40m_preselector.filterdesk.json`
- `tx80m_lpf.filterdesk.json`
- `diplexer_2m.fdsys.json`
