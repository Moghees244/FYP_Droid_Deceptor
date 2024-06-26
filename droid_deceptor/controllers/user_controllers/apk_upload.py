import os
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import render_template, request, redirect, url_for

@jwt_required()
def upload_apk():
    if request.method == "POST":
        return get_apk(request.files)
    # Render the 'upload.html' template for the 'GET' request
    return render_template('upload.html', user = get_jwt_identity())

def get_apk(files):
    UPLOAD_FOLDER = 'droid_deceptor/uploads'

    uploaded_file = None
    file = files['file']

    # Check if the user submitted an empty file input
    if file.filename == '':
        return render_template('upload.html', message="APK Not Selected.")
    
    if not file.filename.endswith('.apk'):
        return render_template('upload.html', message="You Can Only Upload APK Files.")
    
    # Check file size
    max_size = 50000000  # 50 MB
    file.seek(0, 2)  # Move the file pointer to the end of the file
    file_length = file.tell()  # Get the current position of the file pointer
    file.seek(0)  # Reset the file pointer to the beginning of the file
    
    if file_length > max_size:
        return render_template('upload.html', message="File size exceeds maximum limit")

    if file:
        # Ensure the folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # Save the uploaded APK file to the UPLOAD_FOLDER
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
        uploaded_file = file.filename

    return redirect(url_for('user.display_results', uploaded_file=uploaded_file))