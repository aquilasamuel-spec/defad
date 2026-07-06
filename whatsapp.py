import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Credenciais da API Oficial do WhatsApp (Meta Cloud API)
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'SEU_PHONE_NUMBER_ID')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', 'SEU_ACCESS_TOKEN')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v19.0')
API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}"

def format_phone_number(phone):
    """Garante que o telefone tem apenas números e aplica regras de nono dígito do Brasil"""
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Se por algum motivo o usuário não preencheu o 55 da máscara, adiciona
    if not clean_phone.startswith('55'):
        clean_phone = '55' + clean_phone
        
    # Extrai o DDD e aplica a regra do 9º dígito
    if len(clean_phone) >= 12:
        ddd = int(clean_phone[2:4])
        numero = clean_phone[4:]
        
        # Se DDD > 28 e o número tem 9 dígitos começando com 9, remove o 9
        # (A API oficial da Meta costuma exigir sem o 9 para alguns DDDs > 28)
        if ddd > 28 and len(numero) == 9 and numero.startswith('9'):
            clean_phone = f"55{ddd:02d}{numero[1:]}"
            
    # A API oficial não usa @c.us, apenas os números diretos
    return clean_phone

def send_message(phone, text):
    """Envia uma mensagem de texto livre (Requer janela de 24h aberta)"""
    url = f"{API_URL}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": format_phone_number(phone),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": text
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None

def send_template(phone, template_name, language_code="pt_BR", components=None):
    """Envia um template aprovado da Meta (Não requer janela de 24h aberta)"""
    url = f"{API_URL}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": format_phone_number(phone),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {
                "code": language_code
            }
        }
    }
    
    if components:
        payload["template"]["components"] = components
        
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar Template WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None

def send_image_by_url(phone, image_url, caption=""):
    """Envia uma imagem por URL (Requer janela de 24h aberta)"""
    url = f"{API_URL}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": format_phone_number(phone),
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar QR Code WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None

def send_file_by_upload(phone, file_bytes, filename, caption=""):
    """Envia um arquivo PDF por upload (Requer janela de 24h aberta)"""
    # Passo 1: Fazer upload do arquivo para a Meta e obter o media_id
    url_media = f"{API_URL}/media"
    headers_media = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    files = {
        'file': (filename, file_bytes, 'application/pdf')
    }
    data = {
        'messaging_product': 'whatsapp'
    }
    
    try:
        res_media = requests.post(url_media, headers=headers_media, data=data, files=files)
        res_media.raise_for_status()
        media_id = res_media.json().get('id')
    except Exception as e:
        print(f"Erro ao fazer upload do arquivo para a Meta: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None
        
    # Passo 2: Enviar a mensagem com o media_id
    url_msg = f"{API_URL}/messages"
    payload_msg = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": format_phone_number(phone),
        "type": "document",
        "document": {
            "id": media_id,
            "caption": caption,
            "filename": filename
        }
    }
    headers_msg = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    try:
        response = requests.post(url_msg, headers=headers_msg, json=payload_msg)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao enviar documento WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None
