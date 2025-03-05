from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_wtf import FlaskForm
from wtforms import FileField, StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired
import os
import uuid
from datetime import datetime
from models import db, UploadedFile, DetectedObject, ProcessingHistory
from sqlalchemy import asc, desc, distinct, func
import cv2
from ultralytics import YOLO
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///uploads.db'
app.config['UPLOAD_FOLDER'] = 'uploading'
app.config['VIDEO_FOLDER'] = 'video_folder'
app.config['RESULT_FOLDER'] = 'RESULT_FOLDER'
db.init_app(app)

with app.app_context():
    db.create_all()

class UploadForm(FlaskForm):
    file = FileField('File', validators=[DataRequired()])
    model_name = StringField('Model Name', validators=[DataRequired()])
    version = SelectField('Version', choices=[('8', '8'), ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12')], validators=[DataRequired()])
    task_type = SelectField('Task Type', choices=[('Detect', 'Detect'), ('OBB', 'OBB'), ('Segment', 'Segment'), ('Classify', 'Classify'), ('Pose', 'Pose')], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])

def detect_objects_in_video(video_path, model_path, model_id):
    if not os.path.isfile(video_path):
        flash(f"Ошибка: файл видео '{video_path}' не найден.", 'danger')
        return False, [], {}

    if not os.path.isfile(model_path):
        flash(f"Ошибка: файл модели '{model_path}' не найден.", 'danger')
        return False, [], {}

    model = YOLO(model_path)
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        flash("Ошибка: не удалось открыть видеофайл.", 'danger')
        return False, [], {}

    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    final_wide = 1000
    r = float(final_wide) / width
    dim = (final_wide, int(height * r))

    class_unique_counts = {}
    unique_track_ids = set()
    detection_logs = []
    class_summary = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.resize(frame, dim)
        results = model.track(frame, iou=0.4, conf=0.5, persist=True, imgsz=608, verbose=False, tracker="botsort.yaml")

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                label = model.model.names[cls]
                track_id = int(box.id[0]) if box.id is not None else 'N/A'

                if track_id != 'N/A':
                    if label not in class_unique_counts:
                        class_unique_counts[label] = set()
                    class_unique_counts[label].add(track_id)

                    if track_id not in unique_track_ids:
                        unique_track_ids.add(track_id)
                        image_name = f"{os.path.splitext(os.path.basename(video_path))[0]}/track_{track_id}_{uuid.uuid4()}.jpg"
                        image_path = os.path.join(app.config['RESULT_FOLDER'], image_name)
                        os.makedirs(os.path.dirname(image_path), exist_ok=True)

                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(frame, f"{label} ID:{track_id}", (x1, y1 - 10), cv2.FONT_HERSHEY_COMPLEX, 0.9, (0, 255, 0), 2)
                        cv2.imwrite(image_path, frame)

                        detection_datetime = datetime.utcnow()
                        detected_object = DetectedObject(
                            uploaded_file_id=model_id,
                            detection_datetime=detection_datetime,
                            image_name=image_name,
                            video_name=os.path.basename(video_path),
                            folder=os.path.dirname(image_path),
                            class_name=label,
                            processing_number=track_id,
                            description=f"Обнаружен {label} с ID {track_id}"
                        )
                        db.session.add(detected_object)
                        detection_logs.append({
                            'image_name': image_name,
                            'class_name': label,
                            'detection_datetime': detection_datetime.strftime('%Y-%m-%d %H:%M:%S')
                        })
                        class_summary[label] = class_summary.get(label, 0) + 1

        y_offset = 15
        for class_name, unique_ids in class_unique_counts.items():
            count = len(unique_ids)
            cv2.putText(frame, f'{class_name}: {count}', (10, y_offset), cv2.FONT_HERSHEY_COMPLEX, 0.4, (0, 255, 0), 1)
            y_offset += 15

    cap.release()
    cv2.destroyAllWindows()
    db.session.commit()
    return True, detection_logs, class_summary

@app.route('/')
def index():
    return render_template('base.html', current_page='index')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        model_name = form.model_name.data
        version = form.version.data
        task_type = form.task_type.data
        description = form.description.data

        today = datetime.now().strftime('%Y-%m-%d')
        upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], today)
        os.makedirs(upload_folder, exist_ok=True)

        guid = uuid.uuid4()
        filename = f"{guid}_{file.filename}"
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        uploaded_file = UploadedFile(
            model_name=model_name,
            version=version,
            task_type=task_type,
            description=description,
            file_path=file_path,
            original_filename=file.filename,
            filename_without_guid=file.filename,
            upload_datetime=datetime.utcnow()
        )
        db.session.add(uploaded_file)
        db.session.commit()

        return redirect(url_for('view_files'))
    return render_template('upload.html', form=form, current_page='upload')

@app.route('/view', methods=['GET'])
def view_files():
    model_name = request.args.get('model_name')
    version = request.args.get('version')
    task_type = request.args.get('task_type')
    sort_by = request.args.get('sort_by', 'upload_datetime')
    sort_dir = request.args.get('sort_dir', 'desc')

    query = UploadedFile.query
    if model_name:
        query = query.filter(UploadedFile.model_name.ilike(f'%{model_name}%'))
    if version:
        query = query.filter_by(version=version)
    if task_type:
        query = query.filter_by(task_type=task_type)

    sortable_fields = {
        'id': UploadedFile.id,
        'model_name': UploadedFile.model_name,
        'version': UploadedFile.version,
        'task_type': UploadedFile.task_type,
        'description': UploadedFile.description,
        'filename_without_guid': UploadedFile.filename_without_guid,
        'upload_datetime': UploadedFile.upload_datetime
    }

    if sort_by in sortable_fields:
        sort_column = sortable_fields[sort_by]
        if sort_dir == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

    files = query.all()
    unique_model_names = [row[0] for row in db.session.query(distinct(UploadedFile.model_name)).all()]
    return render_template(
        'view.html',
        files=files,
        current_page='view',
        sort_by=sort_by,
        sort_dir=sort_dir,
        unique_model_names=unique_model_names
    )

