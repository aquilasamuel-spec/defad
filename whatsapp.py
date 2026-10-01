import requests
import json
import os
import threading
from dotenv import load_dotenv

load_dotenv()

# Credenciais da API Oficial do WhatsApp (Meta Cloud API)
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'SEU_PHONE_NUMBER_ID')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', 'SEU_ACCESS_TOKEN')
WHATSAPP_API_VERSION = os.environ.get('WHATSAPP_API_VERSION', 'v19.0')
API_URL = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}"

# Hub de atendimento: cada envio é registrado lá (POST /api/disparos) para que, quando o
# cliente responder, o bot/IA saiba o assunto ("jantar") e o atendente veja no Chatwoot o
# que foi enviado. Sem HUB_URL/HUB_API_KEY nada é registrado e os envios seguem normais.
HUB_URL = os.environ.get('HUB_URL', '').rstrip('/')
HUB_API_KEY = os.environ.get('HUB_API_KEY', '')
HUB_SISTEMA = os.environ.get('HUB_SISTEMA', 'jantar')  # id do item "Jantar de Casais" no menu do SIGA

DESCRICAO_TEMPLATES = {
    'cobranca_parcela': 'Cobrança de parcela',
    'inscricao_solicitada': 'Inscrição solicitada (comprovante em PDF)',
    'inscricao_finalizada': 'Inscrição finalizada',
    'parcelas_pagas': 'Confirmação de pagamento',
}
ROTULOS_PARAMETROS = {
    'nome_inscrito': 'Inscrito',
    'numero_parcela': 'Parcela',
    'valor_parcela': 'Valor R$',
    'data_vencimento': 'Vencimento',
    'parcelas_pagas_agora': 'Parcela(s) paga(s)',
    'lista_parcelas': 'Parcelas',
}
PARAMETROS_IGNORADOS = {'nome_evento', 'link_whatsapp'}


def resumo_template(template_name, components):
    """Texto curto do template para o atendente/IA, ex.: 'Cobrança de parcela — Inscrito: Maria | Parcela: 2'."""
    partes = []
    for comp in components or []:
        if comp.get('type') != 'body':
            continue
        for i, param in enumerate(comp.get('parameters') or []):
            if param.get('type') != 'text':
                continue
            nome = param.get('parameter_name') or f'param{i + 1}'
            if nome in PARAMETROS_IGNORADOS:
                continue
            partes.append(f"{ROTULOS_PARAMETROS.get(nome, nome)}: {param.get('text', '')}")
    titulo = DESCRICAO_TEMPLATES.get(template_name, f'Template {template_name}')
    return f"{titulo} — {' | '.join(partes)}" if partes else titulo


def _enviar_disparo_ao_hub(dados):
    try:
        requests.post(f"{HUB_URL}/api/disparos", headers={'X-API-Key': HUB_API_KEY}, json=dados, timeout=5)
    except Exception as e:
        print(f"Aviso: não foi possível registrar o disparo no Hub: {e}")


def registrar_disparo_no_hub(phone, tipo, texto, resposta_meta):
    """Avisa o Hub do envio (em segundo plano). Nunca impede nem atrasa o envio."""
    if not HUB_URL or not HUB_API_KEY or not resposta_meta:
        return
    try:
        wa_message_id = ((resposta_meta.get('messages') or [{}])[0]).get('id', '')
        dados = {
            'telefone': format_phone_number(phone),
            'sistema': HUB_SISTEMA,
            'tipo': tipo,
            'texto': texto,
            'wa_message_id': wa_message_id,
        }
        threading.Thread(target=_enviar_disparo_ao_hub, args=(dados,), daemon=True).start()
    except Exception as e:
        print(f"Aviso: não foi possível registrar o disparo no Hub: {e}")

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
        resposta = response.json()
        registrar_disparo_no_hub(phone, 'mensagem', text, resposta)
        return resposta
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
        resposta = response.json()
        registrar_disparo_no_hub(phone, template_name, resumo_template(template_name, components), resposta)
        return resposta
    except Exception as e:
        error_msg = f"Erro ao enviar Template WhatsApp para {phone}: {e}\n"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"Detalhes do erro Meta: {e.response.text}\n"
        
        print(error_msg)
        with open("meta_errors.log", "a", encoding="utf-8") as f:
            f.write(error_msg)
        
        return None

def send_image_by_url(phone, image_url, caption=""):
    """Envia uma imagem baixando-a da URL e fazendo upload, para evitar erros da Meta"""
    import requests
    
    # Baixa a imagem
    try:
        response = requests.get(image_url)
        response.raise_for_status()
        file_bytes = response.content
    except Exception as e:
        print(f"Erro ao baixar imagem de {image_url}: {e}")
        return None

    # Faz upload
    media_id = upload_media(file_bytes, "imagem.png", "image/png")
    if not media_id:
        print("Falha ao fazer upload da imagem para a Meta.")
        return None

    url_msg = f"{API_URL}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": format_phone_number(phone),
        "type": "image",
        "image": {
            "id": media_id,
            "caption": caption
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    try:
        res = requests.post(url_msg, headers=headers, json=payload)
        res.raise_for_status()
        resposta = res.json()
        registrar_disparo_no_hub(phone, 'imagem', caption or 'Imagem enviada', resposta)
        return resposta
    except Exception as e:
        print(f"Erro ao enviar QR Code/Imagem WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None

def upload_media(file_bytes, filename, mime_type='application/pdf'):
    """Faz upload de uma mídia para a Meta e retorna o media_id"""
    url_media = f"{API_URL}/media"
    headers_media = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}'
    }
    
    files = {
        'file': (filename, file_bytes, mime_type)
    }
    data = {
        'messaging_product': 'whatsapp'
    }
    
    try:
        res_media = requests.post(url_media, headers=headers_media, data=data, files=files)
        res_media.raise_for_status()
        return res_media.json().get('id')
    except Exception as e:
        print(f"Erro ao fazer upload da mídia para a Meta: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None

def send_file_by_upload(phone, file_bytes, filename, caption=""):
    """Envia um arquivo PDF por upload (Requer janela de 24h aberta)"""
    # Passo 1: Fazer upload do arquivo para a Meta e obter o media_id
    media_id = upload_media(file_bytes, filename, 'application/pdf')
    
    if not media_id:
        print("Não foi possível obter o media_id. Abortando envio de arquivo.")
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
        resposta = response.json()
        registrar_disparo_no_hub(phone, 'documento', f"{caption or 'Documento'} ({filename})", resposta)
        return resposta
    except Exception as e:
        print(f"Erro ao enviar documento WhatsApp para {phone}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Detalhes do erro Meta:", e.response.text)
        return None
