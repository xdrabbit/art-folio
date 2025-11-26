import os
from flask import Flask, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timezone
import subprocess
import tempfile

app = Flask(__name__)
CORS(app)

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'artfolio.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class ArtGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    items = db.relationship('ArtItem', backref='group', lazy=True, cascade="all, delete-orphan")

class ArtItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('art_group.id'), nullable=False)
    versions = db.relationship('ArtVersion', backref='item', lazy=True, cascade="all, delete-orphan")

class ArtVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    # store a timezone-aware datetime object (SQLAlchemy will handle conversion)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    item_id = db.Column(db.Integer, db.ForeignKey('art_item.id'), nullable=False)

# --- API Endpoints ---

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"}), 200

# --- Group Management ---
@app.route('/api/groups', methods=['POST'])
def create_group():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Group name is required"}), 400
    if ArtGroup.query.filter_by(name=data['name']).first():
        return jsonify({"error": "Group name already exists"}), 409
        # optional interpolation (increase fps to create smoother motion)
        interpolate = int(request.args.get('interpolate', 1)) if request.args.get('interpolate') else 1
        base_fps = int(request.args.get('fps', 25))
        if interpolate and interpolate > 1:
            interp_out = out_path.replace('.mp4', f'.interp_{interpolate}x.mp4')
            target_fps = base_fps * interpolate
            cmd2 = [
                'ffmpeg', '-y', '-i', out_path,
                '-vf', f"minterpolate=fps={target_fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1",
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '20', interp_out
            ]
            try:
                subprocess.run(cmd2, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                # use interpolated file as final
                out_path = interp_out
                out_name = os.path.basename(interp_out)
            except subprocess.CalledProcessError as e:
                return jsonify({"error": "ffmpeg interpolation failed", "details": e.stderr.decode('utf-8', 'ignore')}), 500
    
    new_group = ArtGroup(name=data['name'])
    db.session.add(new_group)
    db.session.commit()
    return jsonify({"id": new_group.id, "name": new_group.name}), 201

@app.route('/api/groups', methods=['GET'])
def get_groups():
    groups = ArtGroup.query.all()
    return jsonify([{"id": g.id, "name": g.name} for g in groups])

@app.route('/api/groups/<int:group_id>/items', methods=['GET'])
def get_items_in_group(group_id):
    group = ArtGroup.query.get_or_404(group_id)
    items = ArtItem.query.filter_by(group_id=group.id).all()
    return jsonify([{"id": i.id, "name": i.name} for i in items])

# --- Item & Version Management ---
@app.route('/api/items', methods=['POST'])
def create_item():
    data = request.get_json()
    if not data or not all(k in data for k in ['name', 'group_id']):
        return jsonify({"error": "Missing name or group_id"}), 400
    
    group = ArtGroup.query.get(data['group_id'])
    if not group:
        return jsonify({"error": "Group not found"}), 404
        
    new_item = ArtItem(name=data['name'], group_id=data['group_id'])
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"id": new_item.id, "name": new_item.name, "group_id": new_item.group_id}), 201

@app.route('/api/items/<int:item_id>/versions', methods=['POST'])
def upload_version(item_id):
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    item = ArtItem.query.get_or_404(item_id)
    
    # Create a unique filename
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    
    # Ensure upload directory exists
    group_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(item.group_id))
    item_dir = os.path.join(group_dir, str(item.id))
    os.makedirs(item_dir, exist_ok=True)
    
    storage_path = os.path.join(item_dir, filename)
    file.save(storage_path)

    # store relative path (inside uploads) so serving is predictable and DB rows are small
    relpath = os.path.join(str(item.group_id), str(item.id), filename)
    created_at_dt = datetime.now(timezone.utc)
    version = ArtVersion(item_id=item_id, filename=filename, filepath=relpath, created_at=created_at_dt)
    db.session.add(version)
    db.session.commit()
    
    return jsonify({
        "id": version.id,
        "filename": version.filename,
        "url": f"/media/{item.group_id}/{item.id}/{filename}"
    }), 201

@app.route('/api/items/<int:item_id>/versions', methods=['GET'])
def get_versions(item_id):
    item = ArtItem.query.get_or_404(item_id)
    versions = ArtVersion.query.filter_by(item_id=item.id).order_by(ArtVersion.created_at.desc()).all()
    return jsonify([{
        "id": v.id,
        "filename": v.filename,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "url": f"/media/{item.group_id}/{item.id}/{v.filename}"
    } for v in versions])


@app.route('/api/items/<int:item_id>/timelapse', methods=['POST'])
def create_timelapse(item_id):
    """Create a simple MP4 timelapse from an item's versions using ffmpeg.
    Requires `ffmpeg` available on PATH. Produces uploads/<group>/<item>/timelapse-<ts>.mp4
    """
    item = ArtItem.query.get_or_404(item_id)
    versions = ArtVersion.query.filter_by(item_id=item.id).order_by(ArtVersion.created_at.asc()).all()
    if not versions:
        return jsonify({"error": "No versions found for item"}), 400

    # build absolute paths and verify files exist
    files = []
    for v in versions:
        full = os.path.join(app.config['UPLOAD_FOLDER'], v.filepath)
        if os.path.exists(full):
            files.append(full)

    if not files:
        return jsonify({"error": "No files available to make timelapse"}), 400

    # make tmp concat list file
    with tempfile.TemporaryDirectory() as tmp:
        list_file = os.path.join(tmp, 'files.txt')
        # 2 second duration per image (flexible)
        duration = int(request.args.get('duration', 2))
        with open(list_file, 'w', encoding='utf-8') as fh:
            for p in files:
                fh.write(f"file '{p}'\n")
                fh.write(f"duration {duration}\n")
            # ffmpeg requires last file listed again
            fh.write(f"file '{files[-1]}'\n")

        # ensure output dir exists
        out_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(item.group_id), str(item.id))
        os.makedirs(out_dir, exist_ok=True)
        out_name = f"timelapse_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.mp4"
        out_path = os.path.join(out_dir, out_name)

        # run ffmpeg to create slideshow
        # Use libx264 to create a widely playable MP4; keep crf sensible for size/quality.
        cmd = [
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file,
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-vf', 'scale=1280:-2', '-preset', 'medium', '-crf', '20', out_path
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": "ffmpeg failed", "details": e.stderr.decode('utf-8', 'ignore')}), 500

    # return url to the created timelapse
    url = f"/media/{item.group_id}/{item.id}/{out_name}"
    return jsonify({"url": url}), 201

# --- Media Serving ---
@app.route('/media/<int:group_id>/<int:item_id>/<filename>')
def serve_media(group_id, item_id, filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], str(group_id), str(item_id))
    return send_from_directory(directory, filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
