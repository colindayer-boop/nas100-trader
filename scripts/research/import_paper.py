#!/usr/bin/env python3
"""
import_paper.py — Automatic paper ingestion from PDF.

Extracts metadata from an academic paper PDF, classifies it against the trading
system's research framework, and generates an Obsidian-friendly note in
research/papers/. Never overwrites existing notes.

Usage:
    python scripts/research/import_paper.py path/to/paper.pdf
    python scripts/research/import_paper.py paper.pdf --url https://ssrn.com/...
    python scripts/research/import_paper.py paper.pdf --dry-run

Extraction pipeline:
  1. Extract raw text from PDF (pymupdf → pdftotext fallback)
  2. Parse bibliographic fields (title, authors, year, abstract)
  3. Classify: strategy, markets, timeframes, edge, limitations
  4. Assess: implementation difficulty, retail/prop feasibility
  5. Generate Obsidian note with frontmatter, backlinks, checklist

No production code touched. Research firewall respected.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PAPERS_DIR = os.path.join(REPO, "research", "papers")
RESULTS_DIR = os.path.join(REPO, "research", "results")
VAULT_RESEARCH_DIR = os.path.join(REPO, "vault", "02-Strategy-Research")


# ── PDF text extraction ─────────────────────────────────────────────────

def extract_text_pymupdf(path):
    """Extract text using pymupdf (fitz). Returns full text string."""
    try:
        import fitz
        doc = fitz.open(path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except ImportError:
        return None
    except Exception as e:
        print(f"[extract] pymupdf error: {e}")
        return None


def extract_text_pdftotext(path):
    """Extract text using external pdftotext binary. Returns string or None."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[extract] pdftotext error: {e}")
        return None


def extract_text(path):
    """Try pymupdf first, then pdftotext. Returns (text, method) or (None, None)."""
    text = extract_text_pymupdf(path)
    if text and text.strip():
        return text, "pymupdf"
    text = extract_text_pdftotext(path)
    if text and text.strip():
        return text, "pdftotext"
    return None, None


# ── Bibliographic parsing ───────────────────────────────────────────────

