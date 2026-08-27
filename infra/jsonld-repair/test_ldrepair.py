"""Checks for the JSON-LD repair: it must fix the observed malformations
without changing what a well-formed blob means."""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ldrepair import parse_ld  # noqa: E402

fails = []


def check(label, cond):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        fails.append(label)


print("clean input is untouched")
clean = '{"@type":"Product","name":"A","offers":{"price":"9.99"}}'
v, how = parse_ld(clean)
check("parses at strict stage", how == "strict")
check("one value", len(v) == 1)
check("price preserved exactly", v[0]["offers"]["price"] == "9.99")
check("round-trips", v[0] == json.loads(clean))

print("\nfairprice: two objects concatenated in one script tag")
two = ('{"@type":"Product","name":"A","offers":{"price":"1.50"}}'
       '{"@type":"Product","name":"B","offers":{"price":"2.50"}}')
v, how = parse_ld(two)
check("both objects recovered", len(v) == 2)
check("strict stage suffices", how == "strict")
check("names A,B", [x["name"] for x in v] == ["A", "B"])
check("prices intact", [x["offers"]["price"] for x in v] == ["1.50", "2.50"])

print("\nyahoo_shopping_tw: literal undefined")
u = '{"@type":"Product","name":"Y","sku":undefined,"offers":{"price":"7"}}'
v, how = parse_ld(u)
check("recovered", len(v) == 1)
check("sku became null", v[0]["sku"] is None)
check("price intact", v[0]["offers"]["price"] == "7")
check("stage is jslit", how == "jslit")

print("\nNaN / Infinity")
v, _ = parse_ld('{"a":NaN,"b":-Infinity,"c":1}')
check("both nulled, c intact", v and v[0] == {"a": None, "b": None, "c": 1})

print("\nfairprice: raw control chars inside a string")
c = '{"@type":"Product","name":"A\tB","offers":{"price":"3.00"}}'
v, how = parse_ld(c)
check("recovered", len(v) == 1)
check("tab became space", v[0]["name"] == "A B")
check("price intact", v[0]["offers"]["price"] == "3.00")

print("\nau_pay_market: stray backslash from Shift_JIS 0x5C trail byte")
b = '{"@type":"Product","name":"\x83\\\x83g","offers":{"price":"1200"}}'
v, how = parse_ld(b)
check("recovered", len(v) == 1)
check("price intact", v and v[0]["offers"]["price"] == "1200")
check("name is a string", v and isinstance(v[0]["name"], str))

print("\nvalid escapes must NOT be mangled")
e = r'{"name":"a\"b\\c\/d\nEé","p":1}'
v, _ = parse_ld(e)
check("valid escapes preserved", v and v[0]["name"] == 'a"b\\c/d\nEé')

print("\ntrailing comma")
v, _ = parse_ld('{"a":1,"b":2,}')
check("recovered", v and v[0] == {"a": 1, "b": 2})

print("\narray at top level and @graph still work")
v, _ = parse_ld('[{"@type":"Product","name":"A"},{"@type":"Offer","price":2}]')
check("list preserved", v and isinstance(v[0], list) and len(v[0]) == 2)

print("\ngenuinely broken input stays broken (no false rescue)")
v, how = parse_ld('this is not json at all')
check("no values", not v)
check("reported unparseable", how == "unparseable")

print("\npartial decode is not accepted over a full one")
p = '{"@type":"Product","name":"A"} {"@type":"Product","name":undefined}'
v, how = parse_ld(p)
check("both recovered via jslit", len(v) == 2)
check("not a partial stage", not how.endswith("_partial"))

print("\nempty input")
v, how = parse_ld("")
check("no values, no crash", v == [])

print("\n%d checks failed" % len(fails))
sys.exit(1 if fails else 0)
