import os
from datetime import date
import psycopg2
from psycopg2 import InterfaceError
from psycopg2.extras import DictCursor

import constants as cns

# retrieve parametes for database from enrironment value
DATABASE_URL = os.environ.get('DATABASE_URL')
DATABASE_SCHEMA = os.environ.get('DATABASE_SCHEMA')
DATABASE_CONNECTION = None

def getDBConnection():
    global DATABASE_CONNECTION
	# Check if the existing connection is alive
    if DATABASE_CONNECTION is None or DATABASE_CONNECTION.closed != 0:
        # SSLモード'require'を指定して新しい接続を確立
        DATABASE_CONNECTION = psycopg2.connect(DATABASE_URL, sslmode='require')
        with DATABASE_CONNECTION.cursor() as cursor:
            cursor.execute(f"SET search_path TO {DATABASE_SCHEMA};")
    return DATABASE_CONNECTION

def sql_select(sql_string, params):
    print("Preparing to execute SQL:", sql_string, "with params:", params)
    cursor = None
    try:
        cursor = getDBConnection().cursor(cursor_factory=DictCursor)
        cursor.execute(sql_string, params)
        results = cursor.fetchall()
        return results
    except Exception as e:
        print("Error during SQL execution:", e)
    finally:
        if cursor is not None:
            cursor.close()


def sql_execute(sql_string, params):
    print("Preparing to execute SQL:", sql_string, "with params:", params)
    connection = None
    cursor = None
    try:
        connection = getDBConnection()
        cursor = connection.cursor()
        cursor.execute(sql_string, params)
        connection.commit()
    except Exception as e:
        print("Error during SQL execution:", e)
        if connection is not None:
            connection.rollback()
        return e
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


# --- auth ---

def get_employee_by_email(email, password):
    sql = ("select employee.id, email, role, first_name, last_name,"
           " company.id as company_id, company.name as company_name, company.plan as company_plan"
           " from employee join company on employee.company_id = company.id"
           " where email=%s and password=%s")
    return sql_select(sql, (email, password))


# --- expense ---

def get_expenses_unassigned(user_id):
    sql = ("select expense.id, name, date, amount, currency, description, receipt_image"
           " from expense join employee on expense.user_id = employee.id"
           " where expense.user_id = %s and expense.report_id is null")
    return sql_select(sql, (user_id,))

def get_expense(expense_id):
    sql = ("select id, name, date, amount, currency, description, receipt_image"
           " from expense where id = %s")
    return sql_select(sql, (expense_id,))

def create_expense(name, expense_date, amount, currency, description, receipt_image, user_id):
    sql = ("insert into expense(name, date, amount, currency, description, receipt_image, user_id)"
           " values(%s, %s, %s, %s, %s, %s, %s)")
    sql_execute(sql, (name, expense_date, amount, currency, description, receipt_image, user_id))

def update_expense(name, expense_date, currency, amount, description, expense_id):
    sql = ("update expense set name = %s, date = %s, currency = %s, amount = %s, description = %s"
           " where id = %s")
    sql_execute(sql, (name, expense_date, currency, amount, description, expense_id))

def delete_expense(expense_id):
    sql = "delete from expense where id = %s"
    sql_execute(sql, (expense_id,))

def update_receipt_image(filename, expense_id):
    sql = "update expense set receipt_image = %s where id = %s"
    sql_execute(sql, (filename, expense_id))

def delete_receipt_image(expense_id):
    sql = "update expense set receipt_image = null where id = %s"
    sql_execute(sql, (expense_id,))


# --- report ---

def get_reports(user_id):
    sql = ("select report.id, name, submit_date, approve_date, status"
           " from report join employee on report.user_id = employee.id"
           " where report.user_id = %s")
    return sql_select(sql, (user_id,))

def get_report(report_id):
    sql = "select id, name from report where id = %s"
    return sql_select(sql, (report_id,))

def get_expenses_in_report(user_id, report_id):
    sql = ("select expense.id, expense.name, date, amount, currency, description"
           " from expense"
           " join employee on expense.user_id = employee.id"
           " join report on expense.report_id = report.id"
           " where expense.user_id = %s and expense.report_id = %s and report.status = %s")
    return sql_select(sql, (user_id, report_id, cns.STATUS_OPEN))

