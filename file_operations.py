import os
import uuid
import werkzeug

from utilities import send_track_event

# Events
EVENT_FILE_UPLOADED = 'FileUploaded'
EVENT_FILE_DELETED = 'FileDeleted'

# root path for image files
RECEIPT_IMAGE_ROOT = 'static/images/receipt/'

# Save the specified file and return the name
# If the format of the file is not correct or the file doesn't exist, then return None
def save_file(file):
	if file:
		file_name = str(uuid.uuid4()) + '_' + werkzeug.utils.secure_filename(file.filename)
		file.save(RECEIPT_IMAGE_ROOT + file_name)
		print('file created at ', RECEIPT_IMAGE_ROOT + file_name)
		send_track_event(EVENT_FILE_UPLOADED)
		return file_name
	else:
		return None

# Delete the specified file
def delete_file(file_name):
	if file_name:
		file_path = RECEIPT_IMAGE_ROOT + file_name
		if os.path.exists(file_path):
			os.remove(file_path)
			send_track_event(EVENT_FILE_DELETED)
			return True
	return False
