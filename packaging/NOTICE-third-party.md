# FilterDesk — third-party notices

FilterDesk itself is licensed under the **Apache License 2.0**
(see `LICENSE`).

The packaged application bundles the following third-party components. This file
is copied next to the executable and into the release archives.

## Qt / PySide6 (LGPL-3.0)

The desktop application links **Qt** via **PySide6**, which is distributed under
the **GNU Lesser General Public License v3.0 (LGPL-3.0)**.

FilterDesk links Qt dynamically (the bundled `PySide6`/`Qt` shared libraries are
separate from the application Python code and can be replaced). In accordance
with the LGPL:

- The full LGPL-3.0 text ships in the `licenses/` folder of the distribution.
- Qt's source code is available from <https://download.qt.io/official_releases/qt/>.
- A written offer for the corresponding source of the bundled Qt version is
  available from the project maintainers; open an issue at
  <https://github.com/fsclavo/filter-desk/issues>.
- You may relink FilterDesk against a modified Qt as permitted by the LGPL.

## Python and scientific stack

Bundled at runtime with their own licenses:

- **Python** — PSF License.
- **NumPy** — BSD-3-Clause.
- **SciPy** — BSD-3-Clause.
- **scikit-rf** — BSD-3-Clause.
- **PyQtGraph** — MIT.
- **Matplotlib** — Matplotlib License (PSF-like, BSD-compatible).

See each project's distribution for the full license text.
