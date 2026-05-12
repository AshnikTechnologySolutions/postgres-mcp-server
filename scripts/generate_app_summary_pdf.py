from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


OUTPUT_PATH = Path("output/pdf/postgres-mcp-server-summary.pdf")


def build_story():
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleSmall",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=20,
        textColor=colors.HexColor("#12344D"),
        spaceAfter=6,
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=12,
        textColor=colors.HexColor("#0F5E7A"),
        spaceBefore=4,
        spaceAfter=2,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.4,
        textColor=colors.HexColor("#1F2933"),
        spaceAfter=2,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=10,
        firstLineIndent=-7,
        bulletIndent=0,
        bulletFontName="Helvetica-Bold",
        bulletFontSize=8.6,
        spaceAfter=1,
    )
    note = ParagraphStyle(
        "Note",
        parent=body,
        fontName="Helvetica-Oblique",
        fontSize=7.8,
        leading=9.2,
        textColor=colors.HexColor("#52606D"),
        spaceBefore=4,
    )

    story = [
        Paragraph("PostgreSQL MCP Server", title),
        Paragraph(
            "One-page repo summary generated from evidence in README, server modules, and deployment files.",
            body,
        ),
        HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#D9E2EC")),
        Spacer(1, 0.08 * inch),
        Paragraph("What It Is", section),
        Paragraph(
            "A secure PostgreSQL MCP server for Claude Desktop and other MCP clients. "
            "The repo provides a FastMCP STDIO server and an optional FastAPI HTTP adapter with read-only enforcement, async connection pooling, audit logging, and optional OpenTelemetry tracing.",
            body,
        ),
        Paragraph("Who It's For", section),
        Paragraph(
            "Primary persona: platform engineers, internal tooling teams, or developers who want AI assistants to access PostgreSQL through MCP without embedding raw database credentials in client configs.",
            body,
        ),
        Paragraph("What It Does", section),
    ]

    feature_bullets = [
        "Exposes tools for health, uptime, schema metadata, table stats, slow queries, explain plans, index advice, and audit log reads.",
        "Provides <b>sql_safe</b> for single-statement read-only SQL with transaction-level read-only enforcement.",
        "Optionally enables <b>sql_query</b> for arbitrary SQL only when <b>ALLOW_ARBITRARY_SQL=true</b>.",
        "Supports separate local and remote targets plus distinct read and write database URLs.",
        "Reuses shared <b>asyncpg</b> pools with connection setup for timeouts and public schema search path.",
        "Writes structured JSONL audit records with request IDs, query previews, query hashes, and trace context.",
        "Includes an optional HTTP deployment path with API-key checks, request-ID propagation, and OTLP tracing hooks.",
    ]
    for item in feature_bullets:
        story.append(Paragraph(item, bullet, bulletText="-"))

    story.extend(
        [
            Paragraph("How It Works", section),
            Paragraph(
                "<b>Client layer:</b> Claude Desktop can launch repo scripts that start <b>cli.py</b> in STDIO mode; HTTP clients can call the FastAPI app in <b>mcp_server/http_app.py</b>.",
                bullet,
                bulletText="-",
            ),
            Paragraph(
                "<b>Tool layer:</b> <b>mcp_server/server.py</b> registers MCP tools directly for STDIO, while <b>mcp_server/router.py</b> maps HTTP routes to tool functions in <b>mcp_server/tools/</b>.",
                bullet,
                bulletText="-",
            ),
            Paragraph(
                "<b>Data/policy layer:</b> <b>config.py</b> loads env settings; <b>sql.py</b> validates single statements and controls read-only execution paths; <b>db.py</b> creates shared read/write pools based on <b>DEFAULT_DB</b>.",
                bullet,
                bulletText="-",
            ),
            Paragraph(
                "<b>Cross-cutting services:</b> <b>audit.py</b> appends JSONL audit events, <b>request_context.py</b> carries request IDs, and <b>otel.py</b> adds optional FastAPI and DB tracing.",
                bullet,
                bulletText="-",
            ),
            Paragraph("How To Run", section),
        ]
    )

    run_bullets = [
        "Create a virtualenv and install dependencies: <b>python3 -m venv venv</b>, <b>source venv/bin/activate</b>, <b>pip install -r requirements.txt</b>.",
        "Copy env templates: <b>cp .env.example .env.claude.local</b> and <b>cp .env.example .env.claude.remote</b>.",
        "Set the real PostgreSQL URLs and choose the default target in the env file.",
        "Start STDIO mode with <b>./venv/bin/python cli.py</b>.",
        "Optional HTTP mode: run <b>uvicorn mcp_server.http_app:app --host 127.0.0.1 --port 8000</b> and set <b>MCP_HTTP_API_KEY</b> for protected access.",
    ]
    for item in run_bullets:
        story.append(Paragraph(item, bullet, bulletText="-"))

    story.append(
        Paragraph(
            "Not found in repo: a bundled production deployment manifest or schema/table allow-list enforcement implementation. "
            "README lists allow-lists as recommended future work.",
            note,
        )
    )
    return story


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=letter,
        leftMargin=0.58 * inch,
        rightMargin=0.58 * inch,
        topMargin=0.52 * inch,
        bottomMargin=0.48 * inch,
        title="PostgreSQL MCP Server Summary",
        author="OpenAI Codex",
    )
    doc.build(build_story())
    print(OUTPUT_PATH.resolve())


if __name__ == "__main__":
    main()