def extract_title(text, filename):
    """
    Extract paper title.
    Strategy: look for the title block on page 1, skipping headers,
    author names, affiliations. Titles tend to be longer lines with
    title-case or mixed case, often before the author list.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # Skip common header noise
    skip_patterns = [
        r"^submitted\s*:",
        r"^received\s*:",
        r"^accepted\s*:",
        r"^published\s*:",
        r"^doi\s*:",
        r"^https?://",
        r"^www\.",
        r"^\d{4}\s+wiley",
        r"^issn\s",
        r"^vol\.?\s*\d",
        r"^journal\s+of",
        r"^review\s+of",
        r"^\d+$",
    ]

    # Author-name heuristics: lines that look like "First Last, First Last"
    author_re = re.compile(
        r"^[A-Z][a-z]+\s+[A-Z]\.?\s*[A-Z]?[a-z]*(?:\s+[A-Z][a-z]+)?"
        r"(?:\s*,\s*[A-Z][a-z]+\s+[A-Z]\.?\s*[A-Z]?[a-z]*)*"
        r"(?:\s+and\s+[A-Z][a-z]+)?\s*$"
    )
    # Abstract heading
    abstract_re = re.compile(r"^(?:ABSTRACT|Abstract)\b", re.I)
    # Affiliation lines (contain @ or university keywords)
    affiliation_re = re.compile(r"@(?:[a-z]+\.)+[a-z]+|university|institute|department", re.I)

    candidates = []
    for i, line in enumerate(lines[:30]):
        line_lower = line.lower()
        if any(re.match(p, line_lower) for p in skip_patterns):
            continue
        if len(line) < 10:
            continue
        if len(line) > 300:
            continue
        words = line.split()
        if len(words) < 2:
            continue

        # Skip author-like lines
        if author_re.match(line) and ("," in line or " and " in line.lower()):
            continue
        # Skip affiliation lines
        if affiliation_re.search(line):
            continue
        # Skip lines that are part of the abstract
        if abstract_re.match(line):
            break

        candidates.append((i, line))
        if len(candidates) >= 5:
            break

    if candidates:
        # Pick the first multi-line title block (consecutive lines before authors)
        # or the longest candidate
        best = max(candidates, key=lambda c: len(c[1]))
        # But prefer the earliest substantial one if multiple lines form a title
        first = candidates[0]
        # If the first candidate is substantially long, use it
        if len(first[1]) > 20:
            return first[1]
        return best[1]

    # Fallback: derive from filename
    base = os.path.splitext(os.path.basename(filename))[0]
    base = base.replace("_", " ").replace("-", " ")
    return base.title()


def extract_authors(text, known_title=None):
    """
    Extract author names.
    Looks for common patterns near the top of the paper, skipping the title.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    abstract_re = re.compile(r"^(?:ABSTRACT|Abstract)\b", re.I)
    author_re = re.compile(
        r"^[A-Z][a-z]+\s+[A-Z]\.?\s*[A-Z]?[a-z]*(?:\s+[A-Z][a-z]+)?"
        r"(?:\s*,\s*[A-Z][a-z]+\s+[A-Z]\.?\s*[A-Z]?[a-z]*)*"
        r"(?:\s+and\s+[A-Z][a-z]+)?\s*$"
    )

    # Find candidate author lines (skip title and abstract)
    title_idx = -1
    if known_title:
        for i, line in enumerate(lines[:20]):
            if known_title.strip().lower() in line.strip().lower() or line.strip().lower() in known_title.strip().lower():
                title_idx = i
                break

    author_line = None
    for i, line in enumerate(lines[:40]):
        # Skip the title itself
        if i == title_idx:
            continue
        if known_title and (line.strip().lower() == known_title.strip().lower()):
            continue
        # Stop at abstract
        if abstract_re.match(line):
            break

        # "By John Smith"
        m = re.match(r"^(?:by\s+)([A-Z].+)", line, re.I)
        if m:
            author_line = m.group(1)
            break

        # Author patterns: Name with capitals, comma-separated
        if author_re.match(line):
            if "," in line or " and " in line.lower():
                author_line = line
                break
            # Single author (3-4 words max)
            if len(line.split()) <= 4:
                author_line = line
                break

    if author_line:
        author_line = re.sub(r"\d+", "", author_line)
        author_line = re.sub(r"[a-z]+@[a-z.]+", "", author_line, flags=re.I)
        author_line = re.sub(r"\s+", " ", author_line).strip(" ,;")
        return author_line

    return ""


def extract_year(text):
    """Extract publication year from text."""
    current_year = datetime.date.today().year
    # Look for years in reasonable range
    years = re.findall(r"\b(19[5-9]\d|20[0-4]\d)\b", text[:3000])
    if years:
        year = max(years)  # most recent year mentioned early is likely pub year
        if int(year) <= current_year:
            return int(year)
    return ""


def extract_abstract(text):
    """
    Extract abstract text.
    Looks for 'Abstract' heading and captures until next section.
    """
    # Pattern: "Abstract" followed by text until next heading
    patterns = [
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)\s*(?:\n|\.\s*)(.+?)(?=\n\s*(?:Keywords|JEL|1\.\s|Introduction|I\.\s|©|\*\*\*))",
        r"(?:^|\n)\s*(?:ABSTRACT|Abstract)[:\.\s]*(.+?)(?=\n\s*(?:Keywords|JEL|1\.\s|Introduction|I\.\s))",
    ]

    for pat in patterns:
        m = re.search(pat, text[:10000], re.DOTALL | re.IGNORECASE)
        if m:
            abstract = m.group(1).strip()
            # Clean whitespace
            abstract = re.sub(r"\n{2,}", "\n", abstract)
            abstract = re.sub(r" {2,}", " ", abstract)
            # Limit length
            if len(abstract) > 100:
                return abstract[:2000]
    return ""


