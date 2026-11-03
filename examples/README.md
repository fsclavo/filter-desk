# FilterDesk example files

## Component library with manufacturer models

`component_library_models.json` contains the ten starter parts and optional
frequency-dependent data:

- **Coilcraft 0603CS** inductors: Q(f) points from the public Coilcraft 0603CS
  datasheet (Document 195, revised 06/26/24). The 250 MHz value is Qmin; the
  900 MHz and 1.7 GHz values are typical.
- **Murata GRM1885C1H** C0G capacitors: catalog data only (`model: null`).
  No ESR curve is published in the starter source, so no curve was invented.

Load it with **Tools → Component library… → Load library…**, select a part and
inspect **Model**, **Q curve points**, **Source** and **Notes**. Then use
**Tools → Diplexer / multiplexer designer… → Assign parts… → Apply assigned
parts** to apply the model to simple L/C arms.

The JSON is a catalog-level, datasheet-derived example. Verify the current
manufacturer datasheet and your measurement setup before production. No vendor
SPICE/model deck is redistributed.

## Tutorial projects

The ready-to-open tutorial projects live in the packaged application assets:

`src/filterdesk/assets/examples/`

- `rx40m_preselector.filterdesk.json`
- `tx80m_lpf.filterdesk.json`
- `diplexer_2m.fdsys.json`
