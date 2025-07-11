import os
import base64
import json
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_from_directory, make_response
from flask_socketio import SocketIO, emit
from datetime import datetime
from werkzeug.utils import secure_filename
from functools import wraps
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import telebot
from telebot.handler_backends import SkipHandler as Skip
from telebot.types import InputFile
bot=telebot.TeleBot("")


app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

ALERT_IMAGE_DIR = 'static/alerts'
os.makedirs(ALERT_IMAGE_DIR, exist_ok=True)

alerts = []
camera_feeds = {}
users = {
    "admin": {
        "password": "123",
        "name": "System Administrator",
        "role": "admin",
        "station": "HQ"
    }
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connect_confirmed', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('register_android')
def handle_android_registration(data):
    """Handle Android client registration"""
    device_id = data.get('device_id')
    if device_id:
        print(f"Android device registered: {device_id}")
        emit('registration_confirmation', {'status': 'success', 'message': 'Device registered'})

@socketio.on('request_latest_alerts')
def handle_request_alerts(data):
    """Send the latest alerts to the client"""
    count = data.get('count', 5)  
    latest_alerts = alerts[:count]
    
    for alert in latest_alerts:
        image_urls = [request.host_url.strip('/') + image for image in alert.get('images', [])]
        alert_data = {
            'id': alert['id'],
            'time': alert['time'],
            'date': alert['date'],
            'camera_id': alert['camera_id'],
            'location': alert['location'],
            'url': alert.get('url', ''),
            'type': alert['type'],
            'objects': alert['objects'],
            'severity': alert['severity'],
            'images': image_urls,
            'summary': alert.get('summary', ''),
            'reasoning': alert.get('reasoning', ''),
            'recommendation': alert.get('recommendation', '')
        }
        emit('alert_notification', alert_data)

@socketio.on('request_all_alerts')
def handle_request_all_alerts():
    """Send all alerts to the client"""
    for alert in alerts:
        image_urls = [request.host_url.strip('/') + image for image in alert.get('images', [])]
        alert_data = {
            'id': alert['id'],
            'time': alert['time'],
            'date': alert['date'],
            'camera_id': alert['camera_id'],
            'location': alert['location'],
            'url': alert.get('url', ''),
            'type': alert['type'],
            'objects': alert['objects'],
            'severity': alert['severity'],
            'images': image_urls,
            'summary': alert.get('summary', ''),
            'reasoning': alert.get('reasoning', ''),
            'recommendation': alert.get('recommendation', '')
        }
        emit('alert_notification', alert_data)

@app.route('/')
@login_required
def index():
    return render_template('index.html',
                           alerts=alerts,
                           camera_feeds=camera_feeds,
                           user=session.get('user'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = users.get(username)
        if user and user['password'] == password:
            session['username'] = username
            session['user'] = {
                'name': user['name'],
                'role': user['role'],
                'station': user['station']
            }
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'success'})
            return redirect(url_for('index'))
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'fail', 'error': 'Invalid username or password'})
        
        return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'status': 'success'})
    return redirect(url_for('login'))

