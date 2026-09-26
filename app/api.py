"""
app/api.py - Unified REST/JSON API layer.

Combines all three API surfaces of the application into one file:
  - /tcsadmin/api/*    scraper admin backend (register_tcsadmin_api_routes)
  - /visionadmin/api/* CMS backend (register_visionadmin_api_routes)
  - /api/*             public client-facing API (register_client_api_routes)

register_api_routes(app) registers all three. Page-rendering routes for
each of the three areas live in their own dedicated files instead:
  - app/scraperapp/tcsadmin.py       (tcsadmin pages)
  - app/visionadmin/Visionadminroute.py (visionadmin pages)
  - app/siteapp/clientroute.py       (client pages, site_bp blueprint)
"""

import csv
from datetime import datetime
import io
import json
from collections import OrderedDict
import math
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from flask import Response, jsonify, render_template, request, send_file, send_from_directory, session, stream_with_context
from openpyxl import Workbook, load_workbook
import pymysql
from werkzeug.utils import secure_filename

from auth import (
    VALID_ROLES,
    bit_to_bool,
    get_user_by_id,
    has_superadmin,
    hash_password,
    list_active_users,
    list_deleted_users,
    login_required_api,
    require_csrf,
    role_required_api,
    serialize_user,
    to_ist_12h,
    verify_password,
)
from db import get_connection
from models.blog import Blog
from models.page import Page
from models.page_section import PageSection
from models.product import Product
from models.brand import Brand
from models.category import Category
from services.store_context import StoreContext
from i18n import get_locale, localize_value, translate, is_rtl, get_translated_value
from services.audit_service import log_activity, get_activity_logs, get_current_admin_user_id
from services.attribute_service import AttributeService

EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
# This file is app/api.py, so the project root (where scrapers/ and tmp/
# live) is one directory up.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_SCRAPERS_DIR = os.path.join(BASE_DIR, 'tmp', 'scrapers')
sys.path.insert(0, os.path.join(BASE_DIR, 'scrapers'))

import file_scraper_runner
import files_repo
import job_manager
import reports_repo
from scraper_config import SCRIPT_MAP
from scraper_input import (
    InputError,
    build_entries,
    extract_input_source,
    format_invalid_url_message,
    format_unsupported_message,
    parse_csv_urls,
    parse_text_urls,
    validate_url_list,
)
from scraper_status_utils import build_status_summary, parse_status_line


class ScraperSession:
    """In-memory state for one browser session's ad-hoc scraping runs."""
    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.url_statuses = []
        self.job_status = 'idle'  # idle | running | completed_unseen | failed_unseen
        self.stopped = False
        self.job_id = None
        self.output_file = None
        self.thread = None
        self.pending_groups = []
        self.skipped = {'invalid': [], 'unsupported': []}


_scraper_sessions = {}
_sessions_lock = threading.Lock()


def get_scraper_session():
    sid = session.get('sid')
    if not sid:
        sid = secrets.token_hex(16)
        session['sid'] = sid
    with _sessions_lock:
        if sid not in _scraper_sessions:
            _scraper_sessions[sid] = ScraperSession()
        return _scraper_sessions[sid]


