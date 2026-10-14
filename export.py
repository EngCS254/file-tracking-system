
from io import BytesIO

import pandas as pd

from database import get_connection


def create_excel_export() -> bytes:
    """Create the filing-system workbook in memory."""
    conn = get_connection()

    try:
        files_df = pd.read_sql_query(
            """
            SELECT
                f.file_id AS 'File ID',
                f.file_name AS 'File Name',
                f.department AS 'Department',
                COALESCE(f.section, '') AS 'Section',
                f.barcode AS 'Barcode',
                f.status AS 'Status',
                COALESCE(u.name, '') AS 'Current Holder',
                COALESCE(u.staff_number, '') AS 'Holder Staff Number',
                f.created_at AS 'Created At'
            FROM files f
            LEFT JOIN users u ON f.current_holder_id = u.id
            ORDER BY f.id DESC
            """,
            conn,
        )

        movements_df = pd.read_sql_query(
            """
            SELECT
                f.file_id AS 'File ID',
                f.file_name AS 'File Name',
                u.name AS 'User',
                u.staff_number AS 'Staff Number',
                m.action AS 'Action',
                m.movement_time AS 'Movement Time',
                COALESCE(m.remarks, '') AS 'Remarks'
            FROM file_movements m
            JOIN files f ON m.file_id = f.id
            JOIN users u ON m.user_id = u.id
            ORDER BY m.id DESC
            """,
            conn,
        )

        users_df = pd.read_sql_query(
            """
            SELECT
                name AS 'Name',
                email AS 'Organization Email',
                department AS 'Department',
                COALESCE(section, '') AS 'Section',
                staff_number AS 'Staff Number',
                role AS 'Role',
                CASE
                    WHEN active = 1 THEN 'Active'
                    ELSE 'Inactive'
                END AS 'Account Status',
                oath_acknowledged_at AS 'Oath Acknowledged At',
                created_at AS 'Created At'
            FROM users
            ORDER BY name COLLATE NOCASE
            """,
            conn,
        )

        notifications_df = pd.read_sql_query(
            """
            SELECT
                n.title AS 'Title',
                n.message AS 'Message',
                n.notification_type AS 'Type',
                n.is_read AS 'Read Flag',
                COALESCE(u.name, 'All Users') AS 'Recipient',
                n.created_at AS 'Created At'
            FROM notifications n
            LEFT JOIN users u ON n.user_id = u.id
            ORDER BY n.id DESC
            """,
            conn,
        )

    finally:
        conn.close()

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        files_df.to_excel(
            writer,
            sheet_name="File Register",
            index=False,
        )
        movements_df.to_excel(
            writer,
            sheet_name="Movement History",
            index=False,
        )
        users_df.to_excel(
            writer,
            sheet_name="Users",
            index=False,
        )
        notifications_df.to_excel(
            writer,
            sheet_name="Notifications",
            index=False,
        )

        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"

            for column_cells in worksheet.columns:
                max_length = max(
                    len(str(cell.value))
                    if cell.value is not None
                    else 0
                    for cell in column_cells
                )

                worksheet.column_dimensions[
                    column_cells[0].column_letter
                ].width = min(max(max_length + 2, 12), 45)

    output.seek(0)
    return output.getvalue()
