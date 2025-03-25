from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app

from app import db
from models import Client, PaymentBlock, BlockReason, BlockHistory, BlockStatus
from api.auth import token_required, admin_required
from api.validation import validate_block_request, validate_unblock_request, validate_client_request

bp = Blueprint('blocks', __name__, url_prefix='/api')

@bp.route('/clients', methods=['GET'])
@token_required
def get_clients():
    """Get a list of all clients"""
    query = Client.query
    
    # Optional filtering by client number
    client_number = request.args.get('client_number')
    if client_number:
        query = query.filter(Client.client_number.ilike(f'%{client_number}%'))
    
    # Optional filtering by name
    name = request.args.get('name')
    if name:
        query = query.filter(Client.name.ilike(f'%{name}%'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    pagination = query.order_by(Client.id).paginate(page=page, per_page=per_page)
    
    clients = []
    for client in pagination.items:
        # Check if client has active blocks
        has_active_block = False
        for block in client.blocks:
            if block.is_active:
                has_active_block = True
                break
        
        clients.append({
            'id': client.id,
            'client_number': client.client_number,
            'name': client.name,
            'email': client.email,
            'is_blocked': has_active_block,
            'created_at': client.created_at.isoformat(),
            'updated_at': client.updated_at.isoformat()
        })
    
    return jsonify({
        'clients': clients,
        'pagination': {
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@bp.route('/clients', methods=['POST'])
@token_required
def create_client():
    """Create a new client"""
    data = request.json
    validation_errors = validate_client_request(data)
    
    if validation_errors:
        return jsonify({'message': 'Validation error', 'errors': validation_errors}), 400
    
    # Check if client with this number already exists
    existing_client = Client.query.filter_by(client_number=data['client_number']).first()
    if existing_client:
        return jsonify({'message': 'Client with this number already exists'}), 409
    
    # Create new client
    new_client = Client(
        client_number=data['client_number'],
        name=data['name'],
        email=data.get('email')
    )
    
    db.session.add(new_client)
    db.session.commit()
    
    return jsonify({
        'message': 'Client created successfully',
        'client': {
            'id': new_client.id,
            'client_number': new_client.client_number,
            'name': new_client.name,
            'email': new_client.email,
            'created_at': new_client.created_at.isoformat(),
            'updated_at': new_client.updated_at.isoformat()
        }
    }), 201

@bp.route('/clients/<int:client_id>', methods=['GET'])
@token_required
def get_client(client_id):
    """Get details for a specific client"""
    client = Client.query.get_or_404(client_id)
    
    # Get all blocks for the client
    blocks = []
    has_active_block = False
    
    for block in client.blocks:
        is_active = block.is_active
        if is_active:
            has_active_block = True
        
        blocks.append({
            'id': block.id,
            'reason': {
                'id': block.reason.id,
                'code': block.reason.code,
                'description': block.reason.description,
                'is_fraud': block.reason.is_fraud
            },
            'status': block.status,
            'is_active': is_active,
            'notes': block.notes,
            'created_by': block.created_by,
            'created_at': block.created_at.isoformat(),
            'expires_at': block.expires_at.isoformat() if block.expires_at else None
        })
    
    return jsonify({
        'id': client.id,
        'client_number': client.client_number,
        'name': client.name,
        'email': client.email,
        'is_blocked': has_active_block,
        'blocks': blocks,
        'created_at': client.created_at.isoformat(),
        'updated_at': client.updated_at.isoformat()
    }), 200

@bp.route('/block-reasons', methods=['GET'])
@token_required
def get_block_reasons():
    """Get a list of all available block reasons"""
    reasons = BlockReason.query.all()
    
    result = []
    for reason in reasons:
        result.append({
            'id': reason.id,
            'code': reason.code,
            'description': reason.description,
            'is_fraud': reason.is_fraud,
            'created_at': reason.created_at.isoformat()
        })
    
    return jsonify({'reasons': result}), 200

@bp.route('/clients/<int:client_id>/blocks', methods=['POST'])
@token_required
def block_client(client_id):
    """Block a client's payments"""
    client = Client.query.get_or_404(client_id)
    data = request.json
    
    # Validate request data
    validation_errors = validate_block_request(data)
    if validation_errors:
        return jsonify({'message': 'Validation error', 'errors': validation_errors}), 400
    
    # Check if reason exists
    reason = BlockReason.query.get(data['reason_id'])
    if not reason:
        return jsonify({'message': 'Invalid block reason'}), 400
    
    # Check if client already has an active block
    has_active_block = False
    for block in client.blocks:
        if block.is_active:
            has_active_block = True
            break
    
    # If already blocked, we can choose to add another block or return an error
    if has_active_block and not data.get('force', False):
        return jsonify({'message': 'Client already has an active block', 'can_force': True}), 409
    
    # Process expiration date if provided
    expires_at = None
    if data.get('expires_in_days'):
        expires_at = datetime.utcnow() + timedelta(days=int(data['expires_in_days']))
    
    # Create new block
    new_block = PaymentBlock(
        client_id=client.id,
        reason_id=reason.id,
        notes=data.get('notes', ''),
        created_by=request.username,
        expires_at=expires_at
    )
    
    db.session.add(new_block)
    
    # Create history record
    history = BlockHistory(
        block=new_block,
        action='created',
        status_before=None,
        status_after=BlockStatus.ACTIVE,
        performed_by=request.username,
        notes=f"Initial block created with reason: {reason.code}"
    )
    
    db.session.add(history)
    db.session.commit()
    
    return jsonify({
        'message': 'Client blocked successfully',
        'block': {
            'id': new_block.id,
            'client_id': client.id,
            'client_number': client.client_number,
            'reason': {
                'id': reason.id,
                'code': reason.code,
                'description': reason.description,
                'is_fraud': reason.is_fraud
            },
            'status': new_block.status,
            'notes': new_block.notes,
            'created_by': new_block.created_by,
            'created_at': new_block.created_at.isoformat(),
            'expires_at': new_block.expires_at.isoformat() if new_block.expires_at else None
        }
    }), 201

@bp.route('/blocks/<int:block_id>/unblock', methods=['POST'])
@token_required
def unblock_client(block_id):
    """Unblock a client's payments"""
    block = PaymentBlock.query.get_or_404(block_id)
    
    # Check if block is already inactive
    if block.status != BlockStatus.ACTIVE:
        return jsonify({'message': 'Block is already inactive'}), 400
    
    data = request.json or {}
    
    # Validate request data
    validation_errors = validate_unblock_request(data)
    if validation_errors:
        return jsonify({'message': 'Validation error', 'errors': validation_errors}), 400
    
    # Update block status
    old_status = block.status
    block.status = BlockStatus.INACTIVE
    
    # Create history record
    history = BlockHistory(
        block=block,
        action='unblocked',
        status_before=old_status,
        status_after=BlockStatus.INACTIVE,
        performed_by=request.username,
        notes=data.get('notes', 'Block removed')
    )
    
    db.session.add(history)
    db.session.commit()
    
    return jsonify({
        'message': 'Block removed successfully',
        'block': {
            'id': block.id,
            'client_id': block.client_id,
            'client_number': block.client.client_number,
            'status': block.status,
            'reason': {
                'id': block.reason.id,
                'code': block.reason.code,
                'description': block.reason.description,
                'is_fraud': block.reason.is_fraud
            }
        }
    }), 200

@bp.route('/clients/<client_identifier>/check-status', methods=['GET'])
@token_required
def check_client_status(client_identifier):
    """
    Check if a client is blocked
    client_identifier can be either client_id or client_number
    """
    # Determine if the identifier is a number (ID) or string (client_number)
    if client_identifier.isdigit():
        client = Client.query.get(int(client_identifier))
    else:
        client = Client.query.filter_by(client_number=client_identifier).first()
    
    if not client:
        return jsonify({'message': 'Client not found'}), 404
    
    # Check if client has any active blocks
    active_blocks = []
    for block in client.blocks:
        if block.is_active:
            active_blocks.append({
                'id': block.id,
                'reason': {
                    'id': block.reason.id,
                    'code': block.reason.code,
                    'description': block.reason.description,
                    'is_fraud': block.reason.is_fraud
                },
                'notes': block.notes,
                'created_at': block.created_at.isoformat(),
                'expires_at': block.expires_at.isoformat() if block.expires_at else None
            })
    
    is_blocked = len(active_blocks) > 0
    
    # Get the most recent history entry for context
    recent_history = None
    if is_blocked:
        history_entry = BlockHistory.query.join(PaymentBlock).filter(
            PaymentBlock.client_id == client.id
        ).order_by(BlockHistory.timestamp.desc()).first()
        
        if history_entry:
            recent_history = {
                'action': history_entry.action,
                'performed_by': history_entry.performed_by,
                'notes': history_entry.notes,
                'timestamp': history_entry.timestamp.isoformat()
            }
    
    return jsonify({
        'client_id': client.id,
        'client_number': client.client_number,
        'name': client.name,
        'is_blocked': is_blocked,
        'active_blocks': active_blocks,
        'recent_history': recent_history
    }), 200

@bp.route('/blocks', methods=['GET'])
@token_required
def get_blocks():
    """Get a list of all blocks with filtering options"""
    query = PaymentBlock.query
    
    # Filter by status
    status = request.args.get('status')
    if status:
        query = query.filter(PaymentBlock.status == status)
    
    # Filter by client ID
    client_id = request.args.get('client_id')
    if client_id:
        query = query.filter(PaymentBlock.client_id == client_id)
    
    # Filter by reason type (fraud vs non-fraud)
    is_fraud = request.args.get('is_fraud')
    if is_fraud is not None:
        is_fraud_bool = is_fraud.lower() == 'true'
        query = query.join(BlockReason).filter(BlockReason.is_fraud == is_fraud_bool)
    
    # Filter by date range
    date_from = request.args.get('date_from')
    if date_from:
        try:
            date_from_obj = datetime.fromisoformat(date_from)
            query = query.filter(PaymentBlock.created_at >= date_from_obj)
        except ValueError:
            pass
    
    date_to = request.args.get('date_to')
    if date_to:
        try:
            date_to_obj = datetime.fromisoformat(date_to)
            query = query.filter(PaymentBlock.created_at <= date_to_obj)
        except ValueError:
            pass
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    pagination = query.order_by(PaymentBlock.created_at.desc()).paginate(page=page, per_page=per_page)
    
    blocks = []
    for block in pagination.items:
        blocks.append({
            'id': block.id,
            'client': {
                'id': block.client.id,
                'client_number': block.client.client_number,
                'name': block.client.name
            },
            'reason': {
                'id': block.reason.id,
                'code': block.reason.code,
                'description': block.reason.description,
                'is_fraud': block.reason.is_fraud
            },
            'status': block.status,
            'is_active': block.is_active,
            'notes': block.notes,
            'created_by': block.created_by,
            'created_at': block.created_at.isoformat(),
            'expires_at': block.expires_at.isoformat() if block.expires_at else None
        })
    
    return jsonify({
        'blocks': blocks,
        'pagination': {
            'total': pagination.total,
            'pages': pagination.pages,
            'page': page,
            'per_page': per_page,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    }), 200

@bp.route('/blocks/<int:block_id>', methods=['GET'])
@token_required
def get_block(block_id):
    """Get details for a specific block"""
    block = PaymentBlock.query.get_or_404(block_id)
    
    # Get block history
    history_entries = []
    for entry in block.history:
        history_entries.append({
            'id': entry.id,
            'action': entry.action,
            'status_before': entry.status_before,
            'status_after': entry.status_after,
            'performed_by': entry.performed_by,
            'notes': entry.notes,
            'timestamp': entry.timestamp.isoformat()
        })
    
    return jsonify({
        'id': block.id,
        'client': {
            'id': block.client.id,
            'client_number': block.client.client_number,
            'name': block.client.name
        },
        'reason': {
            'id': block.reason.id,
            'code': block.reason.code,
            'description': block.reason.description,
            'is_fraud': block.reason.is_fraud
        },
        'status': block.status,
        'is_active': block.is_active,
        'notes': block.notes,
        'created_by': block.created_by,
        'created_at': block.created_at.isoformat(),
        'expires_at': block.expires_at.isoformat() if block.expires_at else None,
        'history': history_entries
    }), 200

@bp.route('/blocks/<int:block_id>', methods=['PUT'])
@token_required
def update_block(block_id):
    """Update an existing block"""
    block = PaymentBlock.query.get_or_404(block_id)
    data = request.json
    
    # Only active blocks can be updated
    if block.status != BlockStatus.ACTIVE:
        return jsonify({'message': 'Only active blocks can be updated'}), 400
    
    changes_made = False
    changes_description = []
    
    # Update reason if provided
    if 'reason_id' in data:
        reason = BlockReason.query.get(data['reason_id'])
        if not reason:
            return jsonify({'message': 'Invalid block reason'}), 400
        
        old_reason_id = block.reason_id
        if old_reason_id != reason.id:
            block.reason_id = reason.id
            changes_made = True
            changes_description.append(f"Reason changed from {BlockReason.query.get(old_reason_id).code} to {reason.code}")
    
    # Update notes if provided
    if 'notes' in data:
        if block.notes != data['notes']:
            block.notes = data['notes']
            changes_made = True
            changes_description.append("Notes updated")
    
    # Update expiration date if provided
    if 'expires_in_days' in data:
        new_expiry = datetime.utcnow() + timedelta(days=int(data['expires_in_days']))
        old_expiry = block.expires_at
        
        if old_expiry != new_expiry:
            block.expires_at = new_expiry
            changes_made = True
            changes_description.append(f"Expiration date updated to {new_expiry.isoformat()}")
    
    if changes_made:
        # Create history record
        history = BlockHistory(
            block=block,
            action='updated',
            status_before=block.status,
            status_after=block.status,
            performed_by=request.username,
            notes="; ".join(changes_description)
        )
        
        db.session.add(history)
        db.session.commit()
        
        return jsonify({
            'message': 'Block updated successfully',
            'changes': changes_description,
            'block': {
                'id': block.id,
                'client_id': block.client_id,
                'reason_id': block.reason_id,
                'status': block.status,
                'notes': block.notes,
                'created_at': block.created_at.isoformat(),
                'expires_at': block.expires_at.isoformat() if block.expires_at else None
            }
        }), 200
    else:
        return jsonify({'message': 'No changes made'}), 200

@bp.route('/block-reasons', methods=['POST'])
@admin_required
def create_block_reason():
    """Create a new block reason (admin only)"""
    data = request.json
    
    # Validate required fields
    if not data.get('code') or not data.get('description'):
        return jsonify({'message': 'Code and description are required'}), 400
    
    # Check if code already exists
    existing_reason = BlockReason.query.filter_by(code=data['code']).first()
    if existing_reason:
        return jsonify({'message': 'A reason with this code already exists'}), 409
    
    # Create new reason
    new_reason = BlockReason(
        code=data['code'],
        description=data['description'],
        is_fraud=data.get('is_fraud', False)
    )
    
    db.session.add(new_reason)
    db.session.commit()
    
    return jsonify({
        'message': 'Block reason created successfully',
        'reason': {
            'id': new_reason.id,
            'code': new_reason.code,
            'description': new_reason.description,
            'is_fraud': new_reason.is_fraud,
            'created_at': new_reason.created_at.isoformat()
        }
    }), 201

@bp.route('/stats', methods=['GET'])
@token_required
def get_stats():
    """Get statistics about blocks"""
    # Total clients
    total_clients = Client.query.count()
    
    # Total blocks
    total_blocks = PaymentBlock.query.count()
    
    # Active blocks
    active_blocks = PaymentBlock.query.filter_by(status=BlockStatus.ACTIVE).count()
    
    # Fraud vs non-fraud
    fraud_blocks = db.session.query(PaymentBlock).join(BlockReason).filter(
        BlockReason.is_fraud == True,
        PaymentBlock.status == BlockStatus.ACTIVE
    ).count()
    
    non_fraud_blocks = db.session.query(PaymentBlock).join(BlockReason).filter(
        BlockReason.is_fraud == False,
        PaymentBlock.status == BlockStatus.ACTIVE
    ).count()
    
    # Blocks by reason
    reason_stats = []
    reasons = BlockReason.query.all()
    for reason in reasons:
        count = PaymentBlock.query.filter_by(reason_id=reason.id, status=BlockStatus.ACTIVE).count()
        reason_stats.append({
            'reason': {
                'id': reason.id,
                'code': reason.code,
                'description': reason.description,
                'is_fraud': reason.is_fraud
            },
            'active_count': count
        })
    
    # Recent blocks (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_blocks = PaymentBlock.query.filter(PaymentBlock.created_at >= week_ago).count()
    
    return jsonify({
        'total_clients': total_clients,
        'total_blocks': total_blocks,
        'active_blocks': active_blocks,
        'blocks_by_type': {
            'fraud': fraud_blocks,
            'non_fraud': non_fraud_blocks
        },
        'blocks_by_reason': reason_stats,
        'recent_blocks': recent_blocks,
        'timestamp': datetime.utcnow().isoformat()
    }), 200
