from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_wtf import FlaskForm
from wtforms import FileField, StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired
import os
import uuid
from datetime import datetime
from models import db, UploadedFile, DetectedObject
from sqlalchemy import asc, desc

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///uploads.db'
app.config['UPLOAD_FOLDER'] = 'uploading'
app.config['VIDEO_FOLDER'] = 'video_folder'  # New folder for video uploads
db.init_app(app)

with app.app_context():
    db.create_all()

class UploadForm(FlaskForm):
    file = FileField('File', validators=[DataRequired()])
    model_name = StringField('Model Name', validators=[DataRequired()])
    version = SelectField('Version', choices=[('8', '8'), ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12')], validators=[DataRequired()])
    task_type = SelectField('Task Type', choices=[('Detect', 'Detect'), ('OBB', 'OBB'), ('Segment', 'Segment'), ('Classify', 'Classify'), ('Pose', 'Pose')], validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    en_classes = TextAreaField('EN Classes', validators=[DataRequired()])
    ru_classes = TextAreaField('RU Classes', validators=[DataRequired()])
    colors = TextAreaField('Colors', validators=[DataRequired()])

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
        en_classes = form.en_classes.data
        ru_classes = form.ru_classes.data
        colors = form.colors.data

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
            en_classes=en_classes,
            ru_classes=ru_classes,
            colors=colors,
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
        'model_name': UploadedFile.model_name,
        'version': UploadedFile.version,
        'task_type': UploadedFile.task_type,
        'description': UploadedFile.description,
        'en_classes': UploadedFile.en_classes,
        'ru_classes': UploadedFile.ru_classes,
        'colors': UploadedFile.colors,
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
    return render_template(
        'view.html',
        files=files,
        current_page='view',
        sort_by=sort_by,
        sort_dir=sort_dir
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
    if request.method == 'POST':
        video_file = request.files.get('video_file')
        if video_file and video_file.filename:
            os.makedirs(app.config['VIDEO_FOLDER'], exist_ok=True)
            guid = uuid.uuid4()
            filename = f"{guid}_{video_file.filename}"
            file_path = os.path.join(app.config['VIDEO_FOLDER'], filename)
            video_file.save(file_path)
            flash(f'Видео {video_file.filename} успешно загружено', 'success')
            return redirect(url_for('process_video'))

    files = UploadedFile.query.all()
    return render_template('process_video.html', current_page='process_video', files=files)

@app.route('/video_file_processing', methods=['POST'])
def video_file_processing():
    test_data = [
        {
            'model_name': 'Model1',
            'image_name': 'test_image1.jpg',
            'video_name': 'test_video1.mp4',
            'folder': 'test_folder1',
            'class_name': 'Car',
            'processing_number': 1,
            'description': 'Обнаружен автомобиль на видео 1'
        },
        {
            'model_name': 'Model2',
            'image_name': 'test_image2.png',
            'video_name': 'test_video2.mp4',
            'folder': 'test_folder2',
            'class_name': 'Person',
            'processing_number': 2,
            'description': 'Обнаружен человек на видео 2'
        },
        {
            'model_name': 'Model3',
            'image_name': 'test_image3.jpg',
            'video_name': 'test_video3.mp4',
            'folder': 'test_folder3',
            'class_name': 'Tree',
            'processing_number': 3,
            'description': 'Обнаружено дерево на видео 3'
        }
    ]

    for data in test_data:
        detected_object = DetectedObject(
            model_name=data['model_name'],
            detection_datetime=datetime.utcnow(),
            image_name=data['image_name'],
            video_name=data['video_name'],
            folder=data['folder'],
            class_name=data['class_name'],
            processing_number=data['processing_number'],
            description=data['description']
        )
        db.session.add(detected_object)
    
    db.session.commit()
    flash('Тестовые данные успешно добавлены', 'success')
    return redirect(url_for('process_video'))

@app.route('/reports')
def reports():
    return render_template('reports.html', current_page='reports')

@app.route('/found_images')
def found_images():
    detected_objects = DetectedObject.query.all()
    return render_template('found_images.html', current_page='found_images', detected_objects=detected_objects)

if __name__ == '__main__':
    app.run(debug=True)