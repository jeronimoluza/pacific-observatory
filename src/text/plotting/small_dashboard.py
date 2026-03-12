"""Generate a small dashboard HTML with three tabs."""

import importlib.util
import os
from pathlib import Path


def _load_interactive():
    try:
        from src.text.plotting import interactive as interactive_mod

        return interactive_mod
    except Exception:
        interactive_path = Path(__file__).resolve().parent / "interactive.py"
        spec = importlib.util.spec_from_file_location("interactive", interactive_path)
        if not spec or not spec.loader:
            raise ImportError("Could not load interactive module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _build_dashboard_html(topic_bump, topics_epu, actors_epu):
    template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Small Dashboard</title>
    <style>
        :root {{
            --bg: #f6f7fb;
            --panel: #ffffff;
            --text: #1e2432;
            --muted: #667085;
            --accent: #1d77b2;
            --border: #e3e7ef;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding: 16px;
        }}
        .shell {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            box-shadow: 0 12px 30px rgba(30, 36, 50, 0.08);
            overflow: hidden;
        }}
        .header {{
            padding: 16px 18px 10px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .title {{ font-size: 1.1em; font-weight: 700; }}
        .subtitle {{ color: var(--muted); font-size: 0.9em; }}
        .tabs {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .tab {{
            border: 1px solid var(--border);
            background: #fff;
            color: var(--text);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .tab.is-active {{
            background: var(--accent);
            color: #fff;
            border-color: var(--accent);
        }}
        .tab:hover {{ border-color: var(--accent); }}
        .tab-panel {{ display: none; }}
        .tab-panel.is-active {{ display: block; }}
        .frame-wrap {{
            height: 80vh;
            min-height: 520px;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: 0;
        }}
        .actions {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.85em;
        }}
        .actions a {{
            color: var(--accent);
            text-decoration: none;
            border-bottom: 1px dashed transparent;
        }}
        .actions a:hover {{ border-bottom-color: var(--accent); }}
        @media (max-width: 760px) {{
            .frame-wrap {{ height: 75vh; min-height: 420px; }}
        }}
    </style>
</head>
<body>
    <div class="shell">
        <div class="header">
            <div>
                <div class="title">Small Dashboard</div>
                <div class="subtitle">Uncertainty topics and EPU views</div>
            </div>
            <div class="tabs" role="tablist">
                <button class="tab is-active" type="button" data-tab="tab-1">Uncertainty Topics</button>
                <button class="tab" type="button" data-tab="tab-2">Topics EPU</button>
                <button class="tab" type="button" data-tab="tab-3">Actors EPU</button>
            </div>
            <div class="actions">
                <a id="open-tab" href="{topic_bump}" target="_blank" rel="noopener">Open tab</a>
            </div>
        </div>
        <div class="tab-panel is-active" id="tab-1" data-src="{topic_bump}">
            <div class="frame-wrap"><iframe src="{topic_bump}" title="Uncertainty Topics"></iframe></div>
        </div>
        <div class="tab-panel" id="tab-2" data-src="{topics_epu}">
            <div class="frame-wrap"><iframe src="{topics_epu}" title="Topics EPU"></iframe></div>
        </div>
        <div class="tab-panel" id="tab-3" data-src="{actors_epu}">
            <div class="frame-wrap"><iframe src="{actors_epu}" title="Actors EPU"></iframe></div>
        </div>
    </div>
    <script>
        const tabs = Array.from(document.querySelectorAll('.tab'));
        const panels = Array.from(document.querySelectorAll('.tab-panel'));
        const openLink = document.getElementById('open-tab');

        function setActiveTab(tabId) {{
            tabs.forEach(t => t.classList.toggle('is-active', t.dataset.tab === tabId));
            panels.forEach(p => p.classList.toggle('is-active', p.id === tabId));
            const panel = document.getElementById(tabId);
            if (panel && openLink) {{
                openLink.href = panel.dataset.src || '#';
            }}
            if (window.localStorage) {{
                window.localStorage.setItem('small-dashboard-tab', tabId);
            }}
        }}

        tabs.forEach(tab => {{
            tab.addEventListener('click', () => setActiveTab(tab.dataset.tab));
        }});

        const saved = window.localStorage ? window.localStorage.getItem('small-dashboard-tab') : null;
        if (saved && document.getElementById(saved)) {{
            setActiveTab(saved);
        }}
    </script>
</body>
</html>"""
    return template.format(
        topic_bump=topic_bump,
        topics_epu=topics_epu,
        actors_epu=actors_epu,
    )


def generate_dashboard(output_dir, topic_bump, topics_epu, actors_epu):
    dashboard_path = output_dir / "small_dashboard.html"
    with open(dashboard_path, "w") as f:
        f.write(_build_dashboard_html(topic_bump, topics_epu, actors_epu))
    print(f"Created {dashboard_path}")


if __name__ == "__main__":
    interactive = _load_interactive()

    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "outputs" / "text"
    output_dir = project_root / "docs/images/interactive/text"

    countries = [d for d in os.listdir(data_dir) if (data_dir / d).is_dir()]

    topic_bump_name = "topic_attribution_pic.html"
    topics_epu_name = "epu_topics_pic.html"
    actors_epu_name = "epu_actors_pic.html"

    interactive.gen_topic_attribution_html(
        countries,
        data_dir,
        output_dir / topic_bump_name,
        default_top_n=5,
        default_months=12,
    )
    interactive.gen_epu_topics_html(countries, data_dir, output_dir / topics_epu_name)
    interactive.gen_epu_actors_html(countries, data_dir, output_dir / actors_epu_name)

    generate_dashboard(output_dir, topic_bump_name, topics_epu_name, actors_epu_name)
