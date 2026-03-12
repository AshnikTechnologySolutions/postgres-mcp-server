from mcp_server.sql import fetch_rows


async def get_schema():
    rows = await fetch_rows(
        """
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
        """,
        role="read",
        read_only=True,
    )

    schema: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        schema.setdefault(row["table_name"], []).append(
            {
                "column_name": row["column_name"],
                "data_type": row["data_type"],
                "is_nullable": row["is_nullable"],
            }
        )

    return {"ok": True, "schema": schema}
