def validate_block_request(data):
    """Validate block request data"""
    errors = {}
    
    # Check required fields
    if not data.get('reason_id'):
        errors['reason_id'] = 'Block reason is required'
    
    # Validate expires_in_days if provided
    if 'expires_in_days' in data:
        try:
            days = int(data['expires_in_days'])
            if days <= 0:
                errors['expires_in_days'] = 'Expires in days must be positive'
        except (ValueError, TypeError):
            errors['expires_in_days'] = 'Expires in days must be a valid number'
    
    # Validate notes length if provided
    if 'notes' in data and len(data['notes']) > 1000:
        errors['notes'] = 'Notes are too long (max 1000 characters)'
    
    return errors

def validate_unblock_request(data):
    """Validate unblock request data"""
    errors = {}
    
    # Validate notes length if provided
    if 'notes' in data and len(data['notes']) > 1000:
        errors['notes'] = 'Notes are too long (max 1000 characters)'
    
    return errors

def validate_client_request(data):
    """Validate client creation request data"""
    errors = {}
    
    # Check required fields
    if not data.get('client_number'):
        errors['client_number'] = 'Client number is required'
    elif len(data['client_number']) > 50:
        errors['client_number'] = 'Client number is too long (max 50 characters)'
    
    if not data.get('name'):
        errors['name'] = 'Client name is required'
    elif len(data['name']) > 200:
        errors['name'] = 'Client name is too long (max 200 characters)'
    
    # Validate email if provided
    if 'email' in data and data['email']:
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, data['email']):
            errors['email'] = 'Invalid email format'
        elif len(data['email']) > 200:
            errors['email'] = 'Email is too long (max 200 characters)'
    
    return errors
