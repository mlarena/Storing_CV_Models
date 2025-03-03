from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    version = db.Column(db.String(10), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    en_classes = db.Column(db.Text, nullable=False)
    ru_classes = db.Column(db.Text, nullable=False)
    colors = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    filename_without_guid = db.Column(db.String(255), nullable=False)
    upload_datetime = db.Column(db.DateTime, default=datetime.utcnow)

class DetectedObject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(255), nullable=False)
    detection_datetime = db.Column(db.DateTime, default=datetime.utcnow)
    image_name = db.Column(db.String(255), nullable=False)
    video_name = db.Column(db.String(255), nullable=False)
    folder = db.Column(db.String(255), nullable=False)
    class_name = db.Column(db.String(255), nullable=False)
    processing_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, nullable=False)  # Added description field

    def __repr__(self):
        return f"<DetectedObject {self.model_name} - {self.image_name}>"