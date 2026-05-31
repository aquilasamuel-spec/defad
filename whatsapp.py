import requests
import json
import os

# Credenciais do Green API
# Usa variáveis de ambiente se existirem, caso contrário usa as chaves diretamente (para testes locais)
ID_INSTANCE = os.environ.get('GREEN_API_ID_INSTANCE', '7107553786')
API_TOKEN_INSTANCE = os.environ.get('GREEN_API_TOKEN_INSTANCE', '9cdf62444434459aad4a76e1c1a07a4a850de6e22a474bf996')
API_URL = "https://7107.api.greenapi.com"

def format_phone_number(phone):
    """Garante que o telefone tem apenas números e adiciona @c.us"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    # Se por algum motivo o usuário não preencheu o 55 da máscara, adiciona
    if not clean_phone.startswith('55'):
        clean_phone = '55' + clean_phone
    return f"{clean_phone}@c.us"

def send_message(phone, text):
    url = f"{API_URL}/waInstance{ID_INSTANCE}/sendMessage/{API_TOKEN_INSTANCE}"
    
    payload = {
        "chatId": format_phone_number(phone),
        "message": text
    }
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar WhatsApp para {phone}: {e}")
        return None

def send_image_by_url(phone, image_url, caption=""):
    url = f"{API_URL}/waInstance{ID_INSTANCE}/sendFileByUrl/{API_TOKEN_INSTANCE}"
    
    payload = {
        "chatId": format_phone_number(phone),
        "urlFile": image_url,
        "fileName": "qrcode_pix.png",
        "caption": caption
    }
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar QR Code WhatsApp para {phone}: {e}")
        return None
