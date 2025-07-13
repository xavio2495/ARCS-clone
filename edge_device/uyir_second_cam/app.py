import cv2
import time
import torch
import requests
import base64
import numpy as np
import json
from flask import Flask, Response
from datetime import datetime
from ultralytics import YOLO
from PIL import Image
from io import BytesIO
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI  # Updated import

app = Flask(__name__)

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_KEY = ""
OPENAI_MODEL = ""
API_VERSION = ""

# Configure OpenAI API client for Azure - using the new format
client = AzureOpenAI(
    api_key=AZURE_OPENAI_KEY,
    api_version=API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

model = YOLO("models/best.onnx")
CONFIDENCE_THRESHOLD = 0.60  

ALERT_COOLDOWN = 20  # Seconds between alerts
last_alert_time = time.time() - ALERT_COOLDOWN  # Initialize to allow immediate first alert
VERIFICATION_FRAMES = 3  
verification_counter = 0 

# Flag to track if we're in alert cooldown period
alert_sent = False

MAIN_SERVER_URL = "http://172.20.10.5:5000/update_feed"
ALERT_SERVER_URL = "http://172.20.10.5:5000/alert"

CAMERA_ID = "primary"
CAMERA_LOCATION = "Gandhipuram"
POLICE_STATION = "City Police Station"
CAMERA_STREAM_URL = "http://172.20.10.8:5003/video_feed"

AZURE_STORAGE_CONNECTION_STRING = ""
CONTAINER_NAME = "threatlevelevidence"

try:
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    
    if not container_client.exists():
        container_client.create_container()
        print(f"✅ Created Azure container: {CONTAINER_NAME}")
    azure_connected = True
except Exception as e:
    print(f"⚠️ Azure Storage initialization failed: {str(e)}")
    azure_connected = False

def notify_main_server():
    """Notifies the main server that the camera feed is active."""
    try:
        data = {
            "camera_id": CAMERA_ID,
            "url": CAMERA_STREAM_URL,
            "object": "gun"
        }
        response = requests.post(MAIN_SERVER_URL, json=data, timeout=15)
        if response.status_code == 200:
            print(f"✅ Camera feed registered: {CAMERA_ID}")
        else:
            print(f"❌ Failed to update main server. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error notifying main server: {e}")

def upload_alert_to_azure(frame, metadata):
    """
    Uploads alert data to Azure Blob Storage in a folder structure.
    Creates a unique folder for each alert and stores both the image and metadata JSON.
    
    Args:
        frame: The camera frame with the detection
        metadata: Dict containing all alert metadata
    
    Returns:
        dict: URLs for the stored files
    """
    if not azure_connected:
        return None
    
    try:
        # Generate a unique alert ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        alert_id = f"alert_{CAMERA_ID}_{timestamp}"
        
        # Create folder path with alert_id
        folder_path = f"{alert_id}/"
        
        # Convert frame to image bytes
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img)
        
        img_bytes = BytesIO()
        pil_img.save(img_bytes, format='PNG', optimize=True, quality=95)
        img_bytes.seek(0)
        
        # Create image file path
        image_blob_name = f"{folder_path}evidence.png"
        
        # Upload image
        image_blob_client = container_client.get_blob_client(image_blob_name)
        image_blob_client.upload_blob(img_bytes, overwrite=True)
        image_url = image_blob_client.url
        
        # Prepare metadata for JSON storage
        # Remove the base64 image data to avoid redundant storage
        metadata_copy = metadata.copy()
        
        # Store the path to the image instead of the base64 data
        if "image" in metadata_copy:
            del metadata_copy["image"]
        
        metadata_copy["image_path"] = image_blob_name
        metadata_copy["alert_id"] = alert_id
        
        # Convert metadata to JSON
        metadata_json = json.dumps(metadata_copy, indent=2)
        metadata_bytes = BytesIO(metadata_json.encode('utf-8'))
        
        # Create metadata file path
        metadata_blob_name = f"{folder_path}metadata.json"
        
        # Upload metadata
        metadata_blob_client = container_client.get_blob_client(metadata_blob_name)
        metadata_blob_client.upload_blob(metadata_bytes, overwrite=True)
        metadata_url = metadata_blob_client.url
        
        print(f"✅ Alert data uploaded to Azure: {alert_id}")
        
        return {
            "alert_id": alert_id,
            "image_url": image_url,
            "metadata_url": metadata_url,
            "folder": folder_path
        }
            
    except Exception as e:
        print(f"❌ Azure upload error: {str(e)}")
        return None