def extract_keywords(text):
    """Extract keywords if present."""
    m = re.search(r"(?:Keywords?|Key\s+words)[:\.\s]*(.+?)(?=\n\s*(?:JEL|1\.\s|Introduction|\*\*\*|Classification))",
                  text[:10000], re.DOTALL | re.IGNORECASE)
    if m:
        kw = m.group(1).strip().rstrip(".")
        return [k.strip() for k in re.split(r"[;,]", kw) if k.strip()]
    return []


# ── Classification ──────────────────────────────────────────────────────

# Strategy type detection
STRATEGY_PATTERNS = {
    "momentum": [r"\bmomentum\b", r"\btsmom\b", r"\btime[- ]series momentum\b", r"trend[- ]?following"],
    "mean-reversion": [r"\bmean[- ]reversion\b", r"\brevert", r"\bcontrarian\b", r"\boversold\b"],
    "orb": [r"opening\s+range", r"\borb\b", r"opening\s+breakout"],
    "overnight": [r"\bovernight\b", r"\bond\b", r"close[- ]to[- ]open"],
    "volatility": [r"\bvolatility\b", r"\bvol[- ]?target", r"\bgarch\b", r"\bvar\b"],
    "arbitrage": [r"\barbitrage\b", r"\bpairs?\b", r"\bcointegration\b"],
    "microstructure": [r"\border\s+flow\b", r"\bdark\s+pool\b", r"limit\s+order\s+book", r"\bspread\b"],
    "sentiment": [r"\bsentiment\b", r"\bnews\b", r"\bsocial\s+media\b", r"\btwitter\b"],
    "machine-learning": [r"\bmachine\s+learning\b", r"\bdeep\s+learning\b", r"\bneural\s+net", r"\blstm\b", r"\btransformer\b"],
    "options": [r"\boption\b", r"\bvolatility\s+premium\b", r"\bselling\s+vol\b", r"\bgamma\b", r"\bdix\b", r"\bgex\b"],
    "macro": [r"\bmacro\b", r"\bregime\b", r"\bcycle\b", r"\binflation\b", r"\byield\b"],
    "seasonality": [r"\bseasonal\b", r"\bturn[- ]?of[- ]?month\b", r"\bholiday\b", r"\bjanuary\s+effect\b"],
    "factors": [r"\bfactor\b", r"\b fama\b", r"\bvalue\s+premium\b", r"\bsize\s+premium\b"],
}

MARKET_PATTERNS = {
    "US equities": [r"\bS&P\s?500\b", r"\bNASDAQ\b", r"\bNYSE\b", r"\bQQQ\b", r"\bSPY\b", r"\bstocks?\b", r"\bequit", r"\bCRSP\b"],
    "US sectors": [r"\bsector\b", r"\bindustry\b", r"\btechnology\b"],
    "global equities": [r"\bglobal\b", r"\binternational\b", r"\bdeveloped\b", r"\bemerging\b"],
    "commodities": [r"\bgold\b", r"\boil\b", r"\bsilver\b", r"\bcommodit", r"\bfutures?\b"],
    "forex": [r"\bforex\b", r"\bcurrency\b", r"\bFX\b", r"\bexchange\s+rate\b"],
    "crypto": [r"\bbitcoin\b", r"\bcrypto", r"\bBTC\b", r"\bethereum\b", r"\bETH\b"],
    "bonds": [r"\bbond\b", r"\btreasur", r"\byield\b", r"\bfixed\s+income\b"],
    "volatility": [r"\bVIX\b", r"\bvolatility\s+index\b", r"\bvariance\s+swap\b"],
}

TIMEFRAME_PATTERNS = {
    "intraday": [r"\bintraday\b", r"\bminute\b", r"\bhourly\b", r"\b5[- ]min", r"\b1[- ]min", r"\bopen(?:ing)?\s+range\b"],
    "daily": [r"\bdaily\b", r"\bday[- ]?trading\b"],
    "weekly": [r"\bweekly\b", r"\bweek\b"],
    "monthly": [r"\bmonthly\b", r"\bmonth\b"],
    "quarterly": [r"\bquarterly\b", r"\bquarter\b"],
}


