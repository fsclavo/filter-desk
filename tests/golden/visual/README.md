# Visual regression baselines

`smith_basic.png` is a fixed matplotlib/Agg Smith chart generated from the
three-point synthetic result in `test_visual_regression.py` at 100 dpi.

The comparison uses a tolerant pixel metric rather than an exact hash because
antialiasing can vary slightly between environments. Visual regression runs on
the Linux offscreen baseline; Windows is covered by package smoke/self-test.
