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
        from whatsapp import send_message, send_image_by_url
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
            telefone = inscricao.telefone
            
            msg = f"Olá, *{inscricao.nome_completo}*!\n\n"
            if p.data_vencimento == hoje:
                msg += f"Este é um lembrete amigável de que a sua parcela {p.numero_parcela} (R$ {p.valor_parcela:.2f}) do Jantar de Casais DEFAD vence *hoje*.\n\n"
            else:
                msg += f"Consta em nosso sistema que a sua parcela {p.numero_parcela} (R$ {p.valor_parcela:.2f}) do Jantar de Casais DEFAD está *pendente* e venceu em {p.data_vencimento.strftime('%d/%m/%Y')}.\n\n"
                
            msg += "Abaixo está a chave PIX Copia e Cola. O QR Code também será enviado na próxima mensagem.\n\n"
            msg += f"`{p.chave_pix_copia_cola}`\n\n"
            msg += "Após realizar o pagamento, *envie e guarde o comprovante* enviando para o WhatsApp oficial:\n"
            msg += "📲 wa.me/558382069331\n\n"
            msg += "Se já efetuou o pagamento, por favor desconsidere esta mensagem."
            
            send_message(telefone, msg)
            
            pix_encoded = urllib.parse.quote(p.chave_pix_copia_cola)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={pix_encoded}"
            send_image_by_url(telefone, qr_url, "QR Code para Pagamento")
            
            print(f"Cobrança enviada para {inscricao.nome_completo} ({telefone})")

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