def classify(text_lower, pattern_dict):
    """Return list of matched categories from a pattern dictionary."""
    matches = []
    for category, patterns in pattern_dict.items():
        for pat in patterns:
            if re.search(pat, text_lower):
                matches.append(category)
                break
    return matches


def detect_edge(text_lower):
    """
    Detect the core edge/mechanism described.
    """
    edges = []
    edge_signals = [
        (r"overnight.{0,30}(return|drift|premium)", "Overnight return premium"),
        (r"opening.{0,20}(range|breakout).{0,30}(signal|entry|profit)", "Opening range breakout signal"),
        (r"momentum.{0,20}(signal|entry|factor|return)", "Momentum continuation"),
        (r"mean[- ]reversion.{0,20}(signal|entry|return)", "Mean reversion"),
        (r"volatility.{0,20}(premium|selling|harvest)", "Volatility risk premium"),
        (r"liquidity.{0,20}(premium|return|effect)", "Liquidity premium"),
        (r"sentiment.{0,20}(signal|predict|return)", "Sentiment signal"),
        (r"(dark.{0,10}pool|dix|short.{0,10}interest).{0,20}(signal|predict|return)", "Dark pool / short interest signal"),
        (r"seasonal.{0,20}(effect|pattern|return)", "Seasonality effect"),
        (r"order.{0,10}flow.{0,20}(signal|predict|toxicity)", "Order flow / toxicity signal"),
    ]
    for pat, label in edge_signals:
        if re.search(pat, text_lower):
            edges.append(label)
    return edges if edges else ["Unclear from text — manual review needed"]


def detect_limitations(text_lower):
    """
    Detect stated or implied limitations.
    """
    limitations = []
    lim_signals = [
        (r"transaction\s+cost", "Transaction costs not fully modeled"),
        (r"slippage", "Slippage assumptions may be optimistic"),
        (r"survivorship\s+bias", "Survivorship bias in sample"),
        (r"look[- ]ahead\s+bias", "Look-ahead bias risk"),
        (r"data\s+snoop", "Data snooping / multiple testing"),
        (r"out[- ]of[- ]sample.{0,20}(fail|decay|degrad|weaker)", "Out-of-sample degradation"),
        (r"post[- ]publication.{0,20}(decay|degrad|weaker|fail)", "Post-publication decay"),
        (r"sample.{0,20}(small|limited|short)", "Limited sample size"),
        (r"intraday.{0,20}(data|requir)", "Requires high-frequency data"),
        (r"(colo|latency|HFT|co[- ]location)", "Requires low-latency infrastructure"),
    ]
    for pat, label in lim_signals:
        if re.search(pat, text_lower):
            limitations.append(label)
    return limitations if limitations else ["Not explicitly stated — manual review needed"]


def assess_implementation(text_lower, strategies, markets, timeframes):
    """
    Heuristic assessment of implementation difficulty.
    """
    difficulty = "Medium"
    reasons = []

    if any(s in strategies for s in ["machine-learning", "microstructure"]):
        difficulty = "Hard"
        reasons.append("Complex modeling or infrastructure required")
    elif any(s in strategies for s in ["arbitrage", "options"]):
        difficulty = "Medium"
        reasons.append("Requires specific data or instruments")

    if any("intraday" in tf for tf in timeframes):
        if "1-min" in str(timeframes):
            difficulty = "Hard" if difficulty != "Hard" else difficulty
            reasons.append("Tick/minute-level data needed")

    if any(m in markets for m in ["crypto"]):
        reasons.append("Crypto market — 24/7, exchange-specific")
    elif any(m in markets for m in ["forex"]):
        reasons.append("FX — may need interbank access")

    if not reasons:
        reasons.append("Standard data and execution requirements")

    return difficulty, reasons


