from flask import Flask, request, jsonify, send_from_directory, url_for, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import re
import os
import random
from functools import wraps
import threading
import time
from werkzeug.serving import make_server
from sqlalchemy import Index
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import string

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # تفعيل CORS لجميع المسارات

# إضافة معالج الأخطاء العام
@app.errorhandler(Exception)
def handle_error(error):
    print(f"[ERROR] {type(error).__name__}: {str(error)}")
    return jsonify({
        "error": str(error),
        "type": type(error).__name__
    }), 500

# إضافة middleware للتعامل مع CORS
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# إعدادات التطبيق
app.config.update(
    SECRET_KEY='your-secret-key-here',
    SQLALCHEMY_DATABASE_URI='sqlite:///codify.db',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    
    # إعدادات البريد
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='husseinabutaleb4509@gmail.com',
    MAIL_PASSWORD='ctrv nfzq xzai drlp',
    MAIL_DEFAULT_SENDER=('Codify', 'husseinabutaleb4509@gmail.com'),
    WTF_CSRF_ENABLED=False
)

# تكوين مجلدات التطبيق
app.static_folder = 'static'
app.template_folder = 'templates'

# تكوين مجلد للملفات الثابتة
app.config['STATIC_FOLDER'] = os.path.abspath(os.path.dirname(__file__))

db = SQLAlchemy(app)
mail = Mail(app)

csrf = CSRFProtect(app)

# إضافة rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# النماذج (Models)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    verification_code_expires = db.Column(db.DateTime)
    profile_picture = db.Column(db.String(200))
    last_login = db.Column(db.DateTime)
    account_status = db.Column(db.String(20), default='active')

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    track = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(20))
    duration = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    status = db.Column(db.String(20), default='in_progress')
    progress_percentage = db.Column(db.Float, default=0.0)
    last_accessed = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # العلاقات
    user = db.relationship('User', backref=db.backref('progress_records', lazy=True))
    course = db.relationship('Course', backref=db.backref('progress_records', lazy=True))
    course_rel = db.relationship('Course', foreign_keys=[course_id])

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, nullable=False)
    date_taken = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # العلاقات
    user = db.relationship('User', backref=db.backref('quiz_results', lazy=True))
    course = db.relationship('Course', backref=db.backref('quiz_results', lazy=True))
    course_rel = db.relationship('Course', foreign_keys=[course_id])

# إنشاء الفهارس
Index('idx_user_email', User.email, unique=True)
Index('idx_progress_user_course', Progress.user_id, Progress.course_id)
Index('idx_quiz_user_course', QuizResult.user_id, QuizResult.course_id)

