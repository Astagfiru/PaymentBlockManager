import os
import jwt
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from models import User

bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def get_token_from_header():
    """Extract the JWT token from the Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    return auth_header.split(' ')[1]

def token_required(f):
    """Decorator to verify the JWT token for protected routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_header()
        
        if not token:
            return jsonify({'message': 'Authentication token is missing'}), 401
        
        try:
            # Decode the token
            payload = jwt.decode(
                token, 
                current_app.config['JWT_SECRET_KEY'], 
                algorithms=["HS256"]
            )
            request.user_id = payload['sub']
            request.username = payload['username']
            request.is_admin = payload.get('is_admin', False)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Authentication token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid authentication token'}), 401
            
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator to check if user is admin"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Use token_required first to authenticate
        token = get_token_from_header()
        
        if not token:
            return jsonify({'message': 'Authentication token is missing'}), 401
        
        try:
            # Decode the token
            payload = jwt.decode(
                token, 
                current_app.config['JWT_SECRET_KEY'], 
                algorithms=["HS256"]
            )
            request.user_id = payload['sub']
            request.username = payload['username']
            request.is_admin = payload.get('is_admin', False)
            
            # Check if user is admin
            if not request.is_admin:
                return jsonify({'message': 'Admin privileges required'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Authentication token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid authentication token'}), 401
            
        return f(*args, **kwargs)
    return decorated

@bp.route('/login', methods=['POST'])
def login():
    """Authenticate a user and return a JWT token"""
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Username and password are required'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Invalid username or password'}), 401
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    # Generate JWT token
    token_expiry = datetime.utcnow() + timedelta(hours=1)
    token_payload = {
        'sub': user.id,
        'username': user.username,
        'is_admin': user.is_admin,
        'exp': token_expiry
    }
    
    token = jwt.encode(
        token_payload,
        current_app.config['JWT_SECRET_KEY'],
        algorithm="HS256"
    )
    
    return jsonify({
        'token': token,
        'expires_at': token_expiry.isoformat(),
        'user': {
            'id': user.id,
            'username': user.username,
            'is_admin': user.is_admin
        }
    }), 200

@bp.route('/register', methods=['POST'])
@admin_required
def register():
    """Register a new user (admin only)"""
    data = request.json
    
    # Validate input
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'message': f'{field} is required'}), 400
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already taken'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 409
    
    # Create new user
    new_user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        is_admin=data.get('is_admin', False)
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': {
            'id': new_user.id,
            'username': new_user.username,
            'email': new_user.email,
            'is_admin': new_user.is_admin
        }
    }), 201

@bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current user information"""
    user = User.query.get(request.user_id)
    
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_admin': user.is_admin,
        'last_login': user.last_login.isoformat() if user.last_login else None,
        'created_at': user.created_at.isoformat()
    }), 200

@bp.route('/token/verify', methods=['POST'])
def verify_token():
    """Verify if a token is valid"""
    token = request.json.get('token') or get_token_from_header()
    
    if not token:
        return jsonify({'message': 'Token is required'}), 400
    
    try:
        # Decode the token
        payload = jwt.decode(
            token, 
            current_app.config['JWT_SECRET_KEY'], 
            algorithms=["HS256"]
        )
        
        return jsonify({
            'valid': True,
            'user_id': payload['sub'],
            'username': payload['username'],
            'is_admin': payload.get('is_admin', False),
            'expires_at': datetime.fromtimestamp(payload['exp']).isoformat()
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'message': 'Token has expired'}), 200
    except jwt.InvalidTokenError:
        return jsonify({'valid': False, 'message': 'Invalid token'}), 200