def assess_retail_feasibility(text_lower, markets, timeframes, limitations):
    """Assess retail feasibility."""
    blockers = []
    if re.search(r"\bcolo\b|\bHFT\b|\bco[- ]location\b|microsecond", text_lower):
        blockers.append("Requires HFT/colo infrastructure")
    if re.search(r"\bAP\b|\bauthorized\s+participant\b", text_lower):
        blockers.append("Requires authorized participant access")
    if re.search(r"\binstitutional\b.{0,30}(data|access|infra)", text_lower):
        blockers.append("Institutional-grade data/infrastructure")
    if "Requires low-latency infrastructure" in limitations:
        blockers.append("Latency-sensitive")

    if blockers:
        return "Low", blockers
    return "Medium-High", ["Standard brokerage account sufficient"]


def assess_prop_feasibility(markets, timeframes, strategies):
    """Assess prop firm feasibility."""
    # Prop firms typically: CFD on indices, forex, gold, crypto; no US single stocks
    prop_ok = ["US equities", "commodities", "forex", "crypto", "volatility"]
    prop_markets = [m for m in markets if m in prop_ok]

    blockers = []
    if "US sectors" in markets and "US equities" not in markets:
        blockers.append("US single stocks not available on most prop firms")
    if "machine-learning" in strategies:
        blockers.append("Complex — hard to fit in prop firm risk limits")

    if blockers:
        return "Low-Medium", blockers
    if prop_markets:
        return "Medium-High", ["Tradeable as CFD/futures on most prop firms"]
    return "Unknown", ["Market coverage unclear — manual review needed"]


# ── Note generation ────────────────────────────────────────────────────