def calculate_threat_level(confidence, object_size_ratio, center_proximity):
    """
    Calculate a threat level based on multiple factors:
    - Detection confidence
    - Object size relative to frame
    - Proximity to center of frame (more centered = higher threat)
    
    Returns a value between 0-100
    """
    confidence_weight = 0.5
    size_weight = 0.3
    center_weight = 0.2
    
    threat_level = (
        (confidence * 100) * confidence_weight +
        (object_size_ratio * 100) * size_weight +
        (center_proximity * 100) * center_weight
    )
    
    return min(100, max(0, threat_level))

def analyze_threat_with_ai(detected_object, confidence, threat_level, object_size_ratio, center_proximity):
    """
    Use Azure OpenAI to analyze the threat and generate summary, reasoning, and recommendations.
    
    Args:
        detected_object: The type of object detected (e.g., "gun")
        confidence: Detection confidence (0-1)
        threat_level: Calculated threat level (0-100)
        object_size_ratio: Size of the object relative to frame (0-1)
        center_proximity: How centered the object is in frame (0-1)
        
    Returns:
        dict: Contains summary, reasoning, and recommendation
    """
    try:
        # Prepare detection data for the AI
        detection_data = {
            "detected_object": detected_object,
            "confidence": f"{confidence:.2f}",
            "threat_level": f"{threat_level:.1f}",
            "object_size_ratio": f"{object_size_ratio:.2f}",
            "center_proximity": f"{center_proximity:.2f}",
            "location": CAMERA_LOCATION,
            "camera_id": CAMERA_ID
        }
        
        # Create prompt for summarization
        system_prompt = """
        You are an advanced security threat analysis system. 
        Your task is to assess security camera detections and provide accurate, professional analysis.
        Provide three separate sections:
        1. SUMMARY: A concise one-sentence summary of the threat detection
        2. REASONING: A detailed analysis explaining why this detection represents the estimated threat level
        3. RECOMMENDATION: Concrete action steps based on the threat level
        
        Keep your responses professional, factual, and security-oriented.
        """
        
        user_prompt = f"""
        Analyze this security camera detection:
        
        - Object Detected: {detected_object}
        - Detection Confidence: {confidence:.2f} (scale of 0-1)
        - Object Size Ratio: {object_size_ratio:.2f} (portion of frame, 0-1)
        - Center Proximity: {center_proximity:.2f} (how centered in frame, 0-1)
        - Overall Threat Level: {threat_level:.1f} (scale of 0-100)
        - Location: {CAMERA_LOCATION}
        - Camera ID: {CAMERA_ID}
        
        Provide a SUMMARY (one sentence), REASONING (detailed threat analysis), and RECOMMENDATION (specific actions).
        """
        
        # Call Azure OpenAI API using the new API format
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent responses
            max_tokens=800
        )
        
        # Extract the response text - updated to work with new response format
        analysis_text = response.choices[0].message.content
        
        # Parse the sections from the response
        summary = ""
        reasoning = ""
        recommendation = ""
        
        # Simple parsing by looking for section headers
        sections = analysis_text.split("\n\n")
        for section in sections:
            if section.startswith("SUMMARY:"):
                summary = section.replace("SUMMARY:", "").strip()
            elif section.startswith("REASONING:"):
                reasoning = section.replace("REASONING:", "").strip()
            elif section.startswith("RECOMMENDATION:"):
                recommendation = section.replace("RECOMMENDATION:", "").strip()
        
        # Handle case where AI didn't use the expected format
        if not summary or not reasoning or not recommendation:
            # Try alternate parsing
            if "SUMMARY" in analysis_text:
                parts = analysis_text.split("SUMMARY")
                if len(parts) > 1:
                    summary_section = parts[1].split("REASONING")[0].strip()
                    summary = summary_section.strip(": \n")
            
            if "REASONING" in analysis_text:
                parts = analysis_text.split("REASONING")
                if len(parts) > 1:
                    reasoning_section = parts[1].split("RECOMMENDATION")[0].strip()
                    reasoning = reasoning_section.strip(": \n")
            
            if "RECOMMENDATION" in analysis_text:
                parts = analysis_text.split("RECOMMENDATION")
                if len(parts) > 1:
                    recommendation = parts[1].strip(": \n")
        
        # If any section is still empty, provide fallback responses
        if not summary:
            summary = f"{detected_object.capitalize()} detected with {confidence:.0%} confidence. Threat level: {threat_level:.0f}/100."
        
        if not reasoning:
            reasoning = f"Detection confidence: {confidence:.2f}\nObject size: {object_size_ratio:.2f}\nPosition in frame: {center_proximity:.2f}\nCombined threat level: {threat_level:.1f}/100"
        
        if not recommendation:
            if threat_level > 70:
                recommendation = "Immediate response required. Dispatch security personnel and notify authorities."
            elif threat_level > 40:
                recommendation = "Increase surveillance and prepare response team."
            else:
                recommendation = "Continue monitoring the situation."
        
        print(f"✅ AI Analysis Complete")
        return {
            "summary": summary,
            "reasoning": reasoning,
            "recommendation": recommendation
        }
        
    except Exception as e:
        print(f"❌ AI Analysis failed: {str(e)}")
        # Fall back to rule-based analysis if AI fails
        
        # Generate summary based on rules
        size_description = "small"
        if object_size_ratio > 0.4:
            size_description = "large"
        elif object_size_ratio > 0.2:
            size_description = "medium"
        
        position_description = "periphery"
        if center_proximity > 0.7:
            position_description = "center"
        elif center_proximity > 0.4:
            position_description = "mid-frame"
        
        confidence_description = "possible"
        if confidence > 0.85:
            confidence_description = "confirmed"
        elif confidence > 0.75:
            confidence_description = "likely"
        
        threat_description = "low"
        if threat_level > 80:
            threat_description = "severe"
        elif threat_level > 60:
            threat_description = "high"
        elif threat_level > 40:
            threat_description = "moderate"
        
        summary = f"{confidence_description.capitalize()} {detected_object} detection of {size_description} size in {position_description} of frame. Threat level: {threat_description.upper()}."
        
        # Generate reasoning based on rules
        reasoning = f"Threat assessment is based on multiple factors:\n\n"
        reasoning += f"1. Detection Confidence: {confidence:.2f}\n"
        reasoning += f"2. Object Size: {object_size_ratio:.2f}\n"
        reasoning += f"3. Position in Frame: {center_proximity:.2f}\n"
        reasoning += f"Combined assessment results in a threat level of {threat_level:.1f}/100."
        
        # Generate recommendation based on rules
        if threat_level > 80:
            recommendation = "URGENT ACTION REQUIRED: Immediate police response recommended."
        elif threat_level > 60:
            recommendation = "HIGH PRIORITY RESPONSE: Dispatch police to location."
        elif threat_level > 40:
            recommendation = "MODERATE RESPONSE ADVISED: Notify patrolling officers."
        else:
            recommendation = "LOW PRIORITY MONITORING: Continue monitoring situation."
            
        return {
            "summary": summary,
            "reasoning": reasoning,
            "recommendation": recommendation
        }

