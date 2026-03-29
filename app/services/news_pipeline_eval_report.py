# ruff: noqa: E501

"""HTML report rendering for news pipeline eval runs."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from app.models.news_pipeline_eval_models import (
    NewsPipelineEvalCase,
    NewsPipelineEvalRunConfig,
    NewsPipelineEvalRunResult,
    NewsPipelineEvalSuiteResult,
)


def write_news_pipeline_eval_html_report(
    *,
    cases: list[NewsPipelineEvalCase],
    suite: NewsPipelineEvalSuiteResult,
    output_path: Path,
    report_title: str | None = None,
) -> Path:
    """Render a static HTML report for one or more eval runs."""
    case_by_id = {case.case_id: case for case in cases}
    rendered_cases = [
        _render_case_section(case=case_by_id[result.case_id], result=result)
        for result in suite.results
        if result.case_id in case_by_id
    ]
    comparison_rows = "".join(_render_comparison_row(result=result) for result in suite.results)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    title = report_title or "News Pipeline Eval Report"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f4efe6;
      --panel: #fffdf8;
      --panel-strong: #fff7ea;
      --ink: #17202a;
      --muted: #57606a;
      --line: rgba(23, 32, 42, 0.12);
      --accent: #a44716;
      --accent-soft: rgba(164, 71, 22, 0.10);
      --success: #0f766e;
      --warn: #b45309;
      --danger: #b42318;
      --shadow: 0 18px 50px rgba(23, 32, 42, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(164, 71, 22, 0.16), transparent 32%),
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.10), transparent 28%),
        var(--bg);
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    a {{
      color: inherit;
    }}
    .page {{
      width: min(1280px, calc(100vw - 48px));
      margin: 0 auto;
      padding: 40px 0 64px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(255, 247, 234, 0.96), rgba(255, 253, 248, 0.94));
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 28px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 12px;
      color: var(--accent);
      margin-bottom: 12px;
    }}
    h1, h2, h3 {{
      font-family: Charter, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      margin: 0;
      font-weight: 600;
    }}
    h1 {{
      font-size: clamp(34px, 5vw, 56px);
      max-width: 10ch;
      line-height: 0.95;
      margin-bottom: 12px;
    }}
    .hero p {{
      max-width: 72ch;
      margin: 0;
      color: var(--muted);
      font-size: 16px;
    }}
    .meta-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .meta-card, .case-panel, .bullet-card, .item-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
    }}
    .meta-card {{
      padding: 14px 16px;
    }}
    .meta-card .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .meta-card .value {{
      font-size: 26px;
      margin-top: 4px;
    }}
    .case-list {{
      display: grid;
      gap: 20px;
    }}
    .comparison-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: var(--shadow);
      padding: 22px;
      margin-bottom: 20px;
    }}
    .comparison-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    .comparison-table th,
    .comparison-table td {{
      padding: 12px 10px;
      border-top: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    .comparison-table th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-top: none;
    }}
    .case-panel {{
      padding: 22px;
    }}
    .case-header {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      margin-bottom: 18px;
    }}
    .case-header p {{
      margin: 8px 0 0;
      color: var(--muted);
      max-width: 72ch;
    }}
    .pill-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }}
    .pill {{
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      border: 1px solid var(--line);
      background: var(--panel-strong);
    }}
    .pill.success {{
      color: var(--success);
      border-color: rgba(15, 118, 110, 0.18);
      background: rgba(15, 118, 110, 0.08);
    }}
    .pill.warn {{
      color: var(--warn);
      border-color: rgba(180, 83, 9, 0.18);
      background: rgba(180, 83, 9, 0.08);
    }}
    .pill.danger {{
      color: var(--danger);
      border-color: rgba(180, 35, 24, 0.18);
      background: rgba(180, 35, 24, 0.08);
    }}
    .case-grid {{
      display: grid;
      grid-template-columns: 1.2fr 2fr;
      gap: 18px;
    }}
    .subsection {{
      background: linear-gradient(180deg, rgba(255, 247, 234, 0.52), rgba(255, 253, 248, 0.92));
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
    }}
    .subsection h3 {{
      font-size: 22px;
      margin-bottom: 12px;
    }}
    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.72);
      padding: 12px;
    }}
    .stat .label {{
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .stat .value {{
      font-size: 24px;
    }}
    .mix-list, .finding-list, .artifact-list {{
      margin: 0;
      padding-left: 18px;
    }}
    .finding-list li {{
      margin-bottom: 8px;
    }}
    .artifact-list li + li {{
      margin-top: 6px;
    }}
    .bullet-stack, .item-stack {{
      display: grid;
      gap: 14px;
    }}
    .bullet-card {{
      padding: 18px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 247, 234, 0.72));
    }}
    .bullet-card h4 {{
      margin: 0 0 8px;
      font-size: 22px;
      font-family: Charter, "Iowan Old Style", "Palatino Linotype", Georgia, serif;
    }}
    .bullet-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .bullet-card p {{
      margin: 0 0 14px;
    }}
    .citation-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .item-card {{
      padding: 12px;
      background: rgba(255, 255, 255, 0.76);
      box-shadow: none;
      border-radius: 14px;
    }}
    .item-card h5 {{
      margin: 0 0 6px;
      font-size: 15px;
    }}
    .item-card p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .muted {{
      color: var(--muted);
    }}
    .section-sep {{
      height: 1px;
      background: var(--line);
      margin: 18px 0;
    }}
    @media (max-width: 980px) {{
      .page {{
        width: min(100vw - 24px, 1280px);
      }}
      .case-grid {{
        grid-template-columns: 1fr;
      }}
      .case-header {{
        flex-direction: column;
      }}
      .pill-row {{
        justify-content: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="eyebrow">News Pipeline Eval</div>
      <h1>{escape(title)}</h1>
      <p>
        Static inspection view for end-to-end news pipeline runs. This report compares input corpus
        composition, summary-path behavior, final digest bullets, cited evidence, and uncited items
        so you can evaluate what the curation step kept or dropped.
      </p>
      <div class="meta-strip">
        <div class="meta-card"><div class="label">Cases</div><div class="value">{suite.case_count}</div></div>
        <div class="meta-card"><div class="label">Passed</div><div class="value">{sum(1 for result in suite.results if result.passed)}</div></div>
        <div class="meta-card"><div class="label">Generated</div><div class="value">{escape(generated_at)}</div></div>
        <div class="meta-card"><div class="label">Overall</div><div class="value">{'PASS' if suite.passed else 'CHECK'}</div></div>
      </div>
    </section>
    <section class="comparison-panel">
      <h2>Run Comparison</h2>
      <p class="muted">Embedding model and threshold settings are shown directly from each saved artifact.</p>
      <table class="comparison-table">
        <thead>
          <tr>
            <th>Case</th>
            <th>Embedding Model</th>
            <th>Thresholds</th>
            <th>Bullets</th>
            <th>Unique Cited</th>
            <th>Coverage</th>
            <th>Summary Path</th>
          </tr>
        </thead>
        <tbody>
          {comparison_rows}
        </tbody>
      </table>
    </section>
    <section class="case-list">
      {''.join(rendered_cases)}
    </section>
  </main>
</body>
</html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _render_case_section(
    *,
    case: NewsPipelineEvalCase,
    result: NewsPipelineEvalRunResult,
) -> str:
    rows = _case_rows(case)
    row_count = len(rows)
    cited_ids = {news_item_id for bullet in result.bullets for news_item_id in bullet.news_item_ids}
    coverage_ratio = (len(cited_ids) / result.source_count) if result.source_count else 0.0
    platform_mix = Counter(_row_platform(row) for row in rows)
    scope_mix = Counter(_row_scope(row) for row in rows)
    title_only_rows = sum(1 for row in rows if _is_title_only_row(row))
    cited_user_items, cited_global_items = _split_cited_scope_counts(rows=rows, cited_ids=cited_ids)
    findings = _derive_case_findings(
        row_count=row_count,
        result=result,
        coverage_ratio=coverage_ratio,
        title_only_rows=title_only_rows,
        user_row_count=scope_mix.get("user", 0),
        cited_user_items=cited_user_items,
    )
    bullet_cards = "".join(_render_bullet_card(bullet=bullet, rows=rows) for bullet in result.bullets)
    uncited_cards = "".join(_render_item_card(row=row) for row in _uncited_rows(rows=rows, cited_ids=cited_ids))
    artifact_paths = _artifact_paths_for_case(case.case_id)

    return f"""
    <article class="case-panel">
      <div class="case-header">
        <div>
          <h2>{escape(case.case_id)}</h2>
          <p>{escape(case.description or "No description provided.")}</p>
        </div>
        <div class="pill-row">
          <span class="pill {'success' if result.passed else 'danger'}">{'Passed' if result.passed else 'Failed'}</span>
          <span class="pill">{escape(case.mode.title())}</span>
          <span class="pill">{escape(case.input_mode)}</span>
          {_render_config_pills(result.run_config)}
          <span class="pill {'warn' if row_count > result.source_count else ''}">{row_count} input / {result.source_count} digest candidates</span>
        </div>
      </div>
      <div class="case-grid">
        <section class="subsection">
          <h3>Overview</h3>
          <div class="stats-grid">
            <div class="stat"><div class="label">Processed</div><div class="value">{result.processed_count}</div></div>
            <div class="stat"><div class="label">Generated Summaries</div><div class="value">{result.generated_summary_count}</div></div>
            <div class="stat"><div class="label">Reused Summaries</div><div class="value">{result.reused_summary_count}</div></div>
            <div class="stat"><div class="label">Final Bullets</div><div class="value">{len(result.bullets)}</div></div>
            <div class="stat"><div class="label">Unique Cited</div><div class="value">{len(cited_ids)}</div></div>
            <div class="stat"><div class="label">Coverage</div><div class="value">{coverage_ratio:.1%}</div></div>
          </div>
          <ul class="finding-list">{''.join(f'<li>{escape(finding)}</li>' for finding in findings)}</ul>
          <div class="section-sep"></div>
          <h3>Corpus Mix</h3>
          <ul class="mix-list">{''.join(f'<li><strong>{escape(label)}</strong>: {count}</li>' for label, count in platform_mix.most_common())}</ul>
          <div class="section-sep"></div>
          <h3>Scope Mix</h3>
          <ul class="mix-list">
            {''.join(f'<li><strong>{escape(label)}</strong>: {count}</li>' for label, count in scope_mix.items())}
          </ul>
          <div class="section-sep"></div>
          <h3>Artifacts</h3>
          <ul class="artifact-list">
            <li><a href="{escape(artifact_paths['case'])}">Case JSON</a></li>
            <li><a href="{escape(artifact_paths['artifact'])}">Result JSON</a></li>
          </ul>
          <p class="muted">
            Digest title: <strong>{escape(result.digest_title or "Untitled digest")}</strong>
          </p>
          <p class="muted">
            Citation validity: <strong>{result.citation_validity:.2f}</strong> ·
            User-scoped cited: <strong>{cited_user_items}</strong> ·
            Global cited: <strong>{cited_global_items}</strong> ·
            Title-only inputs: <strong>{title_only_rows}</strong>
          </p>
        </section>
        <section class="subsection">
          <h3>Final Digest</h3>
          <div class="bullet-stack">{bullet_cards or '<p class="muted">No bullets generated.</p>'}</div>
          <div class="section-sep"></div>
          <h3>Uncited Input Sample</h3>
          <div class="item-stack">{uncited_cards or '<p class="muted">Every candidate item was cited.</p>'}</div>
        </section>
      </div>
    </article>"""


def _render_bullet_card(*, bullet: Any, rows: list[dict[str, Any]]) -> str:
    position = _bullet_value(bullet, "position")
    topic = _bullet_value(bullet, "topic")
    details = _bullet_value(bullet, "details")
    news_item_ids = _bullet_value(bullet, "news_item_ids") or []
    cited_cards = "".join(
        _render_item_card(row=_row_for_news_item_id(rows=rows, news_item_id=news_item_id))
        for news_item_id in news_item_ids
        if _row_for_news_item_id(rows=rows, news_item_id=news_item_id) is not None
    )
    return f"""
      <article class="bullet-card">
        <div class="bullet-meta">
          <span class="pill">{position}</span>
          <span class="pill">{len(news_item_ids)} citations</span>
        </div>
        <h4>{escape(str(topic))}</h4>
        <p>{escape(str(details))}</p>
        <div class="citation-grid">{cited_cards}</div>
      </article>"""


def _render_item_card(*, row: dict[str, Any] | None) -> str:
    if row is None:
        return ""
    title = _row_title(row)
    source = _row_source_label(row)
    platform = _row_platform(row)
    scope = _row_scope(row)
    url = _row_url(row)
    url_html = f'<p><a href="{escape(url)}">{escape(url)}</a></p>' if url else ""
    return f"""
      <article class="item-card">
        <h5>{escape(title)}</h5>
        <p>{escape(source)} · {escape(platform)} · {escape(scope)}</p>
        {url_html}
      </article>"""


def _artifact_paths_for_case(case_id: str) -> dict[str, str]:
    base = Path(".tmp/news_pipeline_eval")
    return {
        "case": str((base / "cases" / f"{case_id}.json").resolve()),
        "artifact": str((base / f"{case_id}.json").resolve()),
    }


def _render_comparison_row(*, result: NewsPipelineEvalRunResult) -> str:
    unique_cited_items = len(
        {news_item_id for bullet in result.bullets for news_item_id in bullet.news_item_ids}
    )
    coverage_ratio = (unique_cited_items / result.source_count) if result.source_count else 0.0
    config = result.run_config or NewsPipelineEvalRunConfig()
    model = config.embedding_model or "default"
    thresholds = (
        f"{config.primary_similarity_threshold:.2f} / {config.secondary_similarity_threshold:.2f}"
        if config.primary_similarity_threshold is not None
        and config.secondary_similarity_threshold is not None
        else "default"
    )
    summary_path = (
        f"{result.generated_summary_count} generated / {result.reused_summary_count} reused"
    )
    return (
        "<tr>"
        f"<td><strong>{escape(result.case_id)}</strong><br><span class=\"muted\">{escape(config.label or '')}</span></td>"
        f"<td>{escape(model)}</td>"
        f"<td>{escape(thresholds)}</td>"
        f"<td>{len(result.bullets)}</td>"
        f"<td>{unique_cited_items}</td>"
        f"<td>{coverage_ratio:.1%}</td>"
        f"<td>{escape(summary_path)}</td>"
        "</tr>"
    )


def _render_config_pills(config: NewsPipelineEvalRunConfig | None) -> str:
    if config is None:
        return ""
    pills: list[str] = []
    if config.label:
        pills.append(f'<span class="pill">{escape(config.label)}</span>')
    if config.embedding_model:
        pills.append(f'<span class="pill">{escape(config.embedding_model)}</span>')
    if (
        config.primary_similarity_threshold is not None
        and config.secondary_similarity_threshold is not None
    ):
        pills.append(
            '<span class="pill">'
            f"{config.primary_similarity_threshold:.2f} / {config.secondary_similarity_threshold:.2f}"
            "</span>"
        )
    return "".join(pills)


def _case_rows(case: NewsPipelineEvalCase) -> list[dict[str, Any]]:
    if case.input_mode == "scraped_items":
        return case.scraped_items
    return case.news_item_records


def _row_for_news_item_id(
    *,
    rows: list[dict[str, Any]],
    news_item_id: int,
) -> dict[str, Any] | None:
    index = news_item_id - 1
    if index < 0 or index >= len(rows):
        return None
    return rows[index]


def _bullet_value(bullet: Any, key: str) -> Any:
    if isinstance(bullet, dict):
        return bullet.get(key)
    return getattr(bullet, key)


def _row_title(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or row.get("raw_metadata") or {}
    article = metadata.get("article") if isinstance(metadata, dict) else {}
    summary = metadata.get("summary") if isinstance(metadata, dict) else {}
    candidates = [
        row.get("article_title"),
        row.get("summary_title"),
        summary.get("title") if isinstance(summary, dict) else None,
        article.get("title") if isinstance(article, dict) else None,
        row.get("title"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "Untitled"


def _row_source_label(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or row.get("raw_metadata") or {}
    candidates = [
        row.get("source_label"),
        metadata.get("source_label") if isinstance(metadata, dict) else None,
        metadata.get("source") if isinstance(metadata, dict) else None,
        row.get("platform"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return "Unknown"


def _row_platform(row: dict[str, Any]) -> str:
    candidate = row.get("platform")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return "unknown"


def _row_scope(row: dict[str, Any]) -> str:
    candidate = row.get("visibility_scope")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()
    return "global"


def _row_url(row: dict[str, Any]) -> str | None:
    metadata = row.get("metadata") or row.get("raw_metadata") or {}
    article = metadata.get("article") if isinstance(metadata, dict) else {}
    candidates = [
        row.get("article_url"),
        row.get("canonical_story_url"),
        row.get("url"),
        article.get("url") if isinstance(article, dict) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _is_title_only_row(row: dict[str, Any]) -> bool:
    summary_key_points = row.get("summary_key_points")
    if isinstance(summary_key_points, list) and summary_key_points:
        return False
    if isinstance(row.get("summary_text"), str) and row["summary_text"].strip():
        return False
    summary_title = row.get("summary_title")
    return isinstance(summary_title, str) and bool(summary_title.strip())


def _split_cited_scope_counts(
    *,
    rows: list[dict[str, Any]],
    cited_ids: set[int],
) -> tuple[int, int]:
    cited_user_items = 0
    cited_global_items = 0
    for news_item_id in cited_ids:
        row = _row_for_news_item_id(rows=rows, news_item_id=news_item_id)
        if row is None:
            continue
        if _row_scope(row) == "user":
            cited_user_items += 1
        else:
            cited_global_items += 1
    return cited_user_items, cited_global_items


def _uncited_rows(
    *,
    rows: list[dict[str, Any]],
    cited_ids: set[int],
    limit: int = 12,
) -> list[dict[str, Any]]:
    uncited: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if index in cited_ids:
            continue
        uncited.append(row)
        if len(uncited) >= limit:
            break
    return uncited


def _derive_case_findings(
    *,
    row_count: int,
    result: NewsPipelineEvalRunResult,
    coverage_ratio: float,
    title_only_rows: int,
    user_row_count: int,
    cited_user_items: int,
) -> list[str]:
    findings: list[str] = []
    dropped = row_count - result.source_count
    if dropped > 0:
        findings.append(
            f"Candidate cap dropped {dropped} processed items before digest curation."
        )
    if result.generated_summary_count == 0:
        findings.append("No fresh summaries were generated in this run.")
    else:
        findings.append(
            f"{result.generated_summary_count} items went through live summary generation."
        )
    if coverage_ratio < 0.1:
        findings.append(
            f"Curation cited only {len({nid for bullet in result.bullets for nid in bullet.news_item_ids})} "
            f"unique items out of {result.source_count} digest candidates."
        )
    if title_only_rows > 0:
        findings.append(
            f"{title_only_rows} inputs were title-only summaries, which can suppress fresh summarization."
        )
    if user_row_count > 0 and cited_user_items == 0:
        findings.append("No user-scoped items survived into the final cited set.")
    if result.failures:
        findings.extend(result.failures)
    return findings
