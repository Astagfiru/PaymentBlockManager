import enum
from datetime import datetime
from app import db

class BlockReason(enum.Enum):
    """Перечисление причин блокировки для различения между мошенничеством и техническими проблемами"""
    FRAUD_SUSPICION = "fraud_suspicion"  # Подозрение на мошенничество
    INVALID_DETAILS = "invalid_details"  # Недействительные реквизиты
    OTHER = "other"  # Другие причины

class Client(db.Model):
    """
    Модель, представляющая клиента в системе Т-Банка.
    В соответствии с законодательством РФ о персональных данных (ФЗ-152)
    и требованиями Банка России по информационной безопасности.
    """
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    client_identifier = db.Column(db.String(50), unique=True, nullable=False, index=True)  # ИНН, ОГРН или другой идентификатор
    name = db.Column(db.String(100), nullable=False)  # Наименование организации
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связь с моделью блокировки платежей
    payment_blocks = db.relationship('PaymentBlock', back_populates='client', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Клиент {self.client_identifier}>'

    @property
    def is_blocked(self):
        """Проверка наличия активной блокировки платежей у клиента"""
        active_blocks = [block for block in self.payment_blocks if block.is_active]
        return len(active_blocks) > 0
    
    @property
    def active_block(self):
        """Возвращает активную блокировку, если таковая имеется"""
        active_blocks = [block for block in self.payment_blocks if block.is_active]
        return active_blocks[0] if active_blocks else None

class PaymentBlock(db.Model):
    """
    Модель, представляющая блокировку платежей для клиента.
    Модель соответствует требованиям Положения ЦБ РФ №382-П и рекомендациям 
    по обеспечению информационной безопасности в финансовых организациях.
    """
    __tablename__ = 'payment_blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False, index=True)
    reason = db.Column(db.Enum(BlockReason), nullable=False)
    details = db.Column(db.Text, nullable=True)
    
    # Статус блокировки
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Метки времени
    blocked_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    unblocked_at = db.Column(db.DateTime, nullable=True)
    
    # Метаданные блокировки
    blocked_by = db.Column(db.String(100), nullable=False)  # Сотрудник, создавший блокировку
    unblocked_by = db.Column(db.String(100), nullable=True)  # Сотрудник, снявший блокировку
    unblock_reason = db.Column(db.Text, nullable=True)  # Причина разблокировки
    
    # Связь с моделью клиента
    client = db.relationship('Client', back_populates='payment_blocks')
    
    def __repr__(self):
        return f'<Блокировка платежа {self.id} для клиента {self.client_id}>'
    
    def unblock(self, unblocked_by, reason=None):
        """Разблокировка платежа путем установки is_active в False и записи метаданных"""
        self.is_active = False
        self.unblocked_at = datetime.utcnow()
        self.unblocked_by = unblocked_by
        self.unblock_reason = reason