def slugify(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return s[:60] or "untitled"


def generate_note(filepath, title, authors, year, abstract, keywords,
                  strategies, markets, timeframes, edges, limitations,
                  impl_difficulty, impl_reasons, retail_feasibility, retail_reasons,
                  prop_feasibility, prop_reasons, url="", text_hash=""):
    """Generate the full Obsidian note content."""

    # Frontmatter
    fm_lines = [
        "---",
        f'type: research-paper',
        f'title: "{title}"',
        f'authors: "{authors}"',
        f'year: {year if year else ""}',
        f'url: "{url}"',
        f'status: unread',
        f'created: {datetime.date.today().isoformat()}',
        f'source_file: "{os.path.basename(filepath)}"',
        f'source_hash: "{text_hash[:16]}"',
        f'strategy_types: [{", ".join(strategies)}]',
        f'markets: [{", ".join(markets)}]',
        f'tags: [research, paper{", " + ", ".join(strategies) if strategies else ""}]',
        "---",
    ]

    # Body
    body_lines = [
        f"# {title}",
        "",
        f"**Authors:** {authors or 'Unknown'}  ",
        f"**Year:** {year or 'Unknown'}  ",
        f"**Source:** `{os.path.basename(filepath)}`  ",
        f"**URL:** {url or '(none)'}" if url else f"**URL:** (none)",
        "",
        "## Abstract",
        "",
        textwrap.fill(abstract, width=100) if abstract else "_Abstract not extracted — see source PDF._",
        "",
    ]

    if keywords:
        body_lines.append(f"**Keywords:** {', '.join(keywords)}")
        body_lines.append("")

    # Auto-classification
    body_lines += [
        "## Auto-Classification",
        "",
        f"**Strategy type:** {', '.join(strategies) if strategies else 'Unclassified'}",
        f"**Markets:** {', '.join(markets) if markets else 'Unclassified'}",
        f"**Timeframes:** {', '.join(timeframes) if timeframes else 'Unclassified'}",
        "",
        "**Edge / mechanism:**",
    ]
    for e in edges:
        body_lines.append(f"- {e}")

    body_lines += ["", "**Limitations detected:**"]
    for l in limitations:
        body_lines.append(f"- {l}")

    body_lines += [
        "",
        "## Feasibility Assessment (Auto)",
        "",
        f"**Implementation difficulty:** {impl_difficulty}",
    ]
    for r in impl_reasons:
        body_lines.append(f"- {r}")

    body_lines.append(f"\n**Retail feasibility:** {retail_feasibility}")
    for r in retail_reasons:
        body_lines.append(f"- {r}")

    body_lines.append(f"\n**Prop firm feasibility:** {prop_feasibility}")
    for r in prop_reasons:
        body_lines.append(f"- {r}")

    # Human review sections (from new_paper.py template)
    body_lines += [
        "",
        "## Claim",
        "_What the paper says works (strategy, instrument, reported Sharpe/returns)._",
        "",
        "## Honest assessment checklist",
        "- [ ] Out-of-sample or in-sample only?",
        "- [ ] Transaction costs included? At what level?",
        "- [ ] Sample period vs today — post-publication decay likely?",
        "      (SSRN intraday-momentum precedent: +1.32 in-sample, -0.80 after publication)",
        "- [ ] Retail-accessible, or needs AP/HFT/colo infrastructure?",
        "- [ ] Prop-tradeable instruments (CFD/futures), or US single stocks only?",
        "",
        "## Verdict",
        "_no-edge (default) | idea extracted -> link the idea note below._",
        "",
        "## Extracted ideas",
        "- (create with `python scripts/research/new_idea.py \"...\"` and link here)",
        "",
        "## Links",
        "[[Research Index]] | [[02-Strategy-Research/Gauntlet|Gauntlet]] | [[00 Dashboard]]",
        "",
    ]

    return "\n".join(fm_lines) + "\n" + "\n".join(body_lines)


# ── Obsidian vault cross-link ──────────────────────────────────────────

def update_vault_research_index(slug, title):
    """Append a link to vault/02-Strategy-Research/_index.md if it exists."""
    index_path = os.path.join(VAULT_RESEARCH_DIR, "_index.md")
    if not os.path.exists(index_path):
        return False

    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()

    link_line = f"- [[research/papers/{slug}|{title}]]"
    if link_line in content:
        return False  # already linked

    # Try to find a papers section, otherwise append
    papers_section = re.search(r"(## Papers.*?)(?=\n##|\Z)", content, re.DOTALL)
    if papers_section:
        insert_pos = papers_section.end() - 1 if content[papers_section.end()-1] != "\n" else papers_section.end()
        content = content[:insert_pos] + link_line + "\n" + content[insert_pos:]
    else:
        content += f"\n## Papers\n\n{link_line}\n"

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Import a research paper PDF and generate an Obsidian note."
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file to import",
    )
    parser.add_argument(
        "--url",
        default="",
        help="Source URL (SSRN/arXiv/DOI)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and display results without writing files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite if a note with the same slug exists (default: refuse)",
    )
    args = parser.parse_args()

    pdf_path = os.path.abspath(args.pdf_path)
    if not os.path.exists(pdf_path):
        print(f"ERROR: file not found: {pdf_path}")
        sys.exit(1)
    if not pdf_path.lower().endswith(".pdf"):
        print(f"ERROR: not a PDF: {pdf_path}")
        sys.exit(1)

    # 1. Extract text
    print(f"[extract] reading: {os.path.basename(pdf_path)}")
    text, method = extract_text(pdf_path)
    if not text:
        print("[extract] FAILED — no text extracted.")
        print("         Install pymupdf (pip install pymupdf) or pdftotext (brew install poppler)")
        sys.exit(1)
    print(f"[extract] method: {method}, {len(text)} chars")

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    text_lower = text.lower()

    # 2. Parse bibliographic fields
    title = extract_title(text, pdf_path)
    authors = extract_authors(text, known_title=title)
    year = extract_year(text)
    abstract = extract_abstract(text)
    keywords = extract_keywords(text)

    print(f"[parse] title:    {title}")
    print(f"[parse] authors:  {authors or '(not found)'}")
    print(f"[parse] year:     {year or '(not found)'}")
    print(f"[parse] abstract: {'found (' + str(len(abstract)) + ' chars)' if abstract else '(not found)'}")
    print(f"[parse] keywords: {', '.join(keywords) if keywords else '(none)'}")

    # 3. Classify
    strategies = classify(text_lower, STRATEGY_PATTERNS)
    markets = classify(text_lower, MARKET_PATTERNS)
    timeframes = classify(text_lower, TIMEFRAME_PATTERNS)
    edges = detect_edge(text_lower)
    limitations = detect_limitations(text_lower)

    print(f"[classify] strategies:  {', '.join(strategies) if strategies else '(none)'}")
    print(f"[classify] markets:     {', '.join(markets) if markets else '(none)'}")
    print(f"[classify] timeframes:  {', '.join(timeframes) if timeframes else '(none)'}")
    print(f"[classify] edges:       {len(edges)} detected")
    print(f"[classify] limitations: {len(limitations)} detected")

    # 4. Assess feasibility
    impl_difficulty, impl_reasons = assess_implementation(text_lower, strategies, markets, timeframes)
    retail_feasibility, retail_reasons = assess_retail_feasibility(text_lower, markets, timeframes, limitations)
    prop_feasibility, prop_reasons = assess_prop_feasibility(markets, timeframes, strategies)

    print(f"[assess] implementation: {impl_difficulty}")
    print(f"[assess] retail:         {retail_feasibility}")
    print(f"[assess] prop:           {prop_feasibility}")

    # 5. Generate note
    slug = slugify(f"{title}")
    if year:
        slug = slugify(f"{year}-{title}")

    note_content = generate_note(
        pdf_path, title, authors, year, abstract, keywords,
        strategies, markets, timeframes, edges, limitations,
        impl_difficulty, impl_reasons, retail_feasibility, retail_reasons,
        prop_feasibility, prop_reasons, url=args.url, text_hash=text_hash,
    )

    note_path = os.path.join(PAPERS_DIR, f"{slug}.md")

    # 6. Dry run stops here
    if args.dry_run:
        print(f"\n[dry-run] note would be: research/papers/{slug}.md")
        print(f"[dry-run] note length: {len(note_content)} chars")
        print(f"\n--- PREVIEW (first 60 lines) ---")
        for line in note_content.splitlines()[:60]:
            print(line)
        print("--- END PREVIEW ---")
        return

    # 7. Write note (no overwrite unless --force)
    os.makedirs(PAPERS_DIR, exist_ok=True)
    if os.path.exists(note_path) and not args.force:
        print(f"\nREFUSED: {os.path.relpath(note_path, REPO)} already exists.")
        print("         Use --force to overwrite, or choose a different title.")
        sys.exit(1)

    with open(note_path, "w", encoding="utf-8") as f:
        f.write(note_content)
    print(f"\n[write] note: {os.path.relpath(note_path, REPO)}")

    # 8. Save extraction metadata
    os.makedirs(RESULTS_DIR, exist_ok=True)
    meta_path = os.path.join(RESULTS_DIR, f"{slug}_extraction.json")
    meta = {
        "title": title,
        "authors": authors,
        "year": year,
        "url": args.url,
        "source_file": os.path.basename(pdf_path),
        "source_hash": text_hash[:16],
        "extracted_at": datetime.datetime.now().isoformat(),
        "method": method,
        "text_length": len(text),
        "strategies": strategies,
        "markets": markets,
        "timeframes": timeframes,
        "edges": edges,
        "limitations": limitations,
        "implementation_difficulty": impl_difficulty,
        "retail_feasibility": retail_feasibility,
        "prop_feasibility": prop_feasibility,
        "keywords": keywords,
        "abstract_length": len(abstract),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"[write] metadata: {os.path.relpath(meta_path, REPO)}")

    # 9. Update vault index
    linked = update_vault_research_index(slug, title)
    if linked:
        print(f"[vault] cross-linked in: vault/02-Strategy-Research/_index.md")

    # 10. Summary
    print()
    print("=" * 60)
    print("PAPER INGESTION COMPLETE")
    print(f"  title:       {title}")
    print(f"  authors:     {authors or '(unknown)'}")
    print(f"  year:        {year or '(unknown)'}")
    print(f"  note:        research/papers/{slug}.md")
    print(f"  metadata:    research/results/{slug}_extraction.json")
    print(f"  strategies:  {', '.join(strategies) if strategies else '(none)'}")
    print(f"  markets:     {', '.join(markets) if markets else '(none)'}")
    print(f"  feasibility: impl={impl_difficulty} retail={retail_feasibility} prop={prop_feasibility}")
    print("=" * 60)


if __name__ == "__main__":
    main()
