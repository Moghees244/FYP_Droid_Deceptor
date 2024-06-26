import os
import re
import subprocess
from androguard.core.bytecodes import apk
from flask import render_template, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from droid_deceptor.config import Paths
from droid_deceptor.models.apk import add_apk
from droid_deceptor.controllers.user_controllers.malware_classification import prepare_input, malware_classifier

# Paths
manifest_features_file_path = Paths.manifest_features_file_path
api_calls_file_path = Paths.api_calls_file_path

apks_path = Paths.apks_path
source_code_path = Paths.source_code_path

def convert_bytes_to_megabytes(size_in_bytes):
    return round(size_in_bytes / (1024.0 * 1024.0), 3)

# read all permissions from file and make a list of it
def get_feature_list(file_path):
    
    with open(file_path, "r") as features_file:
        features = features_file.readlines()
    features = [word.strip() for word in features]
    return features


# feature extraction of apk
def extract_features(file_name):

    # List of permissions
    manifest_features = get_feature_list(manifest_features_file_path)
    api_calls = get_feature_list(api_calls_file_path)
    all_features = manifest_features + api_calls
    all_features.insert(0, 'sha256')

    app_data = {}

    # check if the file exists
    if os.path.isfile(os.path.join(apks_path, file_name)):
        # Decompile it
        try:
            app = apk.APK(os.path.join(apks_path, file_name))
            # extract AndroidManifest.xml file
            xml = app.get_android_manifest_axml().get_xml()
            xml = str(xml)
        except:
            return None

            
        # Extracting features from AndroidManifest.xml and making binary indicator vector
        for fea in manifest_features:
            if fea in xml:
                app_data[fea] = 1
            else:
                app_data[fea] = 0

        # Extracting api calls from source code of apk
        extracted_api_calls = extract_api_calls(file_name)
        if extracted_api_calls is None:
            return None
        
        # vectorizing api calls
        for api_call in api_calls:
            if api_call in extracted_api_calls:
                app_data[api_call] = 1
            else:
                app_data[api_call] = 0

        # calculating sha256 hash and storing it
        result = subprocess.run(['sha256sum', os.path.join(apks_path, file_name)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        sha256_hash = result.stdout.split()[0]
        app_data['sha256'] = sha256_hash

        result = subprocess.run(['md5sum', os.path.join(apks_path, file_name)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        md5_hash = result.stdout.split()[0]
        app_data['md5'] = md5_hash
        
        apk_size = os.path.getsize(os.path.join(apks_path, file_name))
        app_data['size'] = convert_bytes_to_megabytes(apk_size)

        # return all the features
        return app_data


def find_java_files(filename):
    java_files = []
    path = os.path.join(source_code_path, filename[:-4])
    
    # Finding and saving paths of all .java files in source code of apk
    for folder_name, subfolders, filenames in os.walk(path):
        for filename in filenames:
            if filename.endswith('.java'):
                java_files.append(os.path.join(folder_name, filename))
    return java_files


def extract_api_calls(filename):
    apk_api_calls = []
    api_calls = get_feature_list(api_calls_file_path)

    subprocess.run(["mkdir", os.path.join(source_code_path, filename[:-4])])

    try:
        # Getting apk source code and saving in a folder
        command = ["jadx", "-d", os.path.join(Paths.jadx_output_path, filename[:-4])
                   , os.path.join(Paths.jadx_apk_path, filename)]
        
        with open(os.devnull, "w") as devnull:
            subprocess.run(command, stdout=devnull, stderr=subprocess.STDOUT)
        
        # Finding api calls from all java files
        for file in find_java_files(filename):
            with open(file, 'r') as source_file:
                code = source_file.read()
                for api_call in api_calls:
                    match = re.match(r"(?P<class>\w+)\.(?P<method>\w+)", api_call)
                    method = match.group("method") + '('
                    if match.group("class") in code and method in code:
                        apk_api_calls.append(api_call)

    except:
        print("Problem in jadx")
        return None

    # Deleting the source code
    subprocess.run(["rm", "-r", os.path.join(source_code_path, filename[:-4])])
    return apk_api_calls

@jwt_required()
def display_results():
    uploaded_file = request.args.get('uploaded_file', '')
    features = extract_features(uploaded_file)
    input_vector = prepare_input(features)
    classification = malware_classifier(input_vector)
    add_apk(uploaded_file, features['sha256'], get_jwt_identity())

    return render_template('results.html', status_message=request.args.get('status_message', ''),
                            uploaded_file=uploaded_file, features=features, classification=classification)
    