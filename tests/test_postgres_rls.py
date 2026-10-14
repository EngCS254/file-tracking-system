"""Integration tests. Run only against a disposable, migrated PostgreSQL database."""
import os
import uuid
import unittest
try:
    import psycopg
except ImportError:
    psycopg = None

APP_URL = os.getenv("TEST_APP_DATABASE_URL")
OWNER_URL = os.getenv("TEST_OWNER_DATABASE_URL")

@unittest.skipUnless(psycopg is not None and APP_URL and OWNER_URL, "Set TEST_APP_DATABASE_URL and TEST_OWNER_DATABASE_URL to run PostgreSQL RLS integration tests")
class PostgresRLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = uuid.uuid4().hex[:12]
        cls.dept_a = "RLS-A-" + cls.token
        cls.dept_b = "RLS-B-" + cls.token
        with psycopg.connect(OWNER_URL) as conn:
            cls.admin_id = conn.execute("""INSERT INTO users(name,email,department,section,staff_number,role,active,created_at)
              VALUES (%s,%s,%s,%s,%s,'Admin',1,'test') RETURNING id""",
              ("RLS Admin", f"admin-{cls.token}@example.test", cls.dept_a, "A", f"ADM-{cls.token}")).fetchone()[0]
            cls.user_a_id = conn.execute("""INSERT INTO users(name,email,department,section,staff_number,role,active,created_at)
              VALUES (%s,%s,%s,%s,%s,'User',1,'test') RETURNING id""",
              ("RLS User A", f"a-{cls.token}@example.test", cls.dept_a, "A", f"USA-{cls.token}")).fetchone()[0]
            cls.user_b_id = conn.execute("""INSERT INTO users(name,email,department,section,staff_number,role,active,created_at)
              VALUES (%s,%s,%s,%s,%s,'User',1,'test') RETURNING id""",
              ("RLS User B", f"b-{cls.token}@example.test", cls.dept_b, "B", f"USB-{cls.token}")).fetchone()[0]
            cls.file_a_id = conn.execute("""INSERT INTO files(file_id,file_name,department,section,barcode,status,created_at,created_by,approval_status)
              VALUES (%s,'A file',%s,'A',%s,'AVAILABLE','test',%s,'APPROVED') RETURNING id""",
              (f"RLS-FA-{cls.token}", cls.dept_a, f"RLS-FA-{cls.token}", cls.user_a_id)).fetchone()[0]
            cls.file_b_id = conn.execute("""INSERT INTO files(file_id,file_name,department,section,barcode,status,created_at,created_by,approval_status)
              VALUES (%s,'B file',%s,'B',%s,'AVAILABLE','test',%s,'APPROVED') RETURNING id""",
              (f"RLS-FB-{cls.token}", cls.dept_b, f"RLS-FB-{cls.token}", cls.user_b_id)).fetchone()[0]

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(OWNER_URL) as conn:
            conn.execute("DELETE FROM audit_trail WHERE file_row_id IN (%s,%s) OR actor_user_id IN (%s,%s,%s)",
                         (cls.file_a_id, cls.file_b_id, cls.admin_id, cls.user_a_id, cls.user_b_id))
            conn.execute("DELETE FROM file_requests WHERE file_row_id IN (%s,%s) OR requester_id IN (%s,%s,%s)",
                         (cls.file_a_id, cls.file_b_id, cls.admin_id, cls.user_a_id, cls.user_b_id))
            conn.execute("DELETE FROM file_movements WHERE file_id IN (%s,%s)", (cls.file_a_id, cls.file_b_id))
            conn.execute("DELETE FROM notifications WHERE user_id IN (%s,%s,%s)", (cls.admin_id, cls.user_a_id, cls.user_b_id))
            conn.execute("DELETE FROM files WHERE id IN (%s,%s)", (cls.file_a_id, cls.file_b_id))
            conn.execute("DELETE FROM users WHERE id IN (%s,%s,%s)", (cls.admin_id, cls.user_a_id, cls.user_b_id))

    def test_user_sees_only_department_scope(self):
        with psycopg.connect(APP_URL) as conn:
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(self.user_a_id),))
            conn.execute("SELECT set_config('app.system_context', 'off', true)")
            ids = {r[0] for r in conn.execute("SELECT id FROM files WHERE id IN (%s,%s)", (self.file_a_id, self.file_b_id)).fetchall()}
            self.assertEqual(ids, {self.file_a_id})

    def test_non_admin_cannot_delete_or_mark_file_deleted(self):
        with psycopg.connect(APP_URL) as conn:
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(self.user_a_id),))
            conn.execute("SELECT set_config('app.system_context', 'off', true)")
            deleted = conn.execute("DELETE FROM files WHERE id=%s RETURNING id", (self.file_a_id,)).fetchall()
            self.assertEqual(deleted, [])
            conn.rollback()
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(self.user_a_id),))
            conn.execute("SELECT set_config('app.system_context', 'off', true)")
            with self.assertRaises(psycopg.Error):
                conn.execute("UPDATE files SET deleted_at='now', deleted_by=%s WHERE id=%s", (self.user_a_id, self.file_a_id))
            conn.rollback()

    def test_admin_can_view_all_scoped_files(self):
        with psycopg.connect(APP_URL) as conn:
            conn.execute("SELECT set_config('app.user_id', %s, true)", (str(self.admin_id),))
            conn.execute("SELECT set_config('app.system_context', 'off', true)")
            ids = {r[0] for r in conn.execute("SELECT id FROM files WHERE id IN (%s,%s)", (self.file_a_id, self.file_b_id)).fetchall()}
            self.assertEqual(ids, {self.file_a_id, self.file_b_id})

if __name__ == "__main__":
    unittest.main()
