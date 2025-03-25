from marshmallow import Schema, fields, validate, validates, ValidationError
from models import BlockReason

class ClientSchema(Schema):
    """Схема для сериализации и валидации модели Client"""
    id = fields.Integer(dump_only=True)
    client_identifier = fields.String(required=True, validate=validate.Length(min=1, max=50))
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    is_blocked = fields.Boolean(dump_only=True)

class BlockReasonField(fields.Field):
    """Пользовательское поле для перечисления BlockReason"""
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return value.value
    
    def _deserialize(self, value, attr, data, **kwargs):
        try:
            return BlockReason(value)
        except ValueError:
            raise ValidationError(f"Недопустимая причина блокировки. Должна быть одной из: {', '.join([r.value for r in BlockReason])}")

class PaymentBlockSchema(Schema):
    """Схема для сериализации и валидации модели PaymentBlock"""
    id = fields.Integer(dump_only=True)
    client_id = fields.Integer(required=True)
    reason = BlockReasonField(required=True)
    details = fields.String(required=False, allow_none=True)
    is_active = fields.Boolean(dump_only=True)
    blocked_at = fields.DateTime(dump_only=True)
    unblocked_at = fields.DateTime(dump_only=True)
    blocked_by = fields.String(required=True, validate=validate.Length(min=1, max=100))
    unblocked_by = fields.String(dump_only=True)
    unblock_reason = fields.String(dump_only=True)

class BlockPaymentSchema(Schema):
    """Схема для блокировки платежей клиента"""
    client_identifier = fields.String(required=True, validate=validate.Length(min=1, max=50))
    reason = BlockReasonField(required=True)
    details = fields.String(required=False, allow_none=True)
    blocked_by = fields.String(required=True, validate=validate.Length(min=1, max=100))

class UnblockPaymentSchema(Schema):
    """Схема для разблокировки платежей клиента"""
    client_identifier = fields.String(required=True, validate=validate.Length(min=1, max=50))
    unblocked_by = fields.String(required=True, validate=validate.Length(min=1, max=100))
    reason = fields.String(required=False, allow_none=True)

class ClientStatusSchema(Schema):
    """Схема для ответа о статусе блокировки клиента"""
    client_identifier = fields.String()
    is_blocked = fields.Boolean()
    block_details = fields.Nested(PaymentBlockSchema, allow_none=True)

class ClientBlockHistorySchema(Schema):
    """Схема для ответа с историей блокировок клиента"""
    client_identifier = fields.String()
    client_name = fields.String()
    block_history = fields.List(fields.Nested(PaymentBlockSchema))

class ErrorSchema(Schema):
    """Схема для ответов с ошибками API"""
    error = fields.String(required=True)
    details = fields.String(required=False, allow_none=True)
