# NumPy / pandas Jupyter Lab

This project is a small, isolated learning workspace for NumPy and pandas.

## Quick Start

```bash
cd /home/lism/work/xlab/python/projects/py-numpy-pandas
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m ipykernel install --user --name xlab-numpy-pandas --display-name "xlab numpy/pandas"
jupyter lab --notebook-dir=.
```

Or use the helper script:

```bash
cd /home/lism/work/xlab/python/projects/py-numpy-pandas
bash scripts/start_jupyter.sh
```

The local server can also be started on a fixed port after dependencies are
installed:

```bash
bash scripts/run_jupyter.sh 8890
```

Open `notebooks/01_numpy_pandas_basics.ipynb` and select the `xlab numpy/pandas`
kernel if Jupyter does not pick it automatically.

## Layout

```text
py-numpy-pandas/
├── data/
│   └── sales.csv
├── notebooks/
│   └── 01_numpy_pandas_basics.ipynb
├── scripts/
│   └── start_jupyter.sh
├── requirements.txt
└── README.md
```

## Suggested Learning Order

1. NumPy array creation, dtype, shape, slicing.
2. Vectorized operations and broadcasting.
3. pandas `DataFrame` loading, selecting, filtering, and assignment.
4. `groupby`, aggregation, sorting, and pivot tables.
5. Exporting results to CSV, Parquet, and Excel.
