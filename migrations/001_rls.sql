-- Apply as a database owner/superuser. Runtime connections must use dfts_app (not dfts_owner).
CREATE OR REPLACE FUNCTION public.dfts_current_user_id() RETURNS BIGINT
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::BIGINT
$$;

CREATE OR REPLACE FUNCTION public.dfts_is_system() RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT COALESCE(current_setting('app.system_context', true), 'off') = 'on'
$$;

CREATE OR REPLACE FUNCTION public.dfts_is_admin() RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT EXISTS (SELECT 1 FROM public.users u
                 WHERE u.id = public.dfts_current_user_id()
                   AND u.active = 1 AND lower(u.role) = 'admin')
$$;

CREATE OR REPLACE FUNCTION public.dfts_can_access_file(p_department TEXT, p_section TEXT) RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
  SELECT public.dfts_is_system() OR EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.id = public.dfts_current_user_id() AND u.active = 1
      AND lower(u.role) = 'admin'
  ) OR EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.id = public.dfts_current_user_id() AND u.active = 1
      AND lower(u.role) <> 'admin'
      AND lower(trim(coalesce(u.department,''))) = lower(trim(coalesce(p_department,'')))
      AND (NULLIF(trim(coalesce(u.section,'')), '') IS NULL
           OR lower(trim(coalesce(u.section,''))) = lower(trim(coalesce(p_section,''))))
  )
$$;

