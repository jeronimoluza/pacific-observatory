from waybackpy import WaybackMachineCDXServerAPI

url = "https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/"
user_agent = (
    "Mozilla/5.0 (Windows NT 5.1; rv:40.0) Gecko/20100101 Firefox/40.0"
)
end_timestamp = '2025-01-01'
cdx = WaybackMachineCDXServerAPI(url, user_agent, end_timestamp=end_timestamp)
for item in cdx.snapshots():
    print(item.archive_url)

# https://web.archive.org/web/20220928054939/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20230208095556/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20230925123634/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20240518062838/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20241006003317/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20250211175336/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20250519110626/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
# https://web.archive.org/web/20250908211823/https://rbpatel.com.fj/product/betty-crocker-super-moist-vanilla-cake-mix-540g/