def get_expenses_unassigned_for_report(user_id):
    sql = ("select expense.id, name, date, amount, currency, description"
           " from expense join employee on expense.user_id = employee.id"
           " where expense.user_id = %s and expense.report_id is null")
    return sql_select(sql, (user_id,))

def create_report(name, user_id):
    sql = "insert into report(name, user_id, status) values(%s, %s, %s)"
    sql_execute(sql, (name, user_id, cns.STATUS_OPEN))

def update_report_name(report_id, name):
    sql = "update report set name = %s where id = %s"
    sql_execute(sql, (name, report_id))

def assign_expenses_to_report(report_id, id_added):
    placeholders = ",".join(["%s"] * len(id_added))
    sql = f"update expense set report_id = %s where id in ({placeholders})"
    sql_execute(sql, (report_id, *id_added))

def unassign_expenses_from_report(id_removed):
    placeholders = ",".join(["%s"] * len(id_removed))
    sql = f"update expense set report_id = null where id in ({placeholders})"
    sql_execute(sql, (*id_removed,))

def delete_report(report_id):
    sql_execute("update expense set report_id = null where expense.report_id = %s", (report_id,))
    sql_execute("delete from report where id = %s", (report_id,))

def submit_report(report_id):
    sql = "update report set submit_date = %s, status = %s where report.id = %s"
    sql_execute(sql, (date.today().strftime('%Y-%m-%d'), cns.STATUS_SUBMITTED, report_id))

def approve_report(report_id):
    sql = "update report set approve_date = %s, status = %s where report.id = %s"
    sql_execute(sql, (date.today().strftime('%Y-%m-%d'), cns.STATUS_APRROVED, report_id))

def reject_report(report_id):
    sql = "update report set submit_date = null, status = %s where report.id = %s"
    sql_execute(sql, (cns.STATUS_OPEN, report_id))

def get_approve_list(company_id):
    sql = ("select report.id as id, report.name as name, report.status as status"
           " from report join employee on report.user_id = employee.id"
           " where employee.company_id = %s and (report.status = %s or report.status = %s)")
    return sql_select(sql, (company_id, cns.STATUS_SUBMITTED, cns.STATUS_APRROVED))


# --- employee ---

def get_employees(company_id):
    sql = "select id, email, first_name, last_name, role from employee where company_id = %s"
    return sql_select(sql, (company_id,))

def get_employee(employee_id):
    sql = "select id, first_name, last_name, email, password, role from employee where id = %s"
    return sql_select(sql, (employee_id,))

def create_employee(first_name, last_name, email, password, role, company_id):
    sql = ("insert into employee(first_name, last_name, email, password, role, company_id)"
           " values(%s, %s, %s, %s, %s, %s)")
    sql_execute(sql, (first_name, last_name, email, password, role, company_id))

def update_employee(first_name, last_name, email, role, employee_id):
    sql = ("update employee set first_name = %s, last_name = %s, email = %s, role = %s"
           " where id = %s")
    sql_execute(sql, (first_name, last_name, email, role, employee_id))

def delete_employee(employee_id):
    sql = "delete from employee where id = %s"
    sql_execute(sql, (employee_id,))


# --- user_home summary ---

def get_open_expenses_count(user_id):
    sql = ("select count(distinct expense.id), count(distinct report.id)"
           " from expense join report on expense.report_id = report.id"
           " where expense.user_id = %s and report.status = %s")
    return sql_select(sql, (user_id, cns.STATUS_OPEN))

def get_reports_summary(user_id):
    sql = ("select count(distinct expense.id), count(distinct report.id)"
           " from expense join report on expense.report_id = report.id"
           " where expense.user_id = %s and report.status = %s")
    return sql_select(sql, (user_id, cns.STATUS_SUBMITTED))

def get_submitted_reports(user_id):
    sql = ("select count(distinct expense.id), count(distinct report.id)"
           " from expense join report on expense.report_id = report.id"
           " where expense.user_id = %s and report.status = %s")
    return sql_select(sql, (user_id, cns.STATUS_APRROVED))
