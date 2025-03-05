from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(10), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    filename_without_guid = db.Column(db.String(255), nullable=False)
    upload_datetime = db.Column(db.DateTime, default=datetime.utcnow)

class DetectedObject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uploaded_file_id = db.Column(db.Integer, db.ForeignKey('uploaded_file.id'), nullable=False)
    detection_datetime = db.Column(db.DateTime, default=datetime.utcnow)
    image_name = db.Column(db.String(255), nullable=False)
    video_name = db.Column(db.String(255), nullable=False)
    folder = db.Column(db.String(255), nullable=False)
    class_name = db.Column(db.String(255), nullable=False)
    processing_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)
    uploaded_file = db.relationship('UploadedFile', backref='detected_objects')

class ProcessingHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    video_name = db.Column(db.String(255), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    processing_time = db.Column(db.Float, nullable=False)  # In seconds
    object_count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)