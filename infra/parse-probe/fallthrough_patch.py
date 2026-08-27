P = ("/Users/jeronimoluza/wb/pacificobservatory/repo/template-repo/src/prices/"
     "cc_warc_fetcher.py")
src = open(P).read()

OLD = '''    def _parse_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Rows for one archived page: the spider's hook, else the selectors.

        A `parse_html` hook may yield several rows per page (product variants,
        SKUs); the selector path always yields at most one.
        """
        if self.parse_html_fn is not None:
            try:
                return [r for r in self.parse_html_fn(html, url) if r]
            except Exception:
                logger.debug(f"parse_html failed for {url}", exc_info=True)
                return []
        extracted = self._extract_data_from_html(html)
        if extracted:
            return [extracted]
        if not self.selectors:
            # Neither a hook nor selectors — try the spider-independent
            # schema.org/OpenGraph surfaces, then a framework hydration
            # payload (Next.js flight), before giving up on the page.
            rows = rows_from_jsonld(html, url)
            if rows:
                return rows
            row = row_from_meta(html, url)
            if row:
                return [row]
            return rows_from_next_flight(html, url)
        return []
'''

NEW = '''    def _generic_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Spider-independent tiers: schema.org/OpenGraph, then Next.js flight.

        These surfaces are standardised, so they survive the site redesigns
        that invalidate a spider's era-specific selectors. That makes them the
        right last resort for archived HTML of any age.
        """
        rows = rows_from_jsonld(html, url)
        if rows:
            return rows
        row = row_from_meta(html, url)
        if row:
            return [row]
        return rows_from_next_flight(html, url)

    def _parse_rows(self, html: str, url: str) -> List[Dict[str, Any]]:
        """Rows for one archived page: the spider's hook, then the selectors,
        then the generic tiers.

        A `parse_html` hook may yield several rows per page (product variants,
        SKUs); the selector path always yields at most one.

        Every tier falls through to the next. The hook and the selectors are
        both written against *current* markup, so on an old capture they
        routinely match nothing — or match a name but not a price. Stopping
        there returned a silent zero for the page and never tried the
        standardised surfaces that would still have parsed it.
        """
        if self.parse_html_fn is not None:
            try:
                rows = [r for r in self.parse_html_fn(html, url) if r]
            except Exception:
                logger.debug(f"parse_html failed for {url}", exc_info=True)
                rows = []
            if rows:
                return rows
            return self._generic_rows(html, url)
        extracted = self._extract_data_from_html(html)
        # A row without a price is not a usable observation: half-matching
        # selectors (name still resolves, price class renamed) are the common
        # wrong-era failure, so treat that as a miss and fall through.
        if extracted.get("price"):
            return [extracted]
        generic = self._generic_rows(html, url)
        if generic:
            return generic
        return [extracted] if extracted else []
'''

assert src.count(OLD) == 1, "anchor not found exactly once: %d" % src.count(OLD)
open(P, "w").write(src.replace(OLD, NEW))
print("patched OK")
