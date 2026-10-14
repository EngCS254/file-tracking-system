import io
import pandas as pd
import streamlit as st

from database import (
    initialize_database,
    add_user,
    get_users,
    get_items,
    find_item,
    authenticate_user,
    authenticate_oauth_email,
    create_first_admin,
    has_users,
    acknowledge_oath,
    add_item,
    issue_item,
    return_item,
    get_movements,
    get_notifications,
    mark_notifications_read,
    modify_item,
    approve_item,
    soft_delete_item,
    get_audit_trail,
    get_file_requests,
    review_file_request,
    request_retrieval,
    admin_delete_user,
)
from barcode_utils import create_barcode_image


# =========================================================
# PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="Digital Filing System",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# BANKING-STYLE UI
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #F8FAFC 0%, #EEF3F8 100%);
        color: #243447;
    }

    [data-testid="stSidebar"] {
        background-color: #102A43;
        border-right: 1px solid #29445F;
    }

    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: #456078;
    }

    .brand-title {
        font-size: 27px;
        font-weight: 800;
        color: #102A43;
        margin-bottom: 3px;
    }

    .brand-subtitle {
        color: #64748B;
        font-size: 13px;
        margin-bottom: 22px;
    }

    .section-heading {
        color: #102A43;
        font-size: 20px;
        font-weight: 750;
        margin-top: 15px;
        margin-bottom: 12px;
    }

    .metric-card {
        background: #FFFFFF;
        border: 1px solid #DCE4EC;
        border-radius: 12px;
        padding: 19px;
        min-height: 125px;
        box-shadow: 0 8px 24px rgba(16,42,67,.06);
    }

    .metric-label {
        color: #64748B;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .metric-value {
        color: #102A43;
        font-size: 30px;
        font-weight: 800;
    }

    .metric-note {
        color: #64748B;
        font-size: 12px;
        margin-top: 4px;
    }

    .panel {
        background: #FFFFFF;
        border: 1px solid #DCE4EC;
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 12px;
    }

    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 8px;
        font-weight: 650;
        min-height: 42px;
    }

    div[data-testid="stButton"] button[kind="primary"] {
        background: #102A43;
        border: 1px solid #102A43;
        color: #FFFFFF;
    }

    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: #243F5A;
        border-color: #243F5A;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 8px;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid #DCE4EC;
        border-radius: 9px;
        overflow: hidden;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    @media (max-width: 768px) {
        .brand-title {
            font-size: 22px;
        }

        .metric-card {
            padding: 13px;
            min-height: 105px;
        }

        .metric-value {
            font-size: 24px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_database()


# =========================================================
# HELPER FUNCTIONS
# =========================================================
def value(record, *keys, default=""):
    """Safely retrieve a value from a database record."""
    if not isinstance(record, dict):
        return default

    for key in keys:
        val = record.get(key)
        if val is not None:
            return val

    return default


def user_id(user):
    return value(user, "id", "user_id", default=None)


def role(user):
    return str(value(user, "role", default="User")).strip().lower()


def is_admin(user):
    return role(user) == "admin"


def is_view_only(user):
    return role(user) in ("view only", "view_only", "viewer")


def can_manage_files(user):
    return not is_view_only(user)


def file_id(item):
    return value(item, "file_id", "system_file_id", default="")


def file_name(item):
    return value(item, "file_name", "title", default="Unnamed file")


def file_status(item):
    return str(value(item, "status", default="AVAILABLE")).upper()


def is_out(item):
    return file_status(item) in (
        "OUT",
        "ISSUED",
        "BORROWED",
        "CHECKED OUT",
        "CHECKED_OUT",
    )


def visible_files(current_user):
    """
    IMPORTANT:
    database.py requires current_user to enforce access permissions.
    Do not call get_items() without passing the logged-in user.
    """
    return get_items(current_user=current_user) or []


def file_dataframe(items):
    rows = []

    for item in items:
        rows.append({
            "File ID": file_id(item),
            "File Name": file_name(item),
            "Department": value(item, "department"),
            "Section": value(item, "section") or "—",
            "Status": file_status(item),
            "Approval": value(
                item, "approval_status", default="APPROVED"
            ),
            "Current Holder": value(
                item, "current_holder_name"
            ) or "—",
            "Barcode": value(item, "barcode") or "—",
        })

    return pd.DataFrame(rows)


def show_header(title, subtitle=""):
    st.markdown(
        f'<div class="brand-title">{title}</div>',
        unsafe_allow_html=True,
    )

    if subtitle:
        st.markdown(
            f'<div class="brand-subtitle">{subtitle}</div>',
            unsafe_allow_html=True,
        )


def metric_card(label, amount, note, icon):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{icon}&nbsp; {label}</div>
            <div class="metric-value">{amount}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def excel_bytes(items):
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        file_dataframe(items).to_excel(
            writer,
            index=False,
            sheet_name="File Register",
        )

    output.seek(0)
    return output.getvalue()


def generate_and_show_barcode(code):
    """
    barcode_utils.py returns the saved PNG file path.
    Streamlit displays the image using that path.
    """
    try:
        path = create_barcode_image(code)

        st.image(
            path,
            caption=f"Barcode: {code}",
            width=440,
        )

        with open(path, "rb") as barcode_file:
            st.download_button(
                label="Download Barcode PNG",
                data=barcode_file.read(),
                file_name=f"{code}_barcode.png",
                mime="image/png",
                key=f"download_barcode_{code}",
            )

        st.caption(
            "Print the downloaded barcode PNG and attach it to the physical file."
        )

    except Exception as exc:
        st.error(f"Could not generate the barcode image: {exc}")


# =========================================================
# FIRST ADMINISTRATOR SETUP
# =========================================================
if not has_users():
    show_header(
        "📁 Digital Filing System",
        "Initial administrator registration",
    )

    st.info(
        "No accounts exist yet. The deployment administrator must enable first-account setup and provide the one-time bootstrap token."
    )

    with st.form("first_admin_form"):
        st.subheader("Create Administrator")

        name = st.text_input("Full Name")
        email = st.text_input("Organization Email")
        department = st.text_input("Department")
        section = st.text_input("Section (optional)")
        staff_no = st.text_input("Staff Number")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        bootstrap_token = st.text_input("One-time bootstrap token", type="password",
                                        help="Provided by the deployment administrator; required only for first-account setup.")

        submitted = st.form_submit_button(
            "Create Administrator",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not all([
            name.strip(),
            email.strip(),
            department.strip(),
            staff_no.strip(),
            password,
        ]):
            st.error("Complete all required fields.")

        elif password != confirm:
            st.error("The passwords do not match.")

        else:
            try:
                create_first_admin(
                    name.strip(),
                    email.strip(),
                    department.strip(),
                    section.strip() or None,
                    staff_no.strip(),
                    password,
                    bootstrap_token=bootstrap_token,
                )

                st.success(
                    "Administrator created. You can now sign in."
                )
                st.rerun()

            except Exception as exc:
                st.error(f"Could not create administrator: {exc}")

    st.stop()


# =========================================================
# LOGIN
# =========================================================
# Streamlit's OIDC identity is verified by the configured identity provider.
try:
    if hasattr(st, "user") and getattr(st.user, "is_logged_in", False):
        _oidc_email = getattr(st.user, "email", None)
        _oidc_user = authenticate_oauth_email(_oidc_email)
        if _oidc_user:
            st.session_state["logged_in_user"] = _oidc_user
        else:
            st.error("This SSO identity is not registered or has been deactivated. Contact an administrator.")
            if st.button("Sign out of SSO"):
                st.logout()
                st.rerun()
except Exception:
    pass

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None


if st.session_state.logged_in_user is None:
    _, center, _ = st.columns([1, 1.2, 1])

    with center:
        st.markdown(
            """
            <div class="panel" style="text-align:center">
                <div style="font-size:46px">📁</div>
                <div class="brand-title">Digital Filing System</div>
                <div class="brand-subtitle">
                    Secure file tracking and accountability
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Optional native Streamlit OIDC: configure [auth] in .streamlit/secrets.toml.
        try:
            oidc_configured = bool(st.secrets.get("auth", {}).get("client_id"))
        except Exception:
            oidc_configured = False
        if oidc_configured and hasattr(st, "login"):
            if st.button("Continue with organization SSO", use_container_width=True):
                st.login()
            st.caption("SSO access is limited to accounts already registered by an administrator.")
            st.divider()

        with st.form("login_form"):
            st.subheader("Sign In")

            staff_no = st.text_input("Staff Number")
            password = st.text_input("Password", type="password")

            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

            if submitted:
                user = authenticate_user(
                    staff_no.strip(),
                    password,
                )

                if user:
                    st.session_state.logged_in_user = user
                    st.rerun()
                else:
                    st.error("Invalid staff number or password.")

    st.stop()


# =========================================================
# CURRENT USER
# =========================================================
current_user = st.session_state.logged_in_user
current_user_id = user_id(current_user)

current_user_name = value(
    current_user, "name", default="Staff Member"
)
current_user_department = value(
    current_user, "department", default="—"
)
current_user_section = value(current_user, "section") or ""
current_user_role = value(current_user, "role", default="User")


# =========================================================
# NAVIGATION
# =========================================================
try:
    _unread_count = len(get_notifications(current_user_id, include_read=False) or [])
except Exception:
    _unread_count = 0
try:
    _pending_requests = get_file_requests(current_user, status="PENDING") if is_admin(current_user) else []
except Exception:
    _pending_requests = []
try:
    _pending_approvals = [
        item for item in (get_items(current_user=current_user) or [])
        if str(value(item, "approval_status", default="APPROVED")).upper() == "PENDING"
    ] if is_admin(current_user) else []
except Exception:
    _pending_approvals = []

pages = [
    "📊 Dashboard",
    "📷 Scan / Issue / Return",
    "🔎 Search Files",
    "📝 Register File",
    "✏️ Modify / Remove File",
    "🕒 Movement History",
    "📜 Audit Trail",
    "🔔 Notifications",
    "📋 Oath & Responsibilities",
    "📤 Export to Excel",
]

if is_admin(current_user):
    pages += [
        "✅ Approve Files",
        "👤 Register User",
        "👥 User Directory",
        "📥 Request Queue",
    ]
elif is_view_only(current_user):
    pages = [p for p in pages if p not in ("📝 Register File", "✏️ Modify / Remove File")]

pages = [
    (f"🔔 Notifications · {_unread_count}" if p == "🔔 Notifications" and _unread_count else p)
    for p in pages
]
if is_admin(current_user) and _pending_requests:
    pages = [
        (f"📥 Request Queue · {len(_pending_requests)}" if p == "📥 Request Queue" else p)
        for p in pages
    ]
if is_admin(current_user) and _pending_approvals:
    pages = [
        (f"✅ Approve Files · {len(_pending_approvals)}" if p == "✅ Approve Files" else p)
        for p in pages
    ]


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div style="padding:10px 4px 18px">
            <div style="font-size:34px">📁</div>
            <div style="font-size:20px;font-weight:800">
                Digital Filing System
            </div>
            <div style="font-size:12px;color:#D7E2ED !important">
                File tracking & accountability
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    st.markdown("**MAIN MENU**")

    quick_page = st.session_state.pop("quick_page", None)

    if quick_page in pages:
        st.session_state["page_navigation"] = quick_page

    current_nav = st.session_state.get("page_navigation")
    if isinstance(current_nav, str):
        for base_label in ("🔔 Notifications", "📥 Request Queue", "✅ Approve Files"):
            if current_nav.startswith(base_label):
                matching = next((p for p in pages if p.startswith(base_label)), None)
                if matching:
                    st.session_state["page_navigation"] = matching
                break
    if st.session_state.get("page_navigation") not in pages:
        st.session_state["page_navigation"] = pages[0]

    selected_page = st.radio(
        "Navigation",
        pages,
        key="page_navigation",
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**SIGNED-IN USER**")
    st.write(f"👤 {current_user_name}")
    st.caption(f"Department: {current_user_department}")
    st.caption(
        f"Section: {current_user_section or 'Not specified'}"
    )
    st.caption(f"Role: {current_user_role}")

    if st.button("🚪 Sign Out", use_container_width=True):
        for key in (
            "logged_in_user",
            "scanned_item",
            "detail_item",
            "page_navigation",
            "quick_page",
        ):
            st.session_state.pop(key, None)

        try:
            if hasattr(st, "user") and getattr(st.user, "is_logged_in", False) and hasattr(st, "logout"):
                st.logout()
        except Exception:
            pass
        st.rerun()


# =========================================================
# DASHBOARD
# =========================================================
if selected_page == "📊 Dashboard":
    show_header(
        "📊 Dashboard",
        "Overview of file records, availability and daily operations.",
    )

    items = visible_files(current_user)
    active_items = [
        item for item in items if not value(item, "deleted_at")
    ]

    out_items = [item for item in active_items if is_out(item)]

    pending = [
        item for item in active_items
        if str(
            value(item, "approval_status", default="APPROVED")
        ).upper() == "PENDING"
    ]

    notifications = get_notifications(current_user_id) or []
    unread = sum(
        1 for note in notifications
        if not bool(value(note, "is_read", default=0))
    )

    cols = st.columns(4)

    metrics = [
        (
            "Visible Files",
            len(active_items),
            "Records you can access",
            "📁",
        ),
        (
            "Available",
            len(active_items) - len(out_items),
            "Not currently issued",
            "✅",
        ),
        (
            "Files Out",
            len(out_items),
            "Currently issued files",
            "📤",
        ),
        (
            "Unread Alerts",
            unread,
            "Sona notifications",
            "🔔",
        ),
    ]

    for col, metric in zip(cols, metrics):
        with col:
            metric_card(*metric)

    st.markdown(
        '<div class="section-heading">⚡ Quick Actions</div>',
        unsafe_allow_html=True,
    )

    quick_cols = st.columns(3)

    quick_actions = [
        (
            "📷 Scan / Issue / Return",
            "📷 Scan / Issue / Return",
        ),
        ("🔎 Search Files", "🔎 Search Files"),
        ("📝 Register New File", "📝 Register File"),
    ]

    for col, (label, page) in zip(quick_cols, quick_actions):
        with col:
            if st.button(
                label,
                type=(
                    "primary"
                    if page == "📷 Scan / Issue / Return"
                    else "secondary"
                ),
                use_container_width=True,
            ):
                st.session_state["quick_page"] = page
                st.rerun()

    if is_admin(current_user) and pending:
        st.warning(
            f"There {'is' if len(pending) == 1 else 'are'} "
            f"{len(pending)} file record(s) awaiting approval."
        )

        if st.button("Review Pending Approvals"):
            st.session_state["quick_page"] = "✅ Approve Files"
            st.rerun()

    st.markdown(
        '<div class="section-heading">📤 Files Currently Out</div>',
        unsafe_allow_html=True,
    )

    if out_items:
        st.dataframe(
            file_dataframe(out_items),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No files are currently marked as issued.")

    st.markdown(
        '<div class="section-heading">🕒 Recent File Activity</div>',
        unsafe_allow_html=True,
    )

    movements = get_movements(current_user=current_user) or []

    if movements:
        recent = [
            {
                "File": value(m, "file_name", default="—"),
                "Staff Member": value(m, "user_name", default="—"),
                "Action": value(m, "action", default="—"),
                "Date & Time": value(m, "movement_time", default="—"),
            }
            for m in movements[:8]
        ]

        st.dataframe(
            pd.DataFrame(recent),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No file movement has been recorded yet.")


# =========================================================
# SCAN / ISSUE / RETURN
# =========================================================
elif selected_page == "📷 Scan / Issue / Return":
    show_header(
        "📷 Scan / Issue / Return",
        "Use a connected barcode scanner or type the file ID/barcode.",
    )

    if is_view_only(current_user):
        st.info(
            "Your View Only role allows you to view records, "
            "but not issue or return files."
        )

    identifier = st.text_input(
        "Scan or enter File ID / Barcode",
        placeholder="Example: DFS-000001",
        key="scan_identifier",
    )

    with st.expander("📸 Scan using this device's camera"):
        st.caption("Allow camera access and capture a clear image of a supported barcode. Manual entry remains available.")
        camera_image = st.camera_input("Capture barcode", key="barcode_camera")
        if camera_image is not None:
            try:
                import zxingcpp
                from PIL import Image
                import numpy as np
                decoded = zxingcpp.read_barcodes(np.array(Image.open(camera_image).convert("RGB")))
                if decoded:
                    st.session_state["decoded_identifier"] = decoded[0].text
                    st.toast(f"Barcode detected: {decoded[0].text}. Select Find File to continue.", icon="📷")
                else:
                    st.warning("No barcode detected. Try better lighting or enter the code manually.")
            except ImportError:
                st.error("Barcode decoding dependency is missing. Install requirements.txt and restart.")
            except Exception as exc:
                st.error(f"Could not decode the captured image: {exc}")

    identifier = st.session_state.get("decoded_identifier") or identifier
    if st.button("🔍 Find File", type="primary"):
        st.session_state.pop("decoded_identifier", None)
        if identifier.strip():
            st.session_state.scanned_item = find_item(
                identifier.strip(),
                current_user=current_user,
            )

            if not st.session_state.scanned_item:
                st.warning(
                    "No matching file was found, or it is outside "
                    "your authorized access."
                )
        else:
            st.warning("Enter or scan a file ID/barcode first.")

    item = st.session_state.get("scanned_item")

    if item:
        st.subheader("File Details")
        c1, c2 = st.columns(2)

        with c1:
            st.write("**File ID:**", file_id(item))
            st.write("**File Name:**", file_name(item))
            st.write("**Department:**", value(item, "department"))
            st.write("**Section:**", value(item, "section") or "—")

        with c2:
            st.write("**Barcode:**", value(item, "barcode") or "—")
            st.write("**Status:**", file_status(item))
            st.write(
                "**Approval:**",
                value(item, "approval_status", default="APPROVED"),
            )
            st.write(
                "**Current Holder:**",
                value(item, "current_holder_name") or "None",
            )

        if str(
            value(item, "approval_status", default="APPROVED")
        ).upper() != "APPROVED":
            st.warning(
                "This file must be approved before it can be retrieved."
            )

        if can_manage_files(current_user):
            remarks = st.text_area(
                "Remarks (optional)",
                key="movement_remarks",
            )

            if is_out(item):
                if str(value(item, "current_holder_id")) == str(
                    current_user_id
                ):
                    if st.button(
                        "↩️ Return This File",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            return_item(
                                int(value(item, "id")),
                                current_user_id,
                                remarks.strip(),
                            )

                            st.success("File returned successfully.")
                            st.session_state.pop("scanned_item", None)
                            st.rerun()

                        except Exception as exc:
                            st.error(f"Could not return file: {exc}")
                else:
                    st.warning(
                        "Only the current holder can return this file."
                    )

            elif str(
                value(item, "approval_status", default="APPROVED")
            ).upper() == "APPROVED":
                issue_label = "📤 Issue This File to Me" if is_admin(current_user) else "📨 Request Retrieval"
                if st.button(
                    issue_label,
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        if is_admin(current_user):
                            issue_item(int(value(item, "id")), current_user_id, remarks.strip())
                            st.toast("File issued successfully.", icon="✅")
                        else:
                            request_retrieval(int(value(item, "id")), current_user_id, remarks.strip())
                            st.toast("Retrieval request sent to an administrator.", icon="📨")
                        st.session_state.pop("scanned_item", None)
                        st.rerun()

                    except Exception as exc:
                        st.error(f"Could not issue file: {exc}")


# =========================================================
# SEARCH FILES
# =========================================================
elif selected_page == "🔎 Search Files":
    show_header(
        "🔎 Search Files",
        "Search only records your role and department/section allow you to view.",
    )

    items = visible_files(current_user)

    if not items:
        st.info("No files are visible to your account yet.")
    else:
        term = st.text_input(
            "Search files",
            placeholder="File name, ID, department or barcode...",
        )

        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Available", "Out"],
        )

        departments = sorted({
            str(value(item, "department"))
            for item in items
            if value(item, "department")
        })

        dept_filter = st.selectbox(
            "Filter by Department",
            ["All Departments"] + departments,
        )

        filtered = []

        for item in items:
            searchable_text = " ".join(
                str(value(item, key, default=""))
                for key in (
                    "file_id",
                    "file_name",
                    "department",
                    "section",
                    "barcode",
                    "current_holder_name",
                )
            ).lower()

            if term.strip().lower() not in searchable_text:
                continue

            if status_filter == "Available" and is_out(item):
                continue

            if status_filter == "Out" and not is_out(item):
                continue

            if (
                dept_filter != "All Departments"
                and str(value(item, "department")) != dept_filter
            ):
                continue

            filtered.append(item)

        st.caption(f"{len(filtered)} file(s) found.")

        if filtered:
            st.dataframe(
                file_dataframe(filtered),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No files match your filters.")

        st.markdown("### View an individual file")

        chosen = st.text_input(
            "File ID or barcode",
            placeholder="Example: DFS-000001",
            key="search_detail_id",
        )

        if st.button("View File Details"):
            st.session_state.detail_item = (
                find_item(
                    chosen.strip(),
                    current_user=current_user,
                )
                if chosen.strip()
                else None
            )

            if not st.session_state.detail_item:
                st.warning("No matching file was found.")

        detail = st.session_state.get("detail_item")

        if detail:
            st.write("**File ID:**", file_id(detail))
            st.write("**File Name:**", file_name(detail))
            st.write("**Department:**", value(detail, "department"))
            st.write("**Section:**", value(detail, "section") or "—")
            st.write("**Status:**", file_status(detail))
            st.write(
                "**Approval:**",
                value(detail, "approval_status", default="APPROVED"),
            )

            if value(detail, "barcode"):
                generate_and_show_barcode(value(detail, "barcode"))


# =========================================================
# REGISTER FILE
# =========================================================
elif selected_page == "📝 Register File":
    show_header(
        "📝 Register File",
        "Register a file and generate a printable barcode label.",
    )

    if is_view_only(current_user):
        st.warning("Your View Only role cannot register files.")
    else:
        with st.form("register_file_form"):
            name = st.text_input(
                "File Name",
                placeholder="Enter the file title",
            )

            if is_admin(current_user):
                department = st.text_input(
                    "Department",
                    value=str(current_user_department),
                )
                section = st.text_input(
                    "Section (optional)",
                    value=str(current_user_section),
                )
            else:
                department = st.text_input(
                    "Department",
                    value=str(current_user_department),
                    disabled=True,
                )
                section = st.text_input(
                    "Section (optional)",
                    value=str(current_user_section),
                    disabled=bool(current_user_section),
                )

            submitted = st.form_submit_button(
                "Register File",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            try:
                new_id = add_item(
                    name,
                    department,
                    section or None,
                    created_by=current_user,
                )

                st.success(f"File registered. File ID: {new_id}")
                st.info(
                    "Your file record may require administrator approval "
                    "before it can be issued."
                )
                generate_and_show_barcode(new_id)

            except Exception as exc:
                st.error(f"Could not register file: {exc}")

    st.divider()
    st.caption("Recent visible records")

    st.dataframe(
        file_dataframe(visible_files(current_user)),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# MODIFY / REMOVE FILE
# =========================================================
elif selected_page == "✏️ Modify / Remove File":
    show_header(
        "✏️ Modify / Remove File",
        "Submit metadata changes or deletion requests for administrator review.",
    )

    items = visible_files(current_user)

    if is_view_only(current_user):
        st.info(
            "Your View Only role cannot modify or remove files."
        )

    elif not items:
        st.info("No accessible files are available.")

    else:
        options = {
            f"{file_id(item)} — {file_name(item)}": item
            for item in items
        }

        selected_label = st.selectbox(
            "Choose a file",
            list(options.keys()),
        )

        item = options[selected_label]
        created_by = value(item, "created_by", default=None)

        if (
            not is_admin(current_user)
            and str(created_by) != str(current_user_id)
        ):
            st.warning(
                "You can view this file, but you can modify or remove "
                "only files you created."
            )

        else:
            with st.form("modify_file_form"):
                new_name = st.text_input(
                    "File Name",
                    value=str(value(item, "file_name")),
                )

                if is_admin(current_user):
                    new_department = st.text_input(
                        "Department",
                        value=str(value(item, "department")),
                    )
                    new_section = st.text_input(
                        "Section",
                        value=str(value(item, "section") or ""),
                    )
                else:
                    new_department = st.text_input(
                        "Department",
                        value=str(value(item, "department")),
                        disabled=True,
                    )
                    new_section = st.text_input(
                        "Section",
                        value=str(value(item, "section") or ""),
                        disabled=bool(current_user_section),
                    )

                modify_submit = st.form_submit_button(
                    "Save Changes",
                    type="primary",
                )

            if modify_submit:
                try:
                    modify_item(
                        int(value(item, "id")),
                        current_user_id,
                        {
                            "file_name": new_name,
                            "department": new_department,
                            "section": new_section,
                        },
                    )

                    if is_admin(current_user):
                        st.toast("File record updated.", icon="✅")
                    else:
                        st.toast("Modification request sent to an administrator.", icon="📨")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not update file: {exc}")

            st.divider()
            st.warning(
                "Removal hides a file from active records; "
                "it does not erase the audit trail."
            )

            remove_reason = st.text_input(
                "Reason for removal (optional)",
                key="remove_reason",
            )

            confirm_remove = st.checkbox(
                "I confirm this file should be removed from active records."
            )

            if st.button(
                "Remove from Active Records",
                type="secondary",
                disabled=not confirm_remove,
            ):
                try:
                    soft_delete_item(
                        int(value(item, "id")),
                        current_user_id,
                        remove_reason.strip(),
                    )

                    if is_admin(current_user):
                        st.toast("File removed from active records.", icon="✅")
                    else:
                        st.toast("Deletion request sent to an administrator.", icon="📨")
                    st.rerun()

                except Exception as exc:
                    st.error(f"Could not remove file: {exc}")


# =========================================================
# APPROVAL QUEUE
# =========================================================
elif selected_page.startswith("✅ Approve Files"):
    show_header(
        "✅ Approve Files",
        "Review file records awaiting administrator approval.",
    )

    if not is_admin(current_user):
        st.error("Administrator access is required.")

    else:
        all_items = get_items(
            current_user=current_user,
            include_deleted=False,
        ) or []

        pending = [
            item for item in all_items
            if str(
                value(item, "approval_status", default="APPROVED")
            ).upper() == "PENDING"
        ]

        if not pending:
            st.success("There are no pending file records.")

        for item in pending:
            with st.expander(
                f"{file_id(item)} — {file_name(item)}"
            ):
                st.write(
                    "**Department:**",
                    value(item, "department"),
                )
                st.write(
                    "**Section:**",
                    value(item, "section") or "—",
                )
                st.write(
                    "**Created by:**",
                    value(item, "creator_name") or "—",
                )

                remarks = st.text_input(
                    "Approval/rejection note (optional)",
                    key=f"approval_note_{value(item, 'id')}",
                )

                c1, c2 = st.columns(2)

                with c1:
                    if st.button(
                        "Approve",
                        key=f"approve_{value(item, 'id')}",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            approve_item(
                                int(value(item, "id")),
                                current_user_id,
                                approved=True,
                                remarks=remarks,
                            )

                            st.success("File approved.")
                            st.rerun()

                        except Exception as exc:
                            st.error(f"Could not approve file: {exc}")

                with c2:
                    if st.button(
                        "Reject",
                        key=f"reject_{value(item, 'id')}",
                        use_container_width=True,
                    ):
                        try:
                            approve_item(
                                int(value(item, "id")),
                                current_user_id,
                                approved=False,
                                remarks=remarks,
                            )

                            st.warning("File rejected.")
                            st.rerun()

                        except Exception as exc:
                            st.error(f"Could not reject file: {exc}")


# =========================================================
# REGISTER USER
# =========================================================
elif selected_page == "👤 Register User":
    show_header(
        "👤 Register User",
        "Create an account for an authorized staff member.",
    )

    if not is_admin(current_user):
        st.error("Administrator access is required.")

    else:
        with st.form("register_user_form"):
            name = st.text_input("Full Name")
            email = st.text_input("Organization Email")
            department = st.text_input("Department")
            section = st.text_input("Section (optional)")
            staff_no = st.text_input("Staff Number")

            new_role = st.selectbox(
                "Role",
                ["User", "View Only", "Admin"],
            )

            password = st.text_input(
                "Temporary Password",
                type="password",
            )
            confirm = st.text_input(
                "Confirm Password",
                type="password",
            )

            submit = st.form_submit_button(
                "Create User",
                type="primary",
                use_container_width=True,
            )

        if submit:
            if not all([
                name.strip(),
                email.strip(),
                department.strip(),
                staff_no.strip(),
                password,
            ]):
                st.error("Complete all required fields.")

            elif password != confirm:
                st.error("Passwords do not match.")

            else:
                try:
                    add_user(
                        name,
                        email,
                        department,
                        section or None,
                        staff_no,
                        role=new_role,
                        password=password,
                        admin_user_id=current_user_id,
                    )

                    st.success("User registered successfully.")

                except Exception as exc:
                    st.error(f"Could not register user: {exc}")


# =========================================================
# ADMIN REQUEST QUEUE
# =========================================================
elif selected_page.startswith("📥 Request Queue"):
    show_header("📥 Request Queue", "Review staff requests for deletion, metadata changes and file retrieval.")
    if not is_admin(current_user):
        st.error("Administrator access is required.")
    else:
        requests = get_file_requests(current_user, status="PENDING") or []
        if not requests:
            st.success("No pending requests.")
        for req in requests:
            kind = str(value(req, "request_type", default="REQUEST")).title()
            with st.expander(f"{kind} · {value(req, 'file_id')} — {value(req, 'file_name')} · {value(req, 'requester_name')}"):
                st.write(f"**Requester:** {value(req, 'requester_name')} ({value(req, 'requester_staff_number')})")
                st.write(f"**Department / Section:** {value(req, 'department')} / {value(req, 'section') or '—'}")
                st.write(f"**Reason:** {value(req, 'reason') or 'Not provided'}")
                if value(req, "payload"):
                    try:
                        st.json(__import__("json").loads(value(req, "payload")))
                    except Exception:
                        st.code(value(req, "payload"))
                note = st.text_input("Review note (optional)", key=f"request_note_{value(req, 'request_id', 'id')}")
                left, right = st.columns(2)
                with left:
                    if st.button("Approve request", key=f"request_approve_{value(req, 'request_id', 'id')}", type="primary", use_container_width=True):
                        try:
                            review_file_request(int(value(req, "id")), current_user_id, True, note)
                            st.toast("Request approved.", icon="✅")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not approve request: {exc}")
                with right:
                    if st.button("Reject request", key=f"request_reject_{value(req, 'request_id', 'id')}", use_container_width=True):
                        try:
                            review_file_request(int(value(req, "id")), current_user_id, False, note)
                            st.toast("Request rejected.", icon="ℹ️")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not reject request: {exc}")


# =========================================================
# USER DIRECTORY
# =========================================================
elif selected_page == "👥 User Directory":
    show_header(
        "👥 User Directory",
        "View registered user accounts.",
    )

    if not is_admin(current_user):
        st.error("Administrator access is required.")

    else:
        users = get_users(active_only=False, current_user=current_user) or []

        rows = [
            {
                "Name": value(user, "name"),
                "Email": value(user, "email"),
                "Department": value(user, "department"),
                "Section": value(user, "section") or "—",
                "Staff Number": value(user, "staff_number"),
                "Role": value(user, "role"),
                "Active": bool(value(user, "active", default=1)),
            }
            for user in users
        ]

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )


        st.divider()
        st.subheader("Deactivate user account")
        active_users = [u for u in users if bool(value(u, "active", default=1))]
        targets = {f"{value(u, 'name')} · {value(u, 'staff_number')} · {value(u, 'role')}": u for u in active_users if str(value(u, "id")) != str(current_user_id)}
        if targets:
            target_label = st.selectbox("Select account", list(targets.keys()))
            if st.button("Deactivate selected account", type="secondary"):
                try:
                    admin_delete_user(current_user_id, int(value(targets[target_label], "id")))
                    st.toast("User account deactivated.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not deactivate account: {exc}")
        else:
            st.info("No other active accounts are available to deactivate.")


# =========================================================
# MOVEMENT HISTORY
# =========================================================
elif selected_page == "🕒 Movement History":
    show_header(
        "🕒 Movement History",
        "Review recorded file issues and returns.",
    )

    movements = get_movements(
        current_user=current_user
    ) or []

    if not movements:
        st.info("No file movements have been recorded.")

    else:
        rows = [
            {
                "File ID": value(
                    movement, "system_file_id", "file_id", default="—"
                ),
                "File Name": value(
                    movement, "file_name", default="—"
                ),
                "Staff Member": value(
                    movement, "user_name", default="—"
                ),
                "Staff Number": value(
                    movement, "staff_number", default="—"
                ),
                "Action": value(
                    movement, "action", default="—"
                ),
                "Date & Time": value(
                    movement, "movement_time", default="—"
                ),
                "Remarks": value(
                    movement, "remarks", default="—"
                ),
            }
            for movement in movements
        ]

        df = pd.DataFrame(rows)

        search = st.text_input(
            "Filter movement history",
            placeholder="Search file, staff member or action...",
        )

        if search.strip():
            mask = df.astype(str).apply(
                lambda col: col.str.contains(
                    search.strip(),
                    case=False,
                    na=False,
                )
            ).any(axis=1)

            df = df[mask]

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# AUDIT TRAIL — READ ONLY
# =========================================================
elif selected_page == "📜 Audit Trail":
    show_header(
        "📜 Audit Trail",
        "Read-only accountability history. Entries cannot be edited or deleted here.",
    )

    audit = get_audit_trail(
        current_user=current_user
    ) or []

    if audit:
        rows = [
            {
                "Date & Time": value(entry, "created_at"),
                "File ID": value(entry, "file_id") or "—",
                "File Name": value(entry, "file_name") or "—",
                "Actor": value(entry, "actor_name"),
                "Action": value(entry, "action"),
                "Outcome": value(entry, "outcome"),
                "Details": value(entry, "details") or "—",
            }
            for entry in audit
        ]

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No audit entries are available for your account.")


# =========================================================
# SONA NOTIFICATIONS
# =========================================================
elif selected_page == "🔔 Notifications":
    show_header(
        "🔔 Notifications",
        "System alerts for file activity and account events.",
    )

    notifications = get_notifications(
        current_user_id,
        include_read=True,
    ) or []

    unread = [
        note for note in notifications
        if not bool(value(note, "is_read", default=0))
    ]

    c1, c2 = st.columns([1, 3])

    with c1:
        st.metric("Unread notifications", len(unread))

        if unread and st.button(
            "Mark All as Read",
            type="primary",
            use_container_width=True,
        ):
            mark_notifications_read(current_user_id)
            st.success("Notifications marked as read.")
            st.rerun()

    with c2:
        if not notifications:
            st.info("You have no notifications.")

        for note in notifications:
            read = bool(value(note, "is_read", default=0))

            with st.container(border=True):
                title = value(
                    note, "title", default="Notification"
                )

                st.markdown(
                    ("**✓ " if read else "**🔔 ")
                    + str(title)
                    + "**"
                )

                st.write(value(note, "message"))

                st.caption(
                    f"{value(note, 'created_at')} · "
                    f"{value(note, 'notification_type', default='INFO')} · "
                    f"{'Read' if read else 'Unread'}"
                )


# =========================================================
# OATH & RESPONSIBILITIES
# =========================================================
elif selected_page == "📋 Oath & Responsibilities":
    show_header(
        "📋 Oath & Responsibilities",
        "Responsibilities for staff using the Digital Filing System.",
    )

    st.markdown(
        """
        <div class="panel">
            <h3>Staff Responsibilities</h3>
            <ul>
                <li>Use the system only for authorized organizational work.</li>
                <li>Ensure file details are accurate when registering or updating records.</li>
                <li>Verify the correct file ID before issuing or returning a physical file.</li>
                <li>Keep physical files secure and return issued files promptly.</li>
                <li>Do not share passwords or use another staff member's account.</li>
                <li>Respect department and section access restrictions.</li>
                <li>Understand that file actions are recorded in an audit trail.</li>
                <li>Report missing files, incorrect records, or suspected unauthorized access.</li>
            </ul>

            <h3>Credit / Filing Administrator Responsibilities</h3>
            <ul>
                <li>Review pending file registrations and approve or reject them responsibly.</li>
                <li>Maintain accurate user roles and access rights.</li>
                <li>Follow organizational retention and records-management procedures.</li>
                <li>Never attempt to alter or erase audit history.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

    acknowledged_at = value(
        current_user,
        "oath_acknowledged_at",
        default=None,
    )

    if acknowledged_at:
        st.success(
            f"You acknowledged these responsibilities on {acknowledged_at}."
        )

    else:
        accepted = st.checkbox(
            "I have read and agree to follow these responsibilities."
        )

        if st.button(
            "Acknowledge Oath",
            type="primary",
            disabled=not accepted,
        ):
            try:
                timestamp = acknowledge_oath(current_user_id)

                st.session_state.logged_in_user[
                    "oath_acknowledged_at"
                ] = timestamp

                st.success(
                    "Your acknowledgement has been recorded."
                )
                st.rerun()

            except Exception as exc:
                st.error(
                    f"Could not record acknowledgement: {exc}"
                )


# =========================================================
# EXCEL EXPORT
# =========================================================
elif selected_page == "📤 Export to Excel":
    show_header(
        "📤 Export to Excel",
        "Download an Excel copy of the file records visible to your account.",
    )

    items = visible_files(current_user)

    if not items:
        st.info(
            "No visible file records are available to export."
        )

    else:
        st.dataframe(
            file_dataframe(items),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download File Register (.xlsx)",
            data=excel_bytes(items),
            file_name="digital_filing_system_export.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            type="primary",
        )
