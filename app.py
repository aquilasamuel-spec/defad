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

    with app.app_context():
        db.create_all()
        
        # Seeding inicial de produtos
        from models import Produto
        if not Produto.query.filter_by(identificador='jantar').first():
            db.session.add(Produto(identificador='jantar', nome='Jantar', valor=250.0, vagas_totais=100))
        if not Produto.query.filter_by(identificador='jantar_hotel').first():
            db.session.add(Produto(identificador='jantar_hotel', nome='Jantar + Hotel', valor=480.0, vagas_totais=50))
        db.session.commit()

    @app.cli.command("cobrar")
    def cobrar():
        """Busca parcelas vencendo hoje e envia cobrança via WhatsApp."""
        from models import ParcelaPagamento, Inscricao
        from datetime import date
        from whatsapp import send_message, send_image_by_url
        
        hoje = date.today()
        # Busca todas as parcelas pendentes com vencimento hoje
        parcelas = ParcelaPagamento.query.filter_by(status_parcela='Pendente', data_vencimento=hoje).all()
        
        print(f"[{hoje}] Encontradas {len(parcelas)} parcelas vencendo hoje.")
        
        for p in parcelas:
            inscricao = p.inscricao
            telefone = inscricao.telefone
            
            msg = f"Olá, *{inscricao.nome_completo}*!\n\n"
            msg += f"Este é um lembrete amigável de que a sua parcela {p.numero_parcela} (R$ {p.valor_parcela:.2f}) do Jantar de Casais DEFAD vence *hoje*.\n\n"
            msg += "Abaixo está a chave PIX Copia e Cola. O QR Code também será enviado na próxima mensagem.\n\n"
            msg += f"`{p.chave_pix_copia_cola}`\n\n"
            msg += "Se já efetuou o pagamento, por favor desconsidere esta mensagem."
            
            # Envia mensagem de texto
            send_message(telefone, msg)
            
            # Gera url do QR Code para envio de imagem
            # api.qrserver.com é uma API pública e gratuita
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={p.chave_pix_copia_cola}"
            send_image_by_url(telefone, qr_url, "QR Code para Pagamento")
            
            print(f"Cobrança enviada para {inscricao.nome_completo} ({telefone})")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
