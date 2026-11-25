# Installing Tarpitch

Tarpitch runs on the Python standard library alone. There is nothing to
download, no service to start, no database to create and no account to seed.

## 1. Prerequisites

| Requirement | Notes |
| ----------- | ----- |
| Python 3.9 or newer | `python3 --version` |
| A POSIX shell | Linux, macOS, or WSL on Windows |
| A terminal | Any monospace terminal; output is plain ASCII |

Nothing else is needed: no `pip` package for the tool itself, no compiler, no
system libraries.

## 2. Install

```bash
cd tarpitch
bash install.sh
```

The script:

1. verifies that `python3` is 3.9 or newer,
2. imports `tarpitch.py` as a self-check (fails loudly if the file is broken),
3. optionally installs the `tarpitch` console script (`pip install -e .`
   without build isolation -- skipped with a note if `setuptools` is missing),
4. installs the test runner from `requirements-dev.txt` if `pytest` is absent.

It is safe to re-run and it **exits when it is done** -- it never starts a
server or blocks a terminal. Run it as a normal user; it never calls `sudo` and
never installs system packages.

Package manager used: **pip** (the only manifest in the repository is
`pyproject.toml` + `requirements*.txt`).

## 3. Verify the install

```bash
python3 tarpitch.py --help
python3 tarpitch.py --version        # tarpitch 1.0.0
```

## 4. Optional: demo data

Tarpitch has no seed step: a fresh working directory is a valid empty
catalogue, and the tool prints copyable hints until you add a spot. To watch a
fully populated session (spots, visits across four seasons, rejected inputs, a
zero-gram chart and a corrupt store) run the scripted demo, which works in a
throwaway directory and leaves your own catalogue untouched:

```bash
bash demo.sh
```

To create a small catalogue by hand:

```bash
python3 tarpitch.py spots add pine-01 --note "north ridge"
python3 tarpitch.py spots add pine-02 --note "south slope"
python3 tarpitch.py visits log pine-01 2025-04-22 260
python3 tarpitch.py visits log pine-02 2025-05-02 150
python3 tarpitch.py report seasons
```

## 5. Run

```bash
python3 tarpitch.py spots list
python3 tarpitch.py visits list pine-01
python3 tarpitch.py report seasons
```

If the optional console script was installed, `tarpitch <command>` is
equivalent to `python3 tarpitch.py <command>`.

The catalogue is written to `.tarpitch.json` **in the directory you run the
command from**. Run every command for one catalogue from the same directory.

## 6. Test

```bash
python3 -m pytest
```

The suite drives the real script as a subprocess in throwaway directories, so it
needs no network and no fixtures on disk.

## Troubleshooting

| Symptom | Cause and fix |
| ------- | ------------- |
| `error: cannot read store file .tarpitch.json: invalid JSON ...` | The catalogue was edited by hand into invalid JSON. Repair it, or delete the file to start a fresh catalogue (existing entries are lost). |
| `error: unknown spot 'pine-09'` | Log visits only for spots that exist. `python3 tarpitch.py spots list` shows the ids you have. |
| `error: spot id already exists` | Ids are unique. Use the existing spot, or pick a new id. |
| Charts look narrow or wide | Bars are fixed at 30 cells and scale to the largest season total; the terminal width does not change them. |
| `error: grams must be a number` | Grams are whole base-10 numbers, 0 or more. Use `250`, not `250.5 g`. |
