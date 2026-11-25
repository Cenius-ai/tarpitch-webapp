# Using Tarpitch

A walkthrough of every command and every state it can print. Commands are shown
as `tarpitch ...`; prepend `python3 tarpitch.py` if you did not install the
console script.

## The three screens

| Screen | Command | States |
| ------ | ------- | ------ |
| Spot catalogue | `tarpitch spots list` | empty hint, populated table, rejected add |
| Visit log | `tarpitch visits list <spot>` | empty hint, populated table, unknown spot |
| Seasonal flow | `tarpitch report seasons [--spot <id>]` | populated chart, empty hint, unknown spot |

## 1. Spot catalogue

Add your first tapping spot:

```bash
$ tarpitch spots add pine-01 --note "north ridge"
Added spot pine-01 (created 2025-03-18, note: north ridge)
```

The `created` date is captured automatically as today's ISO date. Ids are
trimmed and must be unique.

```bash
$ tarpitch spots list
Catalogue -- 3 spots
id       note         created
-------  -----------  ----------
pine-01  north ridge  2025-03-18
pine-02  south slope  2025-03-18
pine-03  creek bend   2025-03-19
```

Empty catalogue (the hint is copyable as-is):

```bash
$ tarpitch spots list
No spots in the catalogue yet.
Add your first tapping spot:
  tarpitch spots add pine-01 --note "north ridge"
```

Rejected ids -- one line on stderr, exit code 2, nothing stored:

```bash
$ tarpitch spots add pine-01
error: spot id already exists: pine-01
$ tarpitch spots add "   "
error: spot id cannot be blank; use an id such as pine-01
```

## 2. Visit log

One entry per tree visit: the date and the grams of resin collected.

```bash
$ tarpitch visits log pine-01 2025-04-22 260
Logged 260 g for pine-01 on 2025-04-22 (1 visit total)
```

```bash
$ tarpitch visits log pine-01 2025-05-02 250
$ tarpitch visits log pine-01 2025-07-19 310
$ tarpitch visits list pine-01
Visits for pine-01 -- 3 visits, 820 g
date        grams
----------  -----
2025-07-19    310 g
2025-05-02    250 g
2025-04-22    260 g
```

The list is newest first. A spot with no visits yet gets a copyable hint:

```bash
$ tarpitch visits list pine-03
Spot pine-03 has no visits logged yet.
Log the first visit (date is ISO YYYY-MM-DD, grams are whole grams):
  tarpitch visits log pine-03 2024-05-02 250
```

Every rejection exits 2, prints one line on stderr, and stores nothing:

```bash
$ tarpitch visits log pine-01 2025-05-02 abc
error: grams must be a number, got 'abc'
$ tarpitch visits log pine-01 2025-05-02 -5
error: grams cannot be negative, got '-5'
$ tarpitch visits log pine-01 2025-13-40 100
error: date must be a real YYYY-MM-DD date, got '2025-13-40'
$ tarpitch visits log ghost-01 2025-05-02 100
error: unknown spot 'ghost-01'; add it first with `tarpitch spots add ghost-01`
```

`0` grams is a legal visit -- a tree you checked but that gave nothing.

## 3. Seasonal flow

```bash
$ tarpitch report seasons
Seasonal flow -- all spots (15 visits, 2310 g)
season    grams  bar
------  -------  -------------------------------
spring    710 g  |####################
summer   1045 g  |##############################
autumn    450 g  |#############
winter    105 g  |###
peak: summer (1045 g)
```

All four seasons always print, in the fixed order spring, summer, autumn,
winter, with bars scaled to the largest total (30 cells). A season with no
resin prints `0 g` and a zero-length bar.

Narrow the chart to one spot:

```bash
$ tarpitch report seasons --spot pine-01
Seasonal flow -- spot pine-01 (8 visits, 1455 g)
season    grams  bar
------  -------  -------------------------------
spring    440 g  |########################
summer    550 g  |##############################
autumn    360 g  |####################
winter    105 g  |######
peak: summer (550 g)
```

An unknown spot is rejected and no chart is printed:

```bash
$ tarpitch report seasons --spot missing-01
error: unknown spot 'missing-01'; add it first with `tarpitch spots add missing-01`
```

Nothing logged yet:

```bash
$ tarpitch report seasons
No visits logged yet for all spots.
Log the first yield with:
  tarpitch visits log pine-01 2024-05-02 250
```

All-zero season set (visits logged, nothing collected):

```bash
$ tarpitch report seasons
Seasonal flow -- all spots (2 visits, 0 g)
season    grams  bar
------  -------  -------------------------------
spring      0 g  |
summer      0 g  |
autumn      0 g  |
winter      0 g  |
peak: none (every season is 0 g)
```

## 4. The store

`.tarpitch.json` sits in the directory you run the command from and is plain
indented JSON with a `spots` array and a `visits` array. Writes are atomic, so
an interrupted command cannot leave a half-written file. If the file is
unreadable, every command says so instead of printing a traceback:

```bash
$ tarpitch spots list
error: cannot read store file .tarpitch.json: invalid JSON (line 1, column 18); repair or remove the file to start over
```

## 5. Scripting it

Results go to stdout, diagnostics to stderr, and the exit code tells you what
happened (0 success, 1 unreadable store, 2 rejected input):

```bash
if tarpitch visits log pine-01 2025-05-02 250 >/dev/null 2>&1; then
    echo "visit recorded"
fi
```
