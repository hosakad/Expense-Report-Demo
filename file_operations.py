import os
import uuid
import boto3
from botocore.exceptions import ClientError
import werkzeug

from utilities import send_track_event

# Events
EVENT_FILE_UPLOADED = 'FileUploaded'
EVENT_FILE_DELETED = 'FileDeleted'

# root path for image files (local fallback)
RECEIPT_IMAGE_ROOT = 'static/images/receipt/'

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

# R2 mode when all four env vars are present, otherwise local mode
_R2_ACCOUNT_ID      = os.environ.get('R2_ACCOUNT_ID')
_R2_ACCESS_KEY_ID   = os.environ.get('R2_ACCESS_KEY_ID')
_R2_SECRET_ACCESS_KEY = os.environ.get('R2_SECRET_ACCESS_KEY')
_R2_BUCKET_NAME     = os.environ.get('R2_BUCKET_NAME')

USE_R2 = all([_R2_ACCOUNT_ID, _R2_ACCESS_KEY_ID, _R2_SECRET_ACCESS_KEY, _R2_BUCKET_NAME])

if USE_R2:
    _s3 = boto3.client(
        's3',
        endpoint_url=f'https://{_R2_ACCOUNT_ID}.r2.cloudflarestorage.com',
        aws_access_key_id=_R2_ACCESS_KEY_ID,
        aws_secret_access_key=_R2_SECRET_ACCESS_KEY,
    )
    print('file_operations: R2 mode')
else:
    _s3 = None
    print('file_operations: local mode')


def _validate_file(file):
    if not file or not file.filename:
        return False
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    if not werkzeug.utils.secure_filename(file.filename):
        return False
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        return False
    return True


def save_file(file):
    if not _validate_file(file):
        return None

    file_name = str(uuid.uuid4()) + '_' + werkzeug.utils.secure_filename(file.filename)

    if USE_R2:
        file.seek(0)
        _s3.upload_fileobj(file, _R2_BUCKET_NAME, file_name)
        print('file uploaded to R2:', file_name)
    else:
        file.seek(0)
        file.save(RECEIPT_IMAGE_ROOT + file_name)
        print('file created at', RECEIPT_IMAGE_ROOT + file_name)

    send_track_event(EVENT_FILE_UPLOADED)
    return file_name


def delete_file(file_name):
    if not file_name:
        return False

    if USE_R2:
        try:
            _s3.delete_object(Bucket=_R2_BUCKET_NAME, Key=file_name)
            send_track_event(EVENT_FILE_DELETED)
            return True
        except ClientError:
            return False
    else:
        file_path = RECEIPT_IMAGE_ROOT + file_name
        if os.path.exists(file_path):
            os.remove(file_path)
            send_track_event(EVENT_FILE_DELETED)
            return True
        return False


def get_file_url(file_name):
    if not file_name:
        return None

    if USE_R2:
        return _s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': _R2_BUCKET_NAME, 'Key': file_name},
            ExpiresIn=3600,
        )
    else:
        return '/' + RECEIPT_IMAGE_ROOT + file_name
