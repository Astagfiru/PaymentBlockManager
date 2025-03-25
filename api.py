import logging
from flask import Blueprint, request, jsonify, current_app
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import db
from models import Client, PaymentBlock, BlockReason
from schemas import (
    BlockPaymentSchema, 
    UnblockPaymentSchema, 
    ClientStatusSchema, 
    ClientBlockHistorySchema,
    PaymentBlockSchema,
    ErrorSchema
)
from utils import get_or_create_client

# Set up logging
logger = logging.getLogger(__name__)

# Create Blueprint for API routes
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Schema instances for request validation and response serialization
block_payment_schema = BlockPaymentSchema()
unblock_payment_schema = UnblockPaymentSchema()
client_status_schema = ClientStatusSchema()
client_block_history_schema = ClientBlockHistorySchema()
payment_block_schema = PaymentBlockSchema()
error_schema = ErrorSchema()

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@api_bp.route('/clients/<client_identifier>/block', methods=['POST'])
def block_client_payments(client_identifier):
    """
    Block payments for a specific client
    ---
    tags:
      - Payment Blocks
    parameters:
      - name: client_identifier
        in: path
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/BlockPaymentSchema'
    responses:
      201:
        description: Client payments blocked successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PaymentBlockSchema'
      400:
        description: Invalid request data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      404:
        description: Client not found
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      500:
        description: Server error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
    """
    try:
        # Parse and validate request data
        data = request.json
        if not data:
            return jsonify(error_schema.dump({"error": "No JSON data provided"})), 400
        
        # Override client_identifier from URL
        data['client_identifier'] = client_identifier
        validated_data = block_payment_schema.load(data)
        
        # Find or create client
        client, created = get_or_create_client(validated_data['client_identifier'])
        if created:
            client.name = validated_data.get('client_identifier')  # Use identifier as name if not provided
            db.session.add(client)
        
        # Check if client already has an active block
        if client.is_blocked:
            return jsonify(error_schema.dump({
                "error": "Client already blocked",
                "details": f"Client {client_identifier} already has an active payment block"
            })), 409
        
        # Create new payment block
        payment_block = PaymentBlock(
            client_id=client.id,
            reason=validated_data['reason'],
            details=validated_data.get('details'),
            blocked_by=validated_data['blocked_by']
        )
        
        db.session.add(payment_block)
        db.session.commit()
        
        return jsonify(payment_block_schema.dump(payment_block)), 201
    
    except ValidationError as err:
        return jsonify(error_schema.dump({"error": "Validation error", "details": str(err)})), 400
    
    except SQLAlchemyError as err:
        db.session.rollback()
        logger.error(f"Database error while blocking client payments: {str(err)}")
        return jsonify(error_schema.dump({"error": "Database error", "details": str(err)})), 500
    
    except Exception as err:
        logger.error(f"Unexpected error while blocking client payments: {str(err)}")
        return jsonify(error_schema.dump({"error": "Server error", "details": str(err)})), 500

@api_bp.route('/clients/<client_identifier>/unblock', methods=['POST'])
def unblock_client_payments(client_identifier):
    """
    Unblock payments for a specific client
    ---
    tags:
      - Payment Blocks
    parameters:
      - name: client_identifier
        in: path
        required: true
        schema:
          type: string
    requestBody:
      required: true
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/UnblockPaymentSchema'
    responses:
      200:
        description: Client payments unblocked successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PaymentBlockSchema'
      400:
        description: Invalid request data
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      404:
        description: Client not found or no active block
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      500:
        description: Server error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
    """
    try:
        # Parse and validate request data
        data = request.json
        if not data:
            return jsonify(error_schema.dump({"error": "No JSON data provided"})), 400
        
        # Override client_identifier from URL
        data['client_identifier'] = client_identifier
        validated_data = unblock_payment_schema.load(data)
        
        # Find client
        client = Client.query.filter_by(client_identifier=client_identifier).first()
        if not client:
            return jsonify(error_schema.dump({
                "error": "Client not found",
                "details": f"No client found with identifier {client_identifier}"
            })), 404
        
        # Find active block
        active_block = client.active_block
        if not active_block:
            return jsonify(error_schema.dump({
                "error": "No active block",
                "details": f"Client {client_identifier} does not have an active payment block"
            })), 404
        
        # Unblock the payment
        active_block.unblock(
            unblocked_by=validated_data['unblocked_by'],
            reason=validated_data.get('reason')
        )
        
        db.session.commit()
        
        return jsonify(payment_block_schema.dump(active_block)), 200
    
    except ValidationError as err:
        return jsonify(error_schema.dump({"error": "Validation error", "details": str(err)})), 400
    
    except SQLAlchemyError as err:
        db.session.rollback()
        logger.error(f"Database error while unblocking client payments: {str(err)}")
        return jsonify(error_schema.dump({"error": "Database error", "details": str(err)})), 500
    
    except Exception as err:
        logger.error(f"Unexpected error while unblocking client payments: {str(err)}")
        return jsonify(error_schema.dump({"error": "Server error", "details": str(err)})), 500

