import os
import time

os.environ['TZ'] = 'America/Sao_Paulo'
if hasattr(time, 'tzset'):
    time.tzset()

from flask import Flask
from models import db
from routes import bp

def create_app():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'defad_secreto_2026'
    # Se estiver rodando no Render (com persistent disk mapeado em /data)
    if os.environ.get('RENDER'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/database.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    app.register_blueprint(bp)
    
    app.config['SCHEDULER_API_ENABLED'] = False
    from flask_apscheduler import APScheduler
    scheduler = APScheduler()
    scheduler.init_app(app)

    with app.app_context():
        db.create_all()
        
        # Adiciona a nova coluna no banco caso ainda não exista (Garante que no Render vai atualizar automático)
        try:
            db.session.execute(db.text("ALTER TABLE inscricao ADD COLUMN data_ultima_cobranca DATE;"))
            db.session.commit()
            print("Coluna 'data_ultima_cobranca' adicionada com sucesso.")
        except Exception as e:
            # Se der erro, é porque a coluna já existe, então ignoramos.
            db.session.rollback()

        # Seeding inicial de produtos
        from models import Produto
        if not Produto.query.filter_by(identificador='jantar').first():
            db.session.add(Produto(identificador='jantar', nome='Jantar', valor=250.0, vagas_totais=100))
        if not Produto.query.filter_by(identificador='jantar_hotel').first():
            db.session.add(Produto(identificador='jantar_hotel', nome='Jantar + Hotel', valor=480.0, vagas_totais=50))
        db.session.commit()

def logica_cobranca():
    from models import ParcelaPagamento, Inscricao
    from datetime import date
    from whatsapp import send_message, send_template
    import urllib.parse
    
    hoje = date.today()
    # Busca todas as parcelas pendentes com vencimento hoje ou antes de hoje (atrasadas)
    parcelas = ParcelaPagamento.query.filter(
        ParcelaPagamento.status_parcela == 'Pendente',
        ParcelaPagamento.data_vencimento <= hoje
    ).all()
    
    print(f"[{hoje}] Encontradas {len(parcelas)} parcelas vencendo/vencidas hoje.")
    
    for p in parcelas:
        inscricao = p.inscricao
        
        # Evita cobrar a mesma pessoa duas vezes no mesmo dia
        if inscricao.data_ultima_cobranca == hoje:
            continue
            
        telefone = inscricao.telefone
        
        import requests
        from whatsapp import upload_media
        
        pix_encoded = urllib.parse.quote(p.chave_pix_copia_cola)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_encoded}"
        
        qr_response = requests.get(qr_url)
        media_id = upload_media(qr_response.content, "qrcode.png", "image/png")
        
        components = [
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "image",
                        "image": {
                            "id": media_id
                        } if media_id else {
                            "link": qr_url
                        }
                    }
                ]
            },
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "parameter_name": "nome_inscrito", "text": str(inscricao.nome_completo)},
                    {"type": "text", "parameter_name": "numero_parcela", "text": str(p.numero_parcela)},
                    {"type": "text", "parameter_name": "valor_parcela", "text": f"{p.valor_parcela:.2f}"},
                    {"type": "text", "parameter_name": "nome_evento", "text": "Jantar de Casais DEFAD"},
                    {"type": "text", "parameter_name": "data_vencimento", "text": p.data_vencimento.strftime('%d/%m/%Y')},
                    {"type": "text", "parameter_name": "link_whatsapp", "text": "wa.me/558382069331"}
                ]
            }
        ]
        send_template(telefone, "cobranca_parcela", components=components)
        
        inscricao.data_ultima_cobranca = hoje
        from models import db
        db.session.commit()
        
        print(f"Cobrança enviada para {inscricao.nome_completo} ({telefone})")

def create_app():
    import os
    from dotenv import load_dotenv
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'defad_secreto_2026'
    # Se estiver rodando no Render (com persistent disk mapeado em /data)
    if os.environ.get('RENDER'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////data/database.db'
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
        
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    app.register_blueprint(bp)
    
    app.config['SCHEDULER_API_ENABLED'] = False
    from flask_apscheduler import APScheduler
    scheduler = APScheduler()
    scheduler.init_app(app)

    with app.app_context():
        db.create_all()
        
        # Adiciona a nova coluna no banco caso ainda não exista (Garante que no Render vai atualizar automático)
        try:
            db.session.execute(db.text("ALTER TABLE inscricao ADD COLUMN data_ultima_cobranca DATE;"))
            db.session.commit()
            print("Coluna 'data_ultima_cobranca' adicionada com sucesso.")
        except Exception as e:
            # Se der erro, é porque a coluna já existe, então ignoramos.
            db.session.rollback()

        # Seeding inicial de produtos
        from models import Produto
        if not Produto.query.filter_by(identificador='jantar').first():
            db.session.add(Produto(identificador='jantar', nome='Jantar', valor=250.0, vagas_totais=100))
        if not Produto.query.filter_by(identificador='jantar_hotel').first():
            db.session.add(Produto(identificador='jantar_hotel', nome='Jantar + Hotel', valor=480.0, vagas_totais=50))
        db.session.commit()
    @app.cli.command("cobrar")
    def cobrar():
        """Busca parcelas vencendo ou atrasadas e envia cobrança via WhatsApp."""
        logica_cobranca()

    # Tarefa automática rodando 1x ao dia, por exemplo, às 08:00
    @scheduler.task('cron', id='cobrar_automaticamente', hour=8, minute=0)
    def task_cobranca():
        with app.app_context():
            logica_cobranca()
            
    # Inicia o scheduler, exceto se for rodar o CLI ou não for a thread principal (evita duplicar)
    if not app.cli and not os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler.start()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