def send_alert(frame, detected_object, confidence, threat_level, object_size_ratio=0, center_proximity=0):
    """Sends alert to server with image, metadata, threat assessment, and recommendations."""
    try:
        _, buffer = cv2.imencode('.jpg', frame)
        base64_image = base64.b64encode(buffer).decode('utf-8')
        
        # Use AI to generate analysis instead of rule-based functions
        ai_analysis = analyze_threat_with_ai(
            detected_object, 
            confidence, 
            threat_level, 
            object_size_ratio, 
            center_proximity
        )
        
        summary = ai_analysis["summary"]
        reasoning = ai_analysis["reasoning"]
        recommendation = ai_analysis["recommendation"]

        # Create complete metadata object
        metadata = {
            "camera_id": CAMERA_ID,
            "location": CAMERA_LOCATION,
            "url": CAMERA_STREAM_URL,
            "police_station": POLICE_STATION,
            "object_detected": detected_object,
            "confidence": float(confidence),
            "threat_level": int(threat_level),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.now().strftime("%H:%M:%S"),
            "image": base64_image,  # Will be removed before storage in Azure
            "summary": summary,
            "reasoning": reasoning,
            "recommendation": recommendation,
            "object_size_ratio": float(object_size_ratio),
            "center_proximity": float(center_proximity)
        }
        
        # Upload alert data to Azure and get URLs
        azure_data = upload_alert_to_azure(frame, metadata)
        
        if azure_data:
            # Add Azure storage info to the data we send to the alert server
            metadata["alert_id"] = azure_data["alert_id"]
            metadata["evidence_url"] = azure_data["image_url"]
            metadata["metadata_url"] = azure_data["metadata_url"]
            metadata["azure_folder"] = azure_data["folder"]

        # Send alert data to alert server
        response = requests.post(ALERT_SERVER_URL, json=metadata, timeout=15)
        
        if response.status_code == 200:
            print(f"🚨 Alert sent successfully: {detected_object} (Threat Level: {threat_level:.1f})")
            print(f"✅ Summary: {summary}")
            if azure_data:
                print(f"✅ Data stored in Azure: {azure_data['alert_id']}")
        else:
            print(f"❌ Failed to send alert. Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Error sending alert: {e}")

