from app import db
from models import Client

def get_or_create_client(client_identifier, name=None):
    """
    Получение существующего клиента или создание нового, если он не существует
    
    Аргументы:
        client_identifier (str): Уникальный идентификатор клиента (ИНН, ОГРН и т.д.)
        name (str, optional): Наименование клиента. Если не указано, для новых клиентов
                              будет использоваться идентификатор в качестве наименования
                             
    Возвращает:
        tuple: (client, created)
            client (Client): Полученный или созданный клиент
            created (bool): True, если был создан новый клиент, False в противном случае
    """
    client = Client.query.filter_by(client_identifier=client_identifier).first()
    
    if client:
        return client, False
    
    # Создание нового клиента
    client_name = name or client_identifier
    client = Client(client_identifier=client_identifier, name=client_name)
    
    return client, True
