from .registry import register_cleaner


@register_cleaner
def clean_times_eswatini_url(url: str, base_url: str = None) -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("https://www.times.co.sz/readmore.php"):
        return url.replace("/readmore.php", "/news/readmore.php", 1)
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("readmore.php"):
        return f"https://www.times.co.sz/news/{url}"
    return url
