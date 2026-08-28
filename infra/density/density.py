"""Measure series density from the resolve manifests, without fetching a page.

The manifests carry url, timestamp and digest for every capture, which is
enough to answer the only question that decides whether price *series* are
achievable: how often does Common Crawl revisit the same product page, over
what span, and did the page actually change between visits.

Digest is the sharp instrument. A repeated identical digest means the payload
was byte-identical, so the price cannot have moved; distinct digests are an
upper bound on distinct price points. Capture count alone overstates both.

One normalisation matters more than it looks. The same product page appears as
http:// before a site's TLS migration and https:// after, and CC records those
as different urls. Left alone that splits nearly every pre-2018 series in two
at the migration date, which is exactly where the long history lives.
"""
import json
import os

import duckdb

DATA = os.environ.get("DATA", "/data")
OUT = os.environ.get("OUT", "/out")
MEM = os.environ.get("MEM", "12GB")

READ = (
    "read_json('%s/*.jsonl.gz', "
    "columns={'url':'VARCHAR','timestamp':'VARCHAR',"
    "'digest':'VARCHAR','spider':'VARCHAR'}, "
    "format='newline_delimited', compression='gzip', ignore_errors=true)"
) % DATA


def dump(con, name, sql):
    rows = con.execute(sql).fetchall()
    cols = [d[0] for d in con.description]
    path = os.path.join(OUT, name + ".csv")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(",".join(cols) + "\n")
        for r in rows:
            fh.write(",".join("" if v is None else str(v) for v in r) + "\n")
    print("wrote %-22s %d rows" % (name + ".csv", len(rows)), flush=True)
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(DATA, "tmp"), exist_ok=True)
    con = duckdb.connect()
    con.execute("SET memory_limit='%s'" % MEM)
    con.execute("SET temp_directory='%s/tmp'" % DATA)
    con.execute("SET preserve_insertion_order=false")

    print("loading captures ...", flush=True)
    con.execute("""
        CREATE TABLE cap AS
        SELECT
          regexp_replace(
            regexp_replace(lower(url), '^https?://', ''), '^www\\.', ''
          ) AS key,
          spider,
          substr(timestamp, 1, 4) AS yr,
          substr(timestamp, 1, 6) AS ym,
          digest
        FROM %s
    """ % READ)

    n_cap, n_key, n_spider = con.execute(
        "SELECT count(*), count(DISTINCT key), count(DISTINCT spider) FROM cap"
    ).fetchone()
    print("captures=%d  distinct_pages=%d  sources=%d"
          % (n_cap, n_key, n_spider), flush=True)

    # One row per product page. n_ver is the ceiling on how many distinct
    # prices that page can ever yield, however many times it was captured.
    con.execute("""
        CREATE TABLE page AS
        SELECT key,
               any_value(spider)          AS spider,
               count(*)                   AS n_cap,
               count(DISTINCT ym)         AS n_months,
               count(DISTINCT yr)         AS n_years,
               count(DISTINCT digest)     AS n_ver,
               min(yr)                    AS y0,
               max(yr)                    AS y1
        FROM cap GROUP BY key
    """)

    with open(os.path.join(OUT, "overall.json"), "w", encoding="utf-8") as fh:
        json.dump({"captures": n_cap, "pages": n_key, "sources": n_spider},
                  fh, indent=2)

    dump(con, "captures_by_year",
         "SELECT yr, count(*) AS captures, count(DISTINCT key) AS pages "
         "FROM cap GROUP BY yr ORDER BY yr")

    dump(con, "captures_per_page",
         "SELECT least(n_cap, 21) AS n_captures, count(*) AS pages "
         "FROM page GROUP BY 1 ORDER BY 1")

    dump(con, "versions_per_page",
         "SELECT least(n_ver, 21) AS n_versions, count(*) AS pages "
         "FROM page GROUP BY 1 ORDER BY 1")

    # The bar that matters: repeat observations that actually differ, spread
    # over enough distinct months to be a trajectory rather than a burst.
    dump(con, "series_bar", """
        SELECT v.min_ver, m.min_months,
               count(*) AS pages,
               count(DISTINCT p.spider) AS sources
        FROM page p,
             (SELECT unnest([2,3,4,6,8,12]) AS min_ver) v,
             (SELECT unnest([2,3,6,12]) AS min_months) m
        WHERE p.n_ver >= v.min_ver AND p.n_months >= m.min_months
        GROUP BY 1, 2 ORDER BY 1, 2
    """)

    dump(con, "span_years",
         "SELECT (CAST(y1 AS INT) - CAST(y0 AS INT)) AS span_years, "
         "count(*) AS pages FROM page GROUP BY 1 ORDER BY 1")

    dump(con, "by_source", """
        SELECT spider,
               count(*)                                  AS pages,
               sum(n_cap)                                AS captures,
               sum(n_ver)                                AS versions,
               round(median(n_cap), 2)                   AS med_captures,
               round(sum(n_ver) * 1.0 / sum(n_cap), 3)   AS change_rate,
               sum(CASE WHEN n_ver >= 4 AND n_months >= 3
                        THEN 1 ELSE 0 END)               AS pages_series
        FROM page GROUP BY spider ORDER BY pages_series DESC
    """)

    tot_ver, = con.execute("SELECT sum(n_ver) FROM page").fetchone()
    print("\ndistinct content versions (ceiling on price points): %d"
          % tot_ver, flush=True)
    print("collapse ratio: %.2fx fewer than raw captures"
          % (n_cap / tot_ver if tot_ver else 0), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
