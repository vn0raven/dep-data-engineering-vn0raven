"""
Run the documented M3 business-question SQL queries against
the processed SQLite database and save the results.
"""

from pathlib import Path
import sqlite3


DATABASE_PATH = Path("data/processed/davao_transit.db")
SQL_PATH = Path("sql/business_questions.sql")
OUTPUT_PATH = Path("data/processed/business_question_results.txt")


def read_statements(sql_text: str) -> list[str]:
    statements = []
    buffer = ""

    for line in sql_text.splitlines():
        buffer += line + "\n"

        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()

            if statement:
                statements.append(statement)

            buffer = ""

    if buffer.strip():
        raise ValueError("Incomplete SQL statement found.")

    return statements


def format_table(columns, rows):
    values = [columns] + [
        ["" if value is None else str(value) for value in row]
        for row in rows
    ]

    widths = [
        max(len(row[index]) for row in values)
        for index in range(len(columns))
    ]

    lines = []

    header = " | ".join(
        columns[index].ljust(widths[index])
        for index in range(len(columns))
    )

    separator = "-+-".join("-" * width for width in widths)

    lines.append(header)
    lines.append(separator)

    for row in values[1:]:
        lines.append(
            " | ".join(
                row[index].ljust(widths[index])
                for index in range(len(columns))
            )
        )

    return "\n".join(lines)


def main():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_PATH}"
        )

    if not SQL_PATH.exists():
        raise FileNotFoundError(
            f"SQL file not found: {SQL_PATH}"
        )

    sql_text = SQL_PATH.read_text(encoding="utf-8")
    statements = read_statements(sql_text)

    connection = sqlite3.connect(DATABASE_PATH)

    output_sections = []

    try:
        question_number = 0

        for statement in statements:
            cursor = connection.execute(statement)

            if cursor.description is None:
                continue

            question_number += 1

            columns = [
                column[0]
                for column in cursor.description
            ]

            rows = cursor.fetchall()

            section = [
                "=" * 80,
                f"BUSINESS QUESTION {question_number}",
                "=" * 80,
                "",
                format_table(columns, rows),
                "",
                f"Rows returned: {len(rows)}",
                "",
            ]

            output_sections.append("\n".join(section))

    finally:
        connection.close()

    output = "\n".join(output_sections)

    print(output)

    OUTPUT_PATH.write_text(
        output,
        encoding="utf-8",
        newline="\n",
    )

    print(f"\nResults saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()