@api_bp.route('/clients/<client_identifier>/status', methods=['GET'])
def check_client_status(client_identifier):
    """
    Check if a client's payments are blocked
    ---
    tags:
      - Payment Blocks
    parameters:
      - name: client_identifier
        in: path
        required: true
        schema:
          type: string
    responses:
      200:
        description: Client status retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ClientStatusSchema'
      404:
        description: Client not found
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      500:
        description: Server error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
    """
    try:
        # Find client
        client = Client.query.filter_by(client_identifier=client_identifier).first()
        if not client:
            return jsonify(error_schema.dump({
                "error": "Client not found",
                "details": f"No client found with identifier {client_identifier}"
            })), 404
        
        # Prepare response
        response_data = {
            "client_identifier": client.client_identifier,
            "is_blocked": client.is_blocked,
            "block_details": client.active_block if client.is_blocked else None
        }
        
        return jsonify(client_status_schema.dump(response_data)), 200
    
    except SQLAlchemyError as err:
        logger.error(f"Database error while checking client status: {str(err)}")
        return jsonify(error_schema.dump({"error": "Database error", "details": str(err)})), 500
    
    except Exception as err:
        logger.error(f"Unexpected error while checking client status: {str(err)}")
        return jsonify(error_schema.dump({"error": "Server error", "details": str(err)})), 500

@api_bp.route('/clients/<client_identifier>/history', methods=['GET'])
def get_client_block_history(client_identifier):
    """
    Get payment block history for a specific client
    ---
    tags:
      - Payment Blocks
    parameters:
      - name: client_identifier
        in: path
        required: true
        schema:
          type: string
    responses:
      200:
        description: Client block history retrieved successfully
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ClientBlockHistorySchema'
      404:
        description: Client not found
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
      500:
        description: Server error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
    """
    try:
        # Find client
        client = Client.query.filter_by(client_identifier=client_identifier).first()
        if not client:
            return jsonify(error_schema.dump({
                "error": "Client not found",
                "details": f"No client found with identifier {client_identifier}"
            })), 404
        
        # Prepare response
        response_data = {
            "client_identifier": client.client_identifier,
            "client_name": client.name,
            "block_history": client.payment_blocks
        }
        
        return jsonify(client_block_history_schema.dump(response_data)), 200
    
    except SQLAlchemyError as err:
        logger.error(f"Database error while retrieving client block history: {str(err)}")
        return jsonify(error_schema.dump({"error": "Database error", "details": str(err)})), 500
    
    except Exception as err:
        logger.error(f"Unexpected error while retrieving client block history: {str(err)}")
        return jsonify(error_schema.dump({"error": "Server error", "details": str(err)})), 500

@api_bp.route('/blocks', methods=['GET'])
def list_payment_blocks():
    """
    List all payment blocks with filtering options
    ---
    tags:
      - Payment Blocks
    parameters:
      - name: active
        in: query
        schema:
          type: boolean
        description: Filter by active status
      - name: reason
        in: query
        schema:
          type: string
          enum: [fraud_suspicion, invalid_details, other]
        description: Filter by block reason
      - name: limit
        in: query
        schema:
          type: integer
          default: 50
        description: Maximum number of results to return
      - name: offset
        in: query
        schema:
          type: integer
          default: 0
        description: Offset for pagination
    responses:
      200:
        description: Payment blocks retrieved successfully
        content:
          application/json:
            schema:
              type: object
              properties:
                blocks:
                  type: array
                  items:
                    $ref: '#/components/schemas/PaymentBlockSchema'
                total:
                  type: integer
                limit:
                  type: integer
                offset:
                  type: integer
      500:
        description: Server error
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ErrorSchema'
    """
    try:
        # Extract query parameters
        active = request.args.get('active')
        reason = request.args.get('reason')
        limit = min(int(request.args.get('limit', 50)), 100)  # Cap at 100
        offset = int(request.args.get('offset', 0))
        
        # Build query
        query = PaymentBlock.query.join(Client)
        
        # Apply filters
        if active is not None:
            is_active = active.lower() == 'true'
            query = query.filter(PaymentBlock.is_active == is_active)
        
        if reason:
            try:
                block_reason = BlockReason(reason)
                query = query.filter(PaymentBlock.reason == block_reason)
            except ValueError:
                # Invalid reason - ignore filter
                pass
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        blocks = query.order_by(PaymentBlock.blocked_at.desc()).limit(limit).offset(offset).all()
        
        # Prepare response
        response = {
            "blocks": payment_block_schema.dump(blocks, many=True),
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
        return jsonify(response), 200
    
    except SQLAlchemyError as err:
        logger.error(f"Database error while listing payment blocks: {str(err)}")
        return jsonify(error_schema.dump({"error": "Database error", "details": str(err)})), 500
    
    except Exception as err:
        logger.error(f"Unexpected error while listing payment blocks: {str(err)}")
        return jsonify(error_schema.dump({"error": "Server error", "details": str(err)})), 500