-- All application tables are forced through RLS, including for their table owner.
ALTER TABLE users ENABLE ROW LEVEL SECURITY; ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY; ALTER TABLE files FORCE ROW LEVEL SECURITY;
ALTER TABLE file_movements ENABLE ROW LEVEL SECURITY; ALTER TABLE file_movements FORCE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY; ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
ALTER TABLE file_requests ENABLE ROW LEVEL SECURITY; ALTER TABLE file_requests FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_trail ENABLE ROW LEVEL SECURITY; ALTER TABLE audit_trail FORCE ROW LEVEL SECURITY;
ALTER TABLE auth_attempts ENABLE ROW LEVEL SECURITY; ALTER TABLE auth_attempts FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_select_scope ON users;
CREATE POLICY users_select_scope ON users FOR SELECT USING (
  public.dfts_is_system() OR id = public.dfts_current_user_id() OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS users_insert_admin ON users;
CREATE POLICY users_insert_admin ON users FOR INSERT WITH CHECK (
  public.dfts_is_system() OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS users_update_admin_or_self ON users;
CREATE POLICY users_update_admin_or_self ON users FOR UPDATE
  USING (public.dfts_is_system() OR public.dfts_is_admin() OR id = public.dfts_current_user_id())
  WITH CHECK (public.dfts_is_system() OR public.dfts_is_admin() OR id = public.dfts_current_user_id());
DROP POLICY IF EXISTS users_delete_admin ON users;
CREATE POLICY users_delete_admin ON users FOR DELETE USING (public.dfts_is_system() OR public.dfts_is_admin());

DROP POLICY IF EXISTS files_select_scope ON files;
CREATE POLICY files_select_scope ON files FOR SELECT USING (
  public.dfts_is_system() OR public.dfts_can_access_file(department, section)
);
DROP POLICY IF EXISTS files_insert_scope ON files;
CREATE POLICY files_insert_scope ON files FOR INSERT WITH CHECK (
  public.dfts_is_system() OR (
    created_by = public.dfts_current_user_id() AND
    public.dfts_can_access_file(department, section)
  )
);
DROP POLICY IF EXISTS files_update_scope ON files;
CREATE POLICY files_update_scope ON files FOR UPDATE
  USING (public.dfts_is_system() OR public.dfts_can_access_file(department, section))
  WITH CHECK (public.dfts_is_system() OR public.dfts_is_admin() OR
              (deleted_at IS NULL AND deleted_by IS NULL AND public.dfts_can_access_file(department, section)));
DROP POLICY IF EXISTS files_delete_admin ON files;
CREATE POLICY files_delete_admin ON files FOR DELETE USING (public.dfts_is_system() OR public.dfts_is_admin());

DROP POLICY IF EXISTS movements_select_scope ON file_movements;
CREATE POLICY movements_select_scope ON file_movements FOR SELECT USING (
  public.dfts_is_system() OR user_id = public.dfts_current_user_id() OR EXISTS (
    SELECT 1 FROM files f WHERE f.id = file_movements.file_id
      AND public.dfts_can_access_file(f.department, f.section)
  )
);
DROP POLICY IF EXISTS movements_insert_scope ON file_movements;
CREATE POLICY movements_insert_scope ON file_movements FOR INSERT WITH CHECK (
  public.dfts_is_system() OR (user_id = public.dfts_current_user_id() AND EXISTS (
    SELECT 1 FROM files f WHERE f.id = file_movements.file_id
      AND public.dfts_can_access_file(f.department, f.section)
  )) OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS movements_update_admin ON file_movements;
CREATE POLICY movements_update_admin ON file_movements FOR UPDATE USING (public.dfts_is_system() OR public.dfts_is_admin()) WITH CHECK (public.dfts_is_system() OR public.dfts_is_admin());
DROP POLICY IF EXISTS movements_delete_admin ON file_movements;
CREATE POLICY movements_delete_admin ON file_movements FOR DELETE USING (public.dfts_is_system() OR public.dfts_is_admin());

DROP POLICY IF EXISTS notifications_select_owner ON notifications;
CREATE POLICY notifications_select_owner ON notifications FOR SELECT USING (
  public.dfts_is_system() OR user_id = public.dfts_current_user_id() OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS notifications_insert_system ON notifications;
CREATE POLICY notifications_insert_system ON notifications FOR INSERT WITH CHECK (
  public.dfts_is_system() OR public.dfts_is_admin() OR user_id = public.dfts_current_user_id()
);
DROP POLICY IF EXISTS notifications_update_owner ON notifications;
CREATE POLICY notifications_update_owner ON notifications FOR UPDATE
  USING (public.dfts_is_system() OR user_id = public.dfts_current_user_id() OR public.dfts_is_admin())
  WITH CHECK (public.dfts_is_system() OR user_id = public.dfts_current_user_id() OR public.dfts_is_admin());
DROP POLICY IF EXISTS notifications_delete_admin ON notifications;
CREATE POLICY notifications_delete_admin ON notifications FOR DELETE USING (public.dfts_is_system() OR public.dfts_is_admin());

DROP POLICY IF EXISTS requests_select_scope ON file_requests;
CREATE POLICY requests_select_scope ON file_requests FOR SELECT USING (
  public.dfts_is_system() OR public.dfts_is_admin() OR requester_id = public.dfts_current_user_id()
);
DROP POLICY IF EXISTS requests_insert_scope ON file_requests;
CREATE POLICY requests_insert_scope ON file_requests FOR INSERT WITH CHECK (
  public.dfts_is_system() OR (requester_id = public.dfts_current_user_id() AND EXISTS (
    SELECT 1 FROM files f WHERE f.id = file_row_id
      AND public.dfts_can_access_file(f.department, f.section)
  )) OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS requests_update_admin ON file_requests;
CREATE POLICY requests_update_admin ON file_requests FOR UPDATE
  USING (public.dfts_is_system() OR public.dfts_is_admin())
  WITH CHECK (public.dfts_is_system() OR public.dfts_is_admin());
DROP POLICY IF EXISTS requests_delete_admin ON file_requests;
CREATE POLICY requests_delete_admin ON file_requests FOR DELETE USING (public.dfts_is_system() OR public.dfts_is_admin());

DROP POLICY IF EXISTS audit_select_scope ON audit_trail;
CREATE POLICY audit_select_scope ON audit_trail FOR SELECT USING (
  public.dfts_is_system() OR public.dfts_is_admin() OR
  (file_row_id IS NOT NULL AND EXISTS (SELECT 1 FROM files f WHERE f.id = audit_trail.file_row_id
     AND public.dfts_can_access_file(f.department, f.section)))
);
DROP POLICY IF EXISTS audit_insert_actor ON audit_trail;
CREATE POLICY audit_insert_actor ON audit_trail FOR INSERT WITH CHECK (
  public.dfts_is_system() OR actor_user_id = public.dfts_current_user_id() OR public.dfts_is_admin()
);
DROP POLICY IF EXISTS audit_no_update ON audit_trail;
CREATE POLICY audit_no_update ON audit_trail FOR UPDATE USING (false) WITH CHECK (false);
DROP POLICY IF EXISTS audit_no_delete ON audit_trail;
CREATE POLICY audit_no_delete ON audit_trail FOR DELETE USING (false);

DROP POLICY IF EXISTS auth_attempts_system_only ON auth_attempts;
CREATE POLICY auth_attempts_system_only ON auth_attempts USING (public.dfts_is_system()) WITH CHECK (public.dfts_is_system());

-- A regular user may acknowledge the oath, but cannot deactivate accounts or edit identity/role fields.
CREATE OR REPLACE FUNCTION public.dfts_guard_user_admin_fields() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
  IF public.dfts_is_system() OR public.dfts_is_admin() THEN
    RETURN NEW;
  END IF;
  IF NEW.active IS DISTINCT FROM OLD.active OR NEW.role IS DISTINCT FROM OLD.role OR
     NEW.email IS DISTINCT FROM OLD.email OR NEW.department IS DISTINCT FROM OLD.department OR
     NEW.section IS DISTINCT FROM OLD.section OR NEW.staff_number IS DISTINCT FROM OLD.staff_number OR
     NEW.password_hash IS DISTINCT FROM OLD.password_hash OR NEW.password_salt IS DISTINCT FROM OLD.password_salt THEN
    RAISE EXCEPTION 'Only an administrator may change user access or identity fields' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS users_guard_admin_fields ON users;
CREATE TRIGGER users_guard_admin_fields BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION public.dfts_guard_user_admin_fields();

-- A non-admin cannot alter deletion markers (including restoring a deleted row).
CREATE OR REPLACE FUNCTION public.dfts_guard_file_delete_fields() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
  IF public.dfts_is_system() OR public.dfts_is_admin() THEN
    RETURN NEW;
  END IF;
  IF (NEW.deleted_at IS DISTINCT FROM OLD.deleted_at OR NEW.deleted_by IS DISTINCT FROM OLD.deleted_by) THEN
    RAISE EXCEPTION 'Only an administrator may change file deletion state' USING ERRCODE = '42501';
  END IF;
  IF (NEW.approval_status IS DISTINCT FROM OLD.approval_status OR
      NEW.approved_by IS DISTINCT FROM OLD.approved_by OR NEW.approved_at IS DISTINCT FROM OLD.approved_at OR
      NEW.file_name IS DISTINCT FROM OLD.file_name OR NEW.department IS DISTINCT FROM OLD.department OR
      NEW.section IS DISTINCT FROM OLD.section OR NEW.file_id IS DISTINCT FROM OLD.file_id OR
      NEW.barcode IS DISTINCT FROM OLD.barcode OR NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
    RAISE EXCEPTION 'Only an administrator may change file metadata or approval state; submit a request' USING ERRCODE = '42501';
  END IF;
  IF NEW.status IS DISTINCT FROM OLD.status OR NEW.current_holder_id IS DISTINCT FROM OLD.current_holder_id THEN
    IF NOT (
      (OLD.status = 'AVAILABLE' AND OLD.deleted_at IS NULL AND OLD.approval_status = 'APPROVED' AND NEW.status = 'OUT' AND NEW.current_holder_id = public.dfts_current_user_id()) OR
      (OLD.status = 'OUT' AND OLD.current_holder_id = public.dfts_current_user_id() AND
       NEW.status = 'AVAILABLE' AND NEW.current_holder_id IS NULL)
    ) THEN
      RAISE EXCEPTION 'File movement is not permitted for this user' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END; $$;
DROP TRIGGER IF EXISTS files_guard_delete_fields ON files;
CREATE TRIGGER files_guard_delete_fields BEFORE UPDATE ON files
  FOR EACH ROW EXECUTE FUNCTION public.dfts_guard_file_delete_fields();

-- Least-privilege grants: no broad UPDATE privilege on user, request or notification tables.
REVOKE ALL ON users, files, file_movements, notifications, auth_attempts, file_requests, audit_trail FROM dfts_app;
GRANT SELECT, INSERT, DELETE ON users, files, file_movements, notifications, auth_attempts, file_requests, audit_trail TO dfts_app;
GRANT UPDATE (active, oath_acknowledged_at) ON users TO dfts_app;
GRANT UPDATE ON files TO dfts_app;
GRANT UPDATE (attempts, window_started, locked_until) ON auth_attempts TO dfts_app;
GRANT UPDATE (status, reviewed_by, reviewed_at, review_note) ON file_requests TO dfts_app;
GRANT UPDATE (is_read) ON notifications TO dfts_app;

-- Keep function execution available to the runtime role; table grants are restricted separately.
GRANT EXECUTE ON FUNCTION public.dfts_current_user_id() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.dfts_is_system() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.dfts_is_admin() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.dfts_can_access_file(TEXT, TEXT) TO PUBLIC;