def generate_frames():
    """Captures frames, runs YOLO ONNX inference, and streams video with verification."""
    global last_alert_time, verification_counter, alert_sent

    cap = cv2.VideoCapture(0) 

    if not cap.isOpened():
        print("❌ Failed to open camera")
        return

    notify_main_server()  

    ret, test_frame = cap.read()
    if ret:
        frame_height, frame_width = test_frame.shape[:2]
        frame_center_x = frame_width / 2
        frame_center_y = frame_height / 2
        frame_area = frame_width * frame_height
    else:
        frame_width, frame_height = 640, 480
        frame_center_x, frame_center_y = 320, 240
        frame_area = frame_width * frame_height
    
    print(f"✅ Camera initialized: {frame_width}x{frame_height}")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            print("❌ Failed to read frame")
            time.sleep(1) 
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) 
        results = model(frame_rgb)  
        gun_detected = False
        max_confidence = 0
        gun_box = None

        for result in results:
            for box in result.boxes:
                confidence = box.conf[0].item()
                if confidence < CONFIDENCE_THRESHOLD:  
                    continue  

                class_index = int(box.cls[0].item())
                class_name = model.names[class_index]

                if class_name.lower() == "guns":
                    gun_detected = True
                    if confidence > max_confidence:
                        max_confidence = confidence
                        gun_box = box.xyxy[0].tolist()  
                    
                    x1, y1, x2, y2 = map(int, box.xyxy[0])  
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    label = f"{class_name} ({confidence:.2f})"
                    cv2.putText(frame, label, (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        current_time = time.time()
        
        # Check if cooldown period has passed
        if current_time - last_alert_time >= ALERT_COOLDOWN:
            # Reset alert_sent flag after cooldown
            alert_sent = False
                
        if gun_detected:
            verification_counter += 1
            
            if verification_counter >= VERIFICATION_FRAMES and not alert_sent:
                print(f"⚠️ Gun verified: {verification_counter} consecutive frames")
                
                x1, y1, x2, y2 = map(float, gun_box)
                box_width = x2 - x1
                box_height = y2 - y1
                box_area = box_width * box_height
                
                # Calculate object size ratio (0-1)
                object_size_ratio = min(1.0, box_area / frame_area)
                
                # Calculate center proximity (0-1)
                box_center_x = (x1 + x2) / 2
                box_center_y = (y1 + y2) / 2
                distance_from_center = ((box_center_x - frame_center_x) ** 2 + 
                                       (box_center_y - frame_center_y) ** 2) ** 0.5
                max_distance = ((frame_width/2) ** 2 + (frame_height/2) ** 2) ** 0.5
                center_proximity = 1.0 - (distance_from_center / max_distance)
                
                # Calculate overall threat level
                threat_level = calculate_threat_level(
                    max_confidence, 
                    object_size_ratio,
                    center_proximity
                )
                
                # Add threat level info to frame
                threat_info = f"Threat Level: {threat_level:.1f}"
                cv2.putText(frame, threat_info, (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Get AI-generated summary for display
                ai_analysis = analyze_threat_with_ai(
                    "gun", 
                    max_confidence, 
                    threat_level, 
                    object_size_ratio, 
                    center_proximity
                )
                summary_short = ai_analysis["summary"]
                if len(summary_short) > 60:
                    summary_short = summary_short[:57] + "..."
                    
                cv2.putText(frame, summary_short, (10, 60), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                
                # Send alert with enriched data
                send_alert(
                    frame, 
                    "gun", 
                    max_confidence, 
                    threat_level,
                    object_size_ratio,
                    center_proximity
                )
                last_alert_time = current_time
                alert_sent = True
                print(f"🔒 Alert cooldown activated for {ALERT_COOLDOWN} seconds")
        else:
            # Reset verification counter if no gun detected
            verification_counter = 0

        # Add status overlay with more informative messages
        if alert_sent:
            cooldown_remaining = max(0, ALERT_COOLDOWN - (current_time - last_alert_time))
            status_text = f"Status: ALERT SENT (Cooldown: {int(cooldown_remaining)}s)"
            status_color = (0, 0, 255)  # Red for alert sent
        elif verification_counter > 0:
            status_text = f"Status: VERIFYING ({verification_counter}/{VERIFICATION_FRAMES})"
            status_color = (0, 165, 255)  # Orange for verifying
        else:
            status_text = "Status: MONITORING"
            status_color = (0, 255, 0)  # Green for monitoring
            
        cv2.putText(frame, status_text, (10, frame_height - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        # Add timestamp overlay
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (frame_width - 210, frame_height - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        _, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    cap.release()

@app.route('/video_feed')
def video_feed():
    """Endpoint to serve video feed."""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/')
def index():
    """Simple status page showing the app is running."""
    status_html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Gun Detection System</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                h1 { color: #333; }
                .status { padding: 20px; background-color: #f0f0f0; border-left: 4px solid #4CAF50; }
                .camera { margin-top: 20px; border: 1px solid #ddd; padding: 10px; }
                .camera img { width: 100%; max-width: 640px; }
                .features { margin-top: 20px; background-color: #f8f9fa; padding: 15px; border-radius: 8px; }
                .features h3 { color: #2196F3; }
                .feature-item { padding: 8px; border-left: 3px solid #2196F3; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <h1>Gun Detection System</h1>
            <div class="status">
                <p><strong>Status:</strong> Active</p>
                <p><strong>Camera ID:</strong> """ + CAMERA_ID + """</p>
                <p><strong>Location:</strong> """ + CAMERA_LOCATION + """</p>
                <p><strong>Azure Storage:</strong> """ + ("Connected" if azure_connected else "Disconnected") + """</p>
                <p><strong>Alert Cooldown:</strong> """ + str(ALERT_COOLDOWN) + """ seconds</p>
                <p><strong>AI Analysis:</strong> Azure OpenAI (""" + OPENAI_MODEL + """)</p>
            </div>
            <div class="features">
                <h3>Enhanced AI Threat Analysis</h3>
                <div class="feature-item">
                    <strong>Summary:</strong> AI-generated threat assessment
                </div>
                <div class="feature-item">
                    <strong>Reasoning:</strong> Dynamic AI analysis of threat factors
                </div>
                <div class="feature-item">
                    <strong>Recommendation:</strong> Context-aware response guidance
                </div>
                <div class="feature-item">
                    <strong>Storage:</strong> All alerts saved to Azure with unique IDs
                </div>
            </div>
            <div class="camera">
                <h2>Live Camera Feed</h2>
                <img src="/video_feed" alt="Live Camera Feed">
            </div>
        </body>
    </html>
    """
    return status_html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
