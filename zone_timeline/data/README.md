# Bundled data

Everything the app needs offline lives in this folder. All files are plain text
(gzipped where they are big) so you can look at them with `zcat` or any editor.

| File | What it is | Source |
| --- | --- | --- |
| `curated.txt` | About 80 well-known cities, one per line: `name\|zone\|lat\|lon`. These win over GeoNames when names clash (so "London" is the one in England). | hand-written |
| `cities.txt.gz` | Roughly 6,000 cities with a population over 100,000. Lines starting with `@` map a country code to its name (`@IT\|Italy`); every other line is `name\|country code\|lat\|lon\|zone\|population\|alternate names separated by ;`. | [GeoNames](https://www.geonames.org/), CC BY 4.0 |
| `markets.txt` | The stock exchanges shown by `M`, one per line: `name\|zone\|lat\|lon\|sessions`. Sessions are local `HH:MM-HH:MM` ranges, comma separated for lunch breaks. Weekdays only, holidays are not modelled. | hand-written |
| `land_mask.bin.gz` | The world map: 1440 x 720 bytes, one per 0.25 degree cell, row-major from the north pole, each 0 (all sea) to 15 (all land). | rasterised from [Natural Earth](https://www.naturalearthdata.com/) 50m, public domain |

The time zone database itself is not here: it comes from the operating system (or the
`tzdata` package) through Python's `zoneinfo`. If `/usr/share/zoneinfo/zone.tab` exists it is
also read, so every zone name is searchable even if no city in the list uses it.