@app.route('/update_feed', methods=['POST'])
def update_feed():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    camera_id = data.get('camera_id')
    url = data.get('url')
    detected_object = data.get('object')

    if not camera_id or not url:
        return jsonify({'error': 'Missing camera_id or url'}), 400

    camera_feeds[camera_id] = {
        'url': url,
        'object': detected_object if detected_object else 'Unknown',
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    socketio.emit('camera_feed_update', {
        'camera_id': camera_id,
        'url': url,
        'object': detected_object if detected_object else 'Unknown',
        'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    return jsonify({'message': 'Feed updated successfully'}), 200

@app.route('/send_live_feed', methods=['POST'])
def send_live_feed():
    """Receive live feed image and send it to connected clients via WebSocket"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    camera_id = data.get('camera_id')
    image_b64 = data.get('image')
    
    if not camera_id or not image_b64:
        return jsonify({'error': 'Missing camera_id or image data'}), 400
    
    socketio.emit('image_data', {
        'camera_id': camera_id,
        'image': image_b64,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return jsonify({'message': 'Live feed sent successfully'}), 200

@app.route('/alert', methods=['POST'])
def receive_alert():
    data = request.get_json()
    url = data.get('url')
    camera_id = data.get('camera_id')
    location = data.get('location')
    police_station = data.get('police_station')
    object_detected = data.get('object_detected')
    alert_date = data.get('date', datetime.now().strftime("%Y-%m-%d"))
    alert_time = data.get('time', datetime.now().strftime("%H:%M:%S"))
    image_b64 = data.get('image')
    threat_level = data.get('threat_level', 0)
    
    # Get the new fields from app.py
    summary = data.get('summary', '')
    reasoning = data.get('reasoning', '')
    recommendation = data.get('recommendation', '')
    evidence_url = data.get('evidence_url', '')
    
    if not image_b64:
        return jsonify({'error': 'Missing image data'}), 400
    
    filename = f"{camera_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    image_path = os.path.join(ALERT_IMAGE_DIR, secure_filename(filename))
    with open(image_path, "wb") as img_file:
        img_file.write(base64.b64decode(image_b64))

    # Create severity level based on threat_level if available
    severity = 'High'
    if threat_level is not None:
        if threat_level > 80:
            severity = 'Critical'
        elif threat_level > 60:
            severity = 'High'
        elif threat_level > 40:
            severity = 'Medium'
        else:
            severity = 'Low'

    alert = {
        'id': f'ALT{len(alerts) + 1:03}',
        'time': alert_time,
        'date': alert_date,
        'camera_id': camera_id,
        'location': location,
        'url': url,
        'type': 'Weapon Detection' if object_detected in ['gun', 'knife'] else 'Fight Detection' if object_detected == 'Fight' else 'Accident Detected' if object_detected == 'accident' else 'Fire Detected' if object_detected == 'fire' else 'Emergency Vehicle Detected',
        'objects': [object_detected],
        'severity': severity,
        'images': [f"/{image_path}"],
        'summary': summary,
        'reasoning': reasoning,
        'recommendation': recommendation,
        'evidence_url': evidence_url,
        'threat_level': threat_level
    }

    alerts.insert(0, alert)
    
    image_urls = [request.host_url.strip('/') + image for image in alert['images']]
    
    socket_alert = {
        'id': alert['id'],
        'time': alert['time'],
        'date': alert['date'],
        'camera_id': alert['camera_id'],
        'location': alert['location'],
        'url': alert['url'],
        'type': alert['type'],
        'objects': alert['objects'],
        'severity': alert['severity'],
        'images': image_urls,
        'image_b64': image_b64,
        'summary': summary,
        'reasoning': reasoning,
        'recommendation': recommendation,
        'evidence_url': evidence_url,
        'threat_level': threat_level
    }
    
    socketio.emit('alert_notification', socket_alert)
    coords={"Gandhipuram": [11.0168, 76.9558],"RS Puram": [11.0069, 76.9498],"Ukkadam": [10.9925, 76.9608],"Peelamedu": [11.0310, 77.0323]}
    captioner=str("CCTV ID: "+socket_alert['camera_id']+"\nStation: "+ socket_alert['location']+"\nSeverity: "+socket_alert['severity'])
    bot.send_photo(1739769811,photo=InputFile(f"C:/Users/91938/Documents/uyir_hack/static/alerts/{filename}"),caption=captioner,disable_notification=True)
    #bot.send_message(1739769811,text=captioner,disable_notification=True)
    bot.send_location(1739769811,latitude=coords[socket_alert['location']][0],longitude=coords[socket_alert['location']][1],disable_notification=True,horizontal_accuracy=3) 
    return jsonify({'message': 'Alert received and saved'}), 200

@app.route('/send_alert_to_android', methods=['GET'])
def send_alert_to_android():
    if not alerts:
        return jsonify({'message': 'No alerts available'}), 404

    latest_alert = alerts[0]  

    image_urls = [request.host_url.strip('/') + image for image in latest_alert['images']]

    android_alert = {
        'id': latest_alert['id'],
        'time': latest_alert['time'],
        'date': latest_alert['date'],
        'camera_id': latest_alert['camera_id'],
        'location': latest_alert['location'],
        'url': latest_alert['url'],
        'type': latest_alert['type'],
        'objects': latest_alert['objects'],
        'severity': latest_alert['severity'],
        'images': image_urls,
        'summary': latest_alert.get('summary', ''),
        'reasoning': latest_alert.get('reasoning', ''),
        'recommendation': latest_alert.get('recommendation', ''),
        'threat_level': latest_alert.get('threat_level', 0)
    }

    return jsonify(android_alert), 200


@app.route('/get_alerts', methods=['GET'])
def get_alerts():
    count = request.args.get('count', default=None, type=int)
    
    if count:
        return jsonify(alerts[:count])
    return jsonify(alerts)

@app.route('/report')
def report():
    report_data = {
        "counts": {
            "weapons": 0,
            "mob": 0,
            "fire": 0,
            "accidents": 0,
            "ambulance": 0,
            "firetruck": 0,
            "red_light_violation": 0
        },
        "locationCounts": {},
        "latestAlerts": []
    }

    return render_template('report_template.html')


@app.route('/get_camera_feeds', methods=['GET'])
def get_camera_feeds():
    return jsonify(camera_feeds)


@app.route('/alerts/<path:filename>')
def serve_alert_image(filename):
    return send_from_directory(ALERT_IMAGE_DIR, filename)


@app.route('/download_report')
@login_required
def download_report():
    try:
        buffer = BytesIO()
        
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height-50, "Security System Report")
        p.setFont("Helvetica", 12)
        p.drawString(50, height-80, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        p.drawString(50, height-100, f"Generated by: {session.get('user', {}).get('name', 'System')}")

        data = [['Time', 'Type', 'Location', 'Severity', 'CCTV ID', 'Threat Level']]
        for alert in alerts[:50]:  
            data.append([
                f"{alert.get('time', '')} {alert.get('date', '')}",
                alert.get('type', ''),
                alert.get('location', ''),
                alert.get('severity', ''),
                alert.get('camera_id', ''),
                str(alert.get('threat_level', 'N/A'))
            ])

        table = Table(data)
        table.setStyle(TableStyle([ 
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#151757')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f6dbcc')),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))

        table.wrapOn(p, width-100, height)
        table.drawOn(p, 50, height-400)

        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, 200, "System Summary:")
        p.setFont("Helvetica", 12)
        p.drawString(50, 180, f"Total Alerts: {len(alerts)}")
        p.drawString(50, 160, f"Active Cameras: {len(camera_feeds)}")
        
        # Add detailed report section with example of last alert if available
        if alerts:
            p.showPage()
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, height-50, "Latest Alert Details")
            
            latest = alerts[0]
            
            p.setFont("Helvetica-Bold", 12)
            p.drawString(50, height-80, f"Alert ID: {latest.get('id', 'Unknown')}")
            
            p.setFont("Helvetica", 12)
            p.drawString(50, height-100, f"Time: {latest.get('time', '')} {latest.get('date', '')}")
            p.drawString(50, height-120, f"Location: {latest.get('location', 'Unknown')}")
            p.drawString(50, height-140, f"Camera ID: {latest.get('camera_id', 'Unknown')}")
            p.drawString(50, height-160, f"Threat Level: {latest.get('threat_level', 'N/A')}")
            
            # Add summary
            if latest.get('summary'):
                p.setFont("Helvetica-Bold", 12)
                p.drawString(50, height-190, "Summary:")
                p.setFont("Helvetica", 10)
                
                summary_text = latest.get('summary', '')
                text_object = p.beginText(50, height-210)
                text_object.setFont("Helvetica", 10)
                
                # Split the text to fit within page width
                words = summary_text.split()
                line = ""
                for word in words:
                    if len(line + " " + word) < 80:
                        line += " " + word if line else word
                    else:
                        text_object.textLine(line)
                        line = word
                if line:
                    text_object.textLine(line)
                
                p.drawText(text_object)
        
        p.showPage()
        p.save()

        buffer.seek(0)
        response = make_response(buffer.getvalue())
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = \
            f'attachment; filename=security_report_{datetime.now().strftime("%Y%m%d")}.pdf'
        
        return response

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)