from flask import Flask, render_template, request, make_response
import os
import cv2
import numpy as np
from ultralytics import YOLO
import torch
import torchvision
print(torch.__version__)
print(torchvision.__version__)
print("test")

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'mp4'}
model = YOLO('Crash.pt')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get("file")
        if file and allowed_file(file.filename):
            filename = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(filename)
            img = cv2.imread(filename)
            results = model(img)
            annotated_img = results[0].plot()
            _, img_encoded = cv2.imencode('.jpg', annotated_img)
            response = make_response(img_encoded.tobytes())
            response.headers['Content-Type'] = 'image/jpeg'
            return response

    return render_template("index.html")

@app.route('/process_frame', methods=['POST'])
def process_frame():
    file = request.files['file']
    nparr = np.fromstring(file.read(), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    results = model(frame)
    annotated_frame = results[0].plot()
    _, img_encoded = cv2.imencode('.jpg', annotated_frame)
    response = make_response(img_encoded.tobytes())
    response.headers['Content-Type'] = 'image/jpeg'
    return response

if __name__ == "__main__":
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host="localhost",port=4000, debug=False)