# دالة للتحقق من التوكن
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
            
        if not token.startswith('Bearer '):
            return jsonify({'error': 'Invalid token format'}), 401
            
        try:
            # إزالة 'Bearer ' من التوكن
            token = token.split('Bearer ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            
            if not current_user:
                return jsonify({'error': 'User not found'}), 404
                
            return f(current_user, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated

# التحقق من صحة البريد الإلكتروني
def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None

# التحقق من قوة كلمة المرور
def is_valid_password(password):
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    if not any(c in '!@#$%^&*(),.?:{}|<>' for c in password):
        return False
    return True

def generate_verification_code():
    """توليد رمز تحقق من 6 أرقام"""
    return ''.join(random.choices(string.digits, k=6))

def send_verification_email(email, code):
    """إرسال رمز التحقق بالبريد"""
    try:
        msg = Message('تحقق من بريدك الإلكتروني - Codify',
                     sender=app.config['MAIL_USERNAME'],
                     recipients=[email])
        msg.body = f'''Welcome to Codify!
        Thank you for signing up with us!
        Your verification code is: {code}
        This code is valid for 10 minutes.
        If you have any questions, feel free to reach out to our support team.

        Best regards,  
        The Codify Team
        '''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

# دالة تهيئة قاعدة البيانات
def init_db():
    with app.app_context():
        print("=== Starting Database Initialization ===")
        print("Dropping all existing tables...")
        db.drop_all()
        print("Creating new tables...")
        db.create_all()
        
        # إضافة بيانات أولية إذا كنت تريد
        # مثال: إضافة بعض الدورات
        courses = [
            Course(
                title='Python Basics',
                description='Learn Python fundamentals',
                track='Python',
                level='Beginner',
                duration=60
            ),
            Course(
                title='Web Development',
                description='Learn web development basics',
                track='Web',
                level='Beginner',
                duration=90
            )
        ]
        
        for course in courses:
            db.session.add(course)
        
        try:
            db.session.commit()
            print("Initial data added successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error adding initial data: {str(e)}")
        
        print("Database initialized successfully!")
        print("=== Database Initialization Complete ===")

# المسارات الرئيسية
@app.route('/')
def home():
    return send_from_directory('.', 'landing.html')

@app.route('/login')
def login_page():
    return send_from_directory('.', 'Login&Signup.html')

@app.route('/profile')
def profile_page():
    return send_from_directory('.', 'profile.html')

@app.route('/tracks')
def tracks_page():
    return send_from_directory('.', 'tracks.html')

@app.route('/roadmaps')
def roadmaps_page():
    return send_from_directory('.', 'roadmaps.html')

@app.route('/quizzes')
def quizzes_page():
    return send_from_directory('.', 'quizzes.html')

# تحديث مسار تسجيل الخروج
@app.route('/logout')
def logout():
    return redirect('/login')

@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    # التعامل مع طلبات OPTIONS
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response

    try:
        data = request.get_json()
        print("Received data:", data)  # للتأكد من وصول البيانات
        
        if not data:
            return jsonify({'error': 'لم يتم استلام البيانات'}), 400
            
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        if not all([name, email, password]):
            return jsonify({'error': 'جميع الحقول مطلوبة'}), 400
            
        # التحقق من عدم وجود المستخدم
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'البريد الإلكتروني مستخدم بالفعل'}), 400
            
        # توليد رمز التحقق
        verification_code = generate_verification_code()
        expiration_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        # إنشاء مستخدم جديد
        user = User(
            name=name,
            email=email,
            password=generate_password_hash(password),
            verification_code=verification_code,
            verification_code_expires=expiration_time
        )
        
        db.session.add(user)
        db.session.commit()
        
        # إرسال رمز التحقق
        if send_verification_email(email, verification_code):
            return jsonify({
                'message': 'تم التسجيل بنجاح وإرسال رمز التحقق',
                'email': email
            }), 201
        else:
            return jsonify({'error': 'فشل في إرسال رمز التحقق'}), 500
        
    except Exception as e:
        print("Error in registration:", str(e))
        return jsonify({'error': 'حدث خطأ في التسجيل'}), 500

@app.route('/verify', methods=['POST'])
def verify():
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')
        
        if not email or not code:
            return jsonify({'error': 'البريد الإلكتروني ورمز التحقق مطلوبان'}), 400
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'error': 'لم يتم العثور على المستخدم'}), 404
            
        if user.is_verified:
            return jsonify({'error': 'تم التحقق من الحساب مسبقاً'}), 400
            
        if user.verification_code != code:
            return jsonify({'error': 'رمز التحقق غير صحيح'}), 400
            
        if user.verification_code_expires < datetime.datetime.utcnow():
            return jsonify({'error': 'انتهت صلاحية رمز التحقق'}), 400
            
        user.is_verified = True
        db.session.commit()
        
        return jsonify({'message': 'تم التحقق من الحساب بنجاح'}), 200
        
    except Exception as e:
        print("Error in verification:", str(e))
        return jsonify({'error': 'حدث خطأ في عملية التحقق'}), 500

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        # يجب إضافة تحقق إضافي من المدخلات
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({'error': 'بيانات غير صحيحة'}), 400

        email = data['email']
        password = data['password']

        # التحقق من وجود البريد الإلكتروني وكلمة المرور
        if not email or not password:
            return jsonify({
                'error': 'يرجى إدخال البريد الإلكتروني وكلمة المرور'
            }), 400

        # البحث عن المستخدم
        user = User.query.filter_by(email=email).first()
        
        # التحقق من وجود المستخدم وصحة كلمة المرور
        if user and check_password_hash(user.password, password):
            # التحقق من تفعيل الحساب
            if not user.is_verified:
                return jsonify({
                    'error': 'يرجى تفعيل حسابك أولاً',
                    'requires_verification': True,
                    'email': email
                }), 401

            # إنشاء توكن
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
            }, app.config['SECRET_KEY'])

            return jsonify({
                'token': token,
                'user': {
                    'name': user.name,
                    'email': user.email
                }
            }), 200
        
        return jsonify({
            'error': 'البريد الإلكتروني أو كلمة المرور غير صحيحة'
        }), 401

    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({
            'error': 'حدث خطأ في تسجيل الدخول'
        }), 500