@app.route('/download/<int:file_id>')
def download_file(file_id):
    uploaded_file = UploadedFile.query.get_or_404(file_id)
    directory, filename = os.path.split(uploaded_file.file_path)
    return send_from_directory(directory, filename, as_attachment=True, download_name=uploaded_file.original_filename)

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    uploaded_file = UploadedFile.query.get_or_404(file_id)
    try:
        os.remove(uploaded_file.file_path)
        db.session.delete(uploaded_file)
        db.session.commit()
        flash('File deleted successfully', 'success')
    except Exception as e:
        flash(f'Error deleting file: {e}', 'danger')
    return redirect(url_for('view_files'))

@app.route('/process_video', methods=['GET', 'POST'])
def process_video():
    detection_logs = []
    class_summary = {}
    if request.method == 'POST':
        video_file = request.files.get('video_file')
        model_id = request.form.get('file_select')

        if not video_file or not video_file.filename:
            flash('Пожалуйста, выберите видеофайл', 'danger')
            return redirect(url_for('process_video'))

        if not model_id:
            flash('Пожалуйста, выберите модель перед обработкой', 'danger')
            return redirect(url_for('process_video'))

        os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)
        guid = uuid.uuid4()
        video_filename = f"{guid}_{video_file.filename}"
        video_path = os.path.join(app.config['VIDEO_FOLDER'], video_filename)
        video_file.save(video_path)

        model_file = UploadedFile.query.get(model_id)
        if model_file:
            start_time = time.time()
            start_datetime = datetime.utcnow()
            model_path = model_file.file_path
            success, detection_logs, class_summary = detect_objects_in_video(video_path, model_path, model_id)
            end_time = time.time()
            processing_time = end_time - start_time
            minutes = int(processing_time // 60)
            seconds = int(processing_time % 60)
            if success:
                flash(f'Обработка видео завершена успешно. Время обработки: {minutes}:{seconds:02d}', 'success')
                # Save to ProcessingHistory
                history_entry = ProcessingHistory(
                    model_name=model_file.model_name,
                    video_name=os.path.splitext(video_file.filename)[0],  # Remove GUID and extension
                    start_datetime=start_datetime,
                    processing_time=processing_time,
                    object_count=sum(class_summary.values())
                )
                db.session.add(history_entry)
                db.session.commit()
        else:
            flash('Ошибка: выбранная модель не найдена', 'danger')

    files = UploadedFile.query.all()
    return render_template('process_video.html', current_page='process_video', files=files, detection_logs=detection_logs, class_summary=class_summary)

@app.route('/reports', methods=['GET'])
def reports():
    summary_query = (db.session.query(
        UploadedFile.model_name,
        DetectedObject.video_name,
        DetectedObject.class_name,
        func.count(DetectedObject.class_name).label('class_count')
    )
    .join(DetectedObject, UploadedFile.id == DetectedObject.uploaded_file_id)
    .group_by(UploadedFile.model_name, DetectedObject.video_name, DetectedObject.class_name)
    .order_by(UploadedFile.model_name, DetectedObject.video_name)
    .all())

    summary_data = {}
    for model_name, video_name, class_name, class_count in summary_query:
        if model_name not in summary_data:
            summary_data[model_name] = {}
        if video_name not in summary_data[model_name]:
            summary_data[model_name][video_name] = []
        summary_data[model_name][video_name].append((class_name, class_count))

    return render_template('reports.html', current_page='reports', summary_data=summary_data)

@app.route('/found_images', methods=['GET'])
def found_images():
    video_name_filter = request.args.get('video_name', '')
    model_name_filter = request.args.get('model_name', '')
    upload_id_filter = request.args.get('upload_id', '')
    show_results = request.args.get('filter', 'false') == 'true'

    detected_objects = []
    if show_results:
        query = DetectedObject.query
        if video_name_filter:
            query = query.filter(DetectedObject.video_name.ilike(f'%{video_name_filter}%'))
        if model_name_filter:
            query = query.join(UploadedFile).filter(UploadedFile.model_name.ilike(f'%{model_name_filter}%'))
        if upload_id_filter:
            query = query.filter(DetectedObject.uploaded_file_id == upload_id_filter)
        detected_objects = query.all()

    unique_video_names = [row[0] for row in db.session.query(distinct(DetectedObject.video_name)).all()]
    unique_model_names = [row[0] for row in db.session.query(distinct(UploadedFile.model_name)).join(DetectedObject).all()]
    unique_upload_ids = [row[0] for row in db.session.query(distinct(DetectedObject.uploaded_file_id)).all()]
    return render_template('found_images.html', current_page='found_images', detected_objects=detected_objects,
                         video_name_filter=video_name_filter, model_name_filter=model_name_filter, upload_id_filter=upload_id_filter,
                         unique_video_names=unique_video_names, unique_model_names=unique_model_names, unique_upload_ids=unique_upload_ids,
                         show_results=show_results)

@app.route('/processing_history', methods=['GET'])
def processing_history():
    history_entries = ProcessingHistory.query.order_by(ProcessingHistory.created_at.desc()).all()
    return render_template('processing_history.html', current_page='processing_history', history_entries=history_entries)

@app.route('/results/<path:filename>')
def serve_result_image(filename):
    return send_from_directory(app.config['RESULT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)