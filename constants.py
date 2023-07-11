
# Session keys
SESSION_EMPLOYEE_ID = 'EMPLOYEE_ID'
SESSION_EMAIL = 'EMPLOYEE_EMAIL' # visitor ID
SESSION_ROLE = 'EMPLOYEE_ROLE'
SESSION_FULL_NAME = 'EMPLOYEE_FULL_NAME'
SESSION_COMPANY_ID = 'COMPANY_ID' # account ID
SESSION_COMPANY_NAME = 'COMPANY_NAME'
SESSION_COMPANY_PLAN = 'COMPANY_PLAN'

# Redis keys
REDIS_LANGUAGE = 'EMPLOYEE_LANGUAGE'
REDIS_MESSAGES = "MESSAGES" # dict for messages

# supported languages
SUPPORTED_LANGUAGES = ['ja-JP', 'ja', 'en-US', 'en']

# constant values to be used in app
# employee roles
ROLE_ADMIN = 'ROLE_ADMIN'
ROLE_APPROVER = 'ROLE_APPROVER'
ROLE_USER = 'ROLE_USER'
ROLES = [ROLE_ADMIN, ROLE_APPROVER, ROLE_USER]
# currencies
CURRENCY_DOLLAR = 'CURRENCY_DOLLAR'
CURRENCY_YEN = 'CURRENCY_YEN'
CURRENCIES = [CURRENCY_DOLLAR, CURRENCY_YEN]
# account plan
ACCOUNT_PLAN = ['Advanced', 'Standard']
# app name
APP_NAME = 'APP_NAME'
# page titles
TITLE_INDEX = 'TITLE_INDEX'
TITLE_EXPENSE_LIST = 'TITLE_EXPENSE_LIST'
TITLE_EXPENSE_NEW = 'TITLE_EXPENSE_NEW'
TITLE_EXPENSE_DETAIL = 'TITLE_EXPENSE_DETAIL'
TITLE_REPORT_LIST = 'TITLE_REPORT_LIST'
TITLE_REPORT_NEW = 'TITLE_REPORT_NEW'
TITLE_REPORT_DETAIL = 'TITLE_REPORT_DETAIL'
TITLE_APPROVE_LIST = 'TITLE_APPROVE_LIST'
TITLE_EMPLOYEE_LIST = 'TITLE_EMPLOYEE_LIST'
TITLE_EMPLOYEE_NEW = 'TITLE_EMPLOYEE_NEW'
TITLE_EMPLOYEE_DETAIL = 'TITLE_EMPLOYEE_DETAIL'
# report status
STATUS_OPEN = 'STATUS_OPEN'
STATUS_SUBMITTED = 'STATUS_SUBMITTED'
STATUS_APRROVED= 'STATUS_APRROVED'

# error messages
MSG_EMAIL_MISMATCH = 'MSG_EMAIL_MISMATCH'
MSG_NO_EMAIL_PASSWORD = 'MSG_NO_EMAIL_PASSWORD'
MSG_NO_EXPENSE_ID_MATCH = 'MSG_NO_EXPENSE_ID_MATCH'
MSG_NO_REPORT_ID_MATCH = 'MSG_NO_REPORT_ID_MATCH'