@app.route('/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'البريد الإلكتروني مطلوب'}), 400
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'error': 'لم يتم العثور على المستخدم'}), 404
            
        if user.is_verified:
            return jsonify({'error': 'تم التحقق من الحساب مسبقاً'}), 400
            
        # توليد رمز جديد
        new_code = generate_verification_code()
        user.verification_code = new_code
        user.verification_code_expires = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        db.session.commit()
        
        # إرسال الرمز الجديد
        if send_verification_email(email, new_code):
            return jsonify({'message': 'تم إرسال رمز تحقق جديد'}), 200
        else:
            return jsonify({'error': 'فشل في إرسال رمز التحقق'}), 500
            
    except Exception as e:
        print("Error in resending verification:", str(e))
        return jsonify({'error': 'حدث خطأ في إعادة إرسال رمز التحقق'}), 500

# الملف الشخصي
@app.route("/api/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    try:
        # تحويل بيانات المستخدم إلى JSON
        user_data = {
            'id': current_user.id,
            'name': current_user.name,
            'email': current_user.email,
            'created_at': current_user.created_at.isoformat()
        }
        
        # جلب تقدم المستخدم
        progress = Progress.query.filter_by(user_id=current_user.id).all()
        progress_data = []
        for p in progress:
            course = p.course_rel
            progress_data.append({
                'course': course.title if course else 'Unknown',
                'completed': p.status == 'completed',
                'score': p.progress_percentage,
                'last_updated': p.last_accessed.isoformat() if p.last_accessed else None
            })
        
        # جلب نتائج الاختبارات
        quiz_results = QuizResult.query.filter_by(user_id=current_user.id).all()
        quiz_data = []
        for q in quiz_results:
            course = q.course_rel
            quiz_data.append({
                'course': course.title if course else 'Unknown',
                'track': course.track if course else 'Unknown',
                'score': q.score,
                'passed': q.passed,
                'date_taken': q.date_taken.isoformat()
            })
        
        return jsonify({
            'user': user_data,
            'progress': progress_data,
            'quiz_results': quiz_data
        }), 200
        
    except Exception as e:
        print(f"Error in get_profile: {str(e)}")
        return jsonify({'error': 'Failed to load profile data'}), 500

# تحديث تقدم المستخدم
@app.route("/progress", methods=["POST"])
@token_required
def update_progress(current_user):
    try:
        data = request.json
        if not all(key in data for key in ['track', 'course', 'completed']):
            return jsonify({"error": "Missing required fields"}), 400

        progress = Progress(
            user_id=current_user.id,
            track=data['track'],
            course=data['course'],
            completed=data['completed'],
            last_updated=datetime.datetime.utcnow() if data['completed'] else None
        )
        db.session.add(progress)
        db.session.commit()

        return jsonify({
            "message": "Progress updated successfully",
            "progress": {
                "track": progress.track,
                "course": progress.course,
                "completed": progress.completed,
                "last_updated": progress.last_updated.isoformat() if progress.last_updated else None
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# تسجيل نتيجة اختبار
@app.route("/quiz-result", methods=["POST"])
@token_required
def submit_quiz_result(current_user):
    try:
        data = request.json
        if not all(key in data for key in ['track', 'course', 'score']):
            return jsonify({"error": "Missing required fields"}), 400

        # تحديد ما إذا كان المستخدم قد نجح (نفترض أن درجة النجاح هي 70%)
        passed = data['score'] >= 70

        result = QuizResult(
            user_id=current_user.id,
            track=data['track'],
            course=data['course'],
            score=data['score'],
            passed=passed
        )
        db.session.add(result)
        db.session.commit()

        return jsonify({
            "message": "Quiz result submitted successfully",
            "result": {
                "track": result.track,
                "course": result.course,
                "score": result.score,
                "passed": result.passed,
                "date_taken": result.date_taken.isoformat()
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# إضافة مسار لخدمة الملفات الثابتة
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/verify')
def verify_page():
    return render_template('verify.html')

@app.route('/api/health')
def health_check():
    return jsonify({"status": "ok", "port": request.host.split(':')[1]}), 200

@app.route('/test')
def test():
    return jsonify({
        "status": "ok",
        "message": "Server is running",
        "port": request.host.split(':')[1] if ':' in request.host else "unknown"
    })

# قائمة الكويزات المتاحة (يمكنك تعديلها حسب الحاجة)
QUIZZES = [
    {"id": 1, "title": "HTML"},
    {"id": 2, "title": "CSS"},
    {"id": 3, "title": "JavaScript"},
    {"id": 4, "title": "React.js"},
    {"id": 5, "title": "Node.js"},
    {"id": 6, "title": "Python"},
    {"id": 7, "title": "PHP"},
    {"id": 8, "title": "Java"},
    {"id": 9, "title": "Intro to Cyber"},
    {"id": 10, "title": "Cyber Essentials"},
    {"id": 11, "title": "CompTIA Security"},
    {"id": 12, "title": "Testing"},
    {"id": 13, "title": "Network Security"},
    {"id": 14, "title": "Ethical Hacking"},
    {"id": 15, "title": "Data Structure"},
    {"id": 16, "title": "Git"},
    {"id": 17, "title": "SQL"},
    {"id": 18, "title": "Math & Statistics"},
    {"id": 19, "title": "Data Collection"},
    {"id": 20, "title": "Machine Learning"},
    {"id": 21, "title": "Deep Learning"},
    {"id": 22, "title": "Specialization"},
    {"id": 23, "title": "Big Data"},
    {"id": 24, "title": "TypeScript"},
    {"id": 25, "title": "Design Patterns"},
    {"id": 26, "title": "React Native"},
    {"id": 27, "title": "Dart"},
    {"id": 28, "title": "Flutter"},
    {"id": 29, "title": "Linux"},
    {"id": 30, "title": "Networking"},
    {"id": 31, "title": "Docker"},
    {"id": 32, "title": "Jenkins"},
    {"id": 33, "title": "AWS"},
    {"id": 34, "title": "Kubernetes"},
    {"id": 35, "title": "Nginx"},
    {"id": 36, "title": "Ansible"},
    {"id": 37, "title": "Terraform"},
    {"id": 38, "title": "Prometheus"},
]

@app.route('/api/quizzes/status', methods=['GET'])
@token_required
def quizzes_status(current_user):
    # جلب نتائج الكويزات لهذا المستخدم
    user_results = QuizResult.query.filter_by(user_id=current_user.id).all()
    results_map = {r.course_id: r for r in user_results}

    quizzes_status = []
    unlocked = True  # أول كويز مفتوح دائماً
    for idx, quiz in enumerate(QUIZZES):
        # ابحث عن نتيجة الكويز حسب الترتيب (هنا course_id == quiz['id'])
        result = results_map.get(quiz['id'])
        if result:
            status = 'passed' if result.passed else 'failed'
        elif unlocked:
            status = 'unlocked'
        else:
            status = 'locked'
        quizzes_status.append({
            'id': quiz['id'],
            'title': quiz['title'],
            'status': status
        })
        # إذا لم يجتز الكويز الحالي، التالي يظل مغلق
        unlocked = unlocked and (status == 'passed')
    return jsonify({'quizzes': quizzes_status})

@app.route("/quiz_results", methods=["GET"])
def get_quiz_results():
    try:
        user_id = get_user_id_from_token()
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        quiz_results = QuizResult.query.filter_by(user_id=user_id).all()
        results = [{
            "id": result.id,
            "course": result.course,
            "score": result.score,
            "passed": result.passed,
            "date_taken": result.date_taken.isoformat()
        } for result in quiz_results]

        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()  # تهيئة قاعدة البيانات
    app.run(debug=True, port=5051)