def get_xlsx_info(output_file):
    if not output_file or not os.path.exists(output_file):
        return 0, set()
    try:
        wb = load_workbook(output_file, read_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            return 0, set()
        header = [str(c).strip().lower() if c is not None else '' for c in rows[0]]
        url_col_idx = None
        for candidate in ('url', 'product url', 'link', 'product link'):
            if candidate in header:
                url_col_idx = header.index(candidate)
                break
        urls = set()
        count = 0
        for row in rows[1:]:
            if any(cell is not None for cell in row):
                count += 1
                if url_col_idx is not None and url_col_idx < len(row):
                    val = row[url_col_idx]
                    if val:
                        urls.add(str(val).strip())
        return count, urls
    except Exception:
        return 0, set()


def _record_status_line(state, cleaned_line):
    parsed_status = parse_status_line(cleaned_line)
    if not parsed_status:
        return
    with state.lock:
        existing = next((item for item in state.url_statuses if item['url'] == parsed_status['url']), None)
        if existing:
            existing['status'] = parsed_status['status']
            if parsed_status.get('parent'):
                existing['parent'] = parsed_status['parent']
            if parsed_status.get('type'):
                existing['type'] = parsed_status['type']
        else:
            state.url_statuses.append({
                'url': parsed_status['url'],
                'status': parsed_status['status'],
                'parent': parsed_status.get('parent') or '',
                'type': parsed_status.get('type') or 'root',
            })


def _merge_xlsx_outputs(source_paths, destination):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Products'
    header_written = False

    for path in source_paths:
        try:
            src_wb = load_workbook(path, read_only=True)
        except Exception:
            continue
        try:
            rows = src_wb.active.iter_rows(values_only=True)
            header = next(rows, None)
            if header is None:
                continue
            if not header_written:
                ws.append(list(header))
                header_written = True
            for row in rows:
                ws.append(list(row))
        finally:
            src_wb.close()

    if not header_written:
        ws.append(['No data'])

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    wb.save(destination)


def _run_job_groups(state):
    group_outputs = []
    had_failure = False

    for group in state.pending_groups:
        with state.lock:
            if state.stopped:
                break

        process = subprocess.Popen(
            [sys.executable, '-u', group['script_path'], group['output_path'], group['input_path']],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with state.lock:
            state.process = process

        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            _record_status_line(state, line.rstrip('\n'))
        process.stdout.close()
        process.wait()

        with state.lock:
            state.process = None
        if process.returncode not in (0, None) and not state.stopped:
            had_failure = True
        if os.path.exists(group['output_path']):
            group_outputs.append(group['output_path'])

    _merge_xlsx_outputs(group_outputs, state.output_file)

    for group in state.pending_groups:
        for path in (group['input_path'], group['output_path']):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    with state.lock:
        if state.stopped:
            state.job_status = 'idle'
        elif had_failure:
            state.job_status = 'failed_unseen'
        else:
            state.job_status = 'completed_unseen'


def _parse_urls_text(urls_text):
    raw_urls = parse_text_urls(urls_text)
    urls, errors = validate_url_list(raw_urls)
    if errors:
        lines = [f"Invalid URL on row {e['row']}: {e['value']}" for e in errors]
        return [], 'Invalid URL(s):\n' + '\n'.join(lines)
    if not urls:
        return [], 'At least one valid URL is required.'
    return urls, None


def _format_scraper_output_filename(site_name, extension='xlsx'):
    clean_site = re.sub(r'[^A-Za-z0-9]+', '_', site_name or '').strip('_').upper() or 'SCRAPER'
    today = datetime.now().strftime('%d-%m-%Y')
    return f"{clean_site}_{today}.{extension}"


def register_tcsadmin_api_routes(app):
    """Registers all REST, JSON, and Scraper execution APIs under /tcsadmin/api (and bare /api aliases)."""

    # ==========================================================================
    # ==========================================================================
    # 1. User, Profile & Authentication APIs (admin_users table)
    # ==========================================================================

    @app.route('/visionadmin/api/me')
    @app.route('/tcsadmin/api/me')
    @app.route('/api/me')
    def api_me():
        user_id = session.get('admin_user_id') or session.get('user_id') or session.get('userid') or session.get('id')
        email = session.get('email') or session.get('Email')
        if not user_id and not email:
            return jsonify({'error': 'Authentication required.'}), 401

        from visionadmin.admin_auth import get_admin_user_by_id, get_admin_user_by_email, serialize_admin_user
        admin_u = None
        if user_id:
            admin_u = get_admin_user_by_id(user_id)
        if not admin_u and email:
            admin_u = get_admin_user_by_email(email)
            if admin_u:
                session['admin_user_id'] = admin_u['id']
                session['user_id'] = admin_u['id']
                session['userid'] = admin_u['id']
                session['id'] = admin_u['id']
                session['name'] = admin_u['name']
                session['Name'] = admin_u['name']
                session['email'] = admin_u['email']
                session['Email'] = admin_u['email']
                session['role'] = 'SuperAdmin' if admin_u['role'] in ('super_admin', 'superadmin', 'SuperAdmin') else ('Admin' if admin_u['role'] in ('manager', 'admin', 'Admin') else 'User')
                session['admin_role'] = admin_u['role']
                session['is_visionadmin'] = True
                session['logged_in'] = True

        if not admin_u:
            return jsonify({'error': 'Authentication required.'}), 401

        role_disp = 'SuperAdmin' if admin_u.get('role') in ('super_admin', 'superadmin', 'SuperAdmin') else ('Admin' if admin_u.get('role') in ('manager', 'admin', 'Admin') else 'User')

        return jsonify({
            'user': {
                'userid': admin_u['id'],
                'id': admin_u['id'],
                'name': admin_u['name'],
                'Name': admin_u['name'],
                'email': admin_u['email'],
                'Email': admin_u['email'],
                'role': role_disp,
                'Role': role_disp,
                'admin_role': admin_u.get('role'),
                'status': bool(admin_u.get('is_active', 1)),
                'avatar': None,
                'createdAt': str(admin_u.get('created_at', '')),
                'updatedAt': str(admin_u.get('updated_at', '')),
            },
            'csrfToken': session.get('csrf_token')
        })

    @app.route('/visionadmin/api/profile', methods=['PUT'])
    @app.route('/tcsadmin/api/profile', methods=['PUT'])
    @app.route('/api/profile', methods=['PUT'])
    @require_csrf
    def api_update_profile():
        user_id = session.get('admin_user_id') or session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required.'}), 401

        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()

        if not name:
            return jsonify({'error': 'Name is required.'}), 400
        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'A valid email is required.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        'UPDATE `admin_users` SET `name` = %s, `email` = %s, `updated_at` = NOW() WHERE `id` = %s',
                        (name, email, user_id),
                    )
                    conn.commit()
                except pymysql.err.IntegrityError:
                    return jsonify({'error': 'That email is already in use.'}), 409
        finally:
            conn.close()

        session['name'] = name
        session['email'] = email

        return jsonify({
            'user': {
                'id': user_id,
                'userid': user_id,
                'name': name,
                'Name': name,
                'email': email,
                'Email': email,
                'role': session.get('role'),
                'Role': session.get('role')
            }
        })

    @app.route('/visionadmin/api/profile/avatar', methods=['DELETE'])
    @app.route('/tcsadmin/api/profile/avatar', methods=['DELETE'])
    @app.route('/api/profile/avatar', methods=['DELETE'])
    @require_csrf
    def api_delete_avatar():
        return jsonify({'success': True})

    @app.route('/visionadmin/api/change-password', methods=['POST'])
    @app.route('/visonadmin/api/change-password', methods=['POST'])
    @app.route('/tcsadmin/api/change-password', methods=['POST'])
    @app.route('/api/change-password', methods=['POST'])
    @require_csrf
    def api_change_password():
        user_id = session.get('admin_user_id') or session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required.'}), 401

        fail_count = session.get('pwd_fail_count', 0)
        if fail_count >= 5:
            return jsonify({'error': 'Too many failed attempts. Please try again later.'}), 429

        data = request.get_json(silent=True) or {}
        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'All fields are required.'}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'New password and confirmation do not match.'}), 400
        if len(new_password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters.'}), 400

        from visionadmin.admin_auth import get_admin_user_by_id, verify_admin_password, update_admin_user_password
        admin_u = get_admin_user_by_id(user_id)
        if not admin_u or not verify_admin_password(current_password, admin_u.get('password', '')):
            session['pwd_fail_count'] = fail_count + 1
            return jsonify({'error': 'Current password is incorrect.'}), 400

        update_admin_user_password(user_id, new_password)
        session['pwd_fail_count'] = 0
        return jsonify({'message': 'Password updated successfully.'})

    @app.route('/tcsadmin/api/profile/delete-account', methods=['POST', 'DELETE'])
    @app.route('/api/profile/delete-account', methods=['POST', 'DELETE'])
    @app.route('/visionadmin/api/profile/delete-account', methods=['POST', 'DELETE'])
    @app.route('/api/profile/delete', methods=['POST', 'DELETE'])
    @login_required_api
    @require_csrf
    def api_self_delete_account():
        user_id = session.get('admin_user_id') or session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Authentication required.'}), 401

        from visionadmin.admin_auth import toggle_admin_user_status, count_super_admins, get_admin_user_by_id
        target = get_admin_user_by_id(user_id)
        if not target:
            session.clear()
            return jsonify({'error': 'User not found.'}), 404

        if target.get('role') == 'super_admin' and count_super_admins() <= 1:
            return jsonify({'error': 'Cannot delete the only remaining Super Administrator.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE `admin_users` SET `is_active` = 0, `updated_at` = NOW() WHERE `id` = %s', (user_id,))
                conn.commit()
        finally:
            conn.close()

        session.clear()
        return jsonify({
            'success': True,
            'message': 'Your account has been deactivated successfully.',
            'redirect': '/visionadmin/login'
        })

    # ==========================================================================
    # 2. Admin User Management APIs (Alias to admin_users table)
    # ==========================================================================

    @app.route('/tcsadmin/api/admin/users', methods=['GET'])
    @app.route('/api/admin/users', methods=['GET'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin', 'super_admin', 'manager')
    def api_admin_list_users():
        return jsonify({'users': [serialize_user(u) for u in list_active_users()]})

    @app.route('/tcsadmin/api/admin/users/trash', methods=['GET'])
    @app.route('/api/admin/users/trash', methods=['GET'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin', 'super_admin', 'manager')
    def api_admin_list_trash():
        return jsonify({'users': [serialize_user(u) for u in list_deleted_users()]})

    @app.route('/tcsadmin/api/admin/users', methods=['POST'])
    @app.route('/api/admin/users', methods=['POST'])
    @login_required_api
    @role_required_api('SuperAdmin')
    @require_csrf
    def api_admin_create_user():
        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''
        role = (data.get('role') or '').strip()
        status = data.get('status', True)

        if not name:
            return jsonify({'error': 'Name is required.'}), 400
        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'A valid email is required.'}), 400
        if not password or len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters.'}), 400
        if role not in VALID_ROLES:
            return jsonify({'error': f"Role must be one of: {', '.join(VALID_ROLES)}."}), 400
        if role == 'SuperAdmin' and has_superadmin():
            return jsonify({'error': 'A SuperAdmin already exists. Only one SuperAdmin account is allowed.'}), 409

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(
                        'INSERT INTO userTbl (Name, Email, password, Status, IsDeleted, Role) '
                        'VALUES (%s, %s, %s, %s, 0, %s)',
                        (name, email, hash_password(password), 1 if status else 0, role),
                    )
                except pymysql.err.IntegrityError:
                    return jsonify({'error': 'A user with that email already exists.'}), 409
                new_user_id = cursor.lastrowid
        finally:
            conn.close()

        return jsonify({'user': serialize_user(get_user_by_id(new_user_id))}), 201

    @app.route('/tcsadmin/api/admin/users/<int:user_id>', methods=['PUT'])
    @app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin')
    @require_csrf
    def api_admin_update_user(user_id):
        target = get_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'User not found.'}), 404

        actor_role = session.get('role')
        if target['Role'] == 'SuperAdmin' and actor_role != 'SuperAdmin':
            return jsonify({'error': 'Only a SuperAdmin can modify a SuperAdmin account.'}), 403

        data = request.get_json(silent=True) or {}
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip()
        role = (data.get('role') or '').strip()
        password = data.get('password') or ''
        status = data.get('status', True)

        if not name:
            return jsonify({'error': 'Name is required.'}), 400
        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'A valid email is required.'}), 400
        if role not in VALID_ROLES:
            return jsonify({'error': f"Role must be one of: {', '.join(VALID_ROLES)}."}), 400
        if role == 'SuperAdmin' and actor_role != 'SuperAdmin':
            return jsonify({'error': 'Only a SuperAdmin can grant the SuperAdmin role.'}), 403
        if role == 'SuperAdmin' and target['Role'] != 'SuperAdmin' and has_superadmin():
            return jsonify({'error': 'A SuperAdmin already exists. Only one SuperAdmin account is allowed.'}), 409
        if password and len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                try:
                    if password:
                        cursor.execute(
                            'UPDATE userTbl SET Name = %s, Email = %s, Role = %s, Status = %s, password = %s '
                            'WHERE userid = %s',
                            (name, email, role, 1 if status else 0, hash_password(password), user_id),
                        )
                    else:
                        cursor.execute(
                            'UPDATE userTbl SET Name = %s, Email = %s, Role = %s, Status = %s WHERE userid = %s',
                            (name, email, role, 1 if status else 0, user_id),
                        )
                except pymysql.err.IntegrityError:
                    return jsonify({'error': 'That email is already in use.'}), 409
        finally:
            conn.close()

        updated = get_user_by_id(user_id)
        if user_id == session.get('user_id'):
            session['name'] = updated['Name']
            session['email'] = updated['Email']
            session['role'] = updated['Role']

        return jsonify({'user': serialize_user(updated)})

    @app.route('/tcsadmin/api/admin/users/<int:user_id>', methods=['DELETE'])
    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin')
    @require_csrf
    def api_admin_delete_user(user_id):
        target = get_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'User not found.'}), 404

        if target['Role'] == 'SuperAdmin' and user_id != session.get('user_id'):
            return jsonify({'error': 'SuperAdmin accounts can only be deleted by the account owner.'}), 403

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    'UPDATE userTbl SET IsDeleted = 1, deleted_at = UTC_TIMESTAMP() WHERE userid = %s',
                    (user_id,),
                )
        finally:
            conn.close()

        is_self = (user_id == session.get('user_id'))
        if is_self:
            session.clear()
            return jsonify({'message': 'Your account has been deleted.', 'selfDeleted': True, 'redirect': '/tcsadmin/login'})

        return jsonify({'message': 'User deleted.'})

    @app.route('/tcsadmin/api/admin/users/<int:user_id>/recover', methods=['POST'])
    @app.route('/api/admin/users/<int:user_id>/recover', methods=['POST'])
    @login_required_api
    @role_required_api('SuperAdmin')
    @require_csrf
    def api_admin_recover_user(user_id):
        target = get_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'User not found.'}), 404
        if not bit_to_bool(target['IsDeleted']):
            return jsonify({'error': 'This account is not deleted.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE userTbl SET IsDeleted = 0, deleted_at = NULL WHERE userid = %s', (user_id,))
        finally:
            conn.close()

        return jsonify({'message': 'User recovered.'})

    # ==========================================================================
    # 3. File / Registered Scraper APIs
    # ==========================================================================

    @app.route('/tcsadmin/api/files/running')
    @app.route('/api/files/running')
    @login_required_api
    def api_list_running_files():
        rows, _ = files_repo.list_files(per_page=200)
        running = [
            {'fileId': r['file_id'], 'siteName': r['site_name']}
            for r in rows
            if file_scraper_runner.is_running(r['file_id'])
        ]
        return jsonify({'files': running})

    @app.route('/tcsadmin/api/files')
    @app.route('/api/files')
    @login_required_api
    def api_list_files():
        search = request.args.get('search', '').strip() or None
        raw_trash = request.args.get('trash')
        is_deleted = None
        if raw_trash is not None:
            is_deleted = raw_trash.lower() in ('1', 'true', 'yes')

        try:
            page = int(request.args.get('page', 1))
        except ValueError:
            page = 1
        try:
            per_page = int(request.args.get('perPage', 20))
        except ValueError:
            per_page = 20

        rows, total = files_repo.list_files(search=search, is_deleted=is_deleted, page=page, per_page=per_page)
        serialized = []
        user_id = session.get('user_id')
        active_map = job_manager.get_all_active_jobs_map()
        all_outputs = file_scraper_runner.get_all_output_paths()

        for r in rows:
            fid = r['file_id']
            item = files_repo.serialize_file(r)
            active = active_map.get(fid)
            if active:
                item['working'] = True
                item['is_owner'] = (active.get('user_id') == user_id)
            else:
                item['working'] = False
                item['is_owner'] = True
            item['outputAvailable'] = bool(all_outputs.get(fid))
            serialized.append(item)

        any_running = bool(active_map)
        has_any_output = bool(all_outputs)

        return jsonify({
            'files': serialized,
            'total': total,
            'page': page,
            'perPage': per_page,
            'anyRunning': any_running,
            'hasAnyOutput': has_any_output,
        })

    @app.route('/tcsadmin/api/files', methods=['POST'])
    @app.route('/api/files', methods=['POST'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin')
    @require_csrf
    def api_create_file():
        data = request.get_json(silent=True) or {}
        site_name = (data.get('siteName') or '').strip()
        python_file_path = (data.get('pythonFilePath') or '').strip()
        logo = (data.get('logo') or '').strip() or None
        urls_text = data.get('urlsText') or ''

        if not site_name:
            return jsonify({'error': 'Name is required.'}), 400
        if not python_file_path:
            return jsonify({'error': 'Python file is required.'}), 400

        urls, url_error = _parse_urls_text(urls_text)
        if url_error:
            return jsonify({'error': url_error}), 400

        try:
            created_by = session.get('user_id')
            file_id = files_repo.create_file(logo, site_name, python_file_path, created_by=created_by)
        except files_repo.FileValidationError as exc:
            return jsonify({'error': str(exc)}), 400

        files_repo.set_urls(file_id, urls)
        return jsonify({'file': files_repo.serialize_file(files_repo.get_file(file_id))}), 201

    @app.route('/tcsadmin/api/files/<int:file_id>', methods=['PUT'])
    @app.route('/api/files/<int:file_id>', methods=['PUT'])
    @login_required_api
    @require_csrf
    def api_update_file(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404
        if file_scraper_runner.is_running(file_id):
            return jsonify({'error': 'Stop this scraper before editing it.'}), 409

        data = request.get_json(silent=True) or {}
        site_name = (data.get('siteName') or '').strip()
        python_file_path = (data.get('pythonFilePath') or '').strip()
        logo = (data.get('logo') or '').strip() or None
        urls_text = data.get('urlsText') or ''

        if not site_name:
            return jsonify({'error': 'Name is required.'}), 400
        if not python_file_path:
            return jsonify({'error': 'Python file is required.'}), 400

        urls, url_error = _parse_urls_text(urls_text)
        if url_error:
            return jsonify({'error': url_error}), 400

        try:
            files_repo.update_file(file_id, logo, site_name, python_file_path)
        except files_repo.FileValidationError as exc:
            return jsonify({'error': str(exc)}), 400

        files_repo.set_urls(file_id, urls)
        return jsonify({'file': files_repo.serialize_file(files_repo.get_file(file_id))})

    @app.route('/tcsadmin/api/files/<int:file_id>', methods=['DELETE'])
    @app.route('/api/files/<int:file_id>', methods=['DELETE'])
    @login_required_api
    @require_csrf
    def api_delete_file(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404
        if file_scraper_runner.is_running(file_id):
            return jsonify({'error': 'Stop this scraper before deleting it.'}), 409

        files_repo.delete_file(file_id)
        return jsonify({'message': 'Scraper permanently deleted.'})

    @app.route('/tcsadmin/api/files/<int:file_id>/toggle-status', methods=['POST'])
    @app.route('/api/files/<int:file_id>/toggle-status', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_toggle_file_status(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404

        if file_scraper_runner.is_running(file_id):
            return jsonify({'error': 'Stop this scraper before disabling it.'}), 409

        data = request.get_json(silent=True) or {}
        currently_deleted = files_repo.bit_to_bool(record.get('is_deleted'))

        if 'enabled' in data:
            new_enabled = bool(data['enabled'])
        else:
            new_enabled = currently_deleted

        files_repo.set_file_enabled(file_id, new_enabled)
        updated = files_repo.get_file(file_id)
        return jsonify({
            'success': True,
            'isEnabled': new_enabled,
            'isDeleted': not new_enabled,
            'message': 'Scraper enabled.' if new_enabled else 'Scraper disabled.',
            'file': files_repo.serialize_file(updated),
        })

    @app.route('/tcsadmin/api/files/<int:file_id>/restore', methods=['POST'])
    @app.route('/api/files/<int:file_id>/restore', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_restore_file(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404

        files_repo.restore_file(file_id)
        updated = files_repo.get_file(file_id)
        return jsonify({
            'success': True,
            'message': 'Scraper restored to Active list.',
            'file': files_repo.serialize_file(updated),
        })

    @app.route('/tcsadmin/api/files/upload-script', methods=['POST'])
    @app.route('/api/files/upload-script', methods=['POST'])
    @login_required_api
    @role_required_api('SuperAdmin', 'Admin')
    @require_csrf
    def api_upload_file_script():
        if not request.files or 'file' not in request.files:
            return jsonify({'error': 'No file uploaded.'}), 400

        upload = request.files['file']
        candidate_name = (upload.filename or '').strip()
        if candidate_name:
            existing = files_repo.get_file_by_path(candidate_name)
            if existing and file_scraper_runner.is_running(existing['file_id']):
                return jsonify({'error': 'Stop this scraper before replacing its Python file.'}), 409

        try:
            filename = files_repo.save_uploaded_script(upload)
        except files_repo.FileValidationError as exc:
            return jsonify({'error': str(exc)}), 400

        return jsonify({'fileName': filename})

    @app.route('/tcsadmin/api/files/parse-urls', methods=['POST'])
    @app.route('/api/files/parse-urls', methods=['POST'])
    @login_required_api
    def api_parse_urls():
        if request.files and 'file' in request.files:
            upload = request.files['file']
            filename = (upload.filename or '').lower()
            if not filename.endswith('.csv'):
                return jsonify({'error': 'Please upload a .csv file.'}), 400
            raw_bytes = upload.read()
            if not raw_bytes:
                return jsonify({'error': 'The uploaded file is empty.'}), 400
            raw_urls = [url for url, _declared_type in parse_csv_urls(raw_bytes)]
        else:
            data = request.get_json(silent=True) or {}
            raw_urls = parse_text_urls(data.get('text') or '')

        urls, errors = validate_url_list(raw_urls)
        if not urls:
            return jsonify({'error': 'No valid URLs were found.', 'errors': errors}), 400

        return jsonify({'urls': urls, 'errors': errors})

    # ==========================================================================
    # 4. Scraper Execution, Job Manager & Streaming APIs
    # ==========================================================================

    @app.route('/tcsadmin/api/scraper/start', methods=['POST'])
    @app.route('/api/scraper/start', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_scraper_job_start():
        data = request.get_json(silent=True) or {}
        file_id = data.get('file_id') or request.form.get('file_id') or request.args.get('file_id')
        if not file_id:
            return jsonify({'success': False, 'error': 'Missing file_id parameter.'}), 400
        try:
            file_id = int(file_id)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid file_id.'}), 400

        user_id = session.get('user_id')
        result = job_manager.start_job(file_id, user_id=user_id)
        if not result.get('success'):
            return jsonify(result), 409
        return jsonify(result)

    @app.route('/tcsadmin/api/scraper/file/<int:file_id>/active-job')
    @app.route('/api/scraper/file/<int:file_id>/active-job')
    @login_required_api
    def api_scraper_file_active_job(file_id):
        user_id = session.get('user_id')
        active_info = job_manager.get_active_job_for_file(file_id, current_user_id=user_id)
        return jsonify(active_info)

    @app.route('/tcsadmin/api/scraper/job/<string:job_id>/status')
    @app.route('/api/scraper/job/<string:job_id>/status')
    @login_required_api
    def api_scraper_job_status(job_id):
        user_id = session.get('user_id')
        data, code = job_manager.get_job_status(job_id, current_user_id=user_id)
        return jsonify(data), code

    @app.route('/tcsadmin/api/scraper/job/<string:job_id>/urls')
    @app.route('/api/scraper/job/<string:job_id>/urls')
    @login_required_api
    def api_scraper_job_urls(job_id):
        user_id = session.get('user_id')
        urls, code = job_manager.get_job_urls(job_id, current_user_id=user_id)
        if code != 200:
            return jsonify(urls), code
        summary = build_status_summary(urls)
        return jsonify({
            'job_id': job_id,
            'statuses': urls,
            'summary': summary,
            'count': len(urls),
        })

    @app.route('/tcsadmin/api/scraper/job/<string:job_id>/events')
    @app.route('/api/scraper/job/<string:job_id>/events')
    @login_required_api
    def api_scraper_job_events(job_id):
        user_id = session.get('user_id')
        job = job_manager.get_log_by_job_id(job_id)
        if not job:
            with job_manager._lock:
                state = job_manager._active_jobs.get(job_id)
            if not state:
                return jsonify({'error': 'Job not found.'}), 404
            if state['started_by_user_id'] != user_id and session.get('role') != 'SuperAdmin':
                return jsonify({'error': 'Forbidden'}), 403
        elif job['user_id'] != user_id and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden'}), 403

        def event_stream():
            q = job_manager.subscribe_sse(job_id)
            try:
                status_data, _ = job_manager.get_job_status(job_id, current_user_id=user_id)
                urls_data, _ = job_manager.get_job_urls(job_id, current_user_id=user_id)
                initial_payload = {
                    'type': 'snapshot',
                    'summary': status_data,
                    'statuses': urls_data
                }
                yield f"data: {json.dumps(initial_payload)}\n\n"

                while True:
                    try:
                        event = q.get(timeout=15.0)
                        yield f"data: {json.dumps(event)}\n\n"
                        if event.get('done') or (event.get('type') == 'status' and event.get('status') in ('SUCCESS', 'STOPPED', 'FAILED', 'FAIL')):
                            break
                    except queue.Empty:
                        yield ": ping\n\n"
            except GeneratorExit:
                pass
            finally:
                job_manager.unsubscribe_sse(job_id, q)

        return Response(
            stream_with_context(event_stream()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive',
            }
        )

    @app.route('/tcsadmin/api/scraper/job/<string:job_id>/stop', methods=['POST'])
    @app.route('/api/scraper/job/<string:job_id>/stop', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_scraper_job_stop(job_id):
        user_id = session.get('user_id')
        is_superadmin = (session.get('role') == 'SuperAdmin')
        result, code = job_manager.stop_job(job_id, current_user_id=user_id, is_superadmin=is_superadmin)
        return jsonify(result), code

    @app.route('/tcsadmin/api/files/<int:file_id>/start', methods=['POST'])
    @app.route('/api/files/<int:file_id>/start', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_start_file(file_id):
        user_id = session.get('user_id')
        result = job_manager.start_job(file_id, user_id=user_id)
        if not result.get('success'):
            return jsonify(result), 409
        return jsonify(result)

    @app.route('/tcsadmin/api/files/<int:file_id>/stop', methods=['POST'])
    @app.route('/api/files/<int:file_id>/stop', methods=['POST'])
    @login_required_api
    @require_csrf
    def api_stop_file(file_id):
        user_id = session.get('user_id')
        is_superadmin = (session.get('role') == 'SuperAdmin')
        result, code = job_manager.stop_file(file_id, current_user_id=user_id, is_superadmin=is_superadmin)
        return jsonify(result), code

    @app.route('/tcsadmin/api/files/<int:file_id>/status')
    @app.route('/api/files/<int:file_id>/status')
    @login_required_api
    def api_file_status(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404

        user_id = session.get('user_id')
        active_info = job_manager.get_active_job_for_file(file_id, current_user_id=user_id)

        if active_info.get('job_id'):
            job_status, code = job_manager.get_job_status(active_info['job_id'], current_user_id=user_id)
            if code == 200:
                job_status['is_owner'] = True
                job_status['working'] = bool(active_info.get('has_active_job'))
                job_status['siteName'] = record['site_name']
                job_status['fileId'] = file_id
                return jsonify(job_status)

        output_path = file_scraper_runner.get_output_path(file_id)
        return jsonify({
            'job_id': None,
            'running': False,
            'working': False,
            'done': True,
            'is_owner': True,
            'siteName': record['site_name'],
            'fileId': file_id,
            'outputAvailable': bool(output_path and os.path.exists(output_path)),
            'total_product_urls': 0,
            'written_to_xlsx': 0,
            'pending': 0,
            'running_count': 0,
            'blocked': 0,
            'main_url_done': 0,
            'product_url_done': 0,
            'progress_percent': 0.0,
        })

    @app.route('/tcsadmin/api/files/<int:file_id>/url-statuses')
    @app.route('/api/files/<int:file_id>/url-statuses')
    @login_required_api
    def api_file_url_statuses(file_id):
        user_id = session.get('user_id')
        active_info = job_manager.get_active_job_for_file(file_id, current_user_id=user_id)

        if active_info['has_active_job'] and not active_info['is_owner']:
            return jsonify({'statuses': [], 'summary': {}, 'xlsx_count': 0, 'error': 'Forbidden'}), 403

        if active_info.get('job_id') and active_info.get('is_owner', True):
            urls, code = job_manager.get_job_urls(active_info['job_id'], current_user_id=user_id)
            if code == 200 and urls:
                summary = build_status_summary(urls)
                return jsonify({
                    'statuses': urls,
                    'summary': summary,
                    'xlsx_count': summary.get('written_to_xlsx', 0),
                })

        urls = file_scraper_runner.get_statuses(file_id)
        summary = build_status_summary(urls)
        return jsonify({
            'statuses': urls,
            'summary': summary,
            'xlsx_count': summary.get('written_to_xlsx', 0),
        })

    @app.route('/tcsadmin/api/files/<int:file_id>/download')
    @app.route('/api/files/<int:file_id>/download')
    @login_required_api
    def api_file_download(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404

        output_path = file_scraper_runner.get_output_path(file_id)
        if not output_path or not os.path.exists(output_path):
            return jsonify({'error': 'No output available for this scraper yet. Run it first.'}), 404

        filename = _format_scraper_output_filename(record['site_name'])
        return send_file(
            output_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )

    @app.route('/tcsadmin/api/files/download-zip')
    @app.route('/api/files/download-zip')
    @login_required_api
    def api_files_download_zip():
        if file_scraper_runner.running_count() > 0:
            return jsonify({
                'error': 'Scraping is in progress. Please wait until all scrapers finish before downloading ZIP.',
                'anyRunning': True,
            }), 409

        all_outputs = file_scraper_runner.get_all_output_paths()
        if not all_outputs:
            return jsonify({'error': 'No completed scraper reports available to download.'}), 404

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            used_names = set()
            for file_id, file_path in all_outputs.items():
                if not os.path.exists(file_path):
                    continue
                record = files_repo.get_file(file_id)
                site_name = record['site_name'] if record else f"scraper_{file_id}"
                base_filename = _format_scraper_output_filename(site_name)
                filename = base_filename
                counter = 1
                while filename in used_names:
                    root, ext = os.path.splitext(base_filename)
                    filename = f"{root}_{counter}{ext}"
                    counter += 1
                used_names.add(filename)
                zf.write(file_path, arcname=filename)

        if not used_names:
            return jsonify({'error': 'No valid output files found to package.'}), 404

        zip_buffer.seek(0)
        today = datetime.now().strftime('%d-%m-%Y')
        zip_filename = f"scrapers_output_{today}.zip"
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=zip_filename,
        )

    @app.route('/tcsadmin/api/files/<int:file_id>/logs')
    @app.route('/api/files/<int:file_id>/logs')
    @login_required_api
    def api_file_logs(file_id):
        record = files_repo.get_file(file_id)
        if not record:
            return jsonify({'error': 'Scraper not found.'}), 404
        rows, total = reports_repo.list_logs(file_id=file_id, per_page=100)
        return jsonify({
            'fileId': file_id,
            'siteName': record.get('site_name') or 'Scraper',
            'logs': [reports_repo.serialize_log(r) for r in rows],
            'total': total,
        })

    # ==========================================================================
    # 5. Reports & Audit Log APIs
    # ==========================================================================

    @app.route('/tcsadmin/api/reports')
    @app.route('/api/reports')
    @login_required_api
    @role_required_api('SuperAdmin', 'super_admin', 'Admin', 'manager')
    def api_list_reports():
        search = request.args.get('search', '').strip() or None
        status = request.args.get('status', '').strip() or None
        user_id_raw = request.args.get('userId', '').strip()
        user_id = int(user_id_raw) if user_id_raw.isdigit() else None
        file_id_raw = request.args.get('fileId', '').strip()
        file_id = int(file_id_raw) if file_id_raw.isdigit() else None
        try:
            page = int(request.args.get('page', 1))
        except ValueError:
            page = 1
        try:
            per_page = int(request.args.get('perPage', 20))
        except ValueError:
            per_page = 20

        rows, total = reports_repo.list_logs(
            search=search,
            status=status,
            user_id=user_id,
            file_id=file_id,
            page=page,
            per_page=per_page,
        )
        stats = reports_repo.get_logs_summary_stats()
        return jsonify({
            'reports': [reports_repo.serialize_log(r) for r in rows],
            'total': total,
            'page': page,
            'perPage': per_page,
            'stats': stats,
        })

    @app.route('/tcsadmin/api/reports/<int:report_id>/download')
    @app.route('/api/reports/<int:report_id>/download')
    @login_required_api
    @role_required_api('SuperAdmin', 'super_admin', 'Admin', 'manager')
    def api_download_report_output(report_id):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM logTbl WHERE id = %s", (report_id,))
                record = cursor.fetchone()
        finally:
            conn.close()

        if not record or not record.get('output_file_path') or not os.path.exists(record['output_file_path']):
            return jsonify({'error': 'Output file not available for this run.'}), 404

        filename = _format_scraper_output_filename(record['scraper'])
        return send_file(
            record['output_file_path'],
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename,
        )

    # ==========================================================================
    # 6. Legacy / Ad-hoc Scraper APIs
    # ==========================================================================

    @app.route('/tcsadmin/api/scraper/analyze', methods=['POST'])
    @app.route('/api/scraper/analyze', methods=['POST'])
    @login_required_api
    def analyze_scraper_input():
        try:
            raw_items = extract_input_source(request)
        except InputError as exc:
            return jsonify({'error': str(exc)}), 400

        entries, errors, unsupported = build_entries(raw_items)

        return jsonify({
            'entries': entries,
            'errors': errors,
            'unsupported': unsupported,
            'message': format_invalid_url_message(errors) or format_unsupported_message(unsupported) or None,
        })

    @app.route('/tcsadmin/StartScraper', methods=['POST'])
    @app.route('/StartScraper', methods=['POST'])
    @login_required_api
    def start_scraper():
        state = get_scraper_session()

        try:
            raw_items = extract_input_source(request)
        except InputError as exc:
            return jsonify({'error': str(exc)}), 400

        entries, errors, unsupported = build_entries(raw_items)

        if not entries:
            message = (
                format_invalid_url_message(errors)
                or format_unsupported_message(unsupported)
                or 'No valid URLs were provided.'
            )
            return jsonify({'error': message, 'errors': errors, 'unsupported': unsupported}), 400

        with state.lock:
            process_running = state.process is not None and state.process.poll() is None
            if process_running or state.job_status == 'running':
                return jsonify({'error': 'Scraper is already running.'}), 409

            state.url_statuses.clear()
            state.stopped = False
            state.job_id = uuid.uuid4().hex
            state.job_status = 'running'
            state.skipped = {'invalid': errors, 'unsupported': unsupported}

            job_id_short = state.job_id[:8]

            groups_by_type = OrderedDict()
            for entry in entries:
                groups_by_type.setdefault(entry['type'], []).append(entry['url'])

            os.makedirs(TMP_SCRAPERS_DIR, exist_ok=True)
            pending_groups = []
            for url_type, urls in groups_by_type.items():
                input_path = os.path.join(TMP_SCRAPERS_DIR, f'job_{job_id_short}_{url_type}.csv')
                with open(input_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    for url in urls:
                        writer.writerow([url])

                pending_groups.append({
                    'type': url_type,
                    'input_path': input_path,
                    'output_path': os.path.join(TMP_SCRAPERS_DIR, f'job_{job_id_short}_{url_type}_output.xlsx'),
                    'script_path': os.path.join(BASE_DIR, 'scrapers', SCRIPT_MAP[url_type]),
                })
            state.pending_groups = pending_groups

            timestamp = datetime.now().strftime('%d-%m-%Y_%H%M%S')
            state.output_file = os.path.join(BASE_DIR, f'pitstoparabia_data_{job_id_short}_{timestamp}.xlsx')

            state.thread = threading.Thread(target=_run_job_groups, args=(state,), daemon=True)
            state.thread.start()

        return jsonify({
            'message': f'Scraper started. Job ID: {state.job_id}',
            'jobId': state.job_id,
            'groups': [g['type'] for g in pending_groups],
            'skipped': {'invalid': errors, 'unsupported': unsupported},
        })

    @app.route('/tcsadmin/stop-scraper', methods=['POST'])
    @app.route('/stop-scraper', methods=['POST'])
    @login_required_api
    def stop_scraper():
        state = get_scraper_session()
        with state.lock:
            process_running = state.process is not None and state.process.poll() is None
            if not process_running and state.job_status != 'running':
                return jsonify({'stopped': False, 'message': 'No scraper process is running.'})

            state.stopped = True
            if process_running:
                try:
                    state.process.terminate()
                    state.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    state.process.kill()
                    state.process.wait()
                finally:
                    state.process = None

        return jsonify({'stopped': True, 'message': 'Scraper has been stopped.'})

    @app.route('/tcsadmin/scraper-url-statuses')
    @app.route('/scraper-url-statuses')
    @login_required_api
    def scraper_url_statuses_endpoint():
        state = get_scraper_session()
        with state.lock:
            statuses = list(state.url_statuses)
            running = state.process is not None and state.process.poll() is None
            output_file = state.output_file
            if not running and state.job_status == 'idle' and state.url_statuses:
                state.url_statuses.clear()

        xlsx_count, xlsx_urls = get_xlsx_info(output_file)
        if xlsx_urls:
            if statuses:
                for item in statuses:
                    u = item.get('url', '').strip()
                    if u in xlsx_urls:
                        item['status'] = 'done'
                        item['written_to_xlsx'] = True
            else:
                statuses = [
                    {'url': u, 'status': 'done', 'parent': '', 'type': 'product', 'written_to_xlsx': True}
                    for u in sorted(xlsx_urls)
                ]

        return jsonify({
            'statuses': statuses,
            'summary': build_status_summary(statuses),
            'xlsx_count': xlsx_count,
        })

    @app.route('/tcsadmin/scraper-status')
    @app.route('/scraper-status')
    @login_required_api
    def scraper_status():
        state = get_scraper_session()
        with state.lock:
            running = state.process is not None and state.process.poll() is None
            if running:
                state.job_status = 'running'

            current = state.job_status
            if current in ('completed_unseen', 'failed_unseen'):
                reported_status = 'completed' if current == 'completed_unseen' else 'failed'
                state.job_status = 'idle'
            elif current == 'running':
                reported_status = 'running'
            else:
                reported_status = 'idle'

            has_active_job = reported_status == 'running'
            job_id = state.job_id if has_active_job else None
            output_file = state.output_file

        output_available = bool(output_file and os.path.exists(output_file))

        return jsonify({
            'running': reported_status == 'running',
            'done': reported_status in ('completed', 'failed'),
            'outputAvailable': output_available,
            'outputFile': os.path.basename(output_file) if output_available else '',
            'status': reported_status,
            'hasActiveJob': has_active_job,
            'jobId': job_id,
        })

    @app.route('/tcsadmin/download-output')
    @app.route('/download-output')
    @login_required_api
    def download_output():
        state = get_scraper_session()
        with state.lock:
            output_file = state.output_file

        if not output_file or not os.path.exists(output_file):
            return Response('No output file found.', status=404, mimetype='text/plain')

        return send_from_directory(BASE_DIR, os.path.basename(output_file), as_attachment=True)


def register_visionadmin_api_routes(app):
    """Registers all /visionadmin/api JSON endpoints (uploads, pages, blogs, sections CRUD)."""

    @app.before_request
    def visionadmin_api_auth_guard():
        """Protects all /visionadmin/api/ endpoints with session auth and RBAC against admin_users."""
        path_lower = request.path.lower()
        if path_lower.startswith('/visionadmin/api/') or path_lower.startswith('/visonadmin/api/'):
            user_id = session.get('admin_user_id') or session.get('user_id')
            if not user_id:
                return jsonify({'error': 'Authentication required. Please sign in to VisionAdmin.'}), 401
            role = session.get('role')
            role_norm = str(role).strip().lower().replace('-', '_').replace(' ', '_') if role else ''
            if role_norm not in {'super_admin', 'superadmin', 'manager', 'support', 'admin'} and role not in ('SuperAdmin', 'Admin'):
                return jsonify({'error': 'Unauthorized. VisionAdmin access requires administrator privileges.'}), 403

    # =========================================================================
    # 1. FILE UPLOAD ENDPOINTS
    # =========================================================================

    @app.route('/visionadmin/api/upload-banner', methods=['POST'])
    def visionadmin_upload_banner():
        file = request.files.get('file') or request.files.get('banner')
        if not file or not file.filename:
            return jsonify({'error': 'No image file provided.'}), 400

        allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif', '.avif'}
        orig_filename = secure_filename(file.filename)
        _, ext = os.path.splitext(orig_filename)
        ext = ext.lower()
        if ext not in allowed_extensions:
            return jsonify({'error': f'Invalid image format "{ext}". Allowed formats: PNG, JPG, JPEG, WEBP, SVG, GIF, AVIF'}), 400

        upload_folder = os.path.join(app.static_folder, 'uploads', 'pages')
        os.makedirs(upload_folder, exist_ok=True)

        unique_name = f"banner_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(upload_folder, unique_name)
        file.save(save_path)

        web_url = f"/static/uploads/pages/{unique_name}"
        return jsonify({
            'success': True,
            'url': web_url,
            'filename': unique_name,
            'message': 'Banner image uploaded successfully.'
        })

    @app.route('/visionadmin/api/upload-blog-image', methods=['POST'])
    def visionadmin_upload_blog_image():
        file = request.files.get('file') or request.files.get('image')
        if not file or not file.filename:
            return jsonify({'error': 'No image file provided.'}), 400

        allowed_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.svg', '.gif', '.avif'}
        orig_filename = secure_filename(file.filename)
        _, ext = os.path.splitext(orig_filename)
        ext = ext.lower()
        if ext not in allowed_extensions:
            return jsonify({'error': f'Invalid image format "{ext}". Allowed formats: PNG, JPG, JPEG, WEBP, SVG, GIF, AVIF'}), 400

        upload_folder = os.path.join(app.static_folder, 'uploads', 'blogs')
        os.makedirs(upload_folder, exist_ok=True)

        unique_name = f"blog_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = os.path.join(upload_folder, unique_name)
        file.save(save_path)

        web_url = f"/static/uploads/blogs/{unique_name}"
        return jsonify({
            'success': True,
            'url': web_url,
            'filename': unique_name,
            'message': 'Featured blog image uploaded successfully.'
        })

    # =========================================================================
    # 2. PAGES JSON API ENDPOINTS (/visionadmin/api/pages & /visionadmin/api/v1/pages)
    # =========================================================================

    @app.route('/visionadmin/api/pages', methods=['GET'])
    @app.route('/visionadmin/api/v1/pages', methods=['GET'])
    def visionadmin_get_pages():
        locale = request.args.get('locale') or request.args.get('lang') or StoreContext.get_current_language()
        include_deleted = request.args.get('trash') == '1'
        status_filter = request.args.get('status')
        query = (request.args.get('q') or '').strip()

        pages = Page.all(include_deleted=include_deleted)

        if include_deleted:
            pages = [p for p in pages if p.deleted_at is not None]
        else:
            pages = [p for p in pages if p.deleted_at is None]

        if status_filter == 'active':
            pages = [p for p in pages if p.is_active]
        elif status_filter == 'inactive':
            pages = [p for p in pages if not p.is_active]

        if query:
            q_lower = query.lower()
            pages = [
                p for p in pages
                if q_lower in p.get_title(locale).lower()
                or q_lower in p.get_title('en').lower()
                or q_lower in (p.slug or '').lower()
            ]

        all_active = [p for p in Page.all(include_deleted=False) if p.deleted_at is None]
        metrics = {
            'total': len(all_active),
            'active': len([p for p in all_active if p.is_active]),
            'inactive': len([p for p in all_active if not p.is_active]),
            'trash': len([p for p in Page.all(include_deleted=True) if p.deleted_at is not None])
        }

        return jsonify({
            'success': True,
            'pages': [p.to_dict(locale=locale) for p in pages],
            'metrics': metrics,
            'count': len(pages)
        })

    @app.route('/visionadmin/api/pages/<int:page_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/pages/<int:page_id>', methods=['GET'])
    def visionadmin_get_page(page_id):
        page = Page.find_by_id(page_id)
        if not page:
            return jsonify({'error': 'Page not found.'}), 404
        return jsonify({'success': True, 'page': page.to_dict()})

    @app.route('/visionadmin/api/pages', methods=['POST'])
    @app.route('/visionadmin/api/v1/pages', methods=['POST'])
    def visionadmin_create_page():
        data = request.get_json(silent=True) or {}
        curr_lang = StoreContext.get_current_language()

        # Validation
        title = data.get('title') or {}
        if isinstance(title, dict):
            page_title = (title.get(curr_lang) or title.get('en') or next((v for v in title.values() if v), '')).strip()
        else:
            page_title = str(title).strip()
            title = {curr_lang: page_title}

        if not page_title:
            return jsonify({'error': 'Page Title is required.'}), 400

        slug = (data.get('slug') or '').strip()
        if not slug:
            slug = Page.slugify(page_title)
        else:
            slug = Page.slugify(slug)

        if not Page.is_slug_available(slug):
            return jsonify({'error': f'The slug "{slug}" is already in use. Please choose a different slug.'}), 409

        content = data.get('content') or {}
        if not isinstance(content, dict):
            content = {curr_lang: str(content)}

        try:
            page = Page.create(
                title=title,
                slug=slug,
                content=content,
                banner_image=data.get('banner_image'),
                seo_title=data.get('seo_title'),
                meta_description=data.get('meta_description'),
                is_active=bool(data.get('is_active', True)),
                created_by=session.get('user_id'),
                updated_by=session.get('user_id')
            )
            return jsonify({
                'success': True,
                'page': page.to_dict(),
                'message': f'Page "{page.get_title()}" created successfully.'
            }), 201
        except Exception as e:
            if 'Duplicate entry' in str(e) or 'IntegrityError' in type(e).__name__:
                return jsonify({'error': f'The slug "{slug}" is already in use. Please enter a different slug.'}), 409
            return jsonify({'error': f'Failed to create page: {str(e)}'}), 500

    @app.route('/visionadmin/api/pages/<int:page_id>', methods=['PUT'])
    def visionadmin_update_page(page_id):
        page = Page.find_by_id(page_id)
        if not page:
            return jsonify({'error': 'Page not found.'}), 404

        data = request.get_json(silent=True) or {}

        if 'slug' in data and data['slug']:
            new_slug = Page.slugify(data['slug'])
            if not Page.is_slug_available(new_slug, exclude_id=page_id):
                return jsonify({'error': f'The slug "{new_slug}" is already in use.'}), 409
            data['slug'] = new_slug

        data['updated_by'] = session.get('user_id')

        try:
            page.update(**data)
            refreshed = Page.find_by_id(page_id)
            return jsonify({
                'success': True,
                'page': refreshed.to_dict(),
                'message': f'Page "{refreshed.get_title()}" updated successfully.'
            })
        except Exception as e:
            if 'Duplicate entry' in str(e) or 'IntegrityError' in type(e).__name__:
                return jsonify({'error': 'The specified slug is already in use.'}), 409
            return jsonify({'error': f'Failed to update page: {str(e)}'}), 500

    @app.route('/visionadmin/api/pages/<int:page_id>', methods=['DELETE'])
    def visionadmin_delete_page(page_id):
        page = Page.find_by_id(page_id)
        if not page:
            return jsonify({'error': 'Page not found.'}), 404

        is_hard = request.args.get('hard') == '1' or request.args.get('permanent') == '1' or page.deleted_at is not None

        if is_hard:
            Page.hard_delete(page_id)
            return jsonify({
                'success': True,
                'message': f'Page "{page.get_title()}" permanently deleted from database.'
            })
        else:
            Page.soft_delete(page_id)
            return jsonify({
                'success': True,
                'message': f'Page "{page.get_title()}" moved to trash.'
            })

    @app.route('/visionadmin/api/pages/<int:page_id>/restore', methods=['POST'])
    def visionadmin_restore_page(page_id):
        Page.restore(page_id)
        return jsonify({
            'success': True,
            'message': 'Page restored successfully.'
        })

    # =========================================================================
    # 3. BLOGS JSON API ENDPOINTS (/visionadmin/api/blogs & /visionadmin/api/v1/blogs)
    # =========================================================================

    @app.route('/visionadmin/api/categories', methods=['GET'])
    @app.route('/visionadmin/api/v1/categories', methods=['GET'])
    @app.route('/visionadmin/api/blog-categories', methods=['GET'])
    @app.route('/visionadmin/api/v1/blog-categories', methods=['GET'])
    def visionadmin_get_categories():
        """Returns all categories from blog_categories table."""
        categories = Blog.get_all_categories()
        names = [c.get('display_name') or localize_value(c.get('name')) for c in categories if (c.get('display_name') or c.get('name'))] or Blog.distinct_categories()
        return jsonify({
            'success': True,
            'categories': categories,
            'category_names': names,
            'count': len(categories)
        })

    @app.route('/visionadmin/api/blogs', methods=['GET'])
    @app.route('/visionadmin/api/v1/blogs', methods=['GET'])
    def visionadmin_get_blogs():
        locale = request.args.get('locale') or request.args.get('lang') or StoreContext.get_current_language()
        include_deleted = request.args.get('trash') == '1'
        status_filter = request.args.get('status')
        query = (request.args.get('q') or '').strip()

        blogs = Blog.all(include_deleted=include_deleted)

        if include_deleted:
            blogs = [b for b in blogs if b.deleted_at is not None]
        else:
            blogs = [b for b in blogs if b.deleted_at is None]

        if status_filter in ('published', 'draft', 'archived'):
            blogs = [b for b in blogs if b.status == status_filter]

        if query:
            q_lower = query.lower()
            blogs = [
                b for b in blogs
                if q_lower in b.get_title(locale).lower()
                or q_lower in b.get_title('en').lower()
                or q_lower in (b.slug or '').lower()
                or q_lower in b.get_short_desc(locale).lower()
                or q_lower in (b.category_name or '').lower()
            ]

        all_active = [b for b in Blog.all(include_deleted=False) if b.deleted_at is None]
        metrics = {
            'total': len(all_active),
            'published': len([b for b in all_active if b.status == 'published']),
            'draft': len([b for b in all_active if b.status == 'draft']),
            'archived': len([b for b in all_active if b.status == 'archived']),
            'trash': len([b for b in Blog.all(include_deleted=True) if b.deleted_at is not None])
        }

        return jsonify({
            'success': True,
            'blogs': [b.to_dict(locale=locale) for b in blogs],
            'metrics': metrics,
            'count': len(blogs)
        })

    @app.route('/visionadmin/api/blogs/<int:blog_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/blogs/<int:blog_id>', methods=['GET'])
    def visionadmin_get_blog(blog_id):
        blog = Blog.find_by_id(blog_id)
        if not blog:
            return jsonify({'error': 'Blog article not found.'}), 404
        return jsonify({'success': True, 'blog': blog.to_dict()})

    @app.route('/visionadmin/api/blogs', methods=['POST'])
    @app.route('/visionadmin/api/v1/blogs', methods=['POST'])
    def visionadmin_create_blog():
        data = request.get_json(silent=True) or {}
        curr_lang = StoreContext.get_current_language()

        title = data.get('title') or {}
        if isinstance(title, dict):
            blog_title = (title.get(curr_lang) or title.get('en') or next((v for v in title.values() if v), '')).strip()
        else:
            blog_title = str(title).strip()
            title = {curr_lang: blog_title}

        if not blog_title:
            return jsonify({'error': 'Blog Title is required.'}), 400

        slug = (data.get('slug') or '').strip()
        if not slug:
            slug = Blog.slugify(blog_title)
        else:
            slug = Blog.slugify(slug)

        if not Blog.is_slug_available(slug):
            return jsonify({'error': f'The slug "{slug}" is already in use. Please choose a unique slug.'}), 409

        content = data.get('content') or {}
        if not isinstance(content, dict):
            content = {curr_lang: str(content)}

        short_desc = data.get('short_description') or {}
        if not isinstance(short_desc, dict):
            short_desc = {curr_lang: str(short_desc)}

        try:
            blog = Blog.create(
                title=title,
                slug=slug,
                content=content,
                short_description=short_desc,
                image=data.get('image'),
                category_id=data.get('category_id') or data.get('blog_category_id'),
                category_name=(data.get('category_name') or data.get('category') or '').strip() or None,
                author_id=data.get('author_id') or session.get('user_id') or 1,
                status=data.get('status') or 'draft',
                published_at=data.get('published_at'),
                meta_title=data.get('meta_title'),
                meta_desc=data.get('meta_desc'),
                faqs=data.get('faqs') or [],
                created_by=session.get('user_id'),
                updated_by=session.get('user_id')
            )
            return jsonify({
                'success': True,
                'blog': blog.to_dict(),
                'message': f'Blog "{blog.get_title()}" created successfully.'
            }), 201
        except Exception as e:
            if 'Duplicate entry' in str(e) or 'IntegrityError' in type(e).__name__:
                return jsonify({'error': f'The slug "{slug}" is already in use.'}), 409
            return jsonify({'error': f'Failed to create blog: {str(e)}'}), 500

    @app.route('/visionadmin/api/blogs/<int:blog_id>', methods=['PUT'])
    def visionadmin_update_blog(blog_id):
        blog = Blog.find_by_id(blog_id)
        if not blog:
            return jsonify({'error': 'Blog article not found.'}), 404

        data = request.get_json(silent=True) or {}

        if 'slug' in data and data['slug']:
            new_slug = Blog.slugify(data['slug'])
            if not Blog.is_slug_available(new_slug, exclude_id=blog_id):
                return jsonify({'error': f'The slug "{new_slug}" is already in use.'}), 409
            data['slug'] = new_slug

        data['updated_by'] = session.get('user_id')

        try:
            blog.update(**data)
            refreshed = Blog.find_by_id(blog_id)
            return jsonify({
                'success': True,
                'blog': refreshed.to_dict(),
                'message': f'Blog "{refreshed.get_title()}" updated successfully.'
            })
        except Exception as e:
            if 'Duplicate entry' in str(e) or 'IntegrityError' in type(e).__name__:
                return jsonify({'error': 'The specified slug is already in use.'}), 409
            return jsonify({'error': f'Failed to update blog: {str(e)}'}), 500

    @app.route('/visionadmin/api/blogs/<int:blog_id>', methods=['DELETE'])
    def visionadmin_delete_blog(blog_id):
        blog = Blog.find_by_id(blog_id)
        if not blog:
            return jsonify({'error': 'Blog article not found.'}), 404

        is_hard = request.args.get('hard') == '1' or request.args.get('permanent') == '1' or blog.deleted_at is not None

        if is_hard:
            Blog.hard_delete(blog_id)
            return jsonify({
                'success': True,
                'message': f'Article "{blog.get_title()}" permanently deleted from database.'
            })
        else:
            Blog.soft_delete(blog_id)
            return jsonify({
                'success': True,
                'message': f'Article "{blog.get_title()}" moved to trash.'
            })

    @app.route('/visionadmin/api/blogs/<int:blog_id>/restore', methods=['POST'])
    def visionadmin_restore_blog(blog_id):
        Blog.restore(blog_id)
        return jsonify({
            'success': True,
            'message': 'Blog article restored successfully.'
        })

    @app.route('/visionadmin/api/blog-categories/<int:cat_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/blog-categories/<int:cat_id>', methods=['GET'])
    def visionadmin_get_blog_category(cat_id):
        """Returns details for a single blog category."""
        category = Blog.get_category_by_id(cat_id)
        if not category:
            return jsonify({'error': 'Blog category not found.'}), 404
        return jsonify({
            'success': True,
            'category': category
        })

    @app.route('/visionadmin/api/blog-categories', methods=['POST'])
    @app.route('/visionadmin/api/v1/blog-categories', methods=['POST'])
    def visionadmin_create_blog_category():
        """Creates a blog category in blog_categories table."""
        data = request.get_json(silent=True) or {}
        name_val = data.get('name') or data.get('title') or data.get('name_en')
        if isinstance(name_val, dict):
            display_name = localize_value(name_val)
        else:
            display_name = str(name_val or '').strip()

        if not display_name:
            return jsonify({'error': 'Category title is required.'}), 400

        user_id = session.get('user_id')
        cat = Blog.create_category(data, user_id=user_id)
        log_activity('create', 'blog_category', cat['id'], None, {'name': cat.get('name'), 'slug': cat.get('slug')}, user_id=user_id)
        return jsonify({
            'success': True,
            'category': cat,
            'message': f"Category '{display_name}' created successfully."
        }), 201

    @app.route('/visionadmin/api/blog-categories/<int:cat_id>', methods=['PUT'])
    @app.route('/visionadmin/api/v1/blog-categories/<int:cat_id>', methods=['PUT'])
    def visionadmin_update_blog_category(cat_id):
        """Updates an existing category in blog_categories table."""
        data = request.get_json(silent=True) or {}
        name_val = data.get('name') or data.get('title') or data.get('name_en')
        if isinstance(name_val, dict):
            display_name = localize_value(name_val)
        else:
            display_name = str(name_val or '').strip()
        slug = (data.get('slug') or '').strip() or None
        user_id = session.get('user_id')

        if not display_name:
            return jsonify({'error': 'Category title is required.'}), 400

        update_kwargs = {k: v for k, v in data.items() if k not in ('name', 'slug')}
        cat = Blog.update_category(cat_id, name_val, slug=slug, user_id=user_id, **update_kwargs)
        if not cat:
            return jsonify({'error': 'Category not found.'}), 404

        log_activity('update', 'blog_category', cat_id, None, {'name': cat.get('name'), 'slug': cat.get('slug')}, user_id=user_id)
        return jsonify({
            'success': True,
            'category': cat,
            'message': f"Category '{display_name}' updated successfully."
        })

    @app.route('/visionadmin/api/blog-categories/<int:cat_id>', methods=['DELETE'])
    def visionadmin_delete_blog_category(cat_id):
        """Soft-deletes a category in blog_categories table."""
        user_id = session.get('user_id')
        success = Blog.delete_category(cat_id, user_id=user_id)
        if not success:
            return jsonify({'error': 'Category not found or already deleted.'}), 404

        log_activity('delete', 'blog_category', cat_id, None, {'deleted_at': 'NOW()'}, user_id=user_id)
        return jsonify({
            'success': True,
            'message': 'Category deleted successfully.'
        })

    # =========================================================================
    # 4. PAGE SECTIONS CRUD & REORDER API (/visionadmin/api/sections & /visionadmin/api/v1/sections)
    # =========================================================================

    @app.route('/visionadmin/api/sections', methods=['GET'])
    @app.route('/visionadmin/api/v1/sections', methods=['GET'])
    def visionadmin_get_sections():
        """Returns all sections for a page (including inactive) ordered by sort_order."""
        page_slug = request.args.get('page') or request.args.get('page_slug') or 'about-us'
        sections = PageSection.all_for_page(page_slug=page_slug, include_inactive=True)
        return jsonify({
            'page': page_slug,
            'sections': sections,
            'count': len(sections)
        })

    @app.route('/visionadmin/api/sections/<int:section_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/sections/<int:section_id>', methods=['GET'])
    def visionadmin_get_section_detail(section_id):
        """Returns a single section by id."""
        sec = PageSection.find_by_id(section_id)
        if not sec:
            return jsonify({'error': 'Section not found.'}), 404
        return jsonify({'section': sec})

    @app.route('/visionadmin/api/sections', methods=['POST'])
    @app.route('/visionadmin/api/v1/sections', methods=['POST'])
    def visionadmin_create_section():
        """Creates a new section."""
        data = request.get_json(silent=True) or request.form.to_dict()
        if not data:
            return jsonify({'error': 'No data provided.'}), 400

        section_type = data.get('section_type')
        if not section_type:
            return jsonify({'error': 'section_type is required.'}), 400

        try:
            new_sec = PageSection.create(data)
            return jsonify({
                'success': True,
                'section': new_sec,
                'message': 'Section added successfully.'
            }), 201
        except Exception as e:
            return jsonify({'error': f'Failed to create section: {str(e)}'}), 500

    @app.route('/visionadmin/api/sections/<int:section_id>', methods=['PUT'])
    def visionadmin_update_section(section_id):
        """Updates an existing section."""
        sec = PageSection.find_by_id(section_id)
        if not sec:
            return jsonify({'error': 'Section not found.'}), 404

        data = request.get_json(silent=True) or request.form.to_dict()
        if not data:
            return jsonify({'error': 'No data provided.'}), 400

        try:
            updated = PageSection.update(section_id, data)
            return jsonify({
                'success': True,
                'section': updated,
                'message': 'Section updated successfully.'
            })
        except Exception as e:
            return jsonify({'error': f'Failed to update section: {str(e)}'}), 500

    @app.route('/visionadmin/api/sections/<int:section_id>', methods=['DELETE'])
    def visionadmin_delete_section(section_id):
        """Soft deletes a section."""
        sec = PageSection.find_by_id(section_id)
        if not sec:
            return jsonify({'error': 'Section not found.'}), 404

        PageSection.soft_delete(section_id)
        return jsonify({
            'success': True,
            'message': 'Section deleted successfully.'
        })

    @app.route('/visionadmin/api/sections/<int:section_id>/toggle', methods=['POST'])
    def visionadmin_toggle_section(section_id):
        """Toggles active/disabled state of a section."""
        sec = PageSection.find_by_id(section_id)
        if not sec:
            return jsonify({'error': 'Section not found.'}), 404

        toggled = PageSection.toggle_active(section_id)
        status_str = 'enabled' if toggled.get('is_active') else 'disabled'
        return jsonify({
            'success': True,
            'section': toggled,
            'message': f'Section {status_str} successfully.'
        })

    @app.route('/visionadmin/api/sections/reorder', methods=['POST'])
    def visionadmin_reorder_sections():
        """Updates section order based on ordered list of IDs."""
        data = request.get_json(silent=True) or {}
        ordered_ids = data.get('ordered_ids') or data.get('ids') or []
        if not ordered_ids or not isinstance(ordered_ids, list):
            return jsonify({'error': 'ordered_ids list is required.'}), 400

        try:
            PageSection.reorder(ordered_ids)
            return jsonify({
                'success': True,
                'message': 'Section order saved successfully.'
            })
        except Exception as e:
            return jsonify({'error': f'Failed to reorder sections: {str(e)}'}), 500

    # =========================================================================
    # 5. REVIEWER SETTINGS CONFIGURATION API
    # =========================================================================

    @app.route('/visionadmin/api/settings/reviewer', methods=['GET'])
    @app.route('/visionadmin/api/v1/settings/reviewer', methods=['GET'])
    @app.route('/visionadmin/api/reviewer-settings', methods=['GET'])
    @app.route('/visionadmin/api/v1/reviewer-settings', methods=['GET'])
    def visionadmin_get_reviewer_settings():
        from models.setting import Setting
        settings = Setting.get_reviewer_settings()
        return jsonify({
            'success': True,
            'settings': settings
        })

    @app.route('/visionadmin/api/settings/reviewer', methods=['POST', 'PUT'])
    @app.route('/visionadmin/api/v1/settings/reviewer', methods=['POST', 'PUT'])
    @app.route('/visionadmin/api/reviewer-settings', methods=['POST', 'PUT'])
    @app.route('/visionadmin/api/v1/reviewer-settings', methods=['POST', 'PUT'])
    def visionadmin_save_reviewer_settings():
        from models.setting import Setting
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        
        # Normalize enabled flag
        enabled_val = data.get('enabled', True)
        if isinstance(enabled_val, str):
            enabled = enabled_val.strip().lower() in ('true', '1', 'yes')
        else:
            enabled = bool(enabled_val)

        payload = {
            'enabled': enabled,
            'name': data.get('name') if isinstance(data.get('name'), dict) else {
                'en': (data.get('name_en') or data.get('name') or 'Sharvil Kumar').strip(),
                'ar': (data.get('name_ar') or 'شارفيل كومار').strip()
            },
            'initials': (data.get('initials') or 'SK').strip(),
            'role': data.get('role') if isinstance(data.get('role'), dict) else {
                'en': (data.get('role_en') or data.get('role') or 'Tyre Selection Specialist, TyresVision').strip(),
                'ar': (data.get('role_ar') or 'أخصائي اختيار الإطارات، تايرز فيجن').strip()
            },
            'bio': data.get('bio') if isinstance(data.get('bio'), dict) else {
                'en': (data.get('bio_en') or data.get('bio') or data.get('description_en') or '').strip(),
                'ar': (data.get('bio_ar') or data.get('description_ar') or '').strip()
            }
        }

        Setting.set('reviewer_settings', payload, group='reviewer')
        return jsonify({
            'success': True,
            'settings': Setting.get_reviewer_settings(),
            'message': 'Reviewer settings saved successfully.'
        })

    # =========================================================================
    # 6. UNIFIED GLOBAL SEARCH API (Deep search across all CMS content & sections)
    # =========================================================================

    @app.route('/visionadmin/api/global-search', methods=['GET'])
    @app.route('/visionadmin/api/v1/global-search', methods=['GET'])
    def visionadmin_global_search():
        """
        Deep content search across:
        1. Pages (title, slug, content HTML/prose, meta_description, seo_title)
        2. Page Sections (section_title, section_subtitle, content, page_slug, section_type)
        3. Blogs & Articles (title, content, slug, category, short_description)
        """
        query = (request.args.get('q') or '').strip()
        if not query:
            return jsonify({
                'success': True,
                'query': '',
                'total': 0,
                'results': {'pages': [], 'sections': [], 'blogs': []}
            })

        q_lower = query.lower()

        def clean_html(text):
            if not text:
                return ''
            clean = re.sub(r'<[^>]+>', ' ', str(text))
            return ' '.join(clean.split())

        def make_snippet(text, q, max_len=110):
            cleaned = clean_html(text)
            idx = cleaned.lower().find(q)
            if idx == -1:
                return cleaned[:max_len] + ('...' if len(cleaned) > max_len else '')
            start = max(0, idx - 25)
            end = min(len(cleaned), idx + len(q) + 55)
            snippet = cleaned[start:end]
            if start > 0:
                snippet = '...' + snippet
            if end < len(cleaned):
                snippet = snippet + '...'
            return snippet

        locale = get_locale()

        # 1. Search Pages across all stored language JSON values
        all_pages = [p for p in Page.all(include_deleted=False) if p.deleted_at is None]
        matched_pages = []
        for p in all_pages:
            slug = p.slug or ''
            title_vals = [str(v) for v in (p.title.values() if isinstance(p.title, dict) else [p.title]) if v]
            content_vals = [clean_html(str(v)) for v in (p.content.values() if isinstance(p.content, dict) else [p.content]) if v]
            meta_vals = [clean_html(str(v)) for v in (p.meta_description.values() if isinstance(p.meta_description, dict) else [p.meta_description]) if v]
            display_title = p.get_title(locale) or (title_vals[0] if title_vals else slug)

            match_found = False
            snippet = ''
            for t in title_vals:
                if q_lower in t.lower():
                    match_found = True
                    snippet = t
                    break
            if not match_found and q_lower in slug.lower():
                match_found = True
                snippet = f"/{slug.lstrip('/')}"
            if not match_found:
                for c in content_vals:
                    if q_lower in c.lower():
                        match_found = True
                        snippet = make_snippet(c, q_lower)
                        break
            if not match_found:
                for m in meta_vals:
                    if q_lower in m.lower():
                        match_found = True
                        snippet = make_snippet(m, q_lower)
                        break

            if match_found:
                matched_pages.append({
                    'id': p.id,
                    'type': 'page',
                    'title': display_title,
                    'slug': f"/{slug.lstrip('/')}",
                    'snippet': snippet,
                    'is_active': bool(p.is_active),
                    'url': f"/visionadmin/pages#page-{p.id}"
                })

        # 2. Search Page Sections
        conn = get_connection()
        matched_sections = []
        matched_products = []
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, page_slug, section_type, section_title, section_subtitle, content, section_data, is_active
                    FROM page_sections
                    WHERE deleted_at IS NULL
                    ORDER BY sort_order ASC, id ASC
                """)
                sec_rows = cursor.fetchall() or []
                for row in sec_rows:
                    sec_id = row.get('id')
                    page_slug = row.get('page_slug') or 'about-us'
                    sec_type = row.get('section_type') or 'section'
                    sec_title_raw = PageSection._parse_json(row.get('section_title'))
                    sec_sub_raw = PageSection._parse_json(row.get('section_subtitle'))
                    sec_content_raw = PageSection._parse_json(row.get('content'))
                    sec_data_str = json.dumps(row.get('section_data') or {})

                    title_vals = [str(v) for v in (sec_title_raw.values() if isinstance(sec_title_raw, dict) else [sec_title_raw]) if v]
                    sub_vals = [str(v) for v in (sec_sub_raw.values() if isinstance(sec_sub_raw, dict) else [sec_sub_raw]) if v]
                    content_vals = [clean_html(str(v)) for v in (sec_content_raw.values() if isinstance(sec_content_raw, dict) else [sec_content_raw]) if v]
                    display_title = localize_value(sec_title_raw, locale) or (title_vals[0] if title_vals else f"{page_slug.replace('-', ' ').title()} {sec_type.title()} Section")

                    match_found = False
                    snippet = ''
                    for t in title_vals:
                        if q_lower in t.lower():
                            match_found = True
                            snippet = t
                            break
                    if not match_found:
                        for s in sub_vals:
                            if q_lower in s.lower():
                                match_found = True
                                snippet = s
                                break
                    if not match_found:
                        for c in content_vals:
                            if q_lower in c.lower():
                                match_found = True
                                snippet = make_snippet(c, q_lower)
                                break
                    if not match_found and q_lower in sec_data_str.lower():
                        match_found = True
                        snippet = make_snippet(sec_data_str, q_lower)
                    elif not match_found and (q_lower in page_slug.lower() or q_lower in sec_type.lower()):
                        match_found = True
                        snippet = f"Page: {page_slug} ({sec_type})"

                    if match_found:
                        matched_sections.append({
                            'id': sec_id,
                            'type': 'section',
                            'title': display_title,
                            'slug': f"/{page_slug.lstrip('/')} ({sec_type})",
                            'page_slug': page_slug,
                            'section_type': sec_type,
                            'snippet': snippet,
                            'is_active': bool(row.get('is_active', 1)),
                            'url': f"/visionadmin/sections?page={page_slug}#section-{sec_id}"
                        })

                # Search Products
                cursor.execute("""
                    SELECT p.id, p.sku, p.name, p.slug, p.tire_size_label, b.name AS brand_name
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    WHERE p.deleted_at IS NULL AND (
                        LOWER(p.sku) LIKE %s OR
                        LOWER(p.slug) LIKE %s OR
                        LOWER(p.tire_size_label) LIKE %s OR
                        LOWER(b.name) LIKE %s
                    )
                    LIMIT 10
                """, (f"%{q_lower}%", f"%{q_lower}%", f"%{q_lower}%", f"%{q_lower}%"))
                prod_rows = cursor.fetchall() or []
                for pr in prod_rows:
                    pr_name = localize_value(pr.get('name'), locale) or pr.get('sku')
                    matched_products.append({
                        'id': pr['id'],
                        'type': 'product',
                        'title': pr_name or pr['sku'],
                        'slug': pr.get('slug'),
                        'snippet': f"SKU: {pr['sku']} | Size: {pr.get('tire_size_label') or 'N/A'}",
                        'is_active': True,
                        'url': f"/product/{pr.get('slug') or pr['id']}"
                    })
        finally:
            conn.close()

        # 3. Search Blogs & Articles across all stored language JSON values
        all_blogs = [b for b in Blog.all(include_deleted=False) if b.deleted_at is None]
        matched_blogs = []
        for b in all_blogs:
            slug = b.slug or ''
            cat_name = b.category_name or ''
            title_vals = [str(v) for v in (b.title.values() if isinstance(b.title, dict) else [b.title]) if v]
            content_vals = [clean_html(str(v)) for v in (b.content.values() if isinstance(b.content, dict) else [b.content]) if v]
            display_title = b.get_title(locale) or (title_vals[0] if title_vals else slug)

            match_found = False
            snippet = ''
            for t in title_vals:
                if q_lower in t.lower():
                    match_found = True
                    snippet = t
                    break
            if not match_found and q_lower in slug.lower():
                match_found = True
                snippet = f"/blog/{slug}"
            if not match_found and q_lower in cat_name.lower():
                match_found = True
                snippet = f"Category: {cat_name}"
            if not match_found:
                for c in content_vals:
                    if q_lower in c.lower():
                        match_found = True
                        snippet = make_snippet(c, q_lower)
                        break

            if match_found:
                matched_blogs.append({
                    'id': b.id,
                    'type': 'blog',
                    'title': display_title,
                    'slug': f"/blog/{slug.lstrip('/')}",
                    'category': cat_name,
                    'snippet': snippet,
                    'is_active': b.status == 'published',
                    'url': f"/visionadmin/blogs#blog-{b.id}"
                })

        total = len(matched_pages) + len(matched_sections) + len(matched_blogs) + len(matched_products)
        return jsonify({
            'success': True,
            'query': query,
            'total': total,
            'results': {
                'pages': matched_pages,
                'sections': matched_sections,
                'blogs': matched_blogs,
                'products': matched_products
            }
        })

    # =========================================================================
    # 7. ENQUIRIES / LEADS MANAGEMENT API (hdweb_enquiry table)
    # =========================================================================

    @app.route('/visionadmin/api/enquiries', methods=['GET'])
    @app.route('/visionadmin/api/v1/enquiries', methods=['GET'])
    def visionadmin_get_enquiries():
        """
        Fetches all enquiries from hdweb_enquiry with metrics, filtering, and search.
        """
        q = (request.args.get('q') or '').strip().lower()
        status_filter = request.args.get('status')
        form_type_filter = request.args.get('form_type')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = "SELECT * FROM hdweb_enquiry ORDER BY enquiry_id DESC"
                cursor.execute(sql)
                rows = cursor.fetchall() or []

                total_count = len(rows)
                new_count = 0
                banner_count = 0
                wa_count = 0

                filtered = []
                for r in rows:
                    st = r.get('status', 0)
                    ft = (r.get('form_type') or '').lower()

                    if st == 0:
                        new_count += 1
                    if 'banner' in ft:
                        banner_count += 1
                    else:
                        wa_count += 1

                    if status_filter is not None and status_filter != '' and status_filter != 'all':
                        try:
                            if int(st) != int(status_filter):
                                continue
                        except (ValueError, TypeError):
                            pass

                    if form_type_filter and form_type_filter != 'all':
                        if form_type_filter == 'banner' and 'banner' not in ft:
                            continue
                        elif form_type_filter == 'whatsapp' and 'banner' in ft:
                            continue

                    if q:
                        haystack = " ".join(str(v or '') for v in [
                            r.get('name'), r.get('email'), r.get('number'),
                            r.get('vehicle'), r.get('make'), r.get('model'),
                            r.get('tyre_size'), r.get('city'), r.get('message'),
                            r.get('enquiry_for')
                        ]).lower()
                        if q not in haystack:
                            continue

                    dt = r.get('created_at')
                    created_at_fmt = to_ist_12h(dt, with_seconds=False) if dt else None
                    created_at_raw = dt.isoformat() + 'Z' if dt and hasattr(dt, 'isoformat') else None

                    status_map = {0: 'New', 1: 'In Progress', 2: 'Resolved', 3: 'Closed'}
                    st_val = r.get('status', 0)

                    filtered.append({
                        'enquiry_id': r.get('enquiry_id'),
                        'name': r.get('name'),
                        'email': r.get('email'),
                        'number': r.get('number'),
                        'enquiry_for': r.get('enquiry_for'),
                        'message': r.get('message'),
                        'status': st_val,
                        'status_label': status_map.get(st_val, 'New'),
                        'form_type': r.get('form_type'),
                        'model': r.get('model'),
                        'make': r.get('make'),
                        'year': r.get('year'),
                        'spec': r.get('spec'),
                        'current_insurance': r.get('current_insurance'),
                        'vehicle': r.get('vehicle'),
                        'tyre_size': r.get('tyre_size'),
                        'city': r.get('city'),
                        'created_at': created_at_fmt,
                        'created_at_raw': created_at_raw
                    })

                return jsonify({
                    'success': True,
                    'enquiries': filtered,
                    'metrics': {
                        'total': total_count,
                        'new': new_count,
                        'banner': banner_count,
                        'whatsapp_direct': wa_count
                    },
                    'count': len(filtered)
                })
        finally:
            conn.close()

    @app.route('/visionadmin/api/enquiries/<int:enquiry_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/enquiries/<int:enquiry_id>', methods=['GET'])
    def visionadmin_get_single_enquiry(enquiry_id):
        """Fetches detail of a single enquiry by enquiry_id."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM hdweb_enquiry WHERE enquiry_id = %s", (enquiry_id,))
                row = cursor.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'Enquiry not found'}), 404

                dt = row.get('created_at')
                created_at_fmt = to_ist_12h(dt, with_seconds=False) if dt else None
                created_at_raw = dt.isoformat() + 'Z' if dt and hasattr(dt, 'isoformat') else None
                status_map = {0: 'New', 1: 'In Progress', 2: 'Resolved', 3: 'Closed'}

                item = {**row}
                item['created_at'] = created_at_fmt
                item['created_at_raw'] = created_at_raw
                item['status_label'] = status_map.get(row.get('status', 0), 'New')

                return jsonify({'success': True, 'enquiry': item})
        finally:
            conn.close()

    @app.route('/visionadmin/api/enquiries/<int:enquiry_id>/status', methods=['PUT', 'POST'])
    @app.route('/visionadmin/api/v1/enquiries/<int:enquiry_id>/status', methods=['PUT', 'POST'])
    def visionadmin_update_enquiry_status(enquiry_id):
        """Updates the status of an enquiry."""
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        new_status = data.get('status')
        if new_status is None:
            return jsonify({'success': False, 'error': 'Status is required'}), 400

        try:
            status_int = int(new_status)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'error': 'Invalid status value'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE hdweb_enquiry SET status = %s WHERE enquiry_id = %s", (status_int, enquiry_id))
                conn.commit()
                return jsonify({'success': True, 'message': 'Status updated successfully', 'status': status_int})
        finally:
            conn.close()

    # =========================================================================
    # 8. VISIONADMIN USER MANAGEMENT API (admin_users table)
    # =========================================================================

    @app.route('/visionadmin/api/users', methods=['GET'])
    @app.route('/visonadmin/api/users', methods=['GET'])
    def visionadmin_api_list_users():
        from visionadmin.admin_auth import list_admin_users, get_admin_user_metrics
        is_trash = request.args.get('trash') in ('1', 'true', 'yes')
        users = list_admin_users(is_trash=is_trash)
        metrics = get_admin_user_metrics()

        return jsonify({
            'success': True,
            'users': users,
            'is_trash': is_trash,
            'metrics': {
                'total': metrics.get('total', 0),
                'super_admins': metrics.get('super', 0),
                'managers': metrics.get('managers', 0),
                'active': metrics.get('active', 0),
                'trash': metrics.get('trash', 0)
            }
        })

    @app.route('/visionadmin/api/users', methods=['POST'])
    @app.route('/visonadmin/api/users', methods=['POST'])
    def visionadmin_api_create_user():
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can create admin users.'}), 403

        data = request.get_json(silent=True) or request.form
        name = (data.get('name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        role = (data.get('role') or 'manager').strip().lower()
        is_active = 1 if data.get('is_active') in (1, True, '1', 'true', 'on') else 0

        if not name:
            return jsonify({'error': 'Full name is required.'}), 400
        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'A valid email address is required.'}), 400
        if not password:
            password = secrets.token_urlsafe(16)
        elif len(password) < 8:
            return jsonify({'error': 'Password must be at least 8 characters long.'}), 400
        if role not in ('super_admin', 'manager', 'support'):
            return jsonify({'error': 'Invalid role. Choose Super Admin, Manager, or Support.'}), 400

        from visionadmin.admin_auth import create_admin_user, get_admin_user_by_email, get_admin_user_by_id, serialize_admin_user

        existing = get_admin_user_by_email(email)
        if existing:
            return jsonify({'error': f"An administrator account with email '{email}' already exists."}), 409

        try:
            new_id = create_admin_user(name, email, password, role, is_active)
            created = get_admin_user_by_id(new_id)

            # Send welcome email with login credentials and reset password link
            try:
                from mailer import send_email
                from visionadmin.admin_auth import create_admin_password_reset_token
                token = create_admin_password_reset_token(email)
                reset_link = f"{request.host_url.rstrip('/')}/visionadmin/reset-password?token={token}"
                login_link = f"{request.host_url.rstrip('/')}/visionadmin/login?email={email}"
                assets_url = 'https://tyrescart-scrapping.klever.ae' if ('localhost' in request.host_url or '127.0.0.1' in request.host_url) else request.host_url.rstrip('/')
                
                html_body = render_template(
                    'emails/welcome_user.html',
                    user_name=name,
                    user_email=email,
                    user_role=role,
                    reset_link=reset_link,
                    login_link=login_link,
                    assets_url=assets_url,
                )
                send_email(
                    email,
                    'Welcome to TyresVision! Your Account Details',
                    html_body,
                )
            except Exception as mail_err:
                app.logger.error(f"Failed to send welcome email to {email}: {mail_err}", exc_info=True)

            return jsonify({
                'success': True,
                'message': f"Administrator '{name}' created successfully. Welcome email sent.",
                'user': serialize_admin_user(created) if created else {}
            }), 201
        except Exception as err:
            return jsonify({'error': f"Failed to create admin user: {err}"}), 500

    @app.route('/visionadmin/api/users/<int:user_id>', methods=['GET'])
    @app.route('/visonadmin/api/users/<int:user_id>', methods=['GET'])
    def visionadmin_api_get_user(user_id):
        from visionadmin.admin_auth import get_admin_user_by_id, serialize_admin_user
        user = get_admin_user_by_id(user_id)
        if not user:
            return jsonify({'error': 'Administrator user not found.'}), 404
        return jsonify({'success': True, 'user': serialize_admin_user(user)})

    @app.route('/visionadmin/api/users/<int:user_id>', methods=['PUT'])
    @app.route('/visonadmin/api/users/<int:user_id>', methods=['PUT'])
    def visionadmin_api_update_user(user_id):
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can update admin users.'}), 403

        from visionadmin.admin_auth import get_admin_user_by_id, update_admin_user, get_admin_user_by_email, serialize_admin_user, count_super_admins

        existing = get_admin_user_by_id(user_id)
        if not existing:
            return jsonify({'error': 'Administrator user not found.'}), 404

        data = request.get_json(silent=True) or request.form
        name = (data.get('name') or existing['name']).strip()
        email = (data.get('email') or existing['email']).strip().lower()
        role = (data.get('role') or existing['role']).strip().lower()
        is_active_val = data.get('is_active')
        is_active = 1 if is_active_val in (1, True, '1', 'true', 'on') else (0 if is_active_val in (0, False, '0', 'false') else existing.get('is_active', 1))
        password = data.get('password')

        if not name:
            return jsonify({'error': 'Name cannot be empty.'}), 400
        if not email or not EMAIL_RE.match(email):
            return jsonify({'error': 'A valid email address is required.'}), 400
        if role not in ('super_admin', 'manager', 'support'):
            return jsonify({'error': 'Invalid role.'}), 400
        if password and len(password) < 8:
            return jsonify({'error': 'New password must be at least 8 characters.'}), 400

        # Check if demoting the only super_admin
        if existing.get('role') == 'super_admin' and role != 'super_admin' and count_super_admins() <= 1:
            return jsonify({'error': 'Action blocked. Cannot demote the only remaining Super Administrator.'}), 400

        # Check email collision
        if email != existing['email'].strip().lower():
            dup = get_admin_user_by_email(email)
            if dup and dup['id'] != user_id:
                return jsonify({'error': f"Email '{email}' is already in use."}), 409

        try:
            update_admin_user(user_id, name, email, role, is_active, password if password else None)
            updated = get_admin_user_by_id(user_id)
            return jsonify({
                'success': True,
                'message': f"Administrator '{name}' updated successfully.",
                'user': serialize_admin_user(updated)
            })
        except Exception as err:
            return jsonify({'error': f"Failed to update user: {err}"}), 500

    @app.route('/visionadmin/api/users/<int:user_id>', methods=['DELETE'])
    @app.route('/visonadmin/api/users/<int:user_id>', methods=['DELETE'])
    def visionadmin_api_delete_user(user_id):
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can delete admin users.'}), 403

        current_admin_id = session.get('admin_user_id') or session.get('user_id')
        if user_id == current_admin_id:
            return jsonify({'error': 'Action not allowed. You cannot delete your own active account.'}), 400

        from visionadmin.admin_auth import get_admin_user_by_id, delete_admin_user, count_super_admins

        target = get_admin_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'Administrator user not found.'}), 404

        if target.get('role') == 'super_admin' and count_super_admins() <= 1:
            return jsonify({'error': 'Action blocked. Cannot delete the only remaining Super Administrator.'}), 400

        try:
            delete_admin_user(user_id)
            return jsonify({
                'success': True,
                'message': f"Administrator account '{target['name']}' moved to trash."
            })
        except Exception as err:
            return jsonify({'error': f"Failed to move user to trash: {err}"}), 500

    @app.route('/visionadmin/api/users/<int:user_id>/restore', methods=['POST'])
    @app.route('/visonadmin/api/users/<int:user_id>/restore', methods=['POST'])
    def visionadmin_api_restore_user(user_id):
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can restore admin users.'}), 403

        from visionadmin.admin_auth import get_admin_user_by_id, restore_admin_user

        target = get_admin_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'Administrator user not found.'}), 404

        try:
            restore_admin_user(user_id)
            return jsonify({
                'success': True,
                'message': f"Administrator account '{target['name']}' restored from trash."
            })
        except Exception as err:
            return jsonify({'error': f"Failed to restore user: {err}"}), 500

    @app.route('/visionadmin/api/users/<int:user_id>/purge', methods=['DELETE', 'POST'])
    @app.route('/visonadmin/api/users/<int:user_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_user(user_id):
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can permanently delete admin users.'}), 403

        current_admin_id = session.get('admin_user_id') or session.get('user_id')
        if user_id == current_admin_id:
            return jsonify({'error': 'Action not allowed. You cannot delete your own account.'}), 400

        from visionadmin.admin_auth import get_admin_user_by_id, permanent_delete_admin_user

        target = get_admin_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'Administrator user not found.'}), 404

        try:
            permanent_delete_admin_user(user_id)
            return jsonify({
                'success': True,
                'message': f"Administrator account '{target['name']}' permanently deleted."
            })
        except Exception as err:
            return jsonify({'error': f"Failed to permanently delete user: {err}"}), 500

    @app.route('/visionadmin/api/users/<int:user_id>/toggle-status', methods=['POST'])
    @app.route('/visonadmin/api/users/<int:user_id>/toggle-status', methods=['POST'])
    def visionadmin_api_toggle_user_status(user_id):
        role_norm = str(session.get('role') or '').strip().lower().replace('-', '_').replace(' ', '_')
        if role_norm not in ('super_admin', 'superadmin') and session.get('role') != 'SuperAdmin':
            return jsonify({'error': 'Forbidden. Only Super Administrators can modify account status.'}), 403

        current_admin_id = session.get('admin_user_id') or session.get('user_id')
        if user_id == current_admin_id:
            return jsonify({'error': 'Action not allowed. You cannot disable your own active account.'}), 400

        from visionadmin.admin_auth import get_admin_user_by_id, toggle_admin_user_status, count_super_admins

        target = get_admin_user_by_id(user_id)
        if not target:
            return jsonify({'error': 'Administrator user not found.'}), 404

        if target.get('role') == 'super_admin' and target.get('is_active', 1) == 1 and count_super_admins() <= 1:
            return jsonify({'error': 'Action blocked. Cannot disable the only remaining active Super Administrator.'}), 400

        new_status = toggle_admin_user_status(user_id)
        return jsonify({
            'success': True,
            'is_active': new_status,
            'message': f"Administrator account '{target['name']}' {'activated' if new_status else 'disabled'}."
        })

    # =========================================================================
    # 7. SCOPE SWITCHER & MULTI-STORE API
    # =========================================================================

    @app.route('/visionadmin/api/scopes/tree', methods=['GET'])
    def visionadmin_api_scope_tree():
        """Returns full hierarchy tree for Topbar Scope Switcher (Global -> Websites -> Stores -> Views)."""
        tree = StoreContext.get_scope_tree()
        active_scope = {
            'website_id': session.get('admin_active_website_id'),
            'store_id': session.get('admin_active_store_id'),
            'store_view_id': session.get('admin_active_store_view_id')
        }
        return jsonify({
            'success': True,
            'tree': tree,
            'active_scope': active_scope,
            'active_scope_name': session.get('admin_active_scope_name', 'All Store Views')
        })

    @app.route('/visionadmin/api/scopes/switch', methods=['POST'])
    def visionadmin_api_scope_switch():
        """Switches active Website, Store, and Store View in admin session."""
        data = request.get_json() or {}
        website_id = data.get('website_id')
        store_id = data.get('store_id')
        store_view_id = data.get('store_view_id')
        scope_name = data.get('scope_name')

        if (website_id in (None, '', 'global') and 
            store_id in (None, '', 'global') and 
            store_view_id in (None, '', 'global')):
            session.pop('admin_active_website_id', None)
            session.pop('admin_active_store_id', None)
            session.pop('admin_active_store_view_id', None)
            session['admin_active_scope_name'] = 'All Store Views'
        else:
            session['admin_active_website_id'] = int(website_id) if website_id and str(website_id).isdigit() else None
            session['admin_active_store_id'] = int(store_id) if store_id and str(store_id).isdigit() else None
            session['admin_active_store_view_id'] = int(store_view_id) if store_view_id and str(store_view_id).isdigit() else None
            session['admin_active_scope_name'] = scope_name or 'All Store Views'

        return jsonify({
            'success': True,
            'website_id': session.get('admin_active_website_id'),
            'store_id': session.get('admin_active_store_id'),
            'store_view_id': session.get('admin_active_store_view_id'),
            'scope_name': session.get('admin_active_scope_name', 'All Store Views'),
            'message': 'Admin scope updated successfully.'
        })

    @app.route('/visionadmin/api/websites', methods=['GET'])
    def visionadmin_api_list_websites():
        websites = StoreContext.get_all_websites(include_inactive=True)
        return jsonify({'websites': websites, 'count': len(websites)})

    @app.route('/visionadmin/api/all-stores', methods=['GET'])
    def visionadmin_api_all_stores():
        filter_website = request.args.get('website')
        filter_store = request.args.get('store')
        filter_view = request.args.get('store_view')
        rows = StoreContext.get_stores_table_rows(
            filter_website=filter_website,
            filter_store=filter_store,
            filter_view=filter_view
        )
        return jsonify({'success': True, 'rows': rows, 'count': len(rows)})

    @app.route('/visionadmin/api/websites', methods=['POST'])
    def visionadmin_api_create_website():
        data = request.get_json() or {}
        code = (data.get('code') or '').strip().lower()
        name = (data.get('name') or '').strip()
        domain = (data.get('domain') or '').strip()
        sort_order = int(data.get('sort_order') or 10)
        is_default = 1 if data.get('is_default') else 0
        status = data.get('status', 'active')
        user_id = session.get('admin_user_id') or session.get('user_id')

        if not code or not name:
            return jsonify({'success': False, 'error': 'Website code and name are required.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, deleted_at FROM websites WHERE code = %s", (code,))
                existing = cursor.fetchone()
                if existing:
                    if existing.get('deleted_at') is None:
                        return jsonify({'success': False, 'error': f"Website code '{code}' is already in use."}), 400
                    cursor.execute("""
                        UPDATE websites
                        SET name = %s, domain = %s, is_default = %s, status = %s, sort_order = %s,
                            deleted_at = NULL, deleted_by = NULL, updated_by = %s
                        WHERE id = %s
                    """, (name, domain, is_default, status, sort_order, user_id, existing['id']))
                    conn.commit()
                    log_activity('create', 'website', existing['id'], {'code': code, 'name': name}, actor_user_id=user_id)
                    return jsonify({'success': True, 'id': existing['id'], 'message': 'Website created successfully.'}), 201

                cursor.execute("""
                    INSERT INTO websites (code, name, domain, is_default, status, sort_order, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (code, name, domain, is_default, status, sort_order, user_id))
                conn.commit()
                new_id = cursor.lastrowid
                log_activity('create', 'website', new_id, {'code': code, 'name': name}, actor_user_id=user_id)
                return jsonify({'success': True, 'id': new_id, 'message': 'Website created successfully.'}), 201
        finally:
            conn.close()

    @app.route('/visionadmin/api/websites/<int:web_id>', methods=['GET'])
    def visionadmin_api_get_website(web_id):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM websites WHERE id = %s AND deleted_at IS NULL", (web_id,))
                web = cursor.fetchone()
                if not web:
                    return jsonify({'success': False, 'error': 'Website not found.'}), 404
                return jsonify({'success': True, 'website': web})
        finally:
            conn.close()

    @app.route('/visionadmin/api/websites/<int:web_id>', methods=['PUT'])
    def visionadmin_api_update_website(web_id):
        data = request.get_json() or {}
        code = (data.get('code') or '').strip().lower()
        name = data.get('name')
        domain = data.get('domain')
        sort_order = int(data.get('sort_order') or 10)
        is_default = 1 if data.get('is_default') else 0
        status = data.get('status', 'active')
        user_id = session.get('admin_user_id') or session.get('user_id')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE websites 
                    SET code = COALESCE(NULLIF(%s, ''), code),
                        name = COALESCE(%s, name),
                        domain = COALESCE(%s, domain),
                        sort_order = %s,
                        is_default = %s,
                        status = %s,
                        updated_by = %s
                    WHERE id = %s
                """, (code, name, domain, sort_order, is_default, status, user_id, web_id))
                conn.commit()
                log_activity('update', 'website', web_id, {'name': name, 'domain': domain}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': 'Website updated successfully.'})
        finally:
            conn.close()

    @app.route('/visionadmin/api/websites/<int:web_id>', methods=['DELETE'])
    def visionadmin_api_delete_website(web_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM websites WHERE id = %s AND deleted_at IS NULL", (web_id,))
                web = cursor.fetchone()
                if not web:
                    return jsonify({'success': False, 'error': 'Website not found.'}), 404
                if web.get('is_default') == 1:
                    return jsonify({'success': False, 'error': 'Cannot delete default primary website.'}), 400

                cursor.execute("UPDATE websites SET deleted_at = NOW(), deleted_by = %s WHERE id = %s", (user_id, web_id))
                conn.commit()
                log_activity('delete', 'website', web_id, web, {'deleted': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Website '{web['name']}' moved to trash."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores', methods=['GET'])
    def visionadmin_api_list_stores():
        website_id = request.args.get('website_id')
        stores = StoreContext.get_all_stores(website_id=website_id, include_inactive=True)
        return jsonify({'stores': stores, 'count': len(stores)})

    @app.route('/visionadmin/api/stores/<int:store_id>', methods=['GET'])
    def visionadmin_api_get_store(store_id):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM stores WHERE id = %s AND deleted_at IS NULL", (store_id,))
                st = cursor.fetchone()
                if not st:
                    return jsonify({'success': False, 'error': 'Store not found.'}), 404

                name_str = st['name']
                name_en = ''
                if isinstance(name_str, dict):
                    name_en = name_str.get('en') or next(iter(name_str.values()), '')
                elif isinstance(name_str, str):
                    if name_str.strip().startswith('{'):
                        try:
                            p = json.loads(name_str)
                            name_en = p.get('en') or next(iter(p.values()), name_str)
                        except Exception:
                            name_en = name_str
                    else:
                        name_en = name_str

                st['display_name'] = name_en
                return jsonify({'success': True, 'store': st})
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores', methods=['POST'])
    def visionadmin_api_create_store():
        data = request.get_json() or {}
        website_id = data.get('website_id') or 1
        code = (data.get('code') or '').strip().lower()
        raw_name = (data.get('name') or '').strip()
        root_category_id = data.get('root_category_id') or None
        default_store_view_id = data.get('default_store_view_id') or None
        sort_order = int(data.get('sort_order') or 10)
        emirate = data.get('emirate') or 'Dubai'
        phone = data.get('phone') or '+971 50 506 9575'
        email = data.get('email') or ''
        is_active = 1 if data.get('is_active', 1) in (1, '1', True) else 0
        user_id = session.get('admin_user_id') or session.get('user_id')

        if not code or not raw_name:
            return jsonify({'success': False, 'error': 'Store code and name are required.'}), 400

        name_json = json.dumps({'en': raw_name}) if not raw_name.startswith('{') else raw_name

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, deleted_at FROM stores WHERE code = %s", (code,))
                existing = cursor.fetchone()
                if existing:
                    if existing.get('deleted_at') is None:
                        return jsonify({'success': False, 'error': f"Store code '{code}' is already in use."}), 400
                    cursor.execute("""
                        UPDATE stores
                        SET website_id = %s, name = %s, root_category_id = %s, default_store_view_id = %s,
                            emirate = %s, phone = %s, email = %s, is_active = %s, sort_order = %s,
                            deleted_at = NULL, deleted_by = NULL, updated_by = %s
                        WHERE id = %s
                    """, (website_id, name_json, root_category_id, default_store_view_id, emirate, phone, email, is_active, sort_order, user_id, existing['id']))
                    conn.commit()
                    log_activity('create', 'store', existing['id'], {'code': code, 'name': raw_name}, actor_user_id=user_id)
                    return jsonify({'success': True, 'id': existing['id'], 'message': 'Store created successfully.'}), 201

                cursor.execute("""
                    INSERT INTO stores (
                        website_id, code, name, root_category_id, default_store_view_id,
                        emirate, phone, email, is_active, sort_order, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (website_id, code, name_json, root_category_id, default_store_view_id, emirate, phone, email, is_active, sort_order, user_id))
                conn.commit()
                new_id = cursor.lastrowid
                log_activity('create', 'store', new_id, {'code': code, 'name': raw_name}, actor_user_id=user_id)
                return jsonify({'success': True, 'id': new_id, 'message': 'Store created successfully.'}), 201
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores/<int:store_id>', methods=['PUT'])
    def visionadmin_api_update_store(store_id):
        data = request.get_json() or {}
        website_id = data.get('website_id') or 1
        code = (data.get('code') or '').strip().lower()
        raw_name = data.get('name')
        root_category_id = data.get('root_category_id') or None
        default_store_view_id = data.get('default_store_view_id') or None
        sort_order = int(data.get('sort_order') or 10)
        emirate = data.get('emirate')
        phone = data.get('phone')
        email = data.get('email')
        is_active = 1 if data.get('is_active', 1) in (1, '1', True) else 0
        user_id = session.get('admin_user_id') or session.get('user_id')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM stores WHERE id = %s AND deleted_at IS NULL", (store_id,))
                existing = cursor.fetchone()
                if not existing:
                    return jsonify({'success': False, 'error': 'Store not found.'}), 404

                name_val = existing['name']
                if raw_name:
                    name_str = str(raw_name).strip()
                    if name_str.startswith('{'):
                        name_val = name_str
                    else:
                        name_val = json.dumps({'en': name_str})

                cursor.execute("""
                    UPDATE stores 
                    SET website_id = %s,
                        code = COALESCE(NULLIF(%s, ''), code),
                        name = %s,
                        root_category_id = %s,
                        default_store_view_id = %s,
                        emirate = COALESCE(%s, emirate),
                        phone = COALESCE(%s, phone),
                        email = COALESCE(%s, email),
                        is_active = %s,
                        sort_order = %s,
                        updated_by = %s
                    WHERE id = %s
                """, (website_id, code, name_val, root_category_id, default_store_view_id, emirate, phone, email, is_active, sort_order, user_id, store_id))
                conn.commit()
                log_activity('update', 'store', store_id, {'code': code, 'name': raw_name}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': 'Store updated successfully.'})
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores/<int:store_id>', methods=['DELETE'])
    def visionadmin_api_delete_store(store_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM stores WHERE id = %s AND deleted_at IS NULL", (store_id,))
                store = cursor.fetchone()
                if not store:
                    return jsonify({'success': False, 'error': 'Store not found.'}), 404

                cursor.execute("UPDATE stores SET deleted_at = NOW(), deleted_by = %s WHERE id = %s", (user_id, store_id))
                conn.commit()
                log_activity('delete', 'store', store_id, store, {'deleted': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store '{store['code']}' moved to trash."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views', methods=['GET'])
    def visionadmin_api_list_store_views():
        store_id = request.args.get('store_id')
        views = StoreContext.get_all_store_views(store_id=store_id, include_inactive=True)
        return jsonify({'store_views': views, 'count': len(views)})

    @app.route('/visionadmin/api/store-views/<int:view_id>', methods=['GET'])
    def visionadmin_api_get_store_view(view_id):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM store_views WHERE id = %s AND deleted_at IS NULL", (view_id,))
                view = cursor.fetchone()
                if not view:
                    return jsonify({'success': False, 'error': 'Store view not found.'}), 404
                return jsonify({'success': True, 'store_view': view})
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views', methods=['POST'])
    def visionadmin_api_create_store_view():
        data = request.get_json() or {}
        store_id = int(data.get('store_id')) if data.get('store_id') else None
        name = (data.get('name') or '').strip()
        code = (data.get('code') or '').strip().lower()
        is_active = 1 if (data.get('status') == '1' or data.get('is_active') in (1, '1', True)) else 0
        sort_order = int(data.get('sort_order') or 10)
        user_id = session.get('admin_user_id') or session.get('user_id')

        if not store_id or not name or not code:
            return jsonify({'success': False, 'error': 'Store, Name, and Code are required.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT website_id FROM stores WHERE id = %s AND deleted_at IS NULL", (store_id,))
                st = cursor.fetchone()
                website_id = st['website_id'] if st else 1

                locale = code.split('_')[0].lower()

                # 1. Check if an ACTIVE store view already uses this code in this store
                cursor.execute("SELECT id FROM store_views WHERE store_id = %s AND code = %s AND deleted_at IS NULL", (store_id, code))
                active_existing = cursor.fetchone()
                if active_existing:
                    return jsonify({'success': False, 'error': f"Store view code '{code}' already exists for this store."}), 400

                # 2. Rename any soft-deleted store views with (store_id, code) so unique constraint does not collide
                cursor.execute("""
                    UPDATE store_views
                    SET code = CONCAT(code, '__deleted_', id, '_', UNIX_TIMESTAMP())
                    WHERE store_id = %s AND code = %s AND deleted_at IS NOT NULL
                """, (store_id, code))

                # 3. Always insert a new store view record
                cursor.execute("""
                    INSERT INTO store_views (store_id, website_id, code, name, locale, currency_code, is_active, sort_order, created_by)
                    VALUES (%s, %s, %s, %s, %s, 'AED', %s, %s, %s)
                """, (store_id, website_id, code, name, locale, is_active, sort_order, user_id))
                conn.commit()
                new_id = cursor.lastrowid
                log_activity('create', 'store_view', new_id, {'code': code, 'name': name}, actor_user_id=user_id)
                return jsonify({'success': True, 'id': new_id, 'message': 'Store view created successfully.'}), 201
        except pymysql.err.IntegrityError as ie:
            conn.rollback()
            return jsonify({'success': False, 'error': f"Database integrity error: {str(ie)}"}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f"Failed to create store view: {str(e)}"}), 500
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views/<int:view_id>', methods=['PUT'])
    def visionadmin_api_update_store_view(view_id):
        data = request.get_json() or {}
        store_id = data.get('store_id')
        name = (data.get('name') or '').strip()
        code = (data.get('code') or '').strip().lower()
        is_active = 1 if (data.get('status') == '1' or data.get('is_active') in (1, '1', True)) else 0
        sort_order = int(data.get('sort_order') or 10)
        user_id = session.get('admin_user_id') or session.get('user_id')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM store_views WHERE id = %s AND deleted_at IS NULL", (view_id,))
                existing = cursor.fetchone()
                if not existing:
                    return jsonify({'success': False, 'error': 'Store view not found.'}), 404

                target_store_id = store_id if store_id is not None else existing['store_id']
                target_code = code if code else existing['code']

                # Check if target_code is already used in target_store_id by ANOTHER active view
                cursor.execute("""
                    SELECT id FROM store_views 
                    WHERE store_id = %s AND code = %s AND id != %s AND deleted_at IS NULL
                """, (target_store_id, target_code, view_id))
                active_conflict = cursor.fetchone()
                if active_conflict:
                    return jsonify({'success': False, 'error': f"Store view code '{target_code}' is already in use by another active store view in this store."}), 400

                # Clean up / rename any soft-deleted views occupying (target_store_id, target_code)
                cursor.execute("""
                    UPDATE store_views
                    SET code = CONCAT(code, '__deleted_', id, '_', UNIX_TIMESTAMP())
                    WHERE store_id = %s AND code = %s AND id != %s AND deleted_at IS NOT NULL
                """, (target_store_id, target_code, view_id))

                website_id = existing['website_id']
                if store_id:
                    cursor.execute("SELECT website_id FROM stores WHERE id = %s AND deleted_at IS NULL", (store_id,))
                    st = cursor.fetchone()
                    if st:
                        website_id = st['website_id']

                locale = target_code.split('_')[0].lower() if target_code else existing['locale']
                cursor.execute("""
                    UPDATE store_views
                    SET store_id = COALESCE(%s, store_id),
                        website_id = %s,
                        name = COALESCE(NULLIF(%s, ''), name),
                        code = COALESCE(NULLIF(%s, ''), code),
                        locale = %s,
                        is_active = %s,
                        sort_order = %s,
                        updated_by = %s
                    WHERE id = %s
                """, (store_id, website_id, name, code, locale, is_active, sort_order, user_id, view_id))
                conn.commit()
                log_activity('update', 'store_view', view_id, {'code': target_code, 'name': name or existing['name']}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': 'Store view updated successfully.'})
        except pymysql.err.IntegrityError as ie:
            conn.rollback()
            return jsonify({'success': False, 'error': f"Database integrity error: {str(ie)}"}), 400
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f"Failed to update store view: {str(e)}"}), 500
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views/<int:view_id>', methods=['DELETE'])
    def visionadmin_api_delete_store_view(view_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM store_views WHERE id = %s AND deleted_at IS NULL", (view_id,))
                view = cursor.fetchone()
                if not view:
                    return jsonify({'success': False, 'error': 'Store view not found.'}), 404

                cursor.execute("""
                    UPDATE store_views 
                    SET deleted_at = NOW(), 
                        deleted_by = %s, 
                        code = CONCAT(code, '__deleted_', id, '_', UNIX_TIMESTAMP()) 
                    WHERE id = %s
                """, (user_id, view_id))
                conn.commit()
                log_activity('delete', 'store_view', view_id, view, {'deleted': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store view '{view['name']}' moved to trash."})
        except Exception as e:
            conn.rollback()
            return jsonify({'success': False, 'error': f"Failed to delete store view: {str(e)}"}), 500
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores/trash', methods=['GET'])
    def visionadmin_api_stores_trash():
        """Returns all soft-deleted websites, stores, and store_views."""
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, code, name, domain, is_default, status, sort_order, deleted_at, deleted_by
                    FROM websites
                    WHERE deleted_at IS NOT NULL
                    ORDER BY deleted_at DESC
                """)
                trashed_websites = cursor.fetchall() or []

                cursor.execute("""
                    SELECT s.id, s.website_id, s.code, s.name, s.sort_order, s.deleted_at, s.deleted_by,
                           w.name AS website_name, w.code AS website_code
                    FROM stores s
                    LEFT JOIN websites w ON w.id = s.website_id
                    WHERE s.deleted_at IS NOT NULL
                    ORDER BY s.deleted_at DESC
                """)
                trashed_stores = cursor.fetchall() or []

                cursor.execute("""
                    SELECT sv.id, sv.store_id, sv.website_id, sv.code, sv.name, sv.locale, sv.is_active, sv.sort_order, sv.deleted_at, sv.deleted_by,
                           s.name AS store_name, s.code AS store_code,
                           w.name AS website_name, w.code AS website_code
                    FROM store_views sv
                    LEFT JOIN stores s ON s.id = sv.store_id
                    LEFT JOIN websites w ON w.id = sv.website_id OR w.id = s.website_id
                    WHERE sv.deleted_at IS NOT NULL
                    ORDER BY sv.deleted_at DESC
                """)
                trashed_views = cursor.fetchall() or []

                for v in trashed_views:
                    raw_c = v.get('code') or ''
                    v['display_code'] = re.sub(r'__deleted_\d+_\d+$', '', raw_c)

                total_count = len(trashed_websites) + len(trashed_stores) + len(trashed_views)
                return jsonify({
                    'success': True,
                    'websites': trashed_websites,
                    'stores': trashed_stores,
                    'store_views': trashed_views,
                    'total_count': total_count
                })
        finally:
            conn.close()

    @app.route('/visionadmin/api/websites/<int:web_id>/restore', methods=['POST'])
    def visionadmin_api_restore_website(web_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM websites WHERE id = %s AND deleted_at IS NOT NULL", (web_id,))
                web = cursor.fetchone()
                if not web:
                    return jsonify({'success': False, 'error': 'Website not found in trash.'}), 404

                cursor.execute("UPDATE websites SET deleted_at = NULL, deleted_by = NULL, updated_by = %s WHERE id = %s", (user_id, web_id))
                conn.commit()
                log_activity('restore', 'website', web_id, {'deleted': True}, {'deleted': False}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Website '{web['name']}' restored successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/websites/<int:web_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_website(web_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM websites WHERE id = %s", (web_id,))
                web = cursor.fetchone()
                if not web:
                    return jsonify({'success': False, 'error': 'Website not found.'}), 404
                if web.get('is_default') == 1:
                    return jsonify({'success': False, 'error': 'Cannot permanently delete the default primary website.'}), 400

                cursor.execute("SELECT id FROM stores WHERE website_id = %s AND deleted_at IS NULL", (web_id,))
                if cursor.fetchone():
                    return jsonify({'success': False, 'error': 'Cannot permanently delete website because it contains active stores. Delete or move them first.'}), 400

                cursor.execute("DELETE FROM store_views WHERE website_id = %s", (web_id,))
                cursor.execute("DELETE FROM stores WHERE website_id = %s", (web_id,))
                cursor.execute("DELETE FROM websites WHERE id = %s", (web_id,))
                conn.commit()
                log_activity('purge', 'website', web_id, web, {'purged': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Website '{web['name']}' permanently deleted."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores/<int:store_id>/restore', methods=['POST'])
    def visionadmin_api_restore_store(store_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM stores WHERE id = %s AND deleted_at IS NOT NULL", (store_id,))
                store = cursor.fetchone()
                if not store:
                    return jsonify({'success': False, 'error': 'Store not found in trash.'}), 404

                cursor.execute("UPDATE stores SET deleted_at = NULL, deleted_by = NULL, updated_by = %s WHERE id = %s", (user_id, store_id))
                conn.commit()
                log_activity('restore', 'store', store_id, {'deleted': True}, {'deleted': False}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store '{store['code']}' restored successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/stores/<int:store_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_store(store_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM stores WHERE id = %s", (store_id,))
                store = cursor.fetchone()
                if not store:
                    return jsonify({'success': False, 'error': 'Store not found.'}), 404

                cursor.execute("SELECT id FROM store_views WHERE store_id = %s AND deleted_at IS NULL", (store_id,))
                if cursor.fetchone():
                    return jsonify({'success': False, 'error': 'Cannot permanently delete store because it contains active store views. Delete them first.'}), 400

                cursor.execute("DELETE FROM store_views WHERE store_id = %s", (store_id,))
                cursor.execute("DELETE FROM stores WHERE id = %s", (store_id,))
                conn.commit()
                log_activity('purge', 'store', store_id, store, {'purged': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store '{store['code']}' permanently deleted."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views/<int:view_id>/restore', methods=['POST'])
    def visionadmin_api_restore_store_view(view_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM store_views WHERE id = %s AND deleted_at IS NOT NULL", (view_id,))
                view = cursor.fetchone()
                if not view:
                    return jsonify({'success': False, 'error': 'Store view not found in trash.'}), 404

                clean_code = re.sub(r'__deleted_\d+_\d+$', '', view.get('code') or '')
                cursor.execute("SELECT id FROM store_views WHERE store_id = %s AND code = %s AND deleted_at IS NULL", (view['store_id'], clean_code))
                if cursor.fetchone():
                    clean_code = f"{clean_code}_restored_{int(time.time())}"

                cursor.execute("UPDATE store_views SET deleted_at = NULL, deleted_by = NULL, code = %s, updated_by = %s WHERE id = %s", (clean_code, user_id, view_id))
                conn.commit()
                log_activity('restore', 'store_view', view_id, {'deleted': True}, {'deleted': False}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store view '{view['name']}' restored successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/store-views/<int:view_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_store_view(view_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM store_views WHERE id = %s", (view_id,))
                view = cursor.fetchone()
                if not view:
                    return jsonify({'success': False, 'error': 'Store view not found.'}), 404

                cursor.execute("DELETE FROM store_views WHERE id = %s", (view_id,))
                conn.commit()
                log_activity('purge', 'store_view', view_id, view, {'purged': True}, actor_user_id=user_id)
                return jsonify({'success': True, 'message': f"Store view '{view['name']}' permanently deleted."})
        finally:
            conn.close()

    # =========================================================================
    # 8. DYNAMIC ATTRIBUTES & ATTRIBUTE SETS API
    # =========================================================================

    @app.route('/visionadmin/api/attributes', methods=['GET'])
    def visionadmin_api_list_attributes():
        """Returns all active attributes or trash attributes with counts."""
        if request.args.get('trash') == '1':
            trash_attrs = AttributeService.get_trash_attributes()
            return jsonify({'attributes': trash_attrs, 'count': len(trash_attrs)})

        attrs = AttributeService.get_all_attributes(include_inactive=True)
        trash_attrs = AttributeService.get_trash_attributes()
        return jsonify({
            'attributes': attrs,
            'count': len(attrs),
            'trash_count': len(trash_attrs),
            'trash': trash_attrs
        })

    @app.route('/visionadmin/api/attributes/<int:attr_id>', methods=['GET'])
    def visionadmin_api_get_attribute(attr_id):
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attributes WHERE id = %s AND deleted_at IS NULL", (attr_id,))
                attr = cursor.fetchone()
                if not attr:
                    return jsonify({'error': 'Attribute not found.'}), 404
                if attr.get('name') and isinstance(attr['name'], str):
                    try:
                        attr['name'] = json.loads(attr['name'])
                    except Exception:
                        pass
                if attr.get('validation_rules') and isinstance(attr['validation_rules'], str):
                    try:
                        attr['validation_rules'] = json.loads(attr['validation_rules'])
                    except Exception:
                        pass
                attr['options'] = AttributeService.get_attribute_options(attr_id)
                return jsonify({'attribute': attr})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attributes', methods=['POST'])
    def visionadmin_api_create_attribute():
        """Creates a new dynamic attribute with options and audit tracking."""
        data = request.get_json() or {}
        code = (data.get('code') or '').strip().lower()
        name = data.get('name') or {}
        attr_type = data.get('type') or 'text'
        scope = data.get('scope') or 'global'
        unit = data.get('unit')
        default_value = data.get('default_value')
        user_id = get_current_admin_user_id()

        if not code:
            return jsonify({'error': 'Attribute code is required.'}), 400

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM attributes WHERE code = %s AND deleted_at IS NULL", (code,))
                if cursor.fetchone():
                    return jsonify({'error': f"Attribute code '{code}' already exists."}), 400

                validation_rules = data.get('validation_rules') or {}
                if isinstance(validation_rules, str):
                    try:
                        validation_rules = json.loads(validation_rules)
                    except Exception:
                        validation_rules = {}

                for k in [
                    'input_validation', 'add_to_columns', 'use_in_filter_options',
                    'use_in_promo_rules', 'allow_html_tags', 'used_in_product_listing',
                    'used_for_sort_by', 'use_in_search_results_nav',
                    'facet_coverage_rate', 'facet_max_size', 'facet_sort_order', 'facet_internal_logic',
                    'layered_nav'
                ]:
                    if k in data:
                        validation_rules[k] = data[k]

                is_required = 1 if data.get('is_required') in (1, '1', True) else 0
                is_unique = 1 if data.get('is_unique') in (1, '1', True) else 0
                is_filterable = 1 if data.get('is_filterable') in (1, '1', True, 'filterable_results', 'filterable_no_results') else 0
                is_searchable = 1 if data.get('is_searchable') in (1, '1', True) else 0
                is_comparable = 1 if data.get('is_comparable') in (1, '1', True) else 0
                is_visible_on_front = 1 if data.get('is_visible_on_front') in (1, '1', True) else 0
                sort_order = int(data.get('sort_order') or data.get('position') or 0)

                cursor.execute("""
                    INSERT INTO attributes (
                        code, name, type, scope, unit, default_value, validation_rules,
                        is_required, is_unique, is_filterable, is_searchable, is_comparable,
                        is_visible_on_front, is_system, sort_order, created_by, updated_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    code,
                    json.dumps(name) if isinstance(name, dict) else str(name),
                    attr_type,
                    scope,
                    unit,
                    default_value,
                    json.dumps(validation_rules) if validation_rules else None,
                    is_required,
                    is_unique,
                    is_filterable,
                    is_searchable,
                    is_comparable,
                    is_visible_on_front,
                    0,
                    sort_order,
                    user_id,
                    user_id
                ))
                attr_id = cursor.lastrowid

                # Insert options if select/multiselect/swatch
                options = data.get('options') or []
                for idx, opt in enumerate(options, start=1):
                    val = opt.get('value') if isinstance(opt, dict) else str(opt)
                    lbl = opt.get('label') if isinstance(opt, dict) else {'default': str(opt)}
                    is_def = 1 if (isinstance(opt, dict) and opt.get('is_default')) else 0
                    swatch_val = opt.get('swatch_value') if isinstance(opt, dict) else None
                    if val:
                        cursor.execute("""
                            INSERT INTO attribute_options (attribute_id, value, label, swatch_value, sort_order, is_default, created_by, updated_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (attr_id, val, json.dumps(lbl) if isinstance(lbl, dict) else str(lbl), swatch_val, idx, is_def, user_id, user_id))

                conn.commit()
                log_activity('create', 'attribute', attr_id, None, data, user_id=user_id)
                return jsonify({'success': True, 'id': attr_id, 'message': f"Attribute '{code}' created successfully."}), 201
        finally:
            conn.close()

    @app.route('/visionadmin/api/attributes/<int:attr_id>', methods=['PUT'])
    def visionadmin_api_update_attribute(attr_id):
        """Updates an existing dynamic attribute, its options and audit log."""
        data = request.get_json() or {}
        name = data.get('name') or {}
        attr_type = data.get('type')
        scope = data.get('scope')
        unit = data.get('unit')
        default_value = data.get('default_value')
        user_id = get_current_admin_user_id()

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attributes WHERE id = %s AND deleted_at IS NULL", (attr_id,))
                old_attr = cursor.fetchone()
                if not old_attr:
                    return jsonify({'error': 'Attribute not found.'}), 404

                existing_vr = {}
                if old_attr.get('validation_rules'):
                    try:
                        existing_vr = json.loads(old_attr['validation_rules']) if isinstance(old_attr['validation_rules'], str) else old_attr['validation_rules']
                    except Exception:
                        existing_vr = {}

                req_vr = data.get('validation_rules') or {}
                if isinstance(req_vr, str):
                    try:
                        req_vr = json.loads(req_vr)
                    except Exception:
                        req_vr = {}
                if isinstance(req_vr, dict):
                    existing_vr.update(req_vr)

                for k in [
                    'input_validation', 'add_to_columns', 'use_in_filter_options',
                    'use_in_promo_rules', 'allow_html_tags', 'used_in_product_listing',
                    'used_for_sort_by', 'use_in_search_results_nav',
                    'facet_coverage_rate', 'facet_max_size', 'facet_sort_order', 'facet_internal_logic',
                    'layered_nav'
                ]:
                    if k in data:
                        existing_vr[k] = data[k]

                name_val = json.dumps(name) if isinstance(name, dict) else (old_attr.get('name') or json.dumps({'default': str(name)}))
                val_rules_val = json.dumps(existing_vr) if existing_vr else None

                is_required = 1 if data.get('is_required') in (1, '1', True) else 0
                is_unique = 1 if data.get('is_unique') in (1, '1', True) else 0
                is_filterable = 1 if data.get('is_filterable') in (1, '1', True, 'filterable_results', 'filterable_no_results') else 0
                is_searchable = 1 if data.get('is_searchable') in (1, '1', True) else 0
                is_comparable = 1 if data.get('is_comparable') in (1, '1', True) else 0
                is_visible_on_front = 1 if data.get('is_visible_on_front') in (1, '1', True) else 0
                sort_order = int(data.get('sort_order') or data.get('position') or old_attr.get('sort_order') or 0)

                cursor.execute("""
                    UPDATE attributes 
                    SET name = %s,
                        type = COALESCE(%s, type),
                        scope = COALESCE(%s, scope),
                        unit = %s,
                        default_value = %s,
                        is_required = %s,
                        is_unique = %s,
                        is_filterable = %s,
                        is_searchable = %s,
                        is_comparable = %s,
                        is_visible_on_front = %s,
                        sort_order = %s,
                        validation_rules = %s,
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    name_val,
                    attr_type,
                    scope,
                    unit,
                    default_value,
                    is_required,
                    is_unique,
                    is_filterable,
                    is_searchable,
                    is_comparable,
                    is_visible_on_front,
                    sort_order,
                    val_rules_val,
                    user_id,
                    attr_id
                ))

                # Update options if provided
                if 'options' in data:
                    cursor.execute("DELETE FROM attribute_options WHERE attribute_id = %s", (attr_id,))
                    options = data.get('options') or []
                    for idx, opt in enumerate(options, start=1):
                        val = opt.get('value') if isinstance(opt, dict) else str(opt)
                        lbl = opt.get('label') if isinstance(opt, dict) else {'default': str(opt)}
                        is_def = 1 if (isinstance(opt, dict) and opt.get('is_default')) else 0
                        swatch_val = opt.get('swatch_value') if isinstance(opt, dict) else None
                        if val:
                            cursor.execute("""
                                INSERT INTO attribute_options (attribute_id, value, label, swatch_value, sort_order, is_default, created_by, updated_by)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (attr_id, val, json.dumps(lbl) if isinstance(lbl, dict) else str(lbl), swatch_val, idx, is_def, user_id, user_id))

                conn.commit()
                log_activity('update', 'attribute', attr_id, old_attr, data, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute #{attr_id} updated successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attributes/<int:attr_id>', methods=['DELETE'])
    def visionadmin_api_delete_attribute(attr_id):
        """Soft-deletes an attribute into trash."""
        user_id = get_current_admin_user_id()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attributes WHERE id = %s AND deleted_at IS NULL", (attr_id,))
                attr = cursor.fetchone()
                if not attr:
                    return jsonify({'error': 'Attribute not found.'}), 404

                # CRITICAL RULE: Required and system attributes CANNOT be deleted by anyone!
                if attr.get('is_required') or attr.get('is_system') or attr.get('code') in ('sku', 'price', 'name', 'product_name', 'status', 'display_name', 'tire_size_label', 'load_index', 'speed_rating'):
                    return jsonify({'error': f"Required attribute '{attr['code']}' cannot be deleted by anyone."}), 403

                cursor.execute("""
                    UPDATE attributes 
                    SET deleted_at = NOW(), deleted_by = %s
                    WHERE id = %s
                """, (user_id, attr_id))
                conn.commit()

                log_activity('delete', 'attribute', attr_id, attr, {'deleted': True}, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute '{attr['code']}' has been moved to trash."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attributes/<int:attr_id>/restore', methods=['POST'])
    def visionadmin_api_restore_attribute(attr_id):
        """Restores a soft-deleted attribute back to the active list."""
        user_id = get_current_admin_user_id()
        success = AttributeService.restore_attribute(attr_id, user_id)
        if not success:
            return jsonify({'error': 'Attribute not found in trash.'}), 404
        log_activity('restore', 'attribute', attr_id, {'deleted': True}, {'deleted': False}, user_id=user_id)
        return jsonify({'success': True, 'message': f"Attribute #{attr_id} restored successfully."})

    @app.route('/visionadmin/api/attributes/<int:attr_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_attribute(attr_id):
        """Permanently deletes an attribute and its options from the database."""
        user_id = get_current_admin_user_id()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attributes WHERE id = %s", (attr_id,))
                attr = cursor.fetchone()
                if not attr:
                    return jsonify({'error': 'Attribute not found.'}), 404

                # CRITICAL RULE: Required and system attributes CANNOT be purged or deleted!
                if attr.get('is_required') or attr.get('is_system') or attr.get('code') in ('sku', 'price', 'name', 'product_name', 'status', 'display_name', 'tire_size_label', 'load_index', 'speed_rating'):
                    return jsonify({'error': f"Required attribute '{attr['code']}' cannot be deleted or purged by anyone."}), 403
        finally:
            conn.close()

        success = AttributeService.purge_attribute(attr_id)
        if not success:
            return jsonify({'error': 'Attribute not found.'}), 404
        log_activity('purge', 'attribute', attr_id, None, {'purged': True}, user_id=user_id)
        return jsonify({'success': True, 'message': f"Attribute #{attr_id} permanently deleted from database."})

    @app.route('/visionadmin/api/attributes/import-csv', methods=['POST'])
    def visionadmin_api_import_attributes_csv():
        """Imports or synchronizes attributes from an ElasticSuite / Magento product attribute CSV file."""
        user_id = get_current_admin_user_id()
        file = request.files.get('file') or request.files.get('csv_file')
        if not file or not file.filename:
            return jsonify({'success': False, 'error': 'No CSV file provided.'}), 400

        try:
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                return jsonify({'success': False, 'error': 'CSV file is empty or invalid format.'}), 400

            type_map = {
                'boolean': {'status', 'runflat', 'ev', 'gift_message_available', 'tabby_payment', 
                            'msrp_display_actual_price_type', 'price_type', 'sku_type', 'weight_type'},
                'decimal': {'price', 'special_price', 'cost', 'msrp', 'tier_price', 'price_per_item', 'weight'},
                'number': {'width', 'height', 'rim', 'cold_test_current_a', 'voltage_v', 'capacity_ah'},
                'date': {'news_from_date', 'news_to_date', 'special_from_date', 'special_to_date', 
                         'custom_design_from', 'custom_design_to', 'created_at', 'updated_at'},
                'textarea': {'description', 'short_description'},
                'file': {'image', 'small_image', 'thumbnail', 'swatch_image', 'gallery', 'media_gallery'},
                'multiselect': {'category_ids', 'oem_tyres'},
                'select': {'brand', 'country', 'country_of_manufacture', 'parts_category', 'pattern', 
                           'oem_marking', 'offers', 'tyre_marking', 'tyre_type', 'tyres_category', 
                           'bike_tyre_type', 'visibility', 'tax_class_id', 'color_finish', 'wheel_type', 
                           'pcd', 'year', 'warranty_period', 'hold_down_type', 'terminal_type', 
                           'post_positions', 'vehicle_compatible', 'page_layout', 'custom_layout', 
                           'custom_design', 'options_container', 'shipment_type', 'price_view', 
                           'quantity_and_stock_status', 'color', 'construction', 'model', 'price_included_text'}
            }
            store_view_codes = {
                'status', 'name', 'display_name', 'color_finish', 'item_code', 'wheel_type', 
                'hub_bore', 'pcd', 'back_space_inches', 'visibility', 'tyre_marking', 'ev', 
                'oem_marking', 'offers', 'promotion', 'description', 'short_description', 
                'url_key', 'meta_title', 'meta_keyword', 'meta_description', 'oem_tyres',
                'image', 'small_image', 'thumbnail', 'swatch_image', 'gallery', 'media_gallery'
            }
            website_codes = {
                'tax_class_id', 'news_from_date', 'news_to_date', 'special_from_date', 
                'special_to_date', 'special_price', 'custom_design_from', 'custom_design_to', 
                'country_of_manufacture'
            }

            def deduce_type(c, default='text'):
                for t, codes in type_map.items():
                    if c in codes:
                        return t
                return default

            def deduce_scope(c, default='global'):
                if c in store_view_codes:
                    return 'store_view'
                if c in website_codes:
                    return 'website'
                return default

            conn = get_connection()
            inserted = 0
            updated = 0
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id, code FROM attributes")
                    existing = {r['code']: r['id'] for r in cursor.fetchall()}

                    for row in reader:
                        code = (row.get('attribute_code') or row.get('code') or '').strip()
                        if not code:
                            continue
                        label = (row.get('attribute_label') or row.get('label') or row.get('name') or code).strip()
                        is_searchable = 1 if str(row.get('is_searchable', '0')).strip() == '1' else 0
                        is_filterable = 1 if str(row.get('is_filterable', '0')).strip() == '1' else 0
                        pos = row.get('position') or row.get('sort_order') or 0
                        try:
                            sort_order = int(pos)
                        except (ValueError, TypeError):
                            sort_order = 0

                        name_json = json.dumps({'en': label, 'ar': label})
                        attr_type = deduce_type(code, row.get('type') or 'text')
                        scope = deduce_scope(code, row.get('scope') or 'global')

                        if code in existing:
                            cursor.execute("""
                                UPDATE attributes 
                                SET name = %s, is_searchable = %s, is_filterable = %s, sort_order = %s, updated_at = NOW(), updated_by = %s
                                WHERE id = %s
                            """, (name_json, is_searchable, is_filterable, sort_order, user_id, existing[code]))
                            updated += 1
                        else:
                            cursor.execute("""
                                INSERT INTO attributes (code, name, type, scope, is_searchable, is_filterable, sort_order, is_system, created_by, updated_by, created_at, updated_at)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s, NOW(), NOW())
                            """, (code, name_json, attr_type, scope, is_searchable, is_filterable, sort_order, user_id, user_id))
                            existing[code] = cursor.lastrowid
                            inserted += 1

                    conn.commit()
            finally:
                conn.close()

            log_activity('import_csv', 'attributes', 0, None, {'inserted': inserted, 'updated': updated}, user_id=user_id)
            return jsonify({
                'success': True,
                'message': f"Successfully processed attributes CSV: {inserted} inserted, {updated} updated.",
                'inserted': inserted,
                'updated': updated,
                'total': inserted + updated
            }), 200
        except Exception as e:
            logger.error(f"Error importing attributes CSV: {e}", exc_info=True)
            return jsonify({'success': False, 'error': f"Failed to import attributes CSV: {str(e)}"}), 500

    @app.route('/visionadmin/api/attribute-sets', methods=['GET'])
    def visionadmin_api_list_attribute_sets():
        sets = AttributeService.get_attribute_sets()
        trash = AttributeService.get_trash_attribute_sets()
        return jsonify({'attribute_sets': sets, 'count': len(sets), 'trash': trash, 'trash_count': len(trash)})

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>', methods=['GET'])
    def visionadmin_api_get_attribute_set_detail(set_id):
        full_set = AttributeService.get_attribute_set_with_groups(set_id)
        if not full_set:
            return jsonify({'error': 'Attribute set not found.'}), 404
        return jsonify({'attribute_set': full_set})

    @app.route('/visionadmin/api/attribute-sets', methods=['POST'])
    def visionadmin_api_create_attribute_set():
        """Creates a new dynamic attribute set, optionally cloned from an existing template set."""
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        slug = (data.get('slug') or '').strip().lower().replace(' ', '_')
        description = data.get('description') or ''
        clone_from_id = data.get('clone_from_id')
        user_id = get_current_admin_user_id()

        if not name:
            return jsonify({'error': 'Attribute set name is required.'}), 400
        if not slug:
            slug = re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_')

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM attribute_sets WHERE (slug = %s OR name = %s) AND deleted_at IS NULL", (slug, name))
                if cursor.fetchone():
                    return jsonify({'error': f"Attribute set with name '{name}' or slug '{slug}' already exists."}), 400

                cursor.execute("""
                    INSERT INTO attribute_sets (name, slug, description, is_system, sort_order, created_by, updated_by)
                    VALUES (%s, %s, %s, 0, 10, %s, %s)
                """, (name, slug, description, user_id, user_id))
                new_set_id = cursor.lastrowid

                # If cloning from an existing set, duplicate all its groups and attribute associations
                if clone_from_id:
                    cursor.execute("""
                        SELECT id, name, code, sort_order 
                        FROM attribute_groups 
                        WHERE attribute_set_id = %s 
                        ORDER BY sort_order ASC, id ASC
                    """, (clone_from_id,))
                    source_groups = cursor.fetchall()
                    for sg in source_groups:
                        g_name = json.dumps(sg['name']) if isinstance(sg['name'], dict) else str(sg['name'])
                        cursor.execute("""
                            INSERT INTO attribute_groups (attribute_set_id, name, code, sort_order, created_by, updated_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (new_set_id, g_name, sg['code'], sg['sort_order'], user_id, user_id))
                        new_grp_id = cursor.lastrowid

                        cursor.execute("""
                            SELECT attribute_id, sort_order 
                            FROM attribute_group_attributes 
                            WHERE attribute_group_id = %s
                            ORDER BY sort_order ASC
                        """, (sg['id'],))
                        source_attrs = cursor.fetchall()
                        for sa in source_attrs:
                            cursor.execute("""
                                INSERT INTO attribute_group_attributes (attribute_group_id, attribute_id, sort_order, created_by, updated_by)
                                VALUES (%s, %s, %s, %s, %s)
                            """, (new_grp_id, sa['attribute_id'], sa['sort_order'], user_id, user_id))
                else:
                    default_grp_name = json.dumps({'en': 'General Attributes', 'ar': 'الخصائص العامة'})
                    cursor.execute("""
                        INSERT INTO attribute_groups (attribute_set_id, name, code, sort_order, created_by, updated_by)
                        VALUES (%s, %s, 'general', 1, %s, %s)
                    """, (new_set_id, default_grp_name, user_id, user_id))

                conn.commit()
                log_activity('create', 'attribute_set', new_set_id, None, {'name': name, 'slug': slug}, user_id=user_id)
                return jsonify({'success': True, 'id': new_set_id, 'message': f"Attribute set '{name}' created successfully."}), 201
        finally:
            conn.close()

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>', methods=['PUT'])
    def visionadmin_api_update_attribute_set(set_id):
        """Updates an attribute set's metadata."""
        data = request.get_json() or {}
        name = data.get('name')
        slug = data.get('slug')
        description = data.get('description')
        user_id = get_current_admin_user_id()

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attribute_sets WHERE id = %s AND deleted_at IS NULL", (set_id,))
                old_set = cursor.fetchone()
                if not old_set:
                    return jsonify({'error': 'Attribute set not found.'}), 404

                cursor.execute("""
                    UPDATE attribute_sets
                    SET name = COALESCE(%s, name),
                        slug = COALESCE(%s, slug),
                        description = COALESCE(%s, description),
                        updated_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (name, slug, description, user_id, set_id))
                conn.commit()

                log_activity('update', 'attribute_set', set_id, old_set, data, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute set '{name or old_set['name']}' updated successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>', methods=['DELETE'])
    def visionadmin_api_delete_attribute_set(set_id):
        """Soft-deletes an attribute set."""
        user_id = get_current_admin_user_id()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM attribute_sets WHERE id = %s AND deleted_at IS NULL", (set_id,))
                attr_set = cursor.fetchone()
                if not attr_set:
                    return jsonify({'error': 'Attribute set not found.'}), 404

                cursor.execute("""
                    UPDATE attribute_sets
                    SET deleted_at = NOW(), deleted_by = %s
                    WHERE id = %s
                """, (user_id, set_id))
                conn.commit()

                log_activity('delete', 'attribute_set', set_id, attr_set, {'deleted': True}, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute set '{attr_set['name']}' moved to trash."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>/restore', methods=['POST'])
    def visionadmin_api_restore_attribute_set(set_id):
        user_id = get_current_admin_user_id()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE attribute_sets SET deleted_at = NULL, deleted_by = NULL, updated_by = %s WHERE id = %s", (user_id, set_id))
                conn.commit()
                if cursor.rowcount == 0:
                    return jsonify({'error': 'Attribute set not found in trash.'}), 404
                log_activity('restore', 'attribute_set', set_id, {'deleted': True}, {'deleted': False}, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute set #{set_id} restored successfully."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_attribute_set(set_id):
        user_id = get_current_admin_user_id()
        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM attribute_group_attributes WHERE attribute_group_id IN (SELECT id FROM attribute_groups WHERE attribute_set_id = %s)", (set_id,))
                cursor.execute("DELETE FROM attribute_groups WHERE attribute_set_id = %s", (set_id,))
                cursor.execute("DELETE FROM attribute_sets WHERE id = %s", (set_id,))
                conn.commit()
                if cursor.rowcount == 0:
                    return jsonify({'error': 'Attribute set not found.'}), 404
                log_activity('purge', 'attribute_set', set_id, None, {'purged': True}, user_id=user_id)
                return jsonify({'success': True, 'message': f"Attribute set #{set_id} permanently deleted."})
        finally:
            conn.close()

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>/groups', methods=['POST'])
    def visionadmin_api_add_group_to_set(set_id):
        """Adds a new schema group to an existing attribute set."""
        data = request.get_json() or {}
        name = data.get('name')
        code = data.get('code')
        user_id = get_current_admin_user_id()

        if not name:
            return jsonify({'error': 'Group name is required.'}), 400

        group_id = AttributeService.add_group_to_set(set_id, name, code=code, user_id=user_id)
        log_activity('create', 'attribute_group', group_id, None, {'set_id': set_id, 'name': name}, user_id=user_id)
        return jsonify({'success': True, 'id': group_id, 'message': 'Group added to set successfully.'}), 201

    @app.route('/visionadmin/api/attribute-groups/<int:group_id>/attributes', methods=['POST'])
    def visionadmin_api_add_attribute_to_group(group_id):
        """Maps an attribute to a schema group."""
        data = request.get_json() or {}
        attribute_id = data.get('attribute_id')
        sort_order = data.get('sort_order', 10)
        user_id = get_current_admin_user_id()

        if not attribute_id:
            return jsonify({'error': 'attribute_id is required.'}), 400

        AttributeService.add_attribute_to_group(group_id, attribute_id, sort_order=sort_order, user_id=user_id)
        log_activity('assign', 'attribute_group', group_id, None, {'attribute_id': attribute_id}, user_id=user_id)
        return jsonify({'success': True, 'message': 'Attribute assigned to group successfully.'}), 200

    @app.route('/visionadmin/api/attribute-groups/<int:group_id>/attributes/<int:attribute_id>', methods=['DELETE'])
    def visionadmin_api_remove_attribute_from_group(group_id, attribute_id):
        """Removes an attribute assignment from a schema group."""
        user_id = get_current_admin_user_id()
        removed = AttributeService.remove_attribute_from_group(group_id, attribute_id)
        if not removed:
            return jsonify({'error': 'Attribute assignment not found.'}), 404
        log_activity('unassign', 'attribute_group', group_id, {'attribute_id': attribute_id}, None, user_id=user_id)
        return jsonify({'success': True, 'message': 'Attribute removed from group successfully.'}), 200

    @app.route('/visionadmin/api/attribute-groups/<int:group_id>', methods=['DELETE'])
    def visionadmin_api_delete_attribute_group(group_id):
        """Deletes an attribute group and its mappings."""
        user_id = get_current_admin_user_id()
        AttributeService.remove_group_from_set(group_id)
        log_activity('delete', 'attribute_group', group_id, None, {'deleted': True}, user_id=user_id)
        return jsonify({'success': True, 'message': 'Group deleted successfully.'}), 200

    @app.route('/visionadmin/api/attribute-groups/<int:group_id>', methods=['PUT'])
    def visionadmin_api_rename_attribute_group(group_id):
        """Renames an attribute group."""
        data = request.get_json() or {}
        name = data.get('name')
        if not name:
            return jsonify({'error': 'Group name is required.'}), 400
        user_id = get_current_admin_user_id()
        AttributeService.rename_group(group_id, name, user_id=user_id)
        return jsonify({'success': True, 'message': 'Group renamed successfully.'}), 200

    @app.route('/visionadmin/api/attribute-sets/<int:set_id>/save-schema', methods=['POST', 'PUT'])
    def visionadmin_api_save_attribute_set_full_schema(set_id):
        """Saves attribute set name, groups, and assigned attributes hierarchy atomically."""
        try:
            data = request.get_json(force=True) or {}
            set_name = data.get('name')
            groups = data.get('groups') or []
            user_id = get_current_admin_user_id()
            AttributeService.save_full_set_schema(set_id, set_name, groups, user_id=user_id)
            return jsonify({'success': True, 'message': 'Attribute set schema saved successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/catalog/form-schema/<int:set_id>', methods=['GET'])
    def visionadmin_api_get_product_form_schema(set_id):
        """Returns reactive Alpine.js form schema with scoped values & fallback flags."""
        product_id = request.args.get('product_id')
        website_id = request.args.get('website_id') or session.get('admin_active_website_id')
        store_id = request.args.get('store_id') or session.get('admin_active_store_id')

        prod_id = int(product_id) if product_id and str(product_id).isdigit() else None
        web_id = int(website_id) if website_id and str(website_id).isdigit() else None
        st_id = int(store_id) if store_id and str(store_id).isdigit() else None

        schema = AttributeService.get_dynamic_form_schema(set_id, prod_id, web_id, st_id)
        return jsonify({'schema': schema})

    # =========================================================================
    # 9. AUDIT ACTIVITY LOGS API
    # =========================================================================

    @app.route('/visionadmin/api/audit-logs', methods=['GET'])
    def visionadmin_api_list_audit_logs():
        """Returns real-time activity log stream for staff audit grid."""
        entity_type = request.args.get('entity_type')
        entity_id = request.args.get('entity_id')
        user_id = request.args.get('user_id')
        action = request.args.get('action')
        website_id = request.args.get('website_id')
        store_id = request.args.get('store_id')

        try:
            limit = min(100, max(1, int(request.args.get('limit', 50))))
            page = max(1, int(request.args.get('page', 1)))
            offset = (page - 1) * limit
        except (ValueError, TypeError):
            limit = 50
            offset = 0

        logs = get_activity_logs(
            entity_type=entity_type,
            entity_id=int(entity_id) if entity_id and str(entity_id).isdigit() else None,
            user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
            action=action,
            website_id=int(website_id) if website_id and str(website_id).isdigit() else None,
            store_id=int(store_id) if store_id and str(store_id).isdigit() else None,
            limit=limit,
            offset=offset
        )
        return jsonify({'success': True, 'logs': logs, 'count': len(logs), 'page': page, 'limit': limit})

    # =========================================================================
    # 10. CATALOG & PRODUCT JSON API (/visionadmin/api/products & brands/categories)
    # =========================================================================

    @app.route('/visionadmin/api/brands', methods=['GET'])
    def visionadmin_api_list_brands():
        """Fetch all active tyre brands for dropdown selection."""
        brands = Brand.all_active()
        return jsonify({'success': True, 'brands': brands})

    @app.route('/visionadmin/api/brands/paginate', methods=['GET'])
    def visionadmin_api_paginate_brands():
        """Paginated, searchable brands with product counts."""
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = max(1, min(100, int(request.args.get('per_page', 15))))
            query = request.args.get('q', '').strip() or None
            status = request.args.get('status', '').strip() or None

            res = Brand.search_and_paginate(query=query, status=status, page=page, per_page=per_page)
            return jsonify({'success': True, **res})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/brands/<int:brand_id>', methods=['GET'])
    def visionadmin_api_get_brand(brand_id):
        """Fetch single brand detail."""
        brand = Brand.find_by_id(brand_id)
        if not brand:
            return jsonify({'success': False, 'error': 'Brand not found'}), 404
        return jsonify({'success': True, 'brand': brand})

    @app.route('/visionadmin/api/brands', methods=['POST'])
    def visionadmin_api_create_brand():
        """Create new brand."""
        try:
            data = request.get_json(force=True) or {}
            if not (data.get('name') or '').strip():
                return jsonify({'success': False, 'error': 'Brand name is required'}), 400

            user_id = session.get('user_id')
            brand_id = Brand.create(data, user_id=user_id)
            return jsonify({'success': True, 'brand_id': brand_id, 'message': 'Brand created successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/brands/<int:brand_id>', methods=['PUT'])
    def visionadmin_api_update_brand(brand_id):
        """Update existing brand."""
        try:
            data = request.get_json(force=True) or {}
            if not (data.get('name') or '').strip():
                return jsonify({'success': False, 'error': 'Brand name is required'}), 400

            user_id = session.get('user_id')
            success = Brand.update(brand_id, data, user_id=user_id)
            if not success:
                return jsonify({'success': False, 'error': 'Brand not found or not modified'}), 404
            return jsonify({'success': True, 'message': 'Brand updated successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/brands/<int:brand_id>', methods=['DELETE'])
    def visionadmin_api_delete_brand(brand_id):
        """Soft delete brand."""
        try:
            user_id = session.get('user_id')
            success = Brand.delete(brand_id, user_id=user_id)
            if not success:
                return jsonify({'success': False, 'error': 'Brand not found'}), 404
            return jsonify({'success': True, 'message': 'Brand deleted successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/upload-brand-logo', methods=['POST'])
    def visionadmin_api_upload_brand_logo():
        """Upload brand logo image."""
        if 'logo' not in request.files and 'file' not in request.files and 'image' not in request.files:
            return jsonify({'error': 'No file part in request.'}), 400
        file = request.files.get('logo') or request.files.get('file') or request.files.get('image')
        if not file or file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400

        allowed = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed:
            return jsonify({'error': f'Invalid image type. Allowed: {", ".join(allowed)}'}), 400

        upload_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'brands')
        os.makedirs(upload_dir, exist_ok=True)
        unique_name = f"brand_{secrets.token_hex(8)}_{int(time.time())}{ext}"
        target_path = os.path.join(upload_dir, unique_name)
        file.save(target_path)

        url = f"/static/uploads/brands/{unique_name}"
        return jsonify({'success': True, 'url': url})

    @app.route('/visionadmin/api/brands/sample-csv', methods=['GET'])
    def visionadmin_api_sample_brands_csv():
        """Return downloadable sample CSV template for brands."""
        import io
        csv_text = "name,country,slug,logo,sort_order,status,is_featured,description_en,meta_title_en,meta_desc_en\n" \
                   "Michelin,France,michelin,,1,active,1,\"Premium French tyre manufacturer known for longevity and performance.\",Buy Michelin Tyres UAE,Best deals on Michelin tyres in UAE\n" \
                   "Bridgestone,Japan,bridgestone,,2,active,1,\"Japanese global tyre leader specializing in high-grip compounds.\",Buy Bridgestone Tyres UAE,Genuine Bridgestone tyres in Dubai\n"
        output = io.BytesIO(csv_text.encode('utf-8'))
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='brands_sample.csv')

    @app.route('/visionadmin/api/brands/import-csv', methods=['POST'])
    def visionadmin_api_import_brands_csv():
        """Import multiple tyre brands from CSV file."""
        import csv
        import io
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            file = request.files['file']
            if not file or not file.filename:
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            stream = io.StringIO(file.stream.read().decode('utf-8', errors='ignore'))
            reader = csv.DictReader(stream)

            user_id = session.get('user_id')
            imported = 0

            for row in reader:
                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                name = clean_row.get('name') or clean_row.get('brand') or clean_row.get('brand_name') or ''
                if not name:
                    continue

                slug = clean_row.get('slug') or Brand.slugify(name)
                country = clean_row.get('country') or None
                logo = clean_row.get('logo') or None
                sort_order = int(clean_row.get('sort_order') or imported + 1)
                status = clean_row.get('status') or 'active'
                is_featured = 1 if clean_row.get('is_featured') in ['1', 'true', 'yes', 1] else 0
                desc = clean_row.get('description_en') or clean_row.get('description') or None
                meta_title = clean_row.get('meta_title_en') or clean_row.get('meta_title') or None
                meta_desc = clean_row.get('meta_desc_en') or clean_row.get('meta_desc') or None

                existing = Brand.find_by_slug(slug)
                if existing:
                    Brand.update(existing['id'], {
                        'name': name,
                        'slug': slug,
                        'country': country or existing.get('country'),
                        'logo': logo or existing.get('logo'),
                        'sort_order': sort_order,
                        'status': status,
                        'is_featured': is_featured,
                        'description_en': desc or existing.get('description_en'),
                        'meta_title_en': meta_title or existing.get('meta_title_en'),
                        'meta_desc_en': meta_desc or existing.get('meta_desc_en')
                    }, user_id=user_id)
                else:
                    Brand.create({
                        'name': name,
                        'slug': slug,
                        'country': country,
                        'logo': logo,
                        'sort_order': sort_order,
                        'status': status,
                        'is_featured': is_featured,
                        'description_en': desc,
                        'meta_title_en': meta_title,
                        'meta_desc_en': meta_desc
                    }, user_id=user_id)
                imported += 1

            return jsonify({
                'success': True,
                'imported': imported,
                'message': f'Successfully imported {imported} brands from CSV!'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to process CSV: {str(e)}'}), 500

    @app.route('/visionadmin/api/catalog/categories', methods=['GET'])
    def visionadmin_api_list_categories():
        """Fetch all active categories for dropdown selection."""
        categories = Category.all_active()
        return jsonify({'success': True, 'categories': categories})

    @app.route('/visionadmin/api/categories/paginate', methods=['GET'])
    def visionadmin_api_paginate_categories():
        """Paginated, searchable categories with product counts and parent names."""
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = max(1, min(100, int(request.args.get('per_page', 15))))
            query = request.args.get('q', '').strip() or None
            status = request.args.get('status', '').strip() or None
            parent_id = int(request.args.get('parent_id')) if request.args.get('parent_id') else None

            trash = request.args.get('trash') in ('1', 'true') or request.args.get('status') == 'trash'
            res = Category.search_and_paginate(query=query, status=status, parent_id=parent_id, page=page, per_page=per_page, trash=trash)
            return jsonify({'success': True, **res})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/tree', methods=['GET'])
    @app.route('/visionadmin/api/catalog/categories/tree', methods=['GET'])
    def visionadmin_api_categories_tree():
        """Returns the category tree hierarchy with product counts."""
        try:
            tree_data = Category.get_category_tree()
            return jsonify({'success': True, **tree_data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>', methods=['GET'])
    @app.route('/visionadmin/api/catalog/categories/<int:cat_id>', methods=['GET'])
    def visionadmin_api_get_category(cat_id):
        """Fetch single category detail."""
        category = Category.find_by_id(cat_id)
        if not category:
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        return jsonify({'success': True, 'category': category})

    @app.route('/visionadmin/api/categories/<int:cat_id>/products', methods=['GET'])
    @app.route('/visionadmin/api/catalog/categories/<int:cat_id>/products', methods=['GET'])
    def visionadmin_api_get_category_products(cat_id):
        """Fetch products for category with assignment status and position."""
        try:
            search = request.args.get('search') or request.args.get('q') or None
            assigned = request.args.get('assigned', 'all')
            stock_status = request.args.get('stock_status') or None
            page = max(1, int(request.args.get('page', 1)))
            per_page = max(1, min(200, int(request.args.get('per_page', 20))))
            res = Category.get_category_products(
                cat_id=cat_id,
                search=search,
                assigned=assigned,
                page=page,
                per_page=per_page,
                stock_status=stock_status
            )
            return jsonify({'success': True, **res})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>/products', methods=['POST'])
    @app.route('/visionadmin/api/catalog/categories/<int:cat_id>/products', methods=['POST'])
    def visionadmin_api_save_category_products(cat_id):
        """Save product category assignments and positions."""
        try:
            data = request.get_json(force=True) or {}
            assignments = data.get('assignments') or []
            if not assignments and 'assigned_ids' in data:
                assigned_ids = set(data.get('assigned_ids', []))
                positions = data.get('positions', {})
                all_ids = set(assigned_ids) | set(int(k) for k in positions.keys())
                assignments = []
                for pid in all_ids:
                    assignments.append({
                        'product_id': pid,
                        'assigned': pid in assigned_ids,
                        'position': int(positions.get(str(pid), positions.get(pid, 0)))
                    })

            success = Category.save_category_products(cat_id, assignments)
            return jsonify({'success': bool(success), 'message': 'Category products updated successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories', methods=['POST'])
    def visionadmin_api_create_category():
        """Create new category."""
        try:
            data = request.get_json(force=True) or {}
            name_input = data.get('name') or data.get('name_en')
            has_name = bool(localize_value(name_input)) if isinstance(name_input, dict) else bool(str(name_input or '').strip())
            if not has_name:
                return jsonify({'success': False, 'error': 'Category name is required'}), 400

            user_id = session.get('user_id')
            cat_id = Category.create(data, user_id=user_id)
            return jsonify({'success': True, 'category_id': cat_id, 'message': 'Category created successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>', methods=['PUT'])
    @app.route('/visionadmin/api/catalog/categories/<int:cat_id>', methods=['PUT'])
    def visionadmin_api_update_category(cat_id):
        """Update existing category."""
        try:
            data = request.get_json(force=True) or {}
            name_input = data.get('name') or data.get('name_en')
            has_name = bool(localize_value(name_input)) if isinstance(name_input, dict) else bool(str(name_input or '').strip())
            if not has_name:
                return jsonify({'success': False, 'error': 'Category name is required'}), 400

            user_id = session.get('user_id')
            success = Category.update(cat_id, data, user_id=user_id)
            if not success:
                return jsonify({'success': False, 'error': 'Category not found or not modified'}), 404
            return jsonify({'success': True, 'message': 'Category updated successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>', methods=['DELETE'])
    @app.route('/visionadmin/api/catalog/categories/<int:cat_id>', methods=['DELETE'])
    def visionadmin_api_delete_category(cat_id):
        """Soft delete or permanently purge category."""
        try:
            permanent = request.args.get('permanent') in ('1', 'true') or request.args.get('hard') in ('1', 'true')
            user_id = session.get('user_id')
            if permanent:
                success = Category.purge(cat_id)
                msg = 'Category permanently deleted!'
            else:
                success = Category.delete(cat_id, user_id=user_id)
                msg = 'Category moved to trash successfully!'
            if not success:
                return jsonify({'success': False, 'error': 'Category not found'}), 404
            return jsonify({'success': True, 'message': msg})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>/restore', methods=['POST'])
    def visionadmin_api_restore_category(cat_id):
        """Restore soft-deleted category."""
        try:
            user_id = session.get('user_id')
            success = Category.restore(cat_id, user_id=user_id)
            if not success:
                return jsonify({'success': False, 'error': 'Category not found or already active'}), 404
            return jsonify({'success': True, 'message': 'Category restored successfully!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/categories/<int:cat_id>/purge', methods=['DELETE'])
    def visionadmin_api_purge_category(cat_id):
        """Permanently delete category."""
        try:
            success = Category.purge(cat_id)
            if not success:
                return jsonify({'success': False, 'error': 'Category not found'}), 404
            return jsonify({'success': True, 'message': 'Category permanently deleted!'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/upload-category-image', methods=['POST'])
    def visionadmin_api_upload_category_image():
        """Upload category image."""
        if 'image' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No file part in request.'}), 400
        file = request.files.get('image') or request.files.get('file')
        if not file or file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400

        allowed = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed:
            return jsonify({'error': f'Invalid image type. Allowed: {", ".join(allowed)}'}), 400

        upload_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'categories')
        os.makedirs(upload_dir, exist_ok=True)
        unique_name = f"cat_{secrets.token_hex(8)}_{int(time.time())}{ext}"
        target_path = os.path.join(upload_dir, unique_name)
        file.save(target_path)

        url = f"/static/uploads/categories/{unique_name}"
        return jsonify({'success': True, 'url': url})

    @app.route('/visionadmin/api/categories/sample-csv', methods=['GET'])
    def visionadmin_api_sample_categories_csv():
        """Return downloadable sample CSV template for categories."""
        import io
        csv_text = "sku,name,categories,price,stock_qty\n" \
                   "TYRE-BR-1856515,Bridgestone Ecopia 185/65 R15,\"Default Category/Tyres,Default Category/Tyres/Brand/Bridgestone,Default Category/Tyres/Tyre Size/185\\/65 R15,Default Category/Tyres/Cars\",320.00,24\n" \
                   "TYRE-MI-2056515,Michelin Pilot 205/65 R15,\"Default Category/Tyres,Default Category/Tyres/Brand/Michelin,Default Category/Tyres/Tyre Size/205\\/65 R15,Default Category/Tyres/Cars\",450.00,16\n" \
                   "TYRE-GY-2156016,Goodyear Eagle 215/60 R16,\"Default Category/Tyres,Default Category/Tyres/Brand/Goodyear,Default Category/Tyres/Tyre Size/215\\/60 R16\",380.00,12\n"
        output = io.BytesIO(csv_text.encode('utf-8'))
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='categories_sample.csv')

    @app.route('/visionadmin/api/categories/import-csv', methods=['POST'])
    def visionadmin_api_import_categories_csv():
        """Import hierarchical categories from CSV file supporting Magento category paths."""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            file = request.files['file']
            if not file or not file.filename:
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            from services.category_importer import CategoryImporter
            user_id = session.get('user_id') or session.get('admin_user_id')
            result = CategoryImporter.import_csv(file.stream, user_id=user_id)
            status_code = 200 if result.get('success') else 400
            return jsonify(result), status_code
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to process CSV: {str(e)}'}), 500

    @app.route('/visionadmin/api/upload-product-image', methods=['POST'])
    def visionadmin_api_upload_product_image():
        """Upload product hero or gallery image."""
        if 'image' not in request.files and 'file' not in request.files:
            return jsonify({'error': 'No file part in request.'}), 400
        file = request.files.get('image') or request.files.get('file')
        if not file or file.filename == '':
            return jsonify({'error': 'No selected file.'}), 400

        allowed = {'.png', '.jpg', '.jpeg', '.webp', '.svg'}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed:
            return jsonify({'error': f'Invalid image type. Allowed: {", ".join(allowed)}'}), 400

        upload_dir = os.path.join(BASE_DIR, 'static', 'uploads', 'products')
        os.makedirs(upload_dir, exist_ok=True)
        unique_name = f"prod_{secrets.token_hex(8)}_{int(time.time())}{ext}"
        target_path = os.path.join(upload_dir, unique_name)
        file.save(target_path)

        url = f"/static/uploads/products/{unique_name}"
        return jsonify({'success': True, 'url': url})

    @app.route('/visionadmin/api/products/sample-csv', methods=['GET'])
    def visionadmin_api_sample_products_csv():
        """Return downloadable sample CSV template for products."""
        import io
        csv_text = "sku,name,brand,category,price,sale_price,stock_qty,tire_size_label,tire_speed_rating,tire_load_index,tire_pattern,vehicle_type,country_of_origin\n" \
                   "MICH-PS4-225-45R17,Pilot Sport 4 225/45 R17,Michelin,Passenger Car Tyres,520,480,24,225/45R17,Y,94,Pilot Sport 4,car,France\n" \
                   "BS-TUR-205-55R16,Turanza T005 205/55 R16,Bridgestone,Passenger Car Tyres,380,350,18,205/55R16,V,91,Turanza T005,car,Japan\n"
        output = io.BytesIO(csv_text.encode('utf-8'))
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='products_sample.csv')

    @app.route('/visionadmin/api/products/import-csv', methods=['POST'])
    def visionadmin_api_import_products_csv():
        """Import multiple products and hierarchical categories from CSV file."""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400
            file = request.files['file']
            if not file or not file.filename:
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            from services.product_importer import ProductImporter
            user_id = session.get('admin_user_id') or session.get('user_id') or 1
            res = ProductImporter.import_csv(file.stream.read(), user_id=user_id)

            if not res.get('success'):
                return jsonify({'success': False, 'error': res.get('error', 'Import failed')}), 400

            return jsonify({
                'success': True,
                'imported': res.get('imported', 0),
                'updated': res.get('updated', 0),
                'total_rows': res.get('total_rows', 0),
                'matched_attributes': res.get('matched_attributes', []),
                'extra_attributes': res.get('extra_attributes', []),
                'missing_attributes': res.get('missing_attributes', []),
                'warning': res.get('warning'),
                'errors': res.get('errors', []),
                'message': res.get('message') or f"Successfully processed {res.get('total_rows', 0)} products ({res.get('imported', 0)} imported, {res.get('updated', 0)} updated)!"
            })
        except Exception as e:
            app.logger.exception(f"Error importing CSV: {e}")
            return jsonify({'success': False, 'error': f'Failed to process CSV: {str(e)}'}), 500

    @app.route('/visionadmin/api/products', methods=['GET'])
    @app.route('/visionadmin/api/v1/products', methods=['GET'])
    def visionadmin_api_list_products():
        """Fetch paginated products with full filtering, sorting, and stats."""
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(100, max(5, int(request.args.get('per_page', 25))))
        except (ValueError, TypeError):
            page = 1
            per_page = 25

        search = request.args.get('search')
        brand_id = request.args.get('brand_id')
        category_id = request.args.get('category_id')
        status = request.args.get('status')
        stock_status = request.args.get('stock_status')
        vehicle_type = request.args.get('vehicle_type')
        attribute_set_id = request.args.get('attribute_set_id')
        is_trash = request.args.get('trash') in ('1', 'true', 'yes')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_dir = request.args.get('sort_dir', 'DESC')

        # Extended attribute filters
        tyres_category = request.args.get('tyres_category')
        parts_category = request.args.get('parts_category')
        run_flat = request.args.get('run_flat')
        ev_rated = request.args.get('ev_rated')
        rim_size = request.args.get('rim_size')
        speed_rating = request.args.get('speed_rating')
        country_of_origin = request.args.get('country_of_origin')
        year = request.args.get('year')
        oem_tyres = request.args.get('oem_tyres')
        attr_code = request.args.get('attr_code')
        attr_value = request.args.get('attr_value')

        bid = int(brand_id) if brand_id and str(brand_id).isdigit() else None
        cid = int(category_id) if category_id and str(category_id).isdigit() else None
        asid = int(attribute_set_id) if attribute_set_id and str(attribute_set_id).isdigit() else None

        result = Product.paginate(
            page=page,
            per_page=per_page,
            search=search,
            brand_id=bid,
            category_id=cid,
            status=status if status else None,
            stock_status=stock_status if stock_status else None,
            vehicle_type=vehicle_type if vehicle_type else None,
            attribute_set_id=asid,
            is_trash=is_trash,
            sort_by=sort_by,
            sort_dir=sort_dir,
            tyres_category=tyres_category if tyres_category else None,
            parts_category=parts_category if parts_category else None,
            run_flat=run_flat if run_flat not in (None, '') else None,
            ev_rated=ev_rated if ev_rated not in (None, '') else None,
            rim_size=rim_size if rim_size else None,
            speed_rating=speed_rating if speed_rating else None,
            country_of_origin=country_of_origin if country_of_origin else None,
            year=year if year else None,
            oem_tyres=oem_tyres if oem_tyres else None,
            attr_code=attr_code if attr_code else None,
            attr_value=attr_value if attr_value not in (None, '') else None
        )
        counts = Product.get_counts()
        result['counts'] = counts
        return jsonify(result)

    @app.route('/visionadmin/api/products/<int:prod_id>', methods=['GET'])
    @app.route('/visionadmin/api/v1/products/<int:prod_id>', methods=['GET'])
    def visionadmin_api_get_product(prod_id):
        product = Product.find_by_id(prod_id, include_trash=True)
        if not product:
            return jsonify({'error': 'Product not found.'}), 404
        set_id = product.get('attribute_set_id') or 1
        schema = AttributeService.get_dynamic_form_schema(set_id, product_id=prod_id)
        return jsonify({'success': True, 'product': product, 'schema': schema})

    @app.route('/visionadmin/api/products', methods=['POST'])
    @app.route('/visionadmin/api/v1/products', methods=['POST'])
    def visionadmin_api_create_product():
        data = request.get_json(silent=True) or request.form.to_dict()
        if not data:
            return jsonify({'error': 'Invalid request body.'}), 400

        sku = (data.get('sku') or '').strip().upper()
        if not sku:
            return jsonify({'error': 'Product SKU is required.'}), 400

        if Product.find_by_sku(sku):
            return jsonify({'error': f'Product with SKU \"{sku}\" already exists.'}), 409

        name = data.get('display_name') or data.get('name_en') or data.get('name')
        if not name:
            return jsonify({'error': 'Product name is required.'}), 400

        try:
            price = float(data.get('price') or 0)
            if price < 0:
                return jsonify({'error': 'Price must be positive.'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid price value.'}), 400

        user_id = session.get('admin_user_id') or session.get('user_id')
        try:
            new_id = Product.create(data, user_id=user_id)
        except Exception as e:
            app.logger.exception(f"Error creating product: {e}")
            return jsonify({'error': f'Failed to create product: {str(e)}'}), 500

        log_activity(
            entity_type='product',
            entity_id=new_id,
            action='create',
            new_values={'sku': sku, 'name': name},
            user_id=user_id
        )

        return jsonify({'success': True, 'id': new_id, 'product_id': new_id, 'message': 'Product created successfully.'}), 201

    @app.route('/visionadmin/api/products/<int:prod_id>', methods=['PUT', 'POST'])
    @app.route('/visionadmin/api/v1/products/<int:prod_id>', methods=['PUT', 'POST'])
    def visionadmin_api_update_product(prod_id):
        existing = Product.find_by_id(prod_id, include_trash=True)
        if not existing:
            return jsonify({'error': 'Product not found.'}), 404

        data = request.get_json(silent=True) or request.form.to_dict()
        if not data:
            return jsonify({'error': 'Invalid request body.'}), 400

        if 'sku' in data and data['sku']:
            new_sku = data['sku'].strip().upper()
            duplicate = Product.find_by_sku(new_sku, exclude_id=prod_id)
            if duplicate:
                return jsonify({'error': f'Product with SKU \"{new_sku}\" already exists.'}), 409

        user_id = session.get('admin_user_id') or session.get('user_id')
        try:
            Product.update(prod_id, data, user_id=user_id)
        except Exception as e:
            app.logger.exception(f"Error updating product {prod_id}: {e}")
            return jsonify({'error': f'Failed to update product: {str(e)}'}), 500

        log_activity(
            entity_type='product',
            entity_id=prod_id,
            action='update',
            old_values={'sku': existing.get('sku'), 'name': existing.get('display_name')},
            new_values=data,
            user_id=user_id
        )

        return jsonify({'success': True, 'message': 'Product updated successfully.'})

    @app.route('/visionadmin/api/products/<int:prod_id>', methods=['DELETE'])
    @app.route('/visionadmin/api/v1/products/<int:prod_id>', methods=['DELETE'])
    def visionadmin_api_delete_product(prod_id):
        existing = Product.find_by_id(prod_id)
        if not existing:
            return jsonify({'error': 'Product not found or already in trash.'}), 404

        user_id = session.get('admin_user_id') or session.get('user_id')
        Product.soft_delete(prod_id, user_id=user_id)

        log_activity(
            entity_type='product',
            entity_id=prod_id,
            action='delete',
            old_values={'sku': existing.get('sku')},
            user_id=user_id
        )

        return jsonify({'success': True, 'message': 'Product moved to trash successfully.'})

    @app.route('/visionadmin/api/products/<int:prod_id>/restore', methods=['POST'])
    @app.route('/visionadmin/api/v1/products/<int:prod_id>/restore', methods=['POST'])
    def visionadmin_api_restore_product(prod_id):
        user_id = session.get('admin_user_id') or session.get('user_id')
        success = Product.restore(prod_id, user_id=user_id)
        if not success:
            return jsonify({'error': 'Product not found in trash.'}), 404

        log_activity(
            entity_type='product',
            entity_id=prod_id,
            action='restore',
            user_id=user_id
        )

        return jsonify({'success': True, 'message': 'Product restored successfully.'})

    @app.route('/visionadmin/api/products/<int:prod_id>/purge', methods=['DELETE', 'POST'])
    @app.route('/visionadmin/api/v1/products/<int:prod_id>/purge', methods=['DELETE', 'POST'])
    def visionadmin_api_purge_product(prod_id):
        success = Product.purge(prod_id)
        if not success:
            return jsonify({'error': 'Product not found.'}), 404

        user_id = session.get('admin_user_id') or session.get('user_id')
        log_activity(
            entity_type='product',
            entity_id=prod_id,
            action='permanent_delete',
            user_id=user_id
        )

        return jsonify({'success': True, 'message': 'Product permanently deleted.'})

    @app.route('/visionadmin/api/products/bulk', methods=['POST'])
    @app.route('/visionadmin/api/v1/products/bulk', methods=['POST'])
    def visionadmin_api_bulk_products():
        data = request.get_json(silent=True) or {}
        action = data.get('action')
        ids = data.get('ids') or []
        if not action or not ids:
            return jsonify({'error': 'Action and ids list are required.'}), 400

        user_id = session.get('admin_user_id') or session.get('user_id')
        affected = Product.bulk_action(action, ids, user_id=user_id)

        log_activity(
            entity_type='product',
            entity_id=None,
            action=f'bulk_{action}',
            new_values={'ids': ids, 'affected': affected},
            user_id=user_id
        )

        return jsonify({'success': True, 'affected': affected, 'message': f'Bulk {action} applied to {affected} products.'})

    # =========================================================================
    # ELASTICSEARCH ACTIVE PRODUCTS API
    # =========================================================================
    @app.route('/visionadmin/api/elasticsearch/status', methods=['GET'])
    @app.route('/visionadmin/api/v1/elasticsearch/status', methods=['GET'])
    def visionadmin_api_elasticsearch_status():
        try:
            from services.es_service import es_service
            status = es_service.check_connection()
            return jsonify({'success': True, 'data': status})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/visionadmin/api/elasticsearch/reindex', methods=['POST'])
    @app.route('/visionadmin/api/v1/elasticsearch/reindex', methods=['POST'])
    def visionadmin_api_elasticsearch_reindex():
        try:
            from services.es_service import es_service
            data = request.get_json(silent=True) or {}
            recreate = bool(data.get('recreate', False))
            batch_size = int(data.get('batch_size', 500))

            res = es_service.index_all_active_products(batch_size=batch_size, recreate=recreate)
            status_code = 200 if res.get('success') else 500
            return jsonify(res), status_code
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


def register_client_api_routes(app):
    """Registers all public, un-prefixed /api/* endpoints for the client storefront."""

    # =========================================================================
    # 1. BLOG JSON API (GET BLOG FROM DATABASE)
    # =========================================================================

    @app.route('/api/blogs', methods=['GET'])
    @app.route('/api/v1/blogs', methods=['GET'])
    @app.route('/api/blog', methods=['GET'])
    @app.route('/api/v1/blog', methods=['GET'])
    def api_get_blogs():
        """
        Public JSON API: Fetch published blogs with pagination, locale,
        search, and category filtering.
        """
        locale = request.args.get('locale') or request.args.get('lang') or get_locale()
        query = (request.args.get('q') or '').strip().lower()
        cat_filter = (request.args.get('category') or '').strip().lower()

        try:
            page_num = max(1, int(request.args.get('page', 1)))
        except (ValueError, TypeError):
            page_num = 1

        try:
            per_page = int(request.args.get('per_page', request.args.get('limit', 12)))
            if per_page not in (4, 6, 8, 12, 16, 24):
                per_page = 12
        except (ValueError, TypeError):
            per_page = 12

        db_blogs = Blog.published()
        formatted_blogs = []

        if db_blogs:
            for b in db_blogs:
                title = b.get_title(locale)
                short_desc = b.get_short_desc(locale)
                content = b.get_content(locale)

                cat_name = b.get_category_name(locale) or translate('Blog', locale)

                prefix = f'/{locale}' if locale and locale != 'en' else ''
                blog_url = f'{prefix}/blog/{b.slug}'

                formatted_blogs.append({
                    'id': b.id,
                    'slug': b.slug,
                    'title': title,
                    'short_description': short_desc or '',
                    'excerpt': short_desc or '',
                    'content': content or '',
                    'image': b.image or '/static/assets/images/online-tyres-shop-dubai.png',
                    'cover_image_url': b.image or '/static/assets/images/online-tyres-shop-dubai.png',
                    'published_at': b.published_at.strftime('%d-%m-%Y') if b.published_at else (b.created_at.strftime('%d-%m-%Y') if b.created_at else '2026'),
                    'published_at_raw': b.published_at.isoformat() if b.published_at else (b.created_at.isoformat() if b.created_at else None),
                    'category': cat_name,
                    'thumb_class': 't-buying' if 'choose' in (b.slug or '') else 't-maint',
                    'read_time': translate('4 min read', locale),
                    'url': blog_url
                })

        # Filter by search keyword
        if query:
            formatted_blogs = [
                b for b in formatted_blogs
                if query in b['title'].lower() or query in b['short_description'].lower()
            ]

        # Filter by category
        if cat_filter:
            formatted_blogs = [
                b for b in formatted_blogs
                if cat_filter == (b.get('category') or '').strip().lower()
                or cat_filter in (b.get('category') or '').strip().lower()
                or cat_filter == Blog.slugify(b.get('category') or '')
            ]

        total_count = len(formatted_blogs)
        num_pages = max(1, math.ceil(total_count / per_page))
        if page_num > num_pages:
            page_num = num_pages

        start_idx = (page_num - 1) * per_page
        end_idx = min(start_idx + per_page, total_count)
        page_blogs = formatted_blogs[start_idx:end_idx]

        pagination = {
            'page': page_num,
            'per_page': per_page,
            'total': total_count,
            'num_pages': num_pages,
            'start': start_idx + 1 if total_count > 0 else 0,
            'end': end_idx,
            'has_prev': page_num > 1,
            'has_next': page_num < num_pages,
            'prev_num': page_num - 1,
            'next_num': page_num + 1
        }

        return jsonify({
            'success': True,
            'locale': locale,
            'blogs': page_blogs,
            'count': len(page_blogs),
            'pagination': pagination
        })

    @app.route('/api/blogs/<slug>', methods=['GET'])
    @app.route('/api/v1/blogs/<slug>', methods=['GET'])
    @app.route('/api/blog/<slug>', methods=['GET'])
    @app.route('/api/v1/blog/<slug>', methods=['GET'])
    def api_get_blog_detail(slug):
        """
        Public JSON API: Fetch a single blog article by slug.
        """
        locale = request.args.get('locale') or request.args.get('lang') or get_locale()
        blog = Blog.find_by_slug(slug)

        if not blog:
            return jsonify({'success': False, 'error': 'Blog not found'}), 404

        data = {
            'id': blog.id,
            'slug': blog.slug,
            'title': blog.get_title(locale),
            'short_description': blog.get_short_desc(locale),
            'content': blog.get_content(locale),
            'image': blog.image or '/static/assets/images/online-tyres-shop-dubai.png',
            'cover_image_url': blog.image or '/static/assets/images/online-tyres-shop-dubai.png',
            'published_at': blog.published_at.strftime('%d-%m-%Y') if blog.published_at else '24-08-2026',
            'meta_title': blog.get_meta_title(locale),
            'meta_desc': blog.get_meta_desc(locale),
            'author': {
                'name': translate('Sharvil Kumar', locale),
                'role': translate('Tyre Selection Specialist, TyresVision', locale),
                'avatar_initials': 'SK'
            }
        }
        return jsonify({'success': True, 'blog': data})

    # =========================================================================
    # 2. PUBLIC PAGE SECTIONS API (Returns active sections ordered by sort_order)
    # =========================================================================

    @app.route('/api/pages/<slug>/sections', methods=['GET'])
    @app.route('/api/v1/pages/<slug>/sections', methods=['GET'])
    @app.route('/api/sections/<slug>', methods=['GET'])
    @app.route('/api/v1/sections/<slug>', methods=['GET'])
    @app.route('/api/sections', methods=['GET'])
    @app.route('/api/v1/sections', methods=['GET'])
    @app.route('/api/pages/about-us/sections', methods=['GET'])
    @app.route('/api/v1/pages/about-us/sections', methods=['GET'])
    def public_get_page_sections(slug=None):
        """Public API returning active sections and page metadata for a page ordered by sort_order."""
        target_slug = request.args.get('page') or slug or 'about-us'
        locale = request.args.get('locale') or request.args.get('lang') or get_locale()
        sections = PageSection.all_for_page(page_slug=target_slug, include_inactive=False)
        formatted = [PageSection.to_localized_dict(s, locale=locale) for s in sections]

        page_obj = Page.find_by_slug(target_slug)
        page_data = page_obj.to_dict(locale=locale) if page_obj else {
            'slug': target_slug,
            'title': target_slug.replace('-', ' ').title(),
            'content': '',
            'meta_description': '',
            'seo_title': target_slug.replace('-', ' ').title()
        }

        labels = {
            'home': translate('Home', locale),
            'about_us': translate('About Us', locale),
            'site_title': translate('TyresVision UAE', locale),
            'loading': translate('Loading...', locale),
            'notice': translate('Notice', locale),
        }

        return jsonify({
            'success': True,
            'locale': locale,
            'labels': labels,
            'page': page_data,
            'sections': formatted,
            'count': len(formatted)
        })

    # =========================================================================
    # 3. ENQUIRY / WHATSAPP BANNER SUBMISSION API (hdweb_enquiry table)
    # =========================================================================

    @app.route('/api/enquiry', methods=['POST'])
    @app.route('/api/v1/enquiry', methods=['POST'])
    def api_create_enquiry():
        """
        Receives quote & WhatsApp requests and saves all fields directly
        into the existing `hdweb_enquiry` table.
        """
        data = request.get_json(silent=True) or request.form.to_dict() or {}

        tyre_size = (data.get('tyre_size') or data.get('tyreSize') or '').strip()
        vehicle_raw = (data.get('vehicle') or data.get('carMake') or data.get('car_make') or '').strip()
        city = (data.get('city') or data.get('emirate') or '').strip()
        spec = (data.get('spec') or data.get('fitting') or '').strip()
        name = (data.get('name') or '').strip() or None
        email = (data.get('email') or '').strip() or None
        number = (data.get('number') or data.get('phone') or data.get('mobile') or '').strip() or None
        enquiry_for = (data.get('enquiry_for') or data.get('enquiryFor') or 'Tyre Quote (WhatsApp Home Banner)').strip()
        form_type = (data.get('form_type') or 'home_banner_whatsapp').strip()
        status = int(data.get('status', 0))

        # Check logged-in user in session if name, email, or mobile is not explicitly supplied
        if not name or not email or not number:
            name = name or session.get('name') or session.get('user_name') or session.get('customer_name')
            email = email or session.get('email') or session.get('user_email') or session.get('customer_email')
            number = number or session.get('phone') or session.get('mobile') or session.get('number') or session.get('customer_phone')

            sess_uid = session.get('user_id') or session.get('customer_id') or session.get('uid')
            if sess_uid:
                try:
                    conn_lookup = get_connection()
                    try:
                        with conn_lookup.cursor() as cur_lookup:
                            # 1. Check users table (e-commerce customer)
                            cur_lookup.execute("SELECT name, email, phone FROM users WHERE id = %s", (sess_uid,))
                            u_row = cur_lookup.fetchone()
                            if u_row:
                                name = name or u_row.get('name')
                                email = email or u_row.get('email')
                                number = number or u_row.get('phone')
                            else:
                                # 2. Check admin_users (administrator user)
                                cur_lookup.execute("SELECT name AS Name, email AS Email FROM admin_users WHERE id = %s", (sess_uid,))
                                u_tbl = cur_lookup.fetchone()
                                if u_tbl:
                                    name = name or u_tbl.get('Name')
                                    email = email or u_tbl.get('Email')
                    finally:
                        conn_lookup.close()
                except Exception as ex:
                    print("Session user lookup error in enquiry:", ex)

        # Build message summary
        message = data.get('message')

        # Fallback: extract tyre_size from message if missing
        if not tyre_size and message:
            size_match = re.search(r'\b([1-3]\d{2}\s*/\s*\d{2}\s*(?:R|ZR|r|zr)?\s*\d{2})\b', message)
            if size_match:
                tyre_size = size_match.group(1).strip()

        # Fallback: extract vehicle from message if missing
        if not vehicle_raw and message:
            veh_match = re.search(r'(?:tyre\s+options\s+for|options\s+for|vehicle:?)\s*([^.\n]+)', message, re.IGNORECASE)
            if veh_match:
                vehicle_raw = veh_match.group(1).strip()

        # Fallback: extract brand from message if missing
        if not spec and message:
            brand_match = re.search(r'(?:tyres\s+from|brand:?)\s*([^.\n]+)', message, re.IGNORECASE)
            if brand_match:
                spec = brand_match.group(1).strip()

        # Extract make, model, year if available in vehicle string
        make = data.get('make')
        model = data.get('model')
        year = data.get('year')
        if vehicle_raw and (not make or not model):
            year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vehicle_raw)
            if year_match:
                year = year or year_match.group(1)
            clean_no_year = re.sub(r'\b(19\d{2}|20\d{2})\b', '', vehicle_raw).strip()
            parts = [p for p in clean_no_year.split() if p]
            if parts and not make:
                make = parts[0].title()
            if len(parts) > 1 and not model:
                model = " ".join(parts[1:]).title()

        if not message:
            msg_parts = []
            if tyre_size:
                msg_parts.append(f"Tyre size: {tyre_size}")
            if vehicle_raw:
                msg_parts.append(f"Car: {vehicle_raw}")
            if city:
                msg_parts.append(f"Emirate: {city}")
            if spec:
                msg_parts.append(f"Fitting: {spec}")
            if name or email or number:
                user_info = []
                if name: user_info.append(f"Name: {name}")
                if email: user_info.append(f"Email: {email}")
                if number: user_info.append(f"Phone: {number}")
                msg_parts.append("User: " + ", ".join(user_info))
            message = "\n".join(msg_parts) if msg_parts else "WhatsApp Tyre Quote Request"

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                sql = """
                    INSERT INTO hdweb_enquiry (
                        name, email, number, enquiry_for, message, status,
                        form_type, model, make, year, spec, current_insurance,
                        vehicle, tyre_size, city
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    )
                """
                cursor.execute(sql, (
                    name,
                    email,
                    number,
                    enquiry_for,
                    message,
                    status,
                    form_type,
                    model,
                    make,
                    str(year) if year else None,
                    spec,
                    data.get('current_insurance'),
                    vehicle_raw or None,
                    tyre_size or None,
                    city or None
                ))
                conn.commit()
                new_id = cursor.lastrowid

            return jsonify({
                'success': True,
                'enquiry_id': new_id,
                'message': 'Enquiry successfully recorded in hdweb_enquiry.'
            }), 201
        except Exception as err:
            return jsonify({
                'success': False,
                'error': f"Failed to record enquiry: {str(err)}"
            }), 500
        finally:
            conn.close()

    # =========================================================================
    # 4. SCOPED FACETED SEARCH & CATALOG API (/api/v1/catalog/search)
    # =========================================================================

    @app.route('/api/catalog/search', methods=['GET'])
    @app.route('/api/v1/catalog/search', methods=['GET'])
    def api_catalog_search():
        """
        Public Scoped Faceted Search API:
        Resolves Website/Store scope, filters products by size & attributes,
        and aggregates real-time filter counts for faceted navigation sidebar.
        """
        ctx = StoreContext.resolve_current_context()
        website = ctx.get('website') or {'id': 1, 'name': 'TyresVision UAE'}
        store = ctx.get('store') or {'id': 1, 'name': 'Dubai Retail Hub'}
        locale = request.args.get('locale') or _get_locale()

        # Query filters
        width = request.args.get('width')
        aspect_ratio = request.args.get('aspect_ratio') or request.args.get('profile')
        rim_size = request.args.get('rim_size') or request.args.get('rim')
        speed_index = request.args.get('speed_index')
        brand_filter = request.args.get('brand')
        brand_id = request.args.get('brand_id')
        run_flat = request.args.get('run_flat')
        min_price = request.args.get('min_price')
        max_price = request.args.get('max_price')
        sort = request.args.get('sort') or 'popularity'

        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = min(48, max(6, int(request.args.get('per_page', request.args.get('limit', 12)))))
        except (ValueError, TypeError):
            page = 1
            per_page = 12

        offset = (page - 1) * per_page

        conn = get_connection()
        try:
            with conn.cursor() as cursor:
                # Build base where conditions
                where_clauses = ["p.deleted_at IS NULL", "p.status = 'active'"]
                params = []

                if brand_id and str(brand_id).isdigit():
                    where_clauses.append("p.brand_id = %s")
                    params.append(int(brand_id))
                elif brand_filter:
                    where_clauses.append("(b.slug = %s OR b.name = %s)")
                    params.extend([brand_filter.lower(), brand_filter])

                if min_price and str(min_price).replace('.', '', 1).isdigit():
                    where_clauses.append("COALESCE(pp.special_price, pp.regular_price, p.price) >= %s")
                    params.append(float(min_price))

                if max_price and str(max_price).replace('.', '', 1).isdigit():
                    where_clauses.append("COALESCE(pp.special_price, pp.regular_price, p.price) <= %s")
                    params.append(float(max_price))

                where_sql = " AND ".join(where_clauses)

                # Sorting clause
                order_sql = "p.sort_order ASC, p.id DESC"
                if sort == 'price_asc':
                    order_sql = "COALESCE(pp.special_price, pp.regular_price, p.price) ASC"
                elif sort == 'price_desc':
                    order_sql = "COALESCE(pp.special_price, pp.regular_price, p.price) DESC"
                elif sort == 'newest':
                    order_sql = "p.created_at DESC"

                # Query Products with Store Scoped Prices
                query = f"""
                    SELECT 
                        p.id, p.sku, p.name, p.slug, p.price AS base_price,
                        p.tire_size_label, p.tire_speed_rating, p.tire_load_index,
                        p.tire_pattern, p.run_flat, p.image_path, p.brand_id,
                        b.name AS brand_name, b.slug AS brand_slug, b.logo AS brand_logo,
                        pp.regular_price AS store_regular_price, pp.special_price AS store_special_price,
                        COALESCE(inv.qty, p.stock_qty, 0) AS stock_qty,
                        COALESCE(inv.is_in_stock, 1) AS is_in_stock
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    LEFT JOIN product_prices pp ON pp.product_id = p.id AND (pp.store_id = %s OR pp.website_id = %s)
                    LEFT JOIN product_inventories inv ON inv.product_id = p.id AND inv.store_id = %s
                    WHERE {where_sql}
                    ORDER BY {order_sql}
                    LIMIT %s OFFSET %s
                """
                query_params = [store.get('id', 1), website.get('id', 1), store.get('id', 1)] + params + [per_page, offset]
                cursor.execute(query, query_params)
                rows = cursor.fetchall()

                # Count total
                count_query = f"""
                    SELECT COUNT(DISTINCT p.id) AS total
                    FROM products p
                    LEFT JOIN brands b ON p.brand_id = b.id
                    LEFT JOIN product_prices pp ON pp.product_id = p.id AND (pp.store_id = %s OR pp.website_id = %s)
                    WHERE {where_sql}
                """
                cursor.execute(count_query, [store.get('id', 1), website.get('id', 1)] + params)
                total_row = cursor.fetchone()
                total_products = total_row['total'] if total_row else 0

                products_list = []
                for r in rows:
                    name_dict = r.get('name')
                    if isinstance(name_dict, str):
                        try:
                            name_dict = json.loads(name_dict)
                        except Exception:
                            pass
                    prod_name = name_dict.get(locale) or name_dict.get('en') if isinstance(name_dict, dict) else (r.get('name') or r.get('sku'))

                    reg_price = float(r.get('store_regular_price') or r.get('base_price') or 0.0)
                    spec_price = float(r.get('store_special_price')) if r.get('store_special_price') is not None else None
                    effective_price = spec_price if spec_price is not None else reg_price

                    # Get resolved scoped attributes
                    scoped_attrs = AttributeService.get_product_scoped_attributes(r['id'], website.get('id'), store.get('id'))

                    products_list.append({
                        'id': r['id'],
                        'sku': r['sku'],
                        'name': prod_name,
                        'slug': r.get('slug'),
                        'brand': {
                            'id': r.get('brand_id'),
                            'name': r.get('brand_name'),
                            'slug': r.get('brand_slug'),
                            'logo': r.get('brand_logo')
                        },
                        'price': effective_price,
                        'regular_price': reg_price,
                        'special_price': spec_price,
                        'in_stock': bool(r.get('is_in_stock', True)),
                        'stock_qty': int(r.get('stock_qty', 0)),
                        'image': r.get('image_path'),
                        'size_label': r.get('tire_size_label'),
                        'attributes': {
                            k: v.get('value') for k, v in scoped_attrs.items()
                        }
                    })

                # Aggregate Facets
                cursor.execute("""
                    SELECT b.id, b.name, b.slug, COUNT(p.id) AS count
                    FROM brands b
                    JOIN products p ON p.brand_id = b.id
                    WHERE p.deleted_at IS NULL AND p.status = 'active'
                    GROUP BY b.id, b.name, b.slug
                    ORDER BY count DESC LIMIT 15
                """)
                brand_facets = cursor.fetchall()

                # Dynamic Option Facets for Rim Size & Speed Index
                cursor.execute("""
                    SELECT opt.value, COUNT(DISTINCT pav.product_id) AS count
                    FROM attribute_options opt
                    JOIN attributes a ON opt.attribute_id = a.id
                    JOIN product_attribute_values pav ON pav.attribute_id = a.id AND pav.value_text = opt.value
                    WHERE a.code = 'rim_size'
                    GROUP BY opt.value
                    ORDER BY CAST(opt.value AS UNSIGNED) ASC
                """)
                rim_facets = cursor.fetchall()

                cursor.execute("""
                    SELECT opt.value, COUNT(DISTINCT pav.product_id) AS count
                    FROM attribute_options opt
                    JOIN attributes a ON opt.attribute_id = a.id
                    JOIN product_attribute_values pav ON pav.attribute_id = a.id AND pav.value_text = opt.value
                    WHERE a.code = 'speed_index'
                    GROUP BY opt.value, opt.sort_order
                    ORDER BY opt.sort_order ASC
                """)
                speed_facets = cursor.fetchall()

                facets = {
                    'brands': brand_facets,
                    'rim_sizes': rim_facets,
                    'speed_indices': speed_facets
                }

                num_pages = max(1, math.ceil(total_products / per_page))
                return jsonify({
                    'success': True,
                    'context': {
                        'website_id': website.get('id'),
                        'website_name': website.get('name'),
                        'store_id': store.get('id'),
                        'store_name': store.get('name'),
                        'locale': locale,
                        'currency': 'AED'
                    },
                    'products': products_list,
                    'total': total_products,
                    'page': page,
                    'num_pages': num_pages,
                    'per_page': per_page,
                    'facets': facets
                })
        finally:
            conn.close()

    @app.route('/api/catalog/facets', methods=['GET'])
    @app.route('/api/v1/catalog/facets', methods=['GET'])
    def api_catalog_facets():
        """Returns pre-computed aggregated facet counts for filter sidebar."""
        return api_catalog_search()

    # =========================================================================
    # ELASTICSEARCH PRODUCTS SEARCH API
    # =========================================================================
    @app.route('/api/es/products', methods=['GET'])
    @app.route('/api/v1/es/products', methods=['GET'])
    def client_api_es_products():
        try:
            from services.es_service import es_service
            q = request.args.get('q', '').strip()
            page = int(request.args.get('page', 1))
            per_page = min(int(request.args.get('per_page', 25)), 100)
            sort_by = request.args.get('sort_by', 'created_at')
            sort_dir = request.args.get('sort_dir', 'desc')

            filters = {}
            for field in ['brand_id', 'brand_name', 'brand_slug', 'category_id', 'tyres_category',
                          'parts_category', 'vehicle_type', 'rim_size', 'speed_rating',
                          'country_of_origin', 'year', 'tire_pattern', 'oem_brand',
                          'run_flat', 'ev_rated', 'min_price', 'max_price']:
                val = request.args.get(field)
                if val is not None and val != '':
                    filters[field] = val

            res = es_service.search_products(
                query=q,
                filters=filters,
                sort_by=sort_by,
                sort_dir=sort_dir,
                page=page,
                per_page=per_page
            )
            status_code = 200 if res.get('success') else 503
            return jsonify(res), status_code
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


def register_api_routes(app):
    """Registers all API endpoints across tcsadmin, visionadmin, and the public client API."""
    register_tcsadmin_api_routes(app)
    register_visionadmin_api_routes(app)
    register_client_api_routes(app)